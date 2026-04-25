# Authentik Upgrade Runbook

Authentik must be upgraded in release-train hops, not directly from `2024.2.2` to the current release. Keep the Helm chart and the external Traefik outpost image on the same version at every hop.

## Current Hop

The repo is prepared for the second hop:

| Component | From | To |
|---|---:|---:|
| `apps/authentik.yaml` chart | `2024.4.2` | `2024.6.4` |
| `manifests/authentik-outpost/outpost-deployment.yaml` image | `2024.4.2` | `2024.6.4` |

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

## Before Each Hop

1. Confirm ArgoCD is healthy and the repo is clean.
2. Confirm a recent PostgreSQL backup exists on the `pg-backups` PVC.
3. If the latest scheduled backup is too old, create a one-off backup job from the CronJob before changing the Authentik version.
4. Read the target release notes and handle manual-action items before syncing.
5. Update both `apps/authentik.yaml` and `manifests/authentik-outpost/outpost-deployment.yaml` together.

## After Each Hop

1. Sync `authentik` and `authentik-outpost` in ArgoCD.
2. Wait for both applications to become `Synced` and `Healthy`.
3. Check `authentik-server`, `authentik-worker`, Redis, and `ak-outpost-traefik` pods.
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
