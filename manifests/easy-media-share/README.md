# Easy Media Share deployment

Easy Media Share runs as one stateful replica on `homelab-desktop-01`. SQLite and uploaded files share the retained `easy-media-share-data` volume.

## Prerequisites

Do not enable the Argo CD Application until all of these are complete:

1. Publish `ghcr.io/pablomarelli/easy-media-share:2026.08.26`. The manifest assumes the GHCR package is public; configure an ESO-managed `imagePullSecret` first if it remains private.
2. Provision a dedicated 250 GiB filesystem on `homelab-desktop-01`, mount it persistently at `/srv/easy-media-share/data`, and set its ownership to UID/GID `10001`.
3. Create an Authentik proxy provider and application for `https://share.pablomarelli.dev`, then attach it to the existing Traefik outpost.
4. Apply the Cloudflare DNS change with `./scripts/tofu plan` and `./scripts/tofu apply`.

The PV and PVC use a static local volume with `Retain` reclaim policy and Argo CD prune/delete protection. The path must be a dedicated mounted filesystem rather than an ordinary directory if the 250 GiB boundary and storage alerts are to represent real capacity.

## Routing

The following paths intentionally bypass Authentik:

- `/s/*`
- `/api/public/*`
- `/assets/*`
- `/sw.js`
- `/api/health`

All other paths use Authentik forward auth. Traefik removes client-supplied `X-Authentik-*` headers before injecting verified identity headers.

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
