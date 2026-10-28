# Cluster upgrade rollout - 2026-10-27

## Dozzle deployed - 2026-10-28; authenticated ingress check pending

- Upgraded `10.6.0 -> 11.3.5` in `e073ea1` after reviewing the intervening release notes, v11 session/authentication changes and exact-tag Kubernetes documentation/RBAC. This installation uses Authentik ForwardAuth rather than Dozzle's internal login, has no persistent application volume and is a read-only Kubernetes log viewer. Added only the documented `get` permissions for workload owners (apps deployments/replicasets/daemonsets/statefulsets and batch jobs/cronjobs). Workload patch remains denied. New optional kubelet disk/network statistics remain unavailable because nodes/stats access is not granted. No local data migration or database restore is required for image rollback.
- Server dry-run and rollout passed. Through a localhost-only port-forward, Playwright loaded v11.3.5, listed 52 containers across two hosts, opened `loki-0/loki` and displayed current streaming log lines. Browser console had zero errors/warnings. Screenshot evidence: `/home/pablo/.tmp/opencode/playwright-mcp/dozzle-upgrade-log-view.png`; private release/deployment evidence: `/home/pablo/.tmp/opencode/dozzle-upgrade-2026-10-28/`. Direct anonymous HTTP ingress returns 302 through the configured ForwardAuth middleware; post-upgrade authenticated ingress still needs the user's browser check.
- Disabled Kubernetes service-link environment injection because its automatically generated DOZZLE_* variables triggered unexpected-variable warnings; DNS-based service discovery and explicit application variables remain available. No Dozzle port-forward remained running after checks. Rollback is a reviewed image-pin revert while retaining compatible read-only RBAC and service-link setting.

## Alloy completed - 2026-10-28

- Upgraded chart `1.8.2 -> 1.14.3`, Alloy `1.16.1 -> 1.21.2`, and chart-managed config-reloader to digest-pinned `0.94.2` in `3cc04e1`. Reviewed intervening application release notes, chart release references, and the complete downloaded chart-template/default-value diff. New optional HPA, DNS, resize and command settings do not affect this DaemonSet; the reloader now uses a restricted security context. The 1.21 WAL stability restriction does not apply because loki.write WAL is not enabled. Removed Kafka/OTel/Windows/cloud-discovery settings and ServiceMonitor file access are not used here.
- Private evidence under `/home/pablo/.tmp/opencode/alloy-upgrade-2026-10-28/`: old DaemonSet/ConfigMap, per-node runtime-state archives with verified checksums, chart sources/diffs, releases, candidate configurations and ingestion responses. The rendered configuration initially matched the old one apart from a trailing newline and passed Alloy 1.21.2 `validate`; manifests passed server-side dry-run. Both DaemonSet pods rolled successfully and delivered fresh synthetic logs from their respective nodes.
- The rollout exposed a pre-existing durability problem: positions lived in the container's `/tmp/alloy`, so replacement containers reread old log files and Loki rejected stale batches with HTTP 400. Commit `ccd027d` moves storage to a per-node `/var/lib/alloy` hostPath. Created temporary node-pinned helpers, verified empty destination directories, copied current runtime state from each running Alloy, and then rolled the new mounts/storage path. The copy was not an atomic collector checkpoint; migration emitted a small number of additional stale-file rejections. Subsequent deliberate replacement of each node's Alloy pod preserved positions and produced no replay errors in the inspected post-restart window. This protects ordinary container/pod replacement, not node/disk loss, and does not make delivery exactly-once.
- End-to-end test also reproduced an existing level-normalization bug: input `error` became label `erroror` because replacement matched the substring `err`. Final expressions `^(err)$` and `^(warning)$` retain the capture groups required by stage.replace and match only complete aliases. The first anchored attempt omitted capture groups and failed the synthetic test; corrected in `70477d9`. Final probes on both nodes verified `err` and `error` both label as `error`, and `warning` and `warn` both label as `warn`, with all eight messages queryable through Loki. Both mounted configurations updated and config-reloader applied the changes.
- The existing top-level `resources` block was ignored by the chart (live Alloy resources were empty). Moved the intended 50m/64Mi requests and 200m/256Mi limits under `alloy.resources`; observed pre-change usage was 8-10m CPU and 61-67Mi memory per collector.
- Rollback uses a reviewed chart-version revert while retaining persistent state and the corrected level expressions; no backend database migration is involved. Runtime-state archives are recovery references, not a guarantee of gap-free replay.

## Loki completed - 2026-10-28

- Migrated from Grafana chart `7.0.0` / Loki `3.6.7` to the maintained OSS community chart `20.0.2` / Loki `3.7.9` in `159812a`. The original candidate, Grafana chart `7.5.0`, explicitly states that its repository now serves Enterprise Logs only. Reviewed the community migration guide, all chart-major transition notes through 20, and intervening application release notes. Sources: [community chart README](https://github.com/grafana-community/helm-charts/blob/loki-20.0.2/charts/loki/README.md), [Loki releases](https://github.com/grafana/loki/releases), and the exact-tag application upgrade guide.
- Renamed deployment mode to Monolithic, removed obsolete selfMonitoring values, and moved the existing intended canary-disable setting to its supported top-level key. The previously ineffective nested key had left a canary running; it is now pruned. Enterprise, MinIO, ephemeral volumes, Cilium policies, legacy read targets and chart-provided monitoring rules are not used. Kept filesystem storage, TSDB/v13 schema, schema start date, PVC name/size, release/service names and scheduling unchanged. The new chart also updates Memcached/exporter and rule sidecar images. Loki 3.7.9 includes WAL ordering/recovery and security fixes; removed Promtail and operator-specific features are not used by this deployment.
- Preflight found a dangerous live `Delete/Delete` PVC retention policy. Commit `c4340f2` changed both scale/delete actions to Retain, and the PVC's owner references cleared before shutdown. The old chart forces one filesystem replica despite a zero replica value, so `bb918e8` did not stop Loki. Commit `171970b` instead paused Application auto-sync; verified the pause, manually scaled to zero, and waited for Pod deletion. The final upgrade restores automatic pruning/self-healing and one replica. Live retention remains Retain/Retain.
- Private recovery directory: `/home/pablo/.tmp/opencode/loki-upgrade-2026-10-28/`. Saved configuration, StatefulSet and PVC identity, fixed historical query/results, chart artifacts and release notes. The 4.9 GiB cold `loki-cold.tar` was indexed and all entries in `BACKUP-SHA256SUMS` passed verification. Loki was unavailable from approximately 14:38 until 15:16 UTC during backup, restore rehearsal and rollout. Alloy retries do not establish gap-free ingestion across this outage; no claim of zero log loss is made.
- Extracted the archive into a private rehearsal directory and started Loki 3.7.9 on an isolated internal Docker network, using the same filesystem/schema paths with local ring and caches disabled. Readiness passed and a fixed historical query returned exactly the same 20 log lines across seven streams as production before shutdown. The actual candidate configuration passed `-verify-config=true`; full candidate manifests passed server-side dry-run under the Argo field manager without StatefulSet recreation.
- Production verification: Loki and both caches rolled out successfully; buildinfo reports 3.7.9; the original PVC UID and bound volume remain unchanged; the fixed historical query exactly matches again. A synthetic Pod's JSON message traversed the existing Alloy file collection/processing pipeline and appeared in Loki with expected namespace, pod, node and level labels. WAL checkpoint/segment recovery completed with errors=false. Startup cache DNS/ring errors occurred while endpoints were coming up; subsequent metrics show one server for each configured cache. All 22 Applications are Synced/Healthy. Removed the synthetic/backup Pods and rehearsal container/network; retained recovery files.
- Rollback: first pause Loki auto-sync and verify Retain/Retain and absent PVC owner references, then stop the StatefulSet. Preserve a new copy of current data before restoring the cold archive to the original PVC with original ownership. Restore the former chart repository/version and compatible values through a reviewed commit, preserving the fixed retention policy; do not assume changing the image alone reverses storage changes. Re-enable auto-sync only after restoration and repeat historical/ingestion checks. Restoration loses writes after the backup; the isolated restore/read test is not a full cluster disaster-recovery rehearsal.

## Monitoring stack deployed - 2026-10-28; browser confirmation pending

- Candidate chart `85.3.3 -> 92.14.0`: operator/config-reloader `0.90.1 -> 0.94.2`, Prometheus `3.11.3 -> 3.15.1`, Alertmanager `0.32.1 -> 0.34.1`, kube-state-metrics `2.19.0 -> 2.20.0`, node-exporter `1.11.1 -> 1.12.1`. Override the chart's Grafana `13.2.4-distroless` with `13.2.5-distroless` for its additional security fixes, staying on the chart's Grafana minor line.
- Reviewed every major transition in the exact-tag chart UPGRADE.md (86 through 92), operator 0.91-0.94.2, Prometheus 3.12-3.15.1, Alertmanager 0.33-0.34.1, Grafana 13.1/13.2 release/patch notes, and exporter release notes. Four chart majors update CRDs; chart 90 replaces filesystem scrape credentials with a chart-managed service-account-token Secret and ConfigMap CA; 92 adds Linux node selectors. Both nodes run Linux, monitors use the release namespace, and no removed credential overrides are set.
- Grafana subchart 13 introduces a read-only root and distroless runtime, while subchart 14 validates values with JSON Schema. No shell entrypoint hooks, `GF_*__FILE`, legacy plugin-install variable or extra `/tmp` mount is configured. Grafana 13.1 removes core Azure/SigV4 Prometheus auth and Zipkin; neither is used here. No removed compressed-alert-state feature flag is configured. Prometheus experimental storage encodings are not enabled. Alertmanager custom routing/inhibition resources pass validation against candidate CRDs.
- Private recovery artifacts and downloaded releases/charts are under `/home/pablo/.tmp/opencode/monitoring-upgrade-2026-10-28/`. Saved live CRDs, monitoring custom resources, Secrets/ConfigMaps, workloads/PVC identities, target/alert baseline and silences. A SQLite online backup of Grafana passed integrity_check. Candidate Grafana started against its copy on an isolated Docker network, returned database=ok/version=13.2.5, and retained both users and four data sources; both databases passed integrity_check. The legacy dashboard table contains zero entries, so this count alone does not verify Grafana's newer dashboard storage.
- Full chart dry-run passed using the existing `argocd-controller` field manager and excluding Helm test hooks. A generic field manager incorrectly retained both old GOMEMLIMIT valueFrom and new literal value; matching the real manager resolves that dry-run artifact. Added RespectIgnoreDifferences so configured Grafana credential exclusions are respected during sync. Applied the ten candidate CRDs ahead of the controller upgrade.
- Existing storage-alert regression tests pass with Prometheus 3.15.1 after exporting the live rule spec as their documented fixture. All 226 existing alert/recording rules pass parser validation. Default duplicate-name lint flags four upstream API-server rules whose preserved `code` labels are disjoint (2xx/3xx/4xx/5xx); parser validation used `--lint=none` after inspecting those expressions.
- Quiesced Prometheus and Alertmanager through GitOps in `0827f04` for cold storage backups. Prometheus data is 5.6 GiB. The initial gzip transfer timed out; that invalid partial file was removed. The valid `prometheus-cold.tar` and `alertmanager-cold.tar` archives were indexed and passed SHA-256 verification along with every other entry in `BACKUP-SHA256SUMS`. Commit `79f696f` deployed the reviewed chart and restored both replicas. Metrics collection and alert delivery were paused for approximately 15-20 minutes; replacement pods started around 13:38 UTC.
- Post-rollout: all 18 targets are healthy, matching the 18-target healthy baseline; all 33 rule groups evaluate without errors. Historical `count(up offset 1h)` returns 18, both node inventory metrics return 2, and effective retention remains 15 days. All monitoring PVC UIDs and volume bindings are preserved. All 22 Argo CD Applications are Synced/Healthy, and the upgraded monitoring containers are ready with zero restarts. Operator and kube-state-metrics logs contained no error-level entries in the inspected post-rollout window.
- Grafana reports database=ok/version=13.2.5. A fresh online database backup passes integrity_check, preserves both users and their password hashes/salts, and retains four data sources. Unified storage contains all 30 original dashboard UIDs plus one additional dashboard. The Kubernetes admin-password Secret differed from its backup despite the ignore/sync setting; restored only that field from the private backup and verified it persisted after a hard refresh. The Secret UID and admin username were unchanged. The precise cause of the field change is not established. No database user password was reset; the pre-existing Secret credential returned HTTP 401 before this upgrade. Post-upgrade SSO and dashboard rendering still require user browser confirmation.
- Actual Alertmanager notification test: posted an isolated critical/warning pair named `MonitoringUpgradeVerification`. The warning was suppressed with a populated inhibitedBy list; the critical remained active. Discord notification count increased from 0 to 1 with every Discord failure counter at zero. Explicitly resolved both test alerts with HTTP 200 afterward. Human receipt confirmation remains pending. Removed the temporary backup Pod, Grafana rehearsal container/network and invalid partial archive; no monitoring port-forward remained running.

### Monitoring recovery

The private recovery directory above contains credentials and must remain access-controlled. Recovery requires an intentional monitoring outage: stop Grafana and set Prometheus/Alertmanager replicas to zero through GitOps before modifying their volumes. Preserve a fresh copy of current data first. Restore `grafana-before.db` and `grafana-files-before.tar.gz` to the Grafana volume with its original ownership; restore the cold tar contents to the corresponding stopped Prometheus/Alertmanager volumes. Revert chart/image values to the pre-upgrade versions using a new reviewed commit, retaining the credential ignore policy and restoring one replica only after data restoration. Reverting the image alone does not reverse database migrations. Do not blindly replace or delete CRDs: assess stored-version and schema compatibility with the old operator first, using `crds-before.json` as reference. Restoring backups loses metrics and state written after their capture; neither archive integrity nor the Grafana migration rehearsal constitutes a full disaster-recovery rehearsal.

## Authentik completed - 2026-10-28

The user subsequently confirmed all three requested browser checks: Authentik login, authenticated Dozzle access and Grafana SSO. This resolves the remaining verification item recorded below and permits the monitoring upgrade to proceed.

- Upgraded chart/server/worker and separately managed proxy from `2026.5.0` to `2026.8.5`. Reviewed official [2026.5](https://docs.goauthentik.io/releases/2026.5/) and [2026.8](https://docs.goauthentik.io/releases/2026.8/) release/patch notes, including security backports, migration fixes in 2026.8.3, proxy fixes in 2026.8.4 and certificate dependency updates in 2026.8.5. This is the next release train.
- Compatibility findings: Rust server/proxy rewrite and stricter trusted forwarded headers require route verification; default trusted CIDRs cover the direct Traefik pod address `10.42.0.160`. No deprecated PostgreSQL connection options or custom hash_password automation are configured. PostgreSQL 16.15 remains external to the chart. Candidate chart rendering and server dry-run passed.
- Private backups are under `/home/pablo/.tmp/opencode/authentik-upgrade-2026-10-28/`: preflight custom-format database dump, original secret key/configuration/Deployments, checksum manifest, and final `authentik-quiesced.dump` with separate checksum. Recovery files are outside Git.
- Restored the preflight dump into disposable PostgreSQL 16.15 on an internal Docker network with no outbound connectivity. Candidate server image digest was `sha256:602227a86455d6772e3d16b7d852713c4f864f40df5df894abd1285bb53979a5`. Migration and `migrate --check` passed; preserved counts were four users, four applications, four providers and fourteen flows immediately after migration. The isolated server passed readiness, login-page HTTP 200 and Grafana OIDC discovery with the correct public HTTPS issuer. HTTP tests used the container's private bridge address because the internal network did not publish its loopback port. Test containers, anonymous database volume and network were removed afterward.
- Quiesced all three production components through GitOps in `25e92e5`, waited for old pods to terminate, and took the final database backup. Deployed matching versions and restored replicas in `7187f57`. Both server and worker now use Recreate; stopping both explicitly avoided cross-Deployment mixed-version access during migration.
- Production `ak migrate --check` and worker `ak healthcheck` passed. All three pods Ready with zero restarts; four users/applications/providers preserved. There are fifteen flows after startup blueprint reconciliation, including `default-request`. Server logs were clean. Worker logged one startup healthcheck BrokenPipeError; outpost retried API retrieval while the server started, then connected its WebSocket and loaded all three proxy applications. A subsequent 60-second log window had zero errors for all three components.
- Public authentication page returned HTTP 200. Dozzle, status dashboard and media-share anonymous requests redirected to the HTTPS Authentik authorization endpoint. Grafana discovery returned its expected HTTPS issuer. An initial discovery check with an extra trailing slash returned 404 on both old and new versions; the canonical endpoint without that slash passed. All 22 ArgoCD Applications are Synced/Healthy.
- **Remaining verification:** real user login, authenticated ForwardAuth session, and Grafana OAuth callback. The public Grafana entry redirected to Cloudflare Access, so HTTP entry checks do not prove the full SSO flow. Do not advance to the monitoring upgrade until these checks are confirmed. Rollback requires restoring the matching Authentik-only database backup and all component versions together; see `docs/09-authentik-upgrade.md`.

## External Secrets completed - 2026-10-28

- Upgraded ArgoCD-managed chart and all three controller images `2.5.0 -> 2.14.0` through `apps/external-secrets.yaml` (implementation commit `1dfd19d`). ArgoCD operation Succeeded, revision 2.14.0 Synced/Healthy.
- Reviewed release notes for every intervening release 2.6.0 through 2.14.0 using the [official releases](https://github.com/external-secrets/external-secrets/releases), plus relevant 1Password PRs #6466, #6318 and #7130. Relevant changes include 1Password cache invalidation fixes and environment support; template/Secret-target validation and error sanitization security fixes; narrower cert-controller write permissions. The image-registry change in 2.11 was reverted in 2.12. No custom image registry, template functions, generic targets, PushSecrets or 1Password environments are used by our five ExternalSecrets.
- Compared old/new chart renderings and relevant CRD schemas. Existing mappings use direct `item/field` lookups, `external-secrets.io/v1`, Owner creation and Retain deletion. The existing vault/service-account configuration remains valid; SDK caching is not enabled. Candidate CRDs keep v1 storage and v1beta1 unserved; no API migration is required for our resources. New optional generators and policies do not change our configuration. Chart minimum Kubernetes version is 1.19; cluster is 1.36.5.
- Backed up controller deployments, controller Secrets, CRDs, ExternalSecrets, ClusterSecretStore and all five generated Secrets outside Git under `/home/pablo/.tmp/opencode/external-secrets-upgrade-2026-10-28/`. Saved both chart archives and rendered manifests. All backup/chart SHA-256 checks passed. Local Helm 3.20.2 was downloaded with its published checksum verified. Candidate full-chart server-side dry-run passed before the GitOps rollout.
- All three pods Ready with zero restarts. Fresh forced synchronization succeeded for each of the five ExternalSecrets at 12:58:11-12:58:28 UTC, with 1Password ClusterSecretStore Ready. All generated Secret UIDs and every data value matched the private pre-upgrade snapshot.
- Created a synthetic ExternalSecret mapping an existing Grafana OAuth client ID into an isolated test Secret. API admission, provider retrieval and exact value comparison passed; deleting the test ExternalSecret garbage-collected its Secret, with deletion verified. No 1Password items were modified. Controller, webhook and certificate-controller logs contained zero error/fatal/panic lines during verification. All 22 ArgoCD Applications remained Synced/Healthy.
- Rollback: revert `apps/external-secrets.yaml` to chart 2.5.0, push and reconcile through ArgoCD, then repeat rollout/provider checks. Preserve CRDs, custom resources and generated Secrets; do not uninstall the chart or delete CRDs. The pre-upgrade chart/resources are retained for recovery. This verified live reconciliation and backup integrity, not a replacement-cluster restore.

## Sealed Secrets completed - 2026-10-28

- Upgraded controller `0.27.3 -> 0.41.2` using `bootstrap/sealed-secrets`, with the upstream release URL pinned and image pinned to `sha256:e63ec6ec2b12a471bf781081bd370a93ca7b7b3999e5b9243341379aeb801d0b`. Docker pull and isolated `--version` execution confirmed the candidate; the downloaded kubeseal archive passed the published SHA-256 checksum.
- Reviewed intervening changes in the [exact-tag release notes](https://github.com/bitnami/sealed-secrets/blob/v0.41.2/RELEASE-NOTES.md): restricted template functions (0.30), scope consistency/rotation fixes (0.36), verification and rotation decryption-oracle fixes (0.39/0.40), Secret healing and dynamic key watching (0.41), and release-pipeline repairs (0.41.1/.2). No custom controller arguments are configured. Upstream manifest comparison showed unchanged RBAC, image replacement and CRD template-data documentation changes, plus resource reordering.
- Before deployment, backed up nine keys, six SealedSecrets, Deployment and CRD under `/home/pablo/.tmp/opencode/sealed-secrets-upgrade-2026-10-28/` with private permissions; all four backup checksums passed. Candidate kubeseal recovered every live SealedSecret offline, and every recovered data field matched its live Secret. Each target had its corresponding SealedSecret controller owner. No credential drift was found before enabling healing.
- Server dry-run and rollout passed. Controller reported 0.41.2, registered all nine existing keys and successfully reconciled all six old SealedSecrets. Live `kubeseal --validate` passed for every original resource, post-rollout credential comparisons matched, and key UIDs/data were preserved.
- A newly sealed random synthetic credential reconciled correctly. After deliberately changing its generated Secret, the controller restored the sealed value. The initial verification command rejected base64 padding in its JSONPath argument; a subsequent direct comparison against offline recovery confirmed healing. The synthetic SealedSecret and generated Secret were deleted and deletion verified.
- Controller pod Ready with zero restarts; both nodes Ready; all 22 ArgoCD Applications Synced/Healthy. All five ExternalSecrets and the 1Password ClusterSecretStore remained Ready. Forced notification ExternalSecret refresh completed at `2026-10-28T12:37:45Z`, proving continued provider access using the sealed bootstrap token.
- Bootstrap ownership is now explicit: this controller has no ArgoCD Application and is maintained through the pinned overlay from any authorized management machine. Recovery/rollback procedure is in `docs/05-secret-management.md`; private backups remain outside Git. Offline recovery was tested, not a full replacement-cluster restore.
- Follow-up disk check found no active DiskSpace alerts after the earlier npm/Docker build-cache cleanup.

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

Production rollout completed through GitOps in commit `9632344`, after taking a fresh online-safe archive at `/home/pablo/.tmp/opencode/cluster-upgrades-2026-10-27/kuma-final-pre-2.5.8.tar.gz`. Startup/readiness probes passed; SQLite integrity is `ok`; all 11 monitors, one notification configuration and two status pages remain. All nine active monitors produced new UP heartbeats after startup, and the public status page rendered "All Systems Operational" in the browser. Finance and Home Assistant monitors remain paused. Notification configuration was preserved, but an external notification delivery was not deliberately triggered.

For rollback, stop the application, retain the failed state, restore the complete pre-upgrade archive to the data PVC and revert to the old image before starting one replica. Heartbeats since the snapshot would be lost. The migration rehearsal and its test login never changed production credentials or monitor activity settings.

## ntfy: 2.14.0 to 2.34.0

Reviewed all published non-prerelease notes between the installed and target versions via the [upstream releases](https://github.com/binwiederhier/ntfy/releases), including the explicit upgrade notes for 2.20.0, 2.28.0, 2.31.0 and 2.31.1, and the target documentation for declarative users/tokens.

### Risks checked

- The existing installation uses SQLite cache/auth stores, declarative publisher/subscriber credentials, deny-all anonymous access and wildcard ACLs. PostgreSQL and experimental clustering changes are not enabled here.
- SQLite ACL matching becomes case-sensitive in 2.24.0; current wildcard rules retain their meaning.
- 2.20.0 takes ownership of attachment-directory cleanup. No attachment store is configured or present in the current data directory.
- 2.28.0 limits titles to 1 KB, combined tags to 512 bytes and cache replay to 10 MB per topic; heavy polling also consumes the attachment-bandwidth budget. Oversized custom publishers may now get HTTP 400/429, and custom replay consumers must honor truncation headers.
- 2.31.0 changes reconnect replay boundaries and custom clients may see duplicate message IDs. Standard ntfy clients deduplicate them.
- Cache schema migrates from 13 to 17; auth schema from 6 to 9. A rollback to 2.14.0 must restore both old databases rather than assume the later backward-compatibility behavior applies to the old binary.
- 2.34.0 fixes subscription authorization revocation; earlier releases also fix weak token randomness, template denial of service, web-push SSRF and web-app issues.
- Use Recreate for the SQLite migration and the newly available `/v1/ready` endpoint for readiness.

### Rehearsal

Created consistent online SQLite snapshots through a temporary read-only PVC helper and restored them into an isolated container with production resource limits and the same provisioning environment. Upstream mobile push was disabled in the rehearsal and its container network had no external route.

All migrations succeeded and both SQLite integrity checks passed. Three user rows (including the built-in row), two tokens and two ACL entries were preserved. All 54 cached messages were preserved before adding two test messages.

Functional checks passed using the existing provisioned tokens: anonymous read/write denied, publisher read denied, subscriber write denied, invalid token denied, authorized publish accepted, authenticated cache replay succeeds, and a live streaming subscriber receives a new publish. Test code reports only outcomes, not credentials.

Pre-upgrade archive: `/home/pablo/.tmp/opencode/cluster-upgrades-2026-10-27/ntfy-pre-2.34.0.tar.gz`.

Candidate image digest: `sha256:901e14503d3f605f445be0e68f2ac71f0aa73391897ce6ceb599f8c48d8b3792`.

Production rollout completed through GitOps in commit `fdc2b92`. Automatic synchronization was temporarily disabled, ntfy was stopped, and both databases were snapshotted before the new image was published. Automatic synchronization was restored afterwards.

Final backup: `/home/pablo/.tmp/opencode/cluster-upgrades-2026-10-27/ntfy-final-pre-2.34.0.tar.gz`; SHA256 `8aaa3c5ff1dc72641f6fdee8df6a40049a6c1fa02ff465aa66e7040b9990751c`.

Production verification passed:

- Startup logs confirm all seven schema steps completed; cache schema is 17 and auth schema is 9.
- Both SQLite integrity checks return `ok`; user, token and ACL counts remain unchanged.
- All eight permission, authentication, publish, cache replay and live-streaming checks passed through the public HTTPS endpoint and Cloudflare Tunnel using the existing publisher/subscriber tokens.
- Two synthetic messages were published to dedicated topic `upgrade-verification-1793129454026`, without Firebase forwarding. Mobile push receipt was not independently verified.

The temporary cluster backup helper, rehearsal containers/networks, unpacked database copies and local credential environment file were removed. Restricted backup archives are retained outside Git. Recovery requires stopping ntfy, retaining failed state, restoring both pre-upgrade databases together, reverting the image in Git, and verifying permissions/delivery before restoring automatic sync.

## First security batch complete

Umami 3.4.1, Uptime Kuma 2.5.8 and ntfy 2.34.0 were individually reviewed, rehearsed, deployed and verified. cloudflared 2026.10.5 was already deployed and its tunnel was verified. Remaining audit candidates have not been upgraded or fully migration-reviewed by this batch; the next platform work is K3s/Traefik, with a separate maintenance plan and datastore recovery check.

## K3s / Traefik: first-step preflight

Both nodes still report `v1.34.3+k3s1` and Ready. Rechecked the official channel service: the current stable destination is `v1.36.5+k3s1`, with intermediate candidates `v1.34.12+k3s1` and `v1.35.9+k3s1`. Upgrade the server first and then the agent at each step; do not skip Kubernetes minors.

The session runs on `homelab-desktop-01` as `pablo`. SSH to `pablo@192.168.100.3` now works with the desktop's dedicated `homelab-management` key. Privileged operations still require the user's interactive sudo session. The user confirmed SQLite and completed a stopped-server backup, then restarted K3s successfully. No version upgrade has run.

Recovery archive: `/home/pablo/k3s-backups/pre-upgrade.nqKbY684/state.tar.gz` on the server, copied to `/home/pablo/.tmp/opencode/k3s-upgrade-2026-10-27/pre-upgrade.nqKbY684/` on the desktop. Both copies have SHA256 `9d39f5181983968eeb77486b8728333bfed05e491ff67e3a402e3ec53ae49340`. The archive includes the server directory/token, node configuration, service unit/environment and installed binary. An extracted database copy passed `PRAGMA integrity_check` with 2,210 kine rows. This verifies archive transfer and database integrity, not a full disaster-recovery rehearsal. Both nodes were Ready and all 22 ArgoCD Applications Synced/Healthy after the backup restart.

### Initial compatibility findings

- Read K3s 1.34.4 through 1.34.12 release notes, the additional 1.34.3+k3s3 release (the k3s2 release endpoint returns 404), upstream Kubernetes 1.34.4 through 1.34.12 changes, and official manual-upgrade/backup guidance. The Kubernetes patch notes describe fixes rather than an API-removal migration. Later minor-version reviews and privileged host configuration checks remain pending.
- All three selected K3s releases bundle Traefik 3.7.13, not the previously identified security target 3.7.16. The packaged upgrade alone does not finish the ingress security update.
- The current packaged Traefik chart is `37.1.1+up37.1.0`, with image 3.5.1 and no HelmChartConfig override. The selected K3s releases move to chart 40.x, whose ingress-nginx provider key changes from `kubernetesIngressNginx` to `kubernetesIngressNGINX`.
- The running Traefik enables Kubernetes CRD and Ingress providers, not Ingress-NGINX or Gateway API, so that provider-key rename does not affect the observed configuration.
- Read Traefik's minor-version migration guidance. Relevant verification includes Authentik ForwardAuth and forwarded HTTPS headers, request path handling, CRD/chart compatibility, and long-lived streams. The configured middleware already sets `trustForwardHeader: true`; that field is deprecated but still supported in the candidate branch.
- Prefer updating the binary with checksum verification and retaining the installed service configuration. Re-running the K3s installer without the original environment/arguments can lose configuration.
- Downloaded the exact amd64 candidate and matched its published SHA256; its version output is `v1.34.12+k3s1 (47b47499)`, Go `go1.26.8`. Artifacts are staged outside Git under `/home/pablo/.tmp/opencode/k3s-upgrade-2026-10-27/` and are not installed.
- Target source manifest specifies separate Traefik/CRD charts `40.1.5+up40.1.0`, `failurePolicy: retry`, and `forceConflicts: true`. Both chart archives were downloaded for inspection. Reviewed chart major releases 38, 39 and 40: CRDs must be upgraded first; HTTP port options move under `http`; Service options move under `service.spec`; schema validation tightens. The target K3s manifest already moves `ipFamilyPolicy` to `service.spec`. There are no live HelmChartConfig overrides to translate. Chart rendering and CRD compatibility checks remain pending.

### Recovery and rollout prerequisites

The SQLite backup prerequisite is satisfied as recorded above. The user ran privileged `k3s check-config`: STATUS pass, cgroup v2 controllers good, required kernel features enabled, and no custom containerd v2/v3 templates. The kernel config was successfully read from `/boot` after the optional `configs` module lookup failed. Existing cluster CIDR routes are expected on this running node. Swap is active (4 GiB configured, about 1.6 GiB used); the live kubelet config explicitly has `failSwapOn: false`, `memorySwap: {}`, and systemd cgroups. Keep the existing host configuration for this patch step rather than changing memory management during the upgrade.

Rendered both exact packaged charts using Helm 3.19.4 with the target K3s values and Kubernetes 1.34.12 capabilities. Server-side dry-run accepted all 35 candidate CRDs; server dry-run accepted the rendered ServiceAccount, RBAC, Service, Deployment and IngressClass. These are admission/render checks, not a live ingress test; Helm/CRD reconciliation and route functionality must still be verified after restart.

The verified binary and checksum are staged on the server under `/home/pablo/k3s-upgrades/v1.34.12/`. SHA256: `ef1df26b26276c0f6d962391c94e12f9362d1f1e30ec7a7926e9ddb84b0d66ce`. Remote checksum and version checks passed. Next is the user's privileged atomic binary replacement and service restart, preserving the existing service configuration. No upgrade has been executed yet. Single-control-plane API interruption is expected; local PVC workloads cannot be assumed to reschedule to the other node.

After each server/agent step, verify node versions and readiness, pod health, DNS and service networking, persistent workloads, Helm reconciliation, public routes, protected-route redirects, analytics ingestion, ntfy streaming, status-page monitors and Argo CD reconciliation. Choose the Traefik security patch override only after inspecting the target chart and CRDs, then publish it declaratively through a HelmChartConfig.

Sources: [K3s channels](https://update.k3s.io/v1-release/channels), [manual upgrade](https://docs.k3s.io/upgrades/manual), [backup/restore](https://docs.k3s.io/datastore/backup-restore), [K3s releases](https://github.com/k3s-io/k3s/releases), [Traefik minor migrations](https://doc.traefik.io/traefik/migrate/v3/).

### Control-plane 1.34.12 rollout

The user completed the checksum-verified atomic binary replacement and restarted `k3s`. Live checks confirm the server is Ready on `v1.34.12+k3s1`, containerd `2.2.7-k3s1`; the worker remains Ready on `v1.34.3+k3s1` pending its own step.

- API `/readyz` returns `ok`. Both Traefik Helm install jobs completed. Traefik, CoreDNS, metrics-server and local-path-provisioner rollouts succeeded; node metrics are available.
- Initial readiness transitions during restart cleared; every non-completed pod's reported containers were ready at the follow-up check.
- Public portfolio, collector heartbeat, Kuma public status and ntfy readiness returned HTTP 200. ArgoCD, Grafana and Authentik returned redirects. Protected Kuma dashboard redirects to Authentik with an HTTPS callback; authenticated browser login remains untested.
- A real portfolio browser visit with query `upgrade_check=k3s-server-1.34.12-20261027` produced a confirmed database pageview. DNS from the worker's Umami pod resolves the control-plane PostgreSQL service.
- All eight ntfy permission/publish/cache/stream checks passed through public HTTPS; two test messages were written to topic `upgrade-verification-1793135206574`. The temporary credential file was removed.
- All nine active Kuma monitors reported UP with fresh post-Traefik-rollout heartbeats.
- Traefik logs revealed two stale routes pointing at removed Finance Manager/Home Assistant services. Commented those routes out in Git to complete their requested disablement; route manifest server dry-run passed.
- Traefik 3.7.13 logs also warn about unset alias-header policy, legacy resource naming and unlimited ForwardAuth response bodies. These require review in the separate ingress security update; the packaged upgrade is not the completed Traefik security patch.

Worker preflight from the API confirms systemd cgroups and `failSwapOn: false`; its agent service is active with no drop-ins. A syntax-checked privileged script is staged outside Git at `/home/pablo/.tmp/opencode/k3s-upgrade-2026-10-27/upgrade-worker-1.34.12.sh`. It checks the hostname/version, runs host checks, stops if custom containerd templates exist, backs up the installed binary and configuration, verifies the new binary checksum, atomically replaces it and restarts only `k3s-agent`. It has not been executed yet.

### Worker 1.34.12 rollout and completed patch step

The user subsequently executed the worker script successfully. Host checks passed, both binary checksums matched, and `k3s-agent` restarted at 21:08:59 UTC. The script created `/home/pablo/k3s-backups/worker-pre-1.34.12.bfLlDumL/config-and-binary.tar.gz` with the old binary and configuration. Its archive listing was validated by the script; an independent restore rehearsal was not performed.

Post-upgrade checks:

- Both nodes are Ready on `v1.34.12+k3s1` and containerd `2.2.7-k3s1`; API readiness returns `ok`, and node metrics are available.
- All 22 ArgoCD Applications are Synced/Healthy. No non-completed pod was non-Running or had a reported unready container. Umami, Kuma and ntfy retain zero restarts.
- A newly created Alpine verification pod on the worker completed successfully, resolving Kubernetes service DNS and fetching Umami's service heartbeat. The pod was deleted afterwards. This exercises new container creation and networking after the runtime upgrade, not just surviving old containers.
- Portfolio, collector heartbeat, public status and ntfy readiness all return HTTP 200.
- The portfolio browser visit `upgrade_check=k3s-worker-1.34.12-20261027` was confirmed as one pageview in PostgreSQL.
- All eight ntfy authorization, publish, replay and streaming checks passed again, using topic `upgrade-verification-1793135396267`; the temporary credential file was removed.
- All nine active Kuma monitors have UP heartbeats later than the worker restart.
- GitOps pruned both disabled-app IngressRoutes; all 22 Applications remained healthy after that cleanup.

The 1.34 patch step is complete. The later 1.35 and 1.36 minor upgrades and separate Traefik security patch remain pending their respective reviews, backups and verification.

### 1.35 preflight started

Reviewed Kubernetes 1.35 urgent upgrade notes, API changes and patch notes through 1.35.9, plus K3s 1.35.0 through 1.35.9 k3s1 release notes. Additional k3s revision notes and final configuration compatibility checks remain pending.

- Kubernetes 1.35 defaults to refusing cgroup v1; both hosts already use cgroup v2.
- The kubelet `pod-infra-container-image` flag was removed. A privileged pre-backup check will stop if that string or custom feature gates appear in the server's K3s configuration/service files. Worker configuration needs the corresponding check before its upgrade.
- StorageVersionMigration v1alpha1 is removed; the live API discovery has no storagemigration resources. There are no live ResourceSlices affected by the partitionable-device alpha API change.
- Image credential verification becomes beta/default-on. No current pods declare imagePullSecrets; private registry/node credentials still need consideration when testing new pod creation.
- The target patch includes fixes disabling the initial 1.35 SchedulerAsyncAPICalls and MaxUnavailableStatefulSet regressions by default.
- The target component table lists the same containerd 2.2.7, Traefik 3.7.13, CoreDNS 1.14.7 and local-path 0.0.37 as the completed patch step; helm-controller changes to 0.17.9.
- Downloaded and checksum-verified amd64 `v1.35.9+k3s1 (58877f27)` outside Git. It is not installed.
- The system kubectl is 1.37.1 and reports unsupported client skew against 1.34; use a version-matched bundled client for subsequent upgrade checks.

A syntax-checked backup-only script is staged on the server at `/home/pablo/k3s-upgrades/pre-1.35-backup.sh`. It checks the current version and flagged configuration, stops K3s to archive the current server state/token/configuration/binary, then restarts it. Await the user's execution, off-node archive copy and SQLite integrity check before installing 1.35.

### 1.35 server backup verified and upgrade staged

The user executed the pre-backup script successfully: no removed kubelet flag or custom feature-gate string was found in the checked server configuration/service files. The stopped-server backup is `/home/pablo/k3s-backups/pre-1.35.KSGccRhD/state.tar.gz`, copied to the desktop's upgrade workspace. SHA256 matches on both machines: `c471a33fb65074428a83c91eff6afb1f211693df5fa79cacc4f84e416ecc856f`. An extracted database copy passed SQLite integrity checking and contains 3,842 kine rows. Both nodes and all 22 Applications are healthy after the backup restart.

Completed the additional K3s `v1.35.0+k3s3` release review, whose notes cover changes since k3s1. Compared exact target/current Traefik manifests: they are identical, including chart `40.1.5+up40.1.0` and image 3.7.13. The earlier chart migration is already exercised by the completed 1.34 patch step. Server-first upgrade leaves the 1.34 worker within the supported older-kubelet skew; upgrade and verify that worker before considering 1.36.

Bundled 1.34 kubectl with the management kubeconfig now works for checks, avoiding the system 1.37 client's unsupported skew. The 1.35.9 binary was copied to `/home/pablo/k3s-upgrades/v1.35.9/` and its remote checksum/version verified: SHA256 `897acb21cca57d477a211102251a6591450ce767344a9faaa121a1007ca9fa9a`, version `v1.35.9+k3s1 (58877f27)`.

The syntax-checked `upgrade-server.sh` in that directory verifies host/current version, cgroup v2, the exact recovery archive hash and candidate binary hash, then atomically replaces the binary and restarts K3s without rewriting its service configuration. Await user execution and full rollout verification. Recovery from a failed minor upgrade must account for datastore changes: retain failed state and use the matching pre-1.35 state/configuration/binary backup rather than assume a binary-only downgrade is supported.

### 1.35 server rollout verified

The user executed the server upgrade successfully. Live verification confirms the control plane Ready on `v1.35.9+k3s1`; the worker remains Ready on `v1.34.12+k3s1`. API readiness returns `ok`, all non-completed pods report Running with their reported containers ready, all 22 Applications are Synced/Healthy, Helm jobs remain successful, and node metrics are available.

A new verification pod scheduled onto the control-plane node completed DNS resolution and fetched the worker-hosted Umami heartbeat through its ClusterIP, then was removed. Public portfolio, collector heartbeat, Kuma status and ntfy readiness returned HTTP 200; the protected dashboard returned HTTP 302. The real browser pageview `upgrade_check=k3s-server-1.35.9-20261027` was confirmed in PostgreSQL. All eight ntfy authorization/publish/replay/stream checks passed using topic `upgrade-verification-1793136379061`; temporary credentials were removed. All nine active Kuma monitors reported UP. Traefik's brief API-watch failures coincided with server startup; a subsequent 30-second log window was empty.

The worker upgrade script is syntax-checked and staged at `/home/pablo/.tmp/opencode/k3s-upgrade-2026-10-27/v1.35.9/upgrade-worker.sh`. It stops on removed kubelet flags/custom feature gates or containerd templates, checks cgroup v2 and the installed version, creates a fresh configuration/binary backup, verifies the candidate, then restarts the agent after atomic replacement. Worker execution and verification remain pending.

### 1.35 worker rollout verified

The user executed the worker script successfully; its configuration checks passed, checksums matched, and the worker configuration/binary backup was created at `/home/pablo/k3s-backups/worker-pre-1.35.KRTUf35E/`. The agent restarted at 21:36:03 UTC.

- Both nodes now report Ready on `v1.35.9+k3s1`, with containerd `2.2.7-k3s1`. API readiness and node metrics work.
- All 22 Applications are Synced/Healthy. All non-completed pods were Running with reported containers ready.
- A newly scheduled worker verification pod, using the existing non-UPS taint toleration, resolved service DNS and reached both control-plane ntfy readiness and worker Umami heartbeat through ClusterIP services. It completed successfully and was removed.
- A real portfolio browser visit with query `upgrade_check=k3s-worker-1.35.9-20261027` produced one confirmed PostgreSQL pageview.
- All eight public ntfy permissions/publish/cache/stream checks passed using topic `upgrade-verification-1793136999076`. The temporary credential file was removed.
- Public Kuma status and analytics heartbeat returned HTTP 200; all nine active monitors reported UP.

The 1.35 minor step is complete. The 1.36 review and a fresh pre-minor server backup are next; the separate Traefik security patch remains pending.

### 1.36 preflight started

Read Kubernetes 1.36 urgent notes, deprecations/API changes and patch notes through 1.36.5, plus K3s releases 1.36.0 through 1.36.5. The target fixes early 1.36 kubelet memory-leak and server-side-apply regressions. The runtime moves from containerd 2.2.7 to 2.3.4-k3s1.36; its additional compatibility review remains pending before installation.

Deployment-specific checks:

- No running pod uses gitRepo, flexVolume or Portworx volumes; all current PVs use local storage. The removed gitRepo plugin and Portworx migration therefore do not affect the observed storage configuration.
- No ResourceClaims or ResourceSlices exist. Scheduling API discovery exposes only PriorityClass, not the removed alpha Workload API. DRA granular RBAC and alpha scheduling API migration are not applicable to these observed resources.
- No repository YAML/JSON references or live monitoring ConfigMap/PrometheusRule references were found for renamed `volume_operation_total_errors` or `etcd_bookmark_counts` metrics.
- No live Service externalIPs/loadBalancerSourceRanges or NetworkPolicy IP blocks were found in the targeted strict-IP/CIDR validation check. This is not an exhaustive check of every possible API field.
- Existing hosts already use cgroup v2. The backup script stops if custom containerd templates or custom control-plane component arguments/feature gates are found, for review before upgrade.
- Downloaded the exact amd64 target, matched its published SHA256, and verified version `v1.36.5+k3s1 (3dd98cc5)`, Go 1.26.8. No installation has occurred.

The syntax-checked backup-only script `/home/pablo/k3s-upgrades/pre-1.36-backup.sh` is staged on the server. Await its execution, an off-node copy and SQLite integrity verification before replacing the 1.35 binary.

### 1.36 backup verified and server upgrade staged

The user completed the backup script; its custom-containerd-template and component-argument checks passed. Backup `/home/pablo/k3s-backups/pre-1.36.zQruOPSK/state.tar.gz` was copied to the desktop workspace. Its SHA256 matches: `fb48f12c2809cf78f33d37bd8ee8107ed7c0713aec2838cb7724577a0d65bf84`. The extracted SQLite copy passed integrity checking with 2,447 kine rows. Both nodes remain Ready on 1.35.9 and all 22 Applications remain Synced/Healthy after restart.

Read containerd 2.3.0 through 2.3.4 release notes. Relevant changes include plugin configuration migration on load, shim bootstrap changes, security/teardown fixes, NRI plugin naming/interface changes, and disabling experimental checkpoint restoration through CreateContainer by default. The rollout uses ordinary container creation, not checkpoint restore. No custom containerd templates were found on the server; the upgrade script additionally stops for nonempty standard NRI plugin/configuration directories. Post-upgrade verification must exercise new pod creation, DNS/cross-node networking, storage-backed applications and metrics rather than rely only on surviving containers.

The exact 1.36.5 Traefik manifest matches the already-tested chart/image configuration (`40.1.5+up40.1.0`, 3.7.13). Candidate binary copied to `/home/pablo/k3s-upgrades/v1.36.5/`, with remote checksum/version checks passing: SHA256 `d73847bcd3c5fccef0115b372e2f9a91f3032dc84bbf71518a4617565294d313`, version `v1.36.5+k3s1 (3dd98cc5)`.

The syntax-checked `upgrade-server.sh` in that directory validates the host, current version, recovery archive and binary, atomically replaces K3s and restarts its existing service. Await user execution and server verification before preparing the worker step. The matching pre-1.36 backup is the recovery baseline; do not assume a binary-only minor downgrade restores datastore/runtime state.

### 1.36 server rollout verified

The user completed the server upgrade. The control-plane node is Ready on `v1.36.5+k3s1` with containerd `2.3.4-k3s1.36`; the worker remains Ready on 1.35.9. API readiness returns `ok`, all 22 Applications are Synced/Healthy, Helm jobs are successful, and all non-completed pods were Running with reported containers ready.

A newly scheduled verification pod on the server passed DNS, local ntfy readiness and cross-node Umami service checks under the new runtime, then was deleted. Public status, analytics heartbeat and ntfy readiness returned HTTP 200; protected dashboard returned 302. The real portfolio pageview `upgrade_check=k3s-server-1.36.5-20261027` was confirmed in PostgreSQL. All eight ntfy permission/publish/replay/stream checks passed using topic `upgrade-verification-1793137666146`; temporary credentials were removed. All active Kuma monitors report UP. Node metrics initially showed unknown server values during restart, then recovered on both nodes; metrics-server logs show a transient kubelet connection refusal during startup.

Worker upgrade script staged and syntax-checked at `/home/pablo/.tmp/opencode/k3s-upgrade-2026-10-27/v1.36.5/upgrade-worker.sh`. It validates version/cgroups/configuration, stops for custom containerd templates or standard NRI plugin configuration, makes a fresh worker configuration/binary backup, verifies the candidate and atomically replaces K3s before restarting the agent. User execution and final two-node verification remain pending.

### K3s stable target reached: both nodes on 1.36.5

The user completed the worker upgrade, with configuration checks and binary checksums passing. Worker configuration/binary backup: `/home/pablo/k3s-backups/worker-pre-1.36.NaHkNG9r/`. The agent restarted at 21:50:20 UTC.

- Both nodes are Ready on `v1.36.5+k3s1`, containerd `2.3.4-k3s1.36`. API readiness returns `ok`; all 22 ArgoCD Applications are Synced/Healthy and all non-completed pods were Running with reported containers ready.
- A newly scheduled worker pod passed DNS and both local Umami and cross-node ntfy ClusterIP requests under containerd 2.3, then was removed.
- A real browser pageview `upgrade_check=k3s-worker-1.36.5-20261027` was confirmed in PostgreSQL. Public status, collector heartbeat and ntfy readiness returned HTTP 200; the protected dashboard returned 302.
- All eight ntfy permission, publish, replay and streaming checks passed using topic `upgrade-verification-1793137854948`. Temporary credentials were removed.
- Worker metrics briefly showed unknown during startup, then both nodes reported CPU/memory successfully. All 12 PVCs remain Bound. Umami, Kuma and ntfy retain zero pod restarts.
- All nine active Kuma monitors report UP.

The planned K3s sequence (1.34 patch, then 1.35 and 1.36, server before worker each time) is complete and verified. Recovery archives remain outside Git. The separate Traefik 3.7.13 to 3.7.16 security update and configuration warnings still require their own reviewed GitOps change and verification.

## Traefik 3.7.13 to 3.7.16

### Review and preflight

Read release notes for [3.7.14](https://github.com/traefik/traefik/releases/tag/v3.7.14), [3.7.15](https://github.com/traefik/traefik/releases/tag/v3.7.15), [3.7.16](https://github.com/traefik/traefik/releases/tag/v3.7.16), their 12 linked security advisories, and the migration guide from the exact target source tag.

- 3.7.15 rejects all CONNECT requests with 501. This installation is a reverse proxy; ordinary HTTP and WebSocket upgrades must still be tested.
- Ingress-NGINX naming/authentication changes and Gateway API precedence/backend-protocol changes do not affect the enabled providers: this installation uses Kubernetes CRD and Ingress only.
- OTLP exponential histogram changes do not affect the configured Prometheus exporter.
- 3.7.16 fixes ForwardAuth connection-bound NTLM/Negotiate identity leakage. The configured auth endpoint is Authentik's proxy outpost, not an identified NTLM/Kerberos backend. This review does not claim the specific exploit was demonstrated here; authentication redirects and denied anonymous access remain verification requirements.
- FastProxy is not enabled. No new optional CRD fields are introduced by this change; the existing chart/CRDs stay at the K3s-packaged 40.1.5+up40.1.0.

Pulled official `docker.io/library/traefik:v3.7.16`, verified the executable reports 3.7.16 (Go 1.26.10), and pinned manifest digest `sha256:1336e85aaed293bd63d005086e0dd013b04078b26aaeb1c18b26a2f928af7e65` in `manifests/traefik/helm-chart-config.yaml`. A HelmChartConfig named traefik in kube-system is reconciled by the existing traefik-config ArgoCD Application; it preserves the image selection across K3s restarts/upgrades.

Rendered the exact installed chart with packaged values plus the override. The sole rendered difference is the container image. Both HelmChartConfig and rendered resources passed server dry-run. Deployment strategy is RollingUpdate with maxUnavailable 0/maxSurge 1. Captured pre-change HelmChart and Deployment/Service configuration outside Git under `/home/pablo/.tmp/opencode/traefik-upgrade-2026-10-27/`.

Rollback: revert the Git change adding the HelmChartConfig, allow ArgoCD pruning and K3s Helm reconciliation to restore the packaged 3.7.13 image, then verify ingress. This restores the earlier vulnerabilities as well and is only a recovery measure. No application database migration is involved.

### Production rollout verified

Deployed through GitOps in commit `ec87b48`; rollout began at 21:57:56 UTC. The live executable reports Traefik 3.7.16 and Go 1.26.10. Pod `traefik-8b75989cb-v57ld` is ready with zero restarts and the expected pinned image digest.

- All 22 ArgoCD Applications are Synced/Healthy. All nine active Kuma monitors have UP heartbeats after the rollout.
- Portfolio, public status, analytics collector heartbeat, ntfy readiness and share health returned HTTP 200. Protected status, Dozzle and share routes returned 302 to `auth.pablomarelli.dev`. ArgoCD, Grafana, Authentik, analytics and Forgejo returned HTTP 200 after redirects.
- The public Kuma WebSocket returned an Engine.IO handshake. A direct LAN CONNECT request to Traefik returned the expected 501.
- Real browser query `upgrade_check=traefik-3.7.16-20261027` produced exactly one confirmed PostgreSQL pageview.
- All eight ntfy permission, publish, replay and live-streaming checks passed with topic `upgrade-verification-1793138325518`. Temporary test credentials were removed.

Verification limits: full authenticated ForwardAuth sessions and production-user login were not exercised; redirects were verified. External Kuma notification delivery and ntfy mobile push receipt were not independently verified. Recovery configuration was captured, but rollback was not rehearsed in production.

Configuration-hardening follow-ups remain: unset `aliasHeadersStrategy`, implicit legacy `safeNaming`, unlimited ForwardAuth `maxResponseBodySize`, and encoded-path defaults. The image-only patch does not resolve these configuration warnings; changes require separate compatibility review and verification.

## PostgreSQL 16.14 to 16.15

### Review and recovery rehearsal

Reviewed the complete [16.15 release notes](https://www.postgresql.org/docs/release/16.15/), including security fixes and post-update requirements. Same-major upgrades do not require dump/restore. Live inventory confirms 16.14, no replication slots or shared preload libraries, and no btree_gist/ltree extensions requiring the documented reindex consideration. All three databases have zero invalid indexes. Authentik has only plpgsql; Umami also has pgcrypto 1.3. No PGP encryption/decryption references were found in either application's schema dump; this does not rule out dynamically issued SQL. The pgcrypto change rejects previously broken encryption with unsupported ciphers. Standard backup scripts use custom-format dumps, not intentionally failing COPY test scripts.

Fresh globals (including role credentials) and custom-format Authentik/Umami dumps are stored with restrictive permissions outside Git at `/home/pablo/.tmp/opencode/postgresql-upgrade-2026-10-27/`, with `SHA256SUMS`. These are on the desktop, separate from the database's battery-backed node. Treat this directory as sensitive recovery material.

Pulled `postgres:16.15-alpine`, digest `sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab`; executable reports 16.15. Restored globals and both complete databases with fail-on-error into a network-isolated Docker instance using temporary memory-backed storage. `pg_amcheck --heapallindexed` passed on both restored databases. Authentik has 215 application tables, four users and four applications; Umami has 27 tables, one website and one user. These key object counts match production, and both restored databases have zero invalid indexes.

Before rollout, all 22 Applications were Synced/Healthy; Authentik readiness and Umami collector heartbeat returned HTTP 200. Upgrade the Deployment and backup CronJob together. Existing Recreate strategy prevents concurrent servers opening the same data directory; expect a brief Authentik/Umami database interruption.

Recovery: for an image startup regression, stop the new server before reverting the image to 16.14 against the same major-version data directory, then verify database and application health. If data recovery is needed, stop dependent writers and restore globals and both dumps into a fresh PostgreSQL 16 instance before reconnecting applications; writes since the dumps would be lost. The logical restore was rehearsed on 16.15, not a production rollback.

### Production rollout and verification

GitOps commit `44b2cbc` upgraded both images. PostgreSQL 16.15 started at 22:06:49 UTC using the existing data directory without initialization or schema migration. The first SQL check caught a startup race: Kubernetes reported the container ready before PostgreSQL accepted connections because the Deployment had no readiness probe. Commit `15aa2db` adds a TCP-local `pg_isready` exec readiness check. After that rollout, the immediate SQL version check passed; the final pod started at 22:07:31 UTC and is ready with zero restarts.

- Both application roles authenticated over TCP with their existing credentials. Authentik still has four users, and both databases have zero invalid indexes.
- Authentik readiness, Umami heartbeat and the analytics UI returned HTTP 200. Protected status, Dozzle and share redirected to Authentik. Full user login/OAuth sessions were not exercised.
- Browser query `upgrade_check=postgresql-16.15-20261027` produced exactly one PostgreSQL pageview, confirming application writes after the final restart.
- Manual Job `pg-backup-1615-verification` ran the upgraded CronJob image successfully, writing both `20261027_220656` dumps to the backup PVC. The pre-upgrade dumps were fully restored and integrity-checked; the newly generated Job dumps were not separately restored.
- All 22 Applications were Synced/Healthy and all non-completed pods were Running with their reported containers ready.
- Kuma recorded the expected PostgreSQL interruption at 22:06:44 UTC and an UP check at 22:07:44 UTC; its parent group briefly retained the earlier DOWN state until the next group check. Final verification confirmed all nine active monitors UP with heartbeats after the final database restart.

The isolated rehearsal also passed an AES-256 pgcrypto encrypt/decrypt round trip. The rehearsal container and its memory-backed data were removed; the off-node recovery files remain and their SHA256 checks pass.

## Argo CD 3.4.2 to 3.5.6

### Review and preflight

Reviewed releases 3.4.3 through 3.4.6 and 3.5.0 through 3.5.6, the exact-tag [3.4-to-3.5 migration guide](https://github.com/argoproj/argo-cd/blob/v3.5.6/docs/operator-manual/upgrading/3.4-3.5.md), disaster-recovery instructions and all eight security advisories linked from 3.5.4. These cover Kustomize command execution, Jsonnet filesystem access, deletion-hook project restrictions, local-login rate limiting, SSH proxy command injection, extension RBAC and OCI manifest memory exhaustion. This review establishes affected version ranges, not exploitation in this cluster.

Compatibility findings:

- Candidate image includes Helm 4.2.1 and Kustomize 5.8.1. All five installed Helm charts (Alloy, Authentik, External Secrets, kube-prometheus-stack and Loki) rendered successfully using the candidate image, existing values and Kubernetes 1.36.5 capabilities. Live hard refresh remains required to verify Argo-specific multi-source rendering.
- All active Git/chart sources use HTTPS. No repository Secrets or plain-HTTP OCI sources were found, so the Helm 4 explicit plain-HTTP setting is not required. No Kustomization files were found in this repository.
- No custom UI extension init containers, impersonation configuration, project signature keys or repo-server mTLS Secret were found. React 19 extension rebuilding, Source Integrity migration and mTLS activation do not require changes for this deployment. Custom event-listing gRPC clients would need regeneration; none are identified in this infrastructure repository.
- Security patches reject Jsonnet imports outside the repository, ignore Kustomize Helm configHome and limit OCI manifests to 4 MiB. Existing sources do not depend on these behaviors.

Saved the exact old/new install manifests, namespace resource snapshot, workload/configuration snapshots and `argocd admin export` under `/home/pablo/.tmp/opencode/argocd-upgrade-2026-10-27/` with restrictive permissions. Export parses successfully and contains 22 Applications, one AppProject and the main Argo CD Secret; the additional namespace snapshot includes other Secrets/configuration. SHA256 checks pass. These files contain credentials and must stay outside Git. Export validation is not a disaster-recovery import rehearsal.

The existing manifest is byte-identical to upstream 3.4.2. The complete upstream 3.5.6 manifest passed server-side dry-run; projected data for every overlapping ConfigMap/Secret is unchanged, as are inspected Role/ClusterRole rules. Non-fatal last-applied annotation ownership migration warnings occurred for GitOps/External Secrets-managed resources; their actual configuration/secret data was preserved in dry-run.

The new dependency set is Argo CD 3.5.6, Dex 2.45.1 and Redis 8.2.3-alpine (unchanged upstream). Use the complete generated manifest without hand-editing embedded images. Rollback replaces install.yaml with the saved complete 3.4.2 manifest and applies the notification-preserving Kustomize overlay described below, then verifies controllers and reconciliation; reverting restores the old security exposure. Bootstrap is manually applied, independent of Argo CD itself or a particular management PC. All 22 Applications were Synced/Healthy before the change.

### Production rollout and verification

Commit `85f0333` replaced the complete upstream manifest and it was applied manually. All six Deployments and the application-controller StatefulSet completed rollout. Live Argo CD reports 3.5.6 and repo-server Helm reports 4.2.1. All seven pods are ready with zero restarts.

- Hard-refreshed all 22 Applications and waited for the refresh annotations to clear. All were Synced/Healthy with no error conditions, including app-of-apps and multi-source Helm applications.
- Through a loopback Kubernetes port-forward, the API reports 3.5.6, rejects anonymous application listing with 401, and accepts the existing admin credential. Authenticated API and matching-version CLI each list all 22 healthy applications. The test session was logged out.
- Authenticated manifest retrieval passed for app-of-apps (22 resources), Alloy (7), Authentik (9), External Secrets (42), kube-prometheus-stack (115), and Loki (16). The application-events REST endpoint also passed.
- The browser rendered the new login form through the local port-forward. A full browser login was not exercised; authenticated API/CLI access was tested. The public hostname redirects unauthenticated visitors to Cloudflare Access, so an HTTP 200 after following redirects alone does not verify the Argo CD UI. The Cloudflare-authenticated browser path remains untested.
- All nine active Kuma monitors have UP heartbeats after the rollout.

### Notification ownership issue found and corrected

Despite the dry-run preserving configuration, applying the raw upstream manifest emptied `argocd-notifications-secret`, which External Secrets owns. Notification-controller logs showed unresolved webhook references during this interval. Forced ExternalSecret reconciliation restored both values at 22:21:51 UTC. A value-by-value comparison confirmed all pre-existing ConfigMap/Secret data now matches the backup.

Commit `71914c6` adds `bootstrap/argocd/kustomization.yaml` to exclude upstream's empty notification ConfigMap/Secret placeholders, preserving their GitOps/External Secrets ownership without editing the generated file. Both installation and upgrade runbooks now apply `-k bootstrap/argocd`, including rollback. The overlay renders 57 resources, excludes both placeholders, passes server-side dry-run, and was reapplied successfully. Post-apply comparison confirmed every pre-existing ConfigMap/Secret value remains intact.

Actual webhook delivery checks found:

- `discord-infra`: HTTP 204, accepted by Discord.
- `discord-main`: HTTP 404 with Discord code 10015, `Unknown Webhook`. Its value is identical to the pre-upgrade backup, so replacing the stale webhook is separate follow-up work. Update the `discord-main-webhook-url` field in the 1Password `argocd-notifications` item, force ExternalSecret refresh and repeat delivery verification. Do not put the webhook URL in Git or chat.

The notification CLI exited zero even on the failed delivery; inspect the HTTP response/log outcome rather than relying on exit status. Logs contain sensitive webhook paths and are kept outside Git with restrictive permissions. Argo CD reconciliation and the upgrade are verified; main-channel notification delivery remains blocked on a valid replacement webhook.

### Notification follow-up resolved

The user replaced the webhook and restored the accidentally removed `discord-main-webhook-url` field in 1Password. Forced ExternalSecret reconciliation returned Ready. Both fields now contain the same webhook URL, targeting the user-confirmed `#notificaciones-infra` channel. Actual notification tests for both `discord-main` and `discord-infra` returned HTTP 204; response logs were checked rather than trusting the CLI exit code. The main-channel delivery blocker above is resolved. Both field names must remain present even when their values are identical.
