# Homelab Infrastructure

Personal, production-grade Kubernetes homelab running at `pablomarelli.dev`. The entire cluster state is declared in this repository and managed via GitOps — ArgoCD watches this repo and reconciles the cluster automatically.

## Architecture at a glance

```
Internet
   │
   ▼
Cloudflare (DNS + DDoS protection)
   │  CNAME *.pablomarelli.dev → tunnel
   ▼
cloudflared (in-cluster tunnel daemon)
   │
   ▼
Traefik (ingress controller, k3s default)
   │
   ├─ auth middleware (Authentik forward auth) ──► protected routes
   └─ direct ──────────────────────────────────► public routes
         │
         ├─► ArgoCD          argocd.pablomarelli.dev
         ├─► Grafana          grafana.pablomarelli.dev
         ├─► Authentik        auth.pablomarelli.dev
         ├─► Uptime Kuma      status.pablomarelli.dev
         ├─► Umami            analytics.pablomarelli.dev
         ├─► Portfolio        portfolio.pablomarelli.dev
         ├─► Finance Manager  finance.pablomarelli.dev
         └─► Home Assistant   home.pablomarelli.dev
```

No ports are exposed on the host. All external traffic flows through a [Cloudflare Tunnel](docs/06-infrastructure.md) — no firewall rules, no port forwarding.

## Stack

| Layer | Tool |
|---|---|
| Orchestration | Kubernetes (k3s, single-node) |
| GitOps | ArgoCD (App-of-Apps) |
| Ingress | Traefik |
| Tunneling | Cloudflare Tunnel (`cloudflared`) |
| DNS / IaC | OpenTofu + Cloudflare provider |
| Secrets | External Secrets Operator + 1Password, Sealed Secrets |
| Identity / SSO | Authentik |
| Metrics | Prometheus (kube-prometheus-stack) |
| Logs | Loki + Grafana Alloy |
| Dashboards | Grafana |
| Alerting | Alertmanager → Discord |
| Uptime | Uptime Kuma |
| Analytics | Umami |
| Database | PostgreSQL 16 |

## Documentation

| Doc | Description |
|---|---|
| [01 — Architecture](docs/01-architecture.md) | How all the pieces connect — GitOps, networking, auth |
| [02 — Prerequisites & Setup](docs/02-prerequisites.md) | Tools needed and bootstrap sequence |
| [03 — Services](docs/03-services.md) | Full catalog of services, namespaces, and URLs |
| [04 — Adding a Service](docs/04-adding-a-service.md) | Step-by-step guide to onboarding a new app |
| [05 — Secret Management](docs/05-secret-management.md) | ESO + 1Password and Sealed Secrets workflows |
| [06 — Infrastructure / DNS](docs/06-infrastructure.md) | Cloudflare Tunnel and OpenTofu DNS |
| [07 — Monitoring & Alerting](docs/07-monitoring.md) | PLG stack, Alloy, Alertmanager, Discord |
| [08 — Backups](docs/08-backups.md) | PostgreSQL and Uptime Kuma backup strategy |

## Repository layout

```
homelab-infra/
├── apps/              # ArgoCD Application manifests (one per service)
├── bootstrap/         # One-time cluster bootstrap (ArgoCD install + namespaces)
├── infrastructure/    # External cloud resources (Cloudflare tunnel + OpenTofu DNS)
├── manifests/         # Kubernetes manifests and Helm values per service
└── scripts/           # Utility shell scripts
```
