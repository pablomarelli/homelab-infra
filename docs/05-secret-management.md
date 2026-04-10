# Secret Management

Two complementary strategies handle secrets with different lifecycle requirements. Neither strategy ever stores plaintext secrets in git.

---

## Strategy 1 — External Secrets Operator + 1Password

**Use when:** The secret can be fetched after the cluster is running (i.e., after ESO itself is deployed).

ESO watches `ExternalSecret` resources and pulls values from the 1Password vault `homelab-secrets` into native Kubernetes `Secret` objects. The `ClusterSecretStore` (`manifests/external-secrets/cluster-secret-store.yaml`) configures the connection to 1Password using the 1Password SDK.

```
1Password vault: homelab-secrets
        │
        │  (1Password service account token)
        ▼
ExternalSecrets Operator (namespace: external-secrets)
        │  reconciles ExternalSecret → Secret
        ▼
Kubernetes Secret (in the target namespace)
        │
        ▼
Pod (mounts secret as env var or volume)
```

### Adding a secret from 1Password

**1. Add the item to 1Password**

In the `homelab-secrets` vault, create or update a Login or Secure Note item. Take note of the item name and field name.

**2. Create an ExternalSecret manifest**

```yaml
apiVersion: external-secrets.io/v1
kind: ExternalSecret
metadata:
  name: my-app-secret
  namespace: my-app
spec:
  refreshInterval: 1h
  secretStoreRef:
    name: onepassword
    kind: ClusterSecretStore
  target:
    name: my-app-secret          # name of the resulting K8s Secret
    creationPolicy: Owner
  data:
    - secretKey: MY_API_KEY      # key in the resulting Secret
      remoteRef:
        key: My App Credentials  # 1Password item name
        property: api_key        # 1Password field name
```

Place this file at `manifests/my-app/secret.external.yaml` (the `.external.yaml` suffix is a convention used in this repo to identify ESO resources).

**3. Commit and push**

ArgoCD syncs the `ExternalSecret`. ESO fetches the value from 1Password and creates the native `Secret`. No plaintext ever touches the repo.

---

## Strategy 2 — Sealed Secrets

**Use when:** A secret must exist _before_ ESO is running — e.g., the 1Password service account token that ESO itself needs. This is the bootstrap chicken-and-egg problem.

Sealed Secrets uses asymmetric encryption. You encrypt with the controller's public key; only the in-cluster controller can decrypt. The encrypted blob is safe to commit.

```
kubeseal (local)
   │  encrypts with controller's public key
   ▼
SealedSecret YAML (committed to git)
   │
   ▼
Sealed Secrets controller (in cluster)
   │  decrypts with private key
   ▼
Kubernetes Secret
```

### Creating a Sealed Secret

**1. Fetch the controller's public key** (only needed once; cache it locally):

```bash
kubeseal --fetch-cert \
  --controller-name=sealed-secrets-controller \
  --controller-namespace=kube-system \
  > pub-sealed-secrets.pem
```

**2. Create the raw secret (dry-run, never apply directly):**

```bash
kubectl create secret generic my-secret \
  --from-literal=token=<secret-value> \
  --namespace my-namespace \
  --dry-run=client -o yaml \
  | kubeseal --cert pub-sealed-secrets.pem --format yaml \
  > manifests/my-app/my-secret.sealed.yaml
```

**3. Commit the `.sealed.yaml` file** — it is safe to commit, the value is encrypted.

**4. Apply or let ArgoCD sync it:**

```bash
kubectl apply -f manifests/my-app/my-secret.sealed.yaml
```

### Rotating a Sealed Secret

Re-run step 2 with the new value and commit the updated `.sealed.yaml`. The controller automatically reconciles the underlying `Secret`.

> **Important:** Sealed Secrets are namespace-scoped by default. A secret sealed for namespace `external-secrets` cannot be decrypted in any other namespace.

---

## Which strategy to use

| Scenario | Strategy |
|---|---|
| App database password | ESO (ExternalSecret) |
| API keys, tokens used at runtime | ESO (ExternalSecret) |
| ESO's own 1Password token | Sealed Secret |
| Any secret needed before ESO is ready | Sealed Secret |
| Secrets for services that ArgoCD deploys before ESO is deployed | Sealed Secret |

---

## File naming conventions

| Suffix | Meaning |
|---|---|
| `*.external.yaml` | ESO `ExternalSecret` resource |
| `*.sealed.yaml` | Bitnami `SealedSecret` resource |
| `*.secret.yaml.example` | Example showing structure; never contains real values |
