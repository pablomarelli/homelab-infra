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

Pending: freeze application writes, take a final backup, deploy the reviewed manifest through GitOps, verify migrations, preserved data, public collection and application health.

### Recovery procedure

If migration or functional verification fails, disable automatic synchronization for the Umami Application, stop its Deployment, retain a copy of the failed database for investigation, and restore the final pre-upgrade backup into a clean replacement database with the original owner and permissions. Restore the 3.1.0 manifest in Git, start one replica, verify the collector and dashboard, then restore automatic synchronization. Do not point 3.1.0 at a migrated 3.4.1 database. Restoring the backup discards writes after that backup; the rollout's write freeze is intended to minimize this interval.
