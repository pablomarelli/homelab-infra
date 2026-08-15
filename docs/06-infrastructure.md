# Infrastructure / DNS

External cloud infrastructure is managed as code via OpenTofu (Terraform fork) using the Cloudflare provider. All files live under `infrastructure/`.

---

## Cloudflare Tunnel

The cluster has no open inbound ports on the host. External traffic reaches the cluster through a **Cloudflare Tunnel**:

1. The `cloudflared` deployment (namespace: `infrastructure`) opens an outbound persistent connection to Cloudflare's edge.
2. Cloudflare routes incoming requests for `*.pablomarelli.dev` through the tunnel to `cloudflared`.
3. `cloudflared` forwards all traffic to `traefik.kube-system.svc.cluster.local:80`.

The tunnel configuration is a `ConfigMap` at `manifests/infrastructure/cloudflared/configmap.yaml`. It contains a single ingress rule:

```yaml
ingress:
  - hostname: "*.pablomarelli.dev"
    service: http://traefik.kube-system.svc.cluster.local:80
  - service: http_status:404
```

The tunnel credentials (the token that authenticates `cloudflared` to Cloudflare) are stored as an `ExternalSecret` and pulled from 1Password at runtime.

---

## DNS — OpenTofu

DNS records are managed in `infrastructure/tofu/`. The configuration creates one CNAME record per subdomain, all pointing at the tunnel.

### How it works

`dns.tf` iterates over the `subdomains` list and creates a proxied CNAME for each:

```hcl
resource "cloudflare_record" "tunnel" {
  for_each = toset(var.subdomains)
  zone_id  = data.cloudflare_zone.main.id
  name     = each.value
  content  = "${var.tunnel_id}.cfargotunnel.com"
  type     = "CNAME"
  proxied  = true
  ttl      = 1
}
```

`proxied = true` means traffic passes through Cloudflare's edge (DDoS protection, TLS termination). `ttl = 1` is Cloudflare's automatic TTL for proxied records.

### Current subdomains

```
argocd, portfolio, finance, home, auth, status, analytics, analytics-collector, grafana, dozzle
```

All resolve to `<tunnel-id>.cfargotunnel.com`.

### Adding a new subdomain

1. Edit `infrastructure/tofu/variables.tf`, add the new name to the `subdomains` list:

```hcl
variable "subdomains" {
  default = ["argocd", "portfolio", "finance", "home", "auth", "status", "analytics", "grafana", "my-app"]
}
```

2. Apply:

```bash
./scripts/tofu plan   # verify the diff
./scripts/tofu apply
```

This creates the DNS record. The subdomain will be routed through the tunnel to Traefik — you still need to add an `IngressRoute` to route it to the correct service. See [Adding a Service](04-adding-a-service.md).

---

## Configuration files

| File | Purpose |
|---|---|
| `infrastructure/tofu/main.tf` | Cloudflare provider configuration |
| `infrastructure/tofu/dns.tf` | CNAME records for all subdomains |
| `infrastructure/tofu/variables.tf` | Domain, tunnel ID, subdomain list |
| `infrastructure/tofu/tofu.env.op` | Safe 1Password references used by the Tofu wrapper |
| `scripts/tofu` | Runs OpenTofu with credentials injected from 1Password |
| `manifests/infrastructure/cloudflared/configmap.yaml` | `cloudflared` routing config |

### OpenTofu state and credentials

OpenTofu stores its state in the private R2 bucket `homelab-opentofu-state`.
Create this bucket manually in the Cloudflare dashboard so it remains available
independently of the state it stores. Do not enable an `r2.dev` URL or attach a
public custom domain.

Create the bucket and its credentials in the Cloudflare dashboard:

1. Open **Storage & databases > R2 > Overview** and create the Standard storage
   bucket `homelab-opentofu-state`.
2. Open **Manage API Tokens** and select **Create User API token**.
3. Grant **Object Read & Write**, apply it only to
   `homelab-opentofu-state`, and create the token.
4. Copy the Access Key ID, Secret Access Key, and S3 endpoint shown by
   Cloudflare. The secret is only displayed once.

Create the following items and fields in the `homelab-secrets` 1Password vault:

| Item | Field | Value |
|---|---|---|
| `opentofu-r2` | `access-key-id` | R2 Access Key ID |
| `opentofu-r2` | `secret-access-key` | R2 Secret Access Key |
| `opentofu-r2` | `endpoint` | `https://<ACCOUNT_ID>.r2.cloudflarestorage.com` |
| `cloudflare` | `api-token` | Token with DNS edit permission |

The committed `tofu.env.op` file contains only references to these fields. The
wrapper resolves them for the lifetime of each OpenTofu process:

```bash
./scripts/tofu init
./scripts/tofu plan
./scripts/tofu apply
```

To migrate an existing local state after the bucket and credentials are ready:

```bash
cp infrastructure/tofu/terraform.tfstate /path/to/a/safe/terraform.tfstate.backup
./scripts/tofu init -migrate-state
./scripts/tofu plan
```

Only remove the local state and `terraform.tfvars` after the migrated state has
been verified from a clean checkout.

The `domain` and `tunnel_id` variables have defaults in `variables.tf` and only need to be overridden if you fork this repo for a different domain/tunnel.

---

## Initial tunnel setup

The Cloudflare Tunnel itself (the tunnel object and its credentials) must be created once in the Cloudflare dashboard or via `cloudflared tunnel create`. Once created:

1. Note the tunnel ID and update `variables.tf` if different from the default.
2. Store the tunnel credentials token in 1Password under `homelab-secrets`.
3. The `cloudflared` deployment pulls the token via an `ExternalSecret` at startup.
