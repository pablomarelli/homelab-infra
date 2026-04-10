# Backups

Two automated backup jobs run in the `monitoring` namespace. Both use `CronJob` resources and store dumps on dedicated `PersistentVolumeClaim` volumes. Retention is 14 copies of each backup.

---

## PostgreSQL

**CronJob:** `manifests/pg-backup/cronjob.yaml`  
**Schedule:** `0 3,15 * * *` — 03:00 and 15:00 daily  
**Image:** `postgres:16-alpine`  
**PVC:** `pg-backups`

### What gets backed up

| Database | Dump file format | Filename pattern |
|---|---|---|
| `authentik` | `pg_dump -Fc` (custom binary) | `authentik_YYYYMMDD_HHMMSS.dump` |
| `umami` | `pg_dump -Fc` (custom binary) | `umami_YYYYMMDD_HHMMSS.dump` |

### Retention

The job keeps the **14 most recent dumps** of each database. Older files are removed at the end of each run.

### Restoring a PostgreSQL backup

1. Exec into a postgres pod or spin up a temporary one with access to the `pg-backups` PVC.
2. Find the dump file to restore:
   ```bash
   ls -lt /backups/authentik_*.dump
   ```
3. Restore using `pg_restore`:
   ```bash
   pg_restore -h postgresql.monitoring.svc.cluster.local \
     -U postgres \
     -d authentik \
     --clean \
     /backups/authentik_20260101_030000.dump
   ```

> `pg_dump -Fc` produces a compressed custom-format archive. It must be restored with `pg_restore`, not `psql`.

---

## Uptime Kuma

**CronJob:** `manifests/uptime-kuma/backup-cronjob.yaml`  
**Schedule:** `30 2 * * *` — 02:30 daily  
**Image:** `alpine:3.21`  
**PVCs:** `uptime-kuma-data` (read-only source), `uptime-kuma-backups` (destination)

### What gets backed up

The backup job uses `sqlite3 .backup` for an online-safe snapshot of the live database, then tarballs:

- `kuma.db` (SQLite database — monitors, status pages, notification settings)
- `docker-tls/` (if present)
- `screenshots/` (if present)
- `upload/` (if present)

**Filename pattern:** `uptime-kuma_YYYYMMDD_HHMMSS.tar.gz`

### Retention

The job keeps the **14 most recent archives**. Older archives are removed at the end of each run.

### Restoring Uptime Kuma

1. Stop the Uptime Kuma deployment to avoid write conflicts:
   ```bash
   kubectl scale deployment uptime-kuma -n monitoring --replicas=0
   ```
2. Spin up a temporary pod with access to both PVCs and extract the archive:
   ```bash
   tar -xzf /backups/uptime-kuma_20260101_023000.tar.gz -C /source/
   ```
3. Restart the deployment:
   ```bash
   kubectl scale deployment uptime-kuma -n monitoring --replicas=1
   ```

---

## Backup storage location

Both jobs write to PVCs backed by the k3s default `local-path` storage class. Backups are stored on the node's local disk. For off-site durability, consider periodically syncing the PVC contents to an external location (e.g., rclone to object storage).

---

## Monitoring backup jobs

Backup job success/failure can be monitored in:
- **Grafana** — query Loki for logs from `monitoring` namespace, pod name matching `pg-backup-*` or `uptime-kuma-backup-*`.
- **kubectl:**
  ```bash
  kubectl get jobs -n monitoring
  kubectl logs -n monitoring job/pg-backup-<id>
  kubectl logs -n monitoring job/uptime-kuma-backup-<id>
  ```
