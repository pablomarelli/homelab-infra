# Cluster upgrade audit - 2026-10-27

## Summary

Live Kubernetes inventory and repository pins were compared with upstream release APIs and Helm repository indexes on 2026-10-27. Versions below are upgrade candidates, not a verified compatibility matrix. Release-note security fixes do not by themselves prove that this deployment is exploitable.

Both nodes are Ready and run `v1.34.3+k3s1`. All inspected non-completed pods are Running with their containers ready. Of 24 Argo CD Applications, 22 are Synced; Finance Manager and Home Assistant have Unknown sync status with repository-access errors. All report Healthy, which does not establish successful reconciliation for those two applications.

## Upgrade inventory

| Component | Observed version | Upstream candidate | Priority and approach |
| --- | --- | --- | --- |
| cloudflared | Live `2026.5.0`; repository `2026.10.5` | `2026.10.5` | Finish delivery of the existing repository update and verify tunnel connectivity. |
| K3s, both nodes | `1.34.3+k3s1` | Same-line `1.34.12+k3s1`; stable channel `1.36.5+k3s1`; latest channel `1.37.1+k3s1` | High priority platform maintenance. Upgrade one minor at a time, server before agent at each step. Prefer stable channel as the destination. |
| Traefik | `3.5.1` | `3.7.16` | High priority: upstream identifies 3.0 through 3.6 as end-of-life. Coordinate with K3s's packaged chart. |
| Argo CD | `3.4.2` | `3.5.6` | Upgrade the complete upstream bootstrap manifest using the existing runbook, including its tested Redis and Dex versions. |
| Sealed Secrets | `0.27.3` | `0.41.2` | Large version gap in a critical controller. Review intervening release notes and back up sealing keys before migration. |
| External Secrets chart/controller | `2.5.0` | Chart `2.14.0` | Review CRDs, provider changes and Kubernetes compatibility; verify 1Password-backed secret reconciliation. |
| Authentik chart/server/worker/outpost | `2026.5.0` | `2026.8.5` | Upgrade chart and separately pinned proxy together; verify database migration, login, OAuth and ForwardAuth. |
| kube-prometheus-stack chart | `85.3.3` | `92.14.0` | Multiple chart-major transitions; review upgrade notes and CRDs, render with current values before choosing the rollout sequence. |
| Grafana, supplied by monitoring chart | `13.0.1-security-01` | Standalone release `13.3.0` | New release lists security fixes. Confirm the chosen stack chart actually includes a patched version. |
| Prometheus, supplied by monitoring chart | `3.11.3-distroless` | Standalone release `3.15.1` | Release contains security fixes; coordinate with stack chart. |
| Prometheus Operator | `0.90.1` | `0.94.2` | Release contains security rebuilds; coordinate operator, CRDs and config-reloader through the chart. |
| Alertmanager | `0.32.1` | `0.34.1` | Coordinate with stack chart; verify Discord delivery and inhibition behavior. |
| Loki chart / application | `7.0.0` / `3.6.7` | Same-repository chart `7.5.0` / `3.6.16`; standalone application `3.7.9` | The chart index and latest application differ. Prefer a tested chart/application pair; review SingleBinary, filesystem storage and WAL behavior. |
| Alloy chart / application | `1.8.2` / `1.16.1` | `1.14.3` / `1.21.2` | Validate existing configuration and log delivery through Loki after rollout. |
| PostgreSQL | `16.14-alpine` | `16.15` | Prefer this maintenance update. PostgreSQL 16 is supported until November 2028; latest stable major 18.6 is a separate migration project. Update backup image too. |
| Forgejo | `15.0.6` | `17.0.1` | Major-version migration review and backup/restore preparation; update deployment and backup job together. |
| Umami | `3.1.0` | `3.4.1` | High priority: upstream calls this a security hotfix and recommends all self-hosted users upgrade. Review intervening releases and database migrations. |
| Uptime Kuma | `2.3.2` | `2.5.8` | Security release includes an admin-only RCE fix; TCP monitor TLS behavior also changes. |
| ntfy | `2.14.0` | `2.34.0` | Release fixes subscriptions surviving user deletion or permission revocation; review intervening configuration changes. |
| Dozzle | `10.6.0` | `11.3.5` | Major-version review, particularly Kubernetes permissions and authentication. |

### Packaged and supporting components

K3s currently supplies containerd `2.1.5-k3s1`, CoreDNS `1.13.1`, metrics-server `0.8.0`, local-path-provisioner `0.0.32`, and klipper-lb `0.4.13`. Upgrade these through the selected K3s release unless deliberately maintaining a supported override.

Do not assume a K3s upgrade brings Traefik to the newest security release: the inspected K3s `1.37.1+k3s1` release bundles Traefik `3.7.13`, older than `3.7.16`. Check the actual target chart and supported HelmChartConfig options before implementation.

Argo CD currently supplies Dex `2.45.0` and Redis `8.2.3-alpine`. Monitoring also supplies sidecars, exporters and Memcached. These should be audited as part of the owning release's rendered manifests, rather than independently replacing images in generated resources.

## Security evidence and qualifications

- [Traefik advisory GHSA-hrpp-p4fc-wwf8](https://github.com/traefik/traefik/security/advisories/GHSA-hrpp-p4fc-wwf8) documents affected versions and the end-of-life branches. Its specific exploit requires NTLM/Negotiate connection-bound authentication. The configured Authentik integration alone does not establish that prerequisite.
- [Umami 3.4.1](https://github.com/umami-software/umami/releases/tag/v3.4.1) is explicitly a security hotfix, including framework and container-base updates. Its statement of no migrations applies to that patch, not the complete jump from 3.1.0.
- [Uptime Kuma 2.5.8](https://github.com/louislam/uptime-kuma/releases/tag/2.5.8) includes a security fix and changes existing TLS-enabled TCP monitors into ordinary TCP monitors.
- [ntfy 2.34.0](https://github.com/binwiederhier/ntfy/releases/tag/v2.34.0) fixes authorization revocation behavior.
- [Grafana 13.3.0](https://github.com/grafana/grafana/releases/tag/v13.3.0), [Prometheus 3.15.1](https://github.com/prometheus/prometheus/releases/tag/v3.15.1), and [Operator 0.94.2](https://github.com/prometheus-operator/prometheus-operator/releases/tag/v0.94.2) list security fixes or security rebuilds. Exact applicability to installed images requires advisory or vulnerability-scan follow-up.

## Operational findings

1. Finance Manager and Home Assistant cannot load desired state: `authentication required: Repository not found`. Resolve repository URLs/access before relying on their GitOps status or attempting their upgrades. Neither appears in the live Deployment/StatefulSet/DaemonSet inventory.
2. The cloudflared version bump exists in local commit `be89277`, while the live inventory still shows `2026.5.0` at audit time. Confirm remote delivery, Argo reconciliation and rollout.
3. PostgreSQL, Forgejo and Uptime Kuma backup CronJobs last succeeded on 2026-10-27. Job success is not proof of a restorable backup; restore checks and cluster-datastore/sealing-key backups remain unverified.
4. One node-exporter pod has 178 recorded restarts, another 19. Both are currently ready; inspect termination history and restart timing before treating monitoring as a reliable upgrade baseline.
5. Sealed Secrets setup documentation installs from a mutable `latest` URL; no pinned controller manifest was found in this repository. Establish a reproducible version and ownership mechanism.

## Recommended rollout order

1. Resolve GitOps repository-access errors and establish backup/restore readiness; complete the existing cloudflared delivery.
2. Upgrade externally reachable applications with security fixes individually: Umami, Uptime Kuma and ntfy; apply PostgreSQL 16.15 as a separate maintenance rollout.
3. Plan K3s and Traefik together: patch the current line, then move through `1.35.9+k3s1` to stable `1.36.5+k3s1`, preserving node configuration and verifying each step. Ensure the final ingress version includes required fixes.
4. Upgrade Argo CD, secret controllers and Authentik in separate changes with focused reconciliation/login checks.
5. Upgrade the monitoring stack, Loki and Alloy with chart-rendering and ingestion/alert checks; schedule Forgejo and Dozzle major upgrades separately.

The cluster has one control-plane node and local storage, so plan for API interruptions and application-specific downtime during node or persistent-workload changes.

## Sources and audit limits

- [K3s channels](https://update.k3s.io/v1-release/channels), [releases](https://github.com/k3s-io/k3s/releases), and [upgrade rules](https://docs.k3s.io/upgrades/manual).
- [Grafana Helm index](https://grafana.github.io/helm-charts/index.yaml), [Prometheus Helm index](https://prometheus-community.github.io/helm-charts/index.yaml), [Authentik Helm index](https://charts.goauthentik.io/index.yaml).
- [Argo CD releases](https://github.com/argoproj/argo-cd/releases), [local upgrade runbook](11-argocd-upgrade.md), [External Secrets releases](https://github.com/external-secrets/external-secrets/releases), [Sealed Secrets releases](https://github.com/bitnami/sealed-secrets/releases).
- [Authentik releases](https://github.com/goauthentik/authentik/releases), [Loki releases](https://github.com/grafana/loki/releases), [Alloy releases](https://github.com/grafana/alloy/releases), [Dozzle releases](https://github.com/amir20/dozzle/releases), [Forgejo release](https://codeberg.org/forgejo/forgejo/releases/tag/v17.0.1).
- [PostgreSQL support/version table](https://www.postgresql.org/support/versioning/).

This is a version and upgrade-planning audit, not an image vulnerability scan or full migration rehearsal. Candidate image availability, complete intermediate changelogs, chart rendering and compatibility must be checked before rollout. Helm is unavailable locally; chart metadata was read directly from official indexes. Context7 documentation retrieval was quota-blocked; official documentation was used instead.

Host OS package updates were not queried: the nodes report Debian 13 and Ubuntu 24.04.5, but those labels cannot establish patch completeness. Custom portfolio/media-share image freshness requires their build repositories. Finance Manager and Home Assistant versions could not be established from this cluster inventory. Supporting Alpine/BusyBox image digests and all transitive chart images were not independently audited.
