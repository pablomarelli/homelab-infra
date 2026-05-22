# Node Topology

The cluster runs as a two-node k3s homelab with distinct reliability roles.

## Nodes

| Node | Role | Power | Storage | Intended use |
|---|---|---|---|---|
| `pablo-ideapad-l340-17irh-gaming` | `control-plane` | `battery-backed` | `ssd-500gb` | k3s server, critical services, stateful workloads |
| `homelab-desktop-01` | `worker` | `non-ups` | `ssd-1tb` | stateless and compute-heavy workloads |

## Labels

Node placement is expressed with homelab-specific labels:

```bash
homelab/node-role=control-plane
homelab/node-role=worker
homelab/power=battery-backed
homelab/power=non-ups
homelab/storage=ssd-500gb
homelab/storage=ssd-1tb
homelab/gpu=nvidia-1660ti
```

## Desktop Taint

The desktop node is intentionally tainted because it is not UPS-backed:

```bash
homelab/power=non-ups:NoSchedule
```

Workloads only run there when their Git-managed manifests explicitly tolerate that taint.

## Placement Policy

Critical stateful workloads stay on the battery-backed notebook until the storage architecture changes.

Examples:

- PostgreSQL
- Uptime Kuma
- backup PVC writers
- control-plane-adjacent services

Stateless or easily recoverable workloads may run on the desktop when they include both:

```yaml
nodeSelector:
  homelab/node-role: worker
  homelab/power: non-ups

tolerations:
  - key: homelab/power
    operator: Equal
    value: non-ups
    effect: NoSchedule
```

Battery-backed workloads should include:

```yaml
nodeSelector:
  homelab/power: battery-backed
```

## GitOps Rule

Workload placement belongs in this repository and is reconciled by ArgoCD. Do not use live `kubectl patch` changes for scheduling policy except during emergency recovery.
