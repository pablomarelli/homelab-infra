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
