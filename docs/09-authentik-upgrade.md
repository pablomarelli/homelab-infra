# Authentik Upgrade Runbook

Authentik must be upgraded in release-train hops when crossing release trains. Keep the Helm chart and the external Traefik outpost image on the same version at every hop.

## Current deployment

The 2026-10-28 rollout deployed this release-train hop after an isolated database migration rehearsal:

| Component | From | To |
|---|---:|---:|
| `apps/authentik.yaml` chart | `2026.5.0` | `2026.8.5` |
| `manifests/authentik-outpost/outpost-deployment.yaml` image | `2026.5.0` | `2026.8.5` |

Migration, readiness, worker health, outpost connectivity, anonymous ForwardAuth redirects and public Grafana OIDC discovery passed. Real user login, authenticated ForwardAuth and Grafana OAuth callback verification remain pending; Grafana's public entry is gated by Cloudflare Access. See `docs/13-cluster-upgrade-rollout-2026-10-27.md` for evidence and backup locations.

## Published Chart Hop Sequence

Use the latest published chart patch in each release train:

1. `2024.2.2` -> `2024.4.2`
2. `2024.4.2` -> `2024.6.4`
3. `2024.6.4` -> `2024.8.4`
4. `2024.8.4` -> `2024.10.5`
5. `2024.10.5` -> `2024.12.3`
6. `2024.12.3` -> `2025.2.4`
7. `2025.2.4` -> `2025.4.1`
8. `2025.4.1` -> `2025.6.4`
9. `2025.6.4` -> `2025.8.4`
10. `2025.8.4` -> `2025.10.3`
11. `2025.10.3` -> `2025.12.4`
12. `2025.12.4` -> `2026.2.2`
13. `2026.2.2` -> `2026.5.0`
14. `2026.5.0` -> `2026.8.5`

## Before Each Hop

1. Confirm ArgoCD is healthy and the repo is clean.
2. Confirm a recent PostgreSQL backup exists on the `pg-backups` PVC.
3. If the latest scheduled backup is too old, create a one-off backup job from the CronJob before changing the Authentik version.
4. Read the target release notes and handle manual-action items before syncing.
5. Update both `apps/authentik.yaml` and `manifests/authentik-outpost/outpost-deployment.yaml` together.
6. Rehearse migrations against a restored database on an isolated network with no outbound access. Keep the production secret key in private storage for recovery.
7. Quiesce server, worker and outpost together through GitOps, wait for their pods to terminate, then take a final Authentik database dump before deploying the new versions. Server and worker use `Recreate`; that strategy alone does not prevent overlap across separate Deployments.

## After Each Hop

1. Sync `authentik` and `authentik-outpost` in ArgoCD.
2. Wait for both applications to become `Synced` and `Healthy`.
3. Check `authentik-server`, `authentik-worker`, and `ak-outpost-traefik` pods, run `ak migrate --check` and `ak healthcheck`, and inspect startup logs. This deployment uses PostgreSQL and has no Authentik Redis component.
4. Verify login at `auth.pablomarelli.dev`.
5. Verify Traefik forward-auth on a protected route.
6. Verify Grafana OAuth login.
7. Only then continue to the next hop.

## Known Release-Note Hazards

- `2024.6` requires PostgreSQL 14 or later. This cluster runs PostgreSQL 16, so the requirement is already satisfied.
- `2024.8` changes source property mappings and can make OAuth/SAML sources sync groups by default when group claims are present.
- `2024.8` and later explicitly warn that outposts should match the Authentik instance version.
- `2024.12` requires an impersonation reason by default and deprecates `AUTHENTIK_POSTGRESQL__USE_PGBOUNCER` / `AUTHENTIK_POSTGRESQL__USE_PGPOOL`. This repo does not set those variables today.
- `2025.4` moves sessions to the database and changes reputation score limits. Expect active sessions to be invalidated during the rolling upgrade.
- `2025.6` upgrades default embedded PostgreSQL/Redis chart dependencies, but this repo disables the embedded PostgreSQL chart and pins Redis image values explicitly.
- `2026.5` changes the default listen address from `0.0.0.0` to `[::]`. IPv4-only environments might need explicit listen settings before syncing.
- `2026.5` reduces worker memory usage with a Rust worker entrypoint and includes security backports. Watch worker startup and health checks after syncing.
- `2026.8` rewrites the server entrypoint and proxy outpost in Rust and strictly enforces trusted proxy networks for forwarded headers. The default trusted networks include our `10.42.x.x` pod addresses; verify HTTPS issuer/redirect behavior through Traefik. The `hash_password` command now reads passwords interactively or from stdin; WebAuthn's duplicate-device option is removed. No custom connection-pooler options are configured here.

## Rollback after a database migration

Do not simply downgrade images against the migrated database. Quiesce all Authentik components through GitOps, preserve a failed-state dump, and restore the matching pre-upgrade **Authentik database only**, using its existing database role and secret key. Do not restore or replace the shared PostgreSQL volume, which also contains Umami. Restore chart/server/worker/outpost versions together, then repeat migration, login and integration checks. The October backup contains a quiesced dump plus a separately restore-tested preflight dump; a full production rollback has not been rehearsed.
