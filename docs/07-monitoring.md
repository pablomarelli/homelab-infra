# Monitoring & Alerting

The observability stack follows the **PLG** pattern: Prometheus (metrics) + Loki (logs) + Grafana (visualization), with Grafana Alloy as the unified collector. All components run in the `monitoring` namespace.

---

## Stack overview

```
Pods (all namespaces)
   │  stdout/stderr logs
   ▼
Grafana Alloy (DaemonSet)
   │  scrapes pod logs via Kubernetes SD
   │  normalizes log levels
   ▼
Loki (single-binary, filesystem storage)
   │
   └──► Grafana (Loki datasource)

Node / kube-state-metrics / cAdvisor
   │  Prometheus metrics
   ▼
Prometheus (15d retention, 10Gi PVC)
   │
   ├──► Grafana (Prometheus datasource)
   └──► Alertmanager
              │
              ▼
           Discord webhooks
```

---

## Prometheus

Deployed via `kube-prometheus-stack` (Helm chart v82.6.0). Configuration: `manifests/kube-prometheus-stack/values.yaml`.

Key settings for a single-node homelab:
- **Retention:** 15 days
- **Storage:** 10Gi PVC
- Components disabled (not present on single-node k3s): `etcd`, `kubeScheduler`, `kubeControllerManager`, `kubeProxy`

---

## Loki

Deployed in `SingleBinary` mode (all components in one pod). Configuration: `manifests/loki/values.yaml`.

- **Storage:** Filesystem (10Gi PVC) — no object storage dependency
- **Mode:** Single binary, no gateway, no distributed components
- **Retention:** Configured via Loki's built-in compactor

Loki has no public UI — it is accessed exclusively through Grafana as a datasource.

---

## Grafana Alloy

Deployed as a `DaemonSet` — one pod per node. Configuration: `manifests/alloy/values.yaml`.

Alloy handles log collection:
1. Discovers all running pods via the Kubernetes API (Kubernetes SD).
2. Reads logs from the container runtime (CRI format).
3. Parses structured JSON logs where available.
4. Normalizes log level labels (maps variants like `warn`, `WARNING`, `Warn` → `warning`).
5. Ships logs to Loki with labels: `namespace`, `pod`, `container`, `node`.

---

## Alertmanager

Configuration: `manifests/alertmanager-config/alertmanager-main.yaml`.

### Routing

| Severity | Action |
|---|---|
| `critical` | Posted to Discord |
| `warning` | Posted to Discord |
| `info` | Silenced |
| `none` | Silenced |

### Inhibition rules

Critical alerts suppress their corresponding warning alerts to reduce noise.

### Discord integration

Two channels are configured:

| Channel | Label | Used for |
|---|---|---|
| `discord-main` | `notifications.argocd/channel: main` | Application deployments |
| `discord-infra` | `notifications.argocd/channel: infra` | Infrastructure changes |

The Discord webhook URLs are stored in 1Password and pulled via `ExternalSecret`.

### Custom disk alerts

`manifests/alertmanager-config/custom-disk-alerts.yaml` adds `PrometheusRule` resources for disk space:

| Alert | Threshold | Severity |
|---|---|---|
| `DiskSpaceLow` | < 30% free | `warning` |
| `DiskSpaceLow` | < 20% free | `warning` |
| `DiskSpaceCritical` | < 10% free | `critical` |

---

## Grafana

Deployed as part of `kube-prometheus-stack`. Access: `grafana.pablomarelli.dev`.

### Authentication

Grafana uses Authentik as its OAuth2 provider (native integration, not Traefik forward auth). Configuration is in `manifests/kube-prometheus-stack/values.yaml` under `grafana.grafana.ini.auth.generic_oauth`.

### Dashboards as code

Dashboards are stored as `ConfigMap` resources in `manifests/grafana-dashboards/`. Grafana's sidecar container discovers them automatically via the label `grafana_dashboard: "1"`.

| Dashboard | File | Purpose |
|---|---|---|
| Application logs | `app-logs-dashboard.yaml` | Loki logs for `portfolio`, `finance`, `home-assistant` namespaces |
| Error overview | `error-overview-dashboard.yaml` | Error-level log aggregation across all namespaces |
| Infrastructure logs | `infra-logs-dashboard.yaml` | Logs from the `infrastructure` namespace |
| Observability logs | `observability-logs-dashboard.yaml` | Logs from the `monitoring` namespace |

To add a new dashboard:
1. Export the JSON from Grafana UI (Dashboard → Share → Export).
2. Create a new `ConfigMap` in `manifests/grafana-dashboards/` with the label `grafana_dashboard: "1"`.
3. Embed the JSON in the `data` field.
4. Commit — ArgoCD syncs the ConfigMap and Grafana's sidecar picks it up automatically.

---

## Datasources

Both datasources are configured in the `kube-prometheus-stack` Helm values:

| Datasource | URL |
|---|---|
| Prometheus | `http://kube-prometheus-stack-prometheus.monitoring.svc.cluster.local:9090` |
| Loki | `http://loki.monitoring.svc.cluster.local:3100` |
