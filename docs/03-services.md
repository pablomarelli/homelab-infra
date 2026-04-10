# Services Catalog

Full list of services running in the cluster, their namespaces, public URLs, and auth status.

## Infrastructure layer

| Service | Namespace | URL | Auth | Notes |
|---|---|---|---|---|
| ArgoCD | `argocd` | `argocd.pablomarelli.dev` | ArgoCD native | GitOps controller |
| Traefik | `kube-system` | — | — | k3s default ingress; no public UI |
| cloudflared | `infrastructure` | — | — | Cloudflare Tunnel daemon; no public UI |
| External Secrets Operator | `external-secrets` | — | — | Syncs secrets from 1Password |
| Sealed Secrets controller | `kube-system` | — | — | Decrypts Sealed Secrets |

## Auth layer

| Service | Namespace | URL | Auth | Notes |
|---|---|---|---|---|
| Authentik server | `monitoring` | `auth.pablomarelli.dev` | Self | IdP for SSO and forward auth |
| Authentik outpost | `monitoring` | — | — | Embedded proxy for Traefik forward auth |

## Monitoring & observability

| Service | Namespace | URL | Auth | Notes |
|---|---|---|---|---|
| Grafana | `monitoring` | `grafana.pablomarelli.dev` | Authentik OAuth2 | Dashboards, logs, metrics |
| Prometheus | `monitoring` | — | — | Metrics scraping; no public UI |
| Alertmanager | `monitoring` | — | — | Routes alerts to Discord |
| Loki | `monitoring` | — | — | Log storage; no public UI |
| Grafana Alloy | `monitoring` | — | — | DaemonSet log collector |
| Uptime Kuma | `monitoring` | `status.pablomarelli.dev` | Mixed (see below) | Public status page + protected admin |
| Umami | `monitoring` | `analytics.pablomarelli.dev` | Umami native | Web analytics |

### Uptime Kuma auth split

The status page uses route-level auth splitting via Traefik IngressRoutes:

| Path | Public / Protected |
|---|---|
| `/` | Redirects to public status page |
| `/status/*` (except `/status/internal`) | Public |
| `/dashboard`, `/settings`, `/manage-status-page`, `/add-status-page`, `/setup`, `/maintenance`, `/status/internal` | Protected — Authentik forward auth |

## Applications

| Service | Namespace | URL | Auth | Source |
|---|---|---|---|---|
| dev-portfolio | `portfolio` | `portfolio.pablomarelli.dev` | None (public) | `manifests/dev-portfolio/` |
| finance-manager | `finance` | `finance.pablomarelli.dev` | App-level | `github.com/PabloMarelli/finance-manager` |
| Home Assistant | `home-assistant` | `home.pablomarelli.dev` | App-level | `github.com/PabloMarelli/home-assistant` |

## Database

| Service | Namespace | URL | Notes |
|---|---|---|---|
| PostgreSQL 16 | `monitoring` | Internal only | Shared instance hosting `authentik` and `umami` databases |

### PostgreSQL databases

| Database | User | Consumer |
|---|---|---|
| `authentik` | `authentik` | Authentik server |
| `umami` | `umami` | Umami analytics |

The init script (`manifests/postgresql/configmap.yaml`) creates both databases, users, and grants on first boot.
