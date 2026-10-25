# Easy Media Share deployment

Easy Media Share runs as one stateful replica on `homelab-desktop-01`. SQLite and uploaded files share the retained `easy-media-share-data` volume.

## Prerequisites

Do not enable the Argo CD Application until all of these are complete:

1. Publish `ghcr.io/pablomarelli/easy-media-share:2026.08.26`. The manifest assumes the GHCR package is public; configure an ESO-managed `imagePullSecret` first if it remains private.
2. Create `/srv/easy-media-share/data` on `homelab-desktop-01` with ownership UID/GID `10001` and mode `0750`. It is a directory on the existing root filesystem; no formatting, partitioning, or additional mount is required.
3. Create an Authentik proxy provider and application for `https://share.pablomarelli.dev`, then attach it to the existing Traefik outpost.
4. Apply the Cloudflare DNS change with `./scripts/tofu plan` and `./scripts/tofu apply`.

The PV and PVC use a static local volume with `Retain` reclaim policy and Argo CD prune/delete protection. Their declared 250 GiB capacity is scheduling metadata, not a reservation or enforced limit. Uploads share the worker's root disk with the OS and other workloads.

## Storage monitoring

`storage-metrics.yaml` runs a separate unprivileged exporter on the same worker, mounting the data volume read-only. Every five minutes it measures allocated directory bytes with `du -sk` and filesystem capacity/free space with `df -Pk`. Prometheus scrapes its internal endpoint every minute; it is not exposed through the public ingress.

- Directory usage at or above **250 GiB for 15 minutes** triggers a warning; uploads are not blocked.
- Root filesystem available space below **15% for 10 minutes** triggers a warning, and below **5% for 5 minutes** triggers a critical alert.
- Missing scans, or scans older than 30 minutes, trigger a warning after 15 minutes.

Do not use kubelet volume percentage metrics as directory-usage measurements: this local volume shares the root filesystem. The exporter measures allocated disk usage rather than logical file size, so sparse files and filesystem overhead can differ from application-reported upload sizes.

Alert tests are in `tests/prometheus/easy-media-share-storage.test.yaml`. Export the storage PrometheusRule's `.spec` as `storage-rules.json` next to a copy of that test file, then run `promtool test rules easy-media-share-storage.test.yaml` in that directory. These tests cover usage below the threshold, the exact 250 GiB threshold and 15-minute delay, and missing metrics.

## Routing

The following paths intentionally bypass Authentik:

- `/s/*`
- `/api/public/*`
- `/assets/*`
- `/sw.js`
- `/api/health`

All other paths use Authentik forward auth. Traefik removes client-supplied `X-Authentik-*` headers before injecting verified identity headers.

The middleware resources live in `media-share`, alongside the IngressRoute, because Traefik rejects cross-namespace middleware references. The local forward-auth middleware calls the shared Authentik outpost in `monitoring` by its service DNS name; this does not require enabling Traefik's `allowCrossNamespace` option. Keep its forward-auth settings aligned with `manifests/traefik/forward-auth-middleware.yaml`.

### Access troubleshooting

If `share.pablomarelli.dev` returns NXDOMAIN, verify public DNS with `dig @1.1.1.1 share.pablomarelli.dev`. The `share` record is already declared in `infrastructure/tofu/variables.tf`; it must also be applied to Cloudflare. Sign in to 1Password, then run `./scripts/tofu plan` and review the changes before running `./scripts/tofu apply`. Changing the machine's resolver cannot fix a missing public DNS record.

To check routing independently of public DNS, send the hostname directly to the LAN Traefik address:

```bash
curl -i --resolve share.pablomarelli.dev:80:192.168.100.3 http://share.pablomarelli.dev/api/health
curl -I --resolve share.pablomarelli.dev:80:192.168.100.3 http://share.pablomarelli.dev/
```

The health endpoint should return 200, and the owner page should redirect to Authentik rather than return Traefik's plain-text 404. If only owner pages fail, check `kubectl logs -n kube-system deployment/traefik --since=5m` for middleware errors. Deploy manifest changes through Argo CD; its automated self-heal can revert manual edits to the live IngressRoute.

## Validation

After deployment:

```bash
kubectl get application easy-media-share -n argocd
kubectl get pv easy-media-share-data
kubectl get pvc,pod,service,ingressroute -n media-share
kubectl logs -n media-share deployment/easy-media-share
curl -fsS https://share.pablomarelli.dev/api/health
```

Verify the following through the public hostname:

- `/` redirects an unauthenticated browser to Authentik.
- A spoofed `X-Authentik-Uid` request cannot access `/api/me`.
- A valid `/s/<token>` and its `/api/public/` downloads work without login.
- Interrupted tus uploads resume successfully.
- Range and streamed ZIP downloads work.
- The application observes distinct client IPs for download concurrency limits.

Add `https://share.pablomarelli.dev/api/health` to Uptime Kuma after the route is live.

## Backups

The initial deployment does not yet claim that same-disk snapshots are durable backups. Before storing anything that cannot be recreated, add the retained backup PV, nightly snapshot CronJob, seven-copy retention, failure/staleness alerts, and a tested stopped-application restore procedure described in `docs/08-backups.md`.
