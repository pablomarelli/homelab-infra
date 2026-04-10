# Adding a Service

Checklist for onboarding a new application into the cluster. Most steps involve adding or editing files in this repo — ArgoCD picks up the changes on the next sync.

---

## 1. Add the namespace (if new)

Edit `bootstrap/namespaces.yaml` and add the new namespace:

```yaml
---
apiVersion: v1
kind: Namespace
metadata:
  name: my-app
```

Apply it immediately (this is one of the few manual `kubectl apply` operations):

```bash
kubectl apply -f bootstrap/namespaces.yaml
```

> Namespaces are declared upfront rather than letting ArgoCD create them via `CreateNamespace=true`, so that RBAC and other namespace-level resources can be controlled explicitly.

---

## 2. Add Kubernetes manifests

Create a directory under `manifests/`:

```
manifests/
└── my-app/
    ├── deployment.yaml
    ├── service.yaml
    └── ...
```

For Helm-based services, add a `values.yaml` file — the chart reference goes in the ArgoCD Application (step 3).

---

## 3. Create the ArgoCD Application

Create `apps/my-app.yaml`. Use one of the two patterns below.

### Plain manifests

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
  labels:
    notifications.argocd/channel: main   # discord-main webhook
    notifications.argocd/profile: app
spec:
  project: default
  source:
    repoURL: https://github.com/PabloMarelli/homelab-infra.git
    targetRevision: HEAD
    path: manifests/my-app
  destination:
    server: https://kubernetes.default.svc
    namespace: my-app
  syncPolicy:
    automated:
      prune: false
      selfHeal: true
    syncOptions:
      - CreateNamespace=false
```

### Helm chart with values from this repo

```yaml
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-app
  namespace: argocd
  labels:
    notifications.argocd/channel: infra
    notifications.argocd/profile: critical
spec:
  project: default
  sources:
    - repoURL: https://charts.example.com
      chart: my-app
      targetRevision: 1.0.0
      helm:
        valueFiles:
          - $values/manifests/my-app/values.yaml
    - repoURL: https://github.com/PabloMarelli/homelab-infra.git
      targetRevision: main
      ref: values
  destination:
    server: https://kubernetes.default.svc
    namespace: my-app
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
      - CreateNamespace=false
      - ServerSideApply=true
```

### Notification labels

| Label | Value | Effect |
|---|---|---|
| `notifications.argocd/channel` | `main` | Posts to `discord-main` (app channel) |
| `notifications.argocd/channel` | `infra` | Posts to `discord-infra` (infra channel) |
| `notifications.argocd/channel` | `none` | No Discord notifications |
| `notifications.argocd/profile` | `app` | Notifies on sync/health events |
| `notifications.argocd/profile` | `critical` | Notifies only on failures |
| `notifications.argocd/profile` | `quiet` | Minimal notifications |

---

## 4. Add a DNS record

Edit `infrastructure/tofu/variables.tf` and add the subdomain to the `subdomains` list:

```hcl
variable "subdomains" {
  default = ["argocd", "portfolio", "finance", "home", "auth", "status", "analytics", "grafana", "my-app"]
}
```

Apply:

```bash
cd infrastructure/tofu
tofu apply
```

This creates a CNAME record `my-app.pablomarelli.dev → <tunnel-id>.cfargotunnel.com`.

---

## 5. Add an IngressRoute

Edit `manifests/traefik/ingress-routes.yaml` and add a route for the new service:

```yaml
---
apiVersion: traefik.io/v1alpha1
kind: IngressRoute
metadata:
  name: my-app
  namespace: my-app
spec:
  entryPoints:
    - web
  routes:
    - match: Host(`my-app.pablomarelli.dev`)
      kind: Rule
      services:
        - name: my-app-svc
          port: 80
```

To protect the route with Authentik forward auth, add the middleware:

```yaml
      middlewares:
        - name: authentik-auth
          namespace: monitoring
```

The `traefik-config` ArgoCD Application watches `manifests/traefik/`, so committing this change is enough — no manual `kubectl apply` needed.

---

## 6. Add secrets (if needed)

If the service needs secrets, choose the appropriate strategy:

- **Runtime secret from 1Password** → see [Secret Management — ESO workflow](05-secret-management.md#adding-a-secret-from-1password)
- **Bootstrap / chicken-and-egg secret** → see [Secret Management — Sealed Secrets workflow](05-secret-management.md#creating-a-sealed-secret)

---

## Summary checklist

- [ ] Namespace added to `bootstrap/namespaces.yaml` and applied
- [ ] Manifests or Helm values added under `manifests/my-app/`
- [ ] ArgoCD Application created at `apps/my-app.yaml`
- [ ] Subdomain added to `infrastructure/tofu/variables.tf` and `tofu apply` run
- [ ] IngressRoute added to `manifests/traefik/ingress-routes.yaml`
- [ ] Secrets configured (if needed)
- [ ] Changes committed and pushed — ArgoCD syncs automatically
