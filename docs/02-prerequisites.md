# Prerequisites & Setup

## Required tools

| Tool | Purpose |
|---|---|
| `kubectl` | Interact with the Kubernetes cluster |
| `kubeseal` | Encrypt secrets into Sealed Secrets |
| `argocd` CLI | Bootstrap and interact with ArgoCD |
| `tofu` (OpenTofu) | Apply DNS changes via Cloudflare |
| `op` (1Password CLI) | Manage secrets in the 1Password vault |
| `helm` | Optional — useful for local chart inspection |

## Cluster assumptions

- Single-node **k3s** cluster.
- Traefik is installed as the default k3s ingress controller — do not disable it.
- The node has outbound internet access (required for the Cloudflare Tunnel).
- A **1Password** account with a vault named `homelab-secrets`.
- A **Cloudflare** account owning the domain, with a tunnel already created.

---

## Bootstrap sequence

The cluster must be bootstrapped in this order. Steps 1–4 are one-time manual operations. After that, ArgoCD manages everything.

### 1. Install k3s

```bash
curl -sfL https://get.k3s.io | sh -
```

Copy the kubeconfig:

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
```

### 2. Create namespaces

All namespaces must exist before ArgoCD tries to deploy into them.

```bash
kubectl apply -f bootstrap/namespaces.yaml
```

### 3. Install ArgoCD

```bash
kubectl apply -n argocd -f bootstrap/argocd/install.yaml
kubectl wait --for=condition=available deployment/argocd-server -n argocd --timeout=120s
```

### 4. Bootstrap secrets (Sealed Secrets + ESO token)

The External Secrets Operator needs a 1Password service account token before it can pull any other secrets. This token is stored as a Sealed Secret so it can be committed safely.

**4a. Install the Sealed Secrets controller** (ArgoCD will manage it after bootstrap, but it must exist first to decrypt the bootstrap token):

```bash
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/latest/download/controller.yaml
```

**4b. Apply the sealed bootstrap token:**

```bash
kubectl apply -f manifests/external-secrets/bootstrap-token.sealed.yaml
```

**4c. Apply the ClusterSecretStore:**

```bash
kubectl apply -f manifests/external-secrets/cluster-secret-store.yaml
```

> If you need to re-create the sealed token (e.g., rotating the 1Password service account):
> ```bash
> # Create the raw secret
> kubectl create secret generic onepassword-token \
>   --from-literal=token=<your-op-service-account-token> \
>   --namespace external-secrets \
>   --dry-run=client -o yaml \
>   | kubeseal --format yaml > manifests/external-secrets/bootstrap-token.sealed.yaml
> ```

### 5. Apply the App-of-Apps

This single command hands control to ArgoCD. From this point on, all changes go through git.

```bash
kubectl apply -f apps/app-of-apps.yaml
```

ArgoCD will discover all `apps/*.yaml` files and begin syncing each service.

### 6. Apply DNS infrastructure

```bash
cd infrastructure/tofu
cp terraform.tfvars.example terraform.tfvars
# Fill in your Cloudflare API token and tunnel ID
tofu init
tofu apply
```

See [Infrastructure / DNS](06-infrastructure.md) for details.

---

## Cluster DNS for ArgoCD access during bootstrap

Before DNS is up, you can access ArgoCD locally via port-forward:

```bash
kubectl port-forward svc/argocd-server -n argocd 8080:443
```

Then log in:

```bash
# Get the initial admin password
argocd admin initial-password -n argocd

argocd login localhost:8080 --insecure
```
