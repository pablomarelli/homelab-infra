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
         ├─► Umami dashboard  analytics.pablomarelli.dev
         ├─► Umami collector  analytics-collector.pablomarelli.dev
         ├─► Dotfiles         dotfiles.pablomarelli.dev → raw GitHub install.sh
         ├─► Portfolio        portfolio.pablomarelli.dev
         ├─► Finance Manager  finance.pablomarelli.dev
         ├─► Forgejo           git.pablomarelli.dev
         └─► Home Assistant    home.pablomarelli.dev
```

No ports are exposed on the host. Application traffic flows through a [Cloudflare Tunnel](docs/06-infrastructure.md) — no firewall rules, no port forwarding. `dotfiles.pablomarelli.dev` is an originless Cloudflare edge redirect, so the public bootstrap command stays short while the installer remains sourced from GitHub and does not depend on the cluster.

## Dotfiles redirect rollout

1. Merge and publish `install.sh` in `https://github.com/pablomarelli/dotfiles` first.
2. Confirm the raw URL exists: `https://raw.githubusercontent.com/pablomarelli/dotfiles/main/install.sh`.
3. Merge/apply this infrastructure change so the Cloudflare DNS record and redirect rule are reconciled.
4. Validate `curl -fsSL https://dotfiles.pablomarelli.dev | sh` from a disposable environment.

The public endpoint may 404 until the dotfiles repository change is published. This repository does not currently have an established declarative Uptime Kuma monitor convention for individual public URLs; add a `dotfiles.pablomarelli.dev` content/availability monitor as a follow-up through the existing Uptime Kuma UI/export workflow.

Rollback/fix-forward:

- If the raw installer URL is missing or broken, do not apply this infra change yet; publish a dotfiles fix first.
- If the Cloudflare rollout fails, revert the dedicated DNS record and redirect ruleset in `infrastructure/tofu/dns.tf`, then apply OpenTofu again.
- If `main` points to a bad installer after rollout, either revert/fix the dotfiles commit or temporarily change the redirect replacement to a known-good raw commit URL, validate it, and then reconcile.
- If the redirect causes unexpected behavior, revert this infrastructure change; it is isolated to the `dotfiles` DNS record and Cloudflare ruleset.

## Stack

| Layer | Tool |
|---|---|
| Orchestration | Kubernetes (k3s, single-node) |
| GitOps | ArgoCD (App-of-Apps) |
| Git hosting | Forgejo |
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
| [08 — Backups](docs/08-backups.md) | PostgreSQL, Uptime Kuma, and Forgejo backup strategy |
| [10 — Node Topology](docs/10-node-topology.md) | Multi-node roles, labels, taints, and placement policy |
| [11 — Argo CD Upgrade](docs/11-argocd-upgrade.md) | Safe upgrade process for the generated Argo CD bootstrap manifest |

## Repository layout

```
homelab-infra/
├── apps/              # ArgoCD Application manifests (one per service)
├── bootstrap/         # One-time cluster bootstrap (ArgoCD install + namespaces)
├── infrastructure/    # External cloud resources (Cloudflare tunnel + OpenTofu DNS)
├── manifests/         # Kubernetes manifests and Helm values per service
└── scripts/           # Utility shell scripts
```
