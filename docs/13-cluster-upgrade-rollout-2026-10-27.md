# Cluster upgrade rollout - 2026-10-27

## Sequence and review policy

Start with Umami's security update, then review Uptime Kuma and ntfy before their individual rollouts. PostgreSQL maintenance, the K3s/Traefik pair, identity/secrets and monitoring follow in separate changes. The initial audit was a release inventory, not a complete intervening-changelog review for every component.

For each rollout: review all intervening release notes and migrations, identify deployment-specific risks, establish recovery, validate a rehearsal where persistent data changes, deploy, then verify user-facing behavior and reconciliation.

## cloudflared

Already running `2026.10.5` at the start of this rollout. Logs confirm four registered QUIC connections and successful connectivity prechecks. The public analytics collector heartbeat returns HTTP 200 through the tunnel.

## Umami: 3.1.0 to 3.4.1

### Review completed before deployment

Read every intervening release: [3.2.0](https://github.com/umami-software/umami/releases/tag/v3.2.0), [3.3.0](https://github.com/umami-software/umami/releases/tag/v3.3.0), [3.3.1](https://github.com/umami-software/umami/releases/tag/v3.3.1), [3.4.0](https://github.com/umami-software/umami/releases/tag/v3.4.0), and [3.4.1](https://github.com/umami-software/umami/releases/tag/v3.4.1).

Also inspected the target Dockerfile, `scripts/start-docker.sh`, `scripts/check-db.js`, and SQL migrations 20 through 26 from the exact `v3.4.1` source tag.

Risks and decisions:

- Seven migrations run at container startup. Migration 20 renames `website.replay_enabled` to `recorder_enabled`, making concurrent old/new versions unsafe. Use Deployment strategy `Recreate`, accepting a brief analytics interruption.
- Migration 23 deletes duplicate session properties before adding a unique index. Production has zero duplicate `(session_id, data_key)` groups.
- Migration 24 lowercases usernames. Production has zero uppercase live usernames.
- New 2FA requires a persistent encryption key before enabling it. Existing accounts have no 2FA configuration; login was tested with the existing environment shape, without introducing 2FA during this upgrade.
- Authentication/session handling changes may require users to log in again. New report APIs retain compatibility handlers, but reporting and event ingestion still need functional verification.
- MCP remains disabled by default.
- A rollback to 3.1.0 requires restoration of the pre-upgrade database, not just an image change.

### Rehearsal evidence

- Created a PostgreSQL custom-format backup of the approximately 9 MB production Umami database under `/home/pablo/.tmp/opencode/cluster-upgrades-2026-10-27/`, with restrictive file permissions.
- Restored successfully into an isolated Docker PostgreSQL 16.14 instance using `pg_restore --exit-on-error`.
- Started the published 3.4.1 image with the production memory/CPU limits and DATABASE_URL-only application configuration.
- All seven pending migrations completed; 26 migrations are recorded as successful.
- Existing data counts were preserved: one website, 75 events, 21 sessions.
- Created a temporary test account only in the restored copy; browser login, website overview and event reporting worked.
- A synthetic event was accepted, persisted and displayed in the Events screen. All observed application API requests succeeded. An external DuckDuckGo favicon lookup returned 404; no application API failure accompanied it.
- Candidate image manifest digest: `sha256:e69d1a7932e9dab0fc523edc7be1f3a53f3c261f57856fc2167ae74a8fc022e8`.

### Production rollout

Completed through GitOps in commit `23bc28f`:

- Temporarily disabled Umami automatic synchronization, scaled the old Deployment to zero and waited for its pod to terminate before the final backup.
- Final backup: `/home/pablo/.tmp/opencode/cluster-upgrades-2026-10-27/umami-final-pre-3.4.1.dump`; SHA256 `5e9b63618e2ffd04a47bf5e3a04ca130dfa4a96e24509abfb3f748a19525381b`.
- Pushed the reviewed manifest and restored the original automatic synchronization policy. The Deployment rolled out successfully with 3.4.1.
- Startup logs confirm all seven migrations applied successfully; the database records 26 completed migrations.
- Before the post-upgrade browser check, existing counts remained one website, 75 events and 21 sessions.
- Public collector heartbeat returned `{"ok":true}`.
- Visited the real portfolio in a browser with query `upgrade_check=umami-3.4.1-20261027`: tracker script returned HTTP 200, collection POST returned HTTP 200, and the corresponding pageview was found in the production database. This adds one intentional verification pageview to analytics.
- All 22 remaining Argo CD Applications report Synced and Healthy, including app-of-apps and Umami. The inactive project exclusions were published in preceding commit `059cf77`.
- Authenticated dashboard login/reporting was verified on the restored production-data rehearsal; a real production-user login was not performed because no user credentials were supplied.

Rehearsal containers and their internal network were removed after verification; the pre-upgrade backups were retained outside Git. Later components still require their own intervening-changelog and deployment-risk review before rollout.

### Recovery procedure

If migration or functional verification fails, disable automatic synchronization for the Umami Application, stop its Deployment, retain a copy of the failed database for investigation, and restore the final pre-upgrade backup into a clean replacement database with the original owner and permissions. Restore the 3.1.0 manifest in Git, start one replica, verify the collector and dashboard, then restore automatic synchronization. Do not point 3.1.0 at a migrated 3.4.1 database. Restoring the backup discards writes after that backup; the rollout's write freeze is intended to minimize this interval.

## Uptime Kuma: 2.3.2 to 2.5.8

Read all intervening published stable release notes (2.4.0, 2.5.0 through 2.5.8) and the database migration changes in the [exact comparison](https://github.com/louislam/uptime-kuma/compare/2.3.2...2.5.8).

### Risks checked

- 2.4.0 and 2.5.8 fix authenticated/admin-only code-execution issues; intervening updates also fix dependency vulnerabilities.
- 2.5.8 removes TLS/STARTTLS checking from TCP monitors. The only configured TCP monitor is PostgreSQL, with no TLS setting, so this behavior change does not affect the current monitor configuration.
- Eight new Knex migration files change monitor fields, status-page analytics types, and daily counters. SQLite column recreation makes a backup and migration rehearsal necessary; rollback uses the original database snapshot.
- Use `Recreate` to avoid simultaneous writers/migrations on the same SQLite PVC, and HTTP startup/readiness probes so rollout success requires a responding application.
- Production baseline: 11 monitors (nine active, including three groups), one notification configuration, two status pages; every active monitor's most recent heartbeat is UP.

### Rehearsal

Created an online-safe SQLite `.backup` plus auxiliary data archive, restored into an isolated Docker container with the production resource limits, and disabled monitors only in the rehearsal copy to prevent duplicate checks and notifications. All migrations succeeded. SQLite integrity check passed; all 11 monitors, one notification configuration, two status pages and 23,939 backed-up heartbeats were preserved. A rehearsal-only password change allowed browser verification of login and dashboard; the public status page rendered correctly.

Backup: `/home/pablo/.tmp/opencode/cluster-upgrades-2026-10-27/kuma-pre-2.5.8.tar.gz`.

Candidate image digest: `sha256:20abea8c48a163cf0a7a5d5936ab418e4b742d908704e1f58f6c06e56a9c6b67`.

Production rollout and post-upgrade monitor checks: pending.
