# Architecture

## Overview

The cluster follows three core design principles:

1. **GitOps** — all state is declared in this repository; ArgoCD is the only thing that applies changes to the cluster.
2. **Zero-trust networking** — no open ports on the host; all external traffic enters through a Cloudflare Tunnel.
3. **Layered security** — forward-auth SSO (Authentik) protects admin routes; secrets are never committed in plaintext.

---

## GitOps — App-of-Apps

ArgoCD is the cluster's control plane for deployments. The pattern used is **App-of-Apps**:

```
bootstrap/argocd/install.yaml   ← applied once manually
        │
        ▼
ArgoCD (running in cluster)
        │  watches apps/
        ▼
apps/app-of-apps.yaml           ← root Application
        │  watches apps/*.yaml
        ├─► apps/kube-prometheus-stack.yaml
        ├─► apps/loki.yaml
        ├─► apps/authentik.yaml
        ├─► apps/dev-portfolio.yaml
        └─► apps/...             ← one file per service
```

The root `app-of-apps` Application (`apps/app-of-apps.yaml`) has `automated` sync **without** `selfHeal` or `prune` — it picks up new Application files but does not auto-remove them. Individual applications configure their own sync policies.

**Adding a new service** is as simple as dropping a new `apps/<name>.yaml` file. ArgoCD picks it up on the next sync cycle. See [Adding a Service](04-adding-a-service.md).

### Helm dual-source pattern

Helm-based services (e.g., `kube-prometheus-stack`, `loki`, `authentik`) use ArgoCD's multi-source feature to keep chart versions and custom values separate:

```yaml
sources:
  - repoURL: https://prometheus-community.github.io/helm-charts
    chart: kube-prometheus-stack
    targetRevision: 82.6.0
    helm:
      valueFiles:
        - $values/manifests/kube-prometheus-stack/values.yaml
  - repoURL: https://github.com/PabloMarelli/homelab-infra.git
    targetRevision: main
    ref: values
```

The chart comes from the upstream Helm repo; the values come from this git repo (referenced as `$values`). This means values are version-controlled and chart upgrades are explicit version bumps.

---

## Networking — Zero-trust tunnel

```
Internet
   │
   ▼
Cloudflare edge
   │  TLS termination + DDoS protection
   │  CNAME *.pablomarelli.dev → <tunnel-id>.cfargotunnel.com
   ▼
cloudflared pod (namespace: infrastructure)
   │  outbound tunnel — no inbound ports on the host
   │  routes all *.pablomarelli.dev → traefik.kube-system.svc.cluster.local:80
   ▼
Traefik (namespace: kube-system, k3s default ingress)
   │  IngressRoute CRDs match by hostname
   ▼
Service pods
```

Key properties:
- The host machine has **no open inbound ports**. The tunnel is an outbound connection from `cloudflared` to Cloudflare's edge.
- DNS records are CNAME to `<tunnel-id>.cfargotunnel.com`, managed as code via OpenTofu. See [Infrastructure / DNS](06-infrastructure.md).
- TLS is handled by Cloudflare (edge) and Traefik handles plain HTTP internally — traffic inside the cluster is unencrypted (acceptable for a single-node homelab on a trusted network).

---

## Auth — Authentik forward auth

Authentik acts as the Identity Provider (IdP). Two integration modes are used:

### Forward auth (Traefik middleware)

For services that do not have native SSO support (Uptime Kuma admin routes):

```
Browser → Traefik → authentik-auth middleware
                         │
                         ▼
                  authentik-server (checks session)
                         │
              ┌──────────┴──────────┐
           authed                not authed
              │                      │
              ▼                      ▼
        upstream service       redirect to login
```

The middleware is defined in `manifests/traefik/forward-auth-middleware.yaml` and referenced by name in the IngressRoute.

### Native OAuth2 (Grafana)

Grafana is configured with Authentik as its OAuth2 provider directly in the Helm values. Users log in via Authentik and are redirected back to Grafana with a session token. No Traefik middleware involved.

---

## Namespaces

| Namespace | Purpose |
|---|---|
| `argocd` | ArgoCD control plane |
| `kube-system` | Traefik (k3s default) |
| `infrastructure` | Cloudflared tunnel daemon |
| `external-secrets` | External Secrets Operator |
| `monitoring` | Prometheus, Grafana, Loki, Alloy, Authentik, Uptime Kuma, Umami, PostgreSQL |
| `portfolio` | dev-portfolio app |
| `finance` | finance-manager app |
| `home-assistant` | Home Assistant app |

All namespaces are pre-declared in `bootstrap/namespaces.yaml` and must exist before ArgoCD attempts to deploy into them.

---

## Secret management

Two complementary strategies handle different lifecycle requirements:

| Strategy | Tool | Use case |
|---|---|---|
| Runtime secrets | External Secrets Operator + 1Password | Secrets that can be fetched after the cluster is running |
| Bootstrap secrets | Sealed Secrets (`kubeseal`) | Secrets needed before ESO is running (e.g., the ESO 1Password token itself) |

See [Secret Management](05-secret-management.md) for the full workflow.
