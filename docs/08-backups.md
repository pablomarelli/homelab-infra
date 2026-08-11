# Backups

Three automated backup jobs run across the `monitoring` and `forgejo` namespaces. They use `CronJob` resources and store dumps on dedicated `PersistentVolumeClaim` volumes. Retention is 14 copies of each backup.

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
**Image:** `alpine:3.23`
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

## Forgejo

**CronJob:** `manifests/forgejo/backup-cronjob.yaml`
**Namespace:** `forgejo`
**Schedule:** `15 3 * * *` — 03:15 daily
**Image:** `codeberg.org/forgejo/forgejo:15.0.6`
**PVCs:** `forgejo-data` (writable source), `forgejo-backups` (destination)

### What gets backed up

The job runs the Forgejo-native `forgejo dump` command against `/data/gitea/conf/app.ini`. The archive captures the SQLite database, Git repositories, configuration and custom files, and Forgejo-managed data such as LFS objects, attachments, packages, indexes, and repository archives. Logs are deliberately skipped.

The source mount must be writable because `forgejo dump` opens the SQLite database read-write. Archives are written to `/backups` as `forgejo_YYYYMMDD_HHMMSS.tar.gz`.

### Retention

The job keeps the **14 most recent archives**. Older archives are removed at the end of each run.

### Consistency

Scheduled dumps run while Forgejo is available and assume there are no concurrent writes. They are not guaranteed to be point-in-time consistent across the database, repositories, and other stored data. For stronger recovery guarantees, stop Forgejo and take a synchronized snapshot of the complete `forgejo-data` PVC.

### Restoring Forgejo

Restores require Forgejo to be stopped and the restore environment to use the same Forgejo version as the archive (`codeberg.org/forgejo/forgejo:15.0.6`).

1. Stop the deployment to prevent writes:
   ```bash
   kubectl scale deployment forgejo -n forgejo --replicas=0
   ```
2. Start a temporary pod using the same Forgejo image with `forgejo-data` mounted at `/data` and `forgejo-backups` mounted at `/backups`.
3. Inspect and extract the selected archive. Restore its database, repositories, configuration/custom files, and data to the locations defined by the archived `app.ini`; Forgejo has no full-instance restore command.
4. Set restored files to UID/GID `1000`, remove the temporary pod, and restart Forgejo:
   ```bash
   kubectl scale deployment forgejo -n forgejo --replicas=1
   ```
5. Verify the HTTPS UI and clone a repository before allowing writes.

---

## Backup storage location

All three jobs write to PVCs backed by the k3s default `local-path` storage class. Backups are stored on node-local disks, so they do not protect against loss of the node or its disk. Forgejo and its backup job are pinned to the battery-backed node because both Forgejo PVCs are local to that node; the backup cannot move independently to another node. For off-site durability, periodically sync backup PVC contents to an external location (for example, with rclone to object storage).

---

## Monitoring backup jobs

Backup job success/failure can be monitored in:
- **Grafana** — query Loki for logs from the `monitoring` and `forgejo` namespaces, with pod names matching `pg-backup-*`, `uptime-kuma-backup-*`, or `forgejo-backup-*`.
- **kubectl:**
  ```bash
  kubectl get jobs -n monitoring
  kubectl get jobs -n forgejo
  kubectl logs -n monitoring job/pg-backup-<id>
  kubectl logs -n monitoring job/uptime-kuma-backup-<id>
  kubectl logs -n forgejo job/forgejo-backup-<id>
  ```
