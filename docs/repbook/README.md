# Activate and operate Repbook

The private deployment is registered in `apps/repbook.yaml`. The namespace is
declared in `bootstrap/namespaces.yaml`. The public route remains parked in
`activation/ingressroute.yaml`; DNS is not enabled yet.

The bundle plans one server on port 8000 with one retained local SQLite
directory. Registry access uses an ESO-managed `repbook-ghcr` secret sourced
from the existing `Family Manager GHCR` vault item.

Initial release: `a3ebc56ec1b23a3925935c88026d116f66c2da99`.
Image: `ghcr.io/pablomarelli/workout-tracker:0.1.0-a3ebc56ec1b23a3925935c88026d116f66c2da99`.
Registry index digest: `sha256:89b1e0dbc565238e7e613b0bb23da3c9387ce2740a65fa7ca4e53c3c1a5c8da7`.
Authenticated registry inspection confirmed Linux/AMD64 support. The node's
`/srv/repbook/data` directory was created with owner `10001:10001` and mode `0700`.

## Check the configuration

Run these commands from the repository root with Python 3.12 or later and uv.
The script pins PyYAML in its PEP 723 dependency metadata.

```sh
uv run --script scripts/check-repbook.py
uv run --no-project --with PyYAML==6.0.3 --with pytest python -m pytest -q tests/workout-tracker/test_check_repbook.py
```

The read-only check validates the resource references, SQLite restrictions,
runtime restrictions, private registration, and vault-managed pull secret. It inspects all checked-in
Application sources in `apps/`, including HTTPS and SSH repository URLs.
It rejects local Helm, Kustomize, and plugin sources that it cannot inspect.
It also rejects Jsonnet files and symlinks inside local source directories.
It rejects unexpected Repbook references outside the canonical deployment and
namespace. It checks decoded YAML and JSON values, including Helm
values without resource metadata. For checked-in Terraform files, it removes
comments and decodes quoted string escapes. It does not evaluate Terraform
expressions or remote plans. It does not render unrelated charts or inspect
remote repositories, live Applications, or manual cluster changes.

A passing check is static configuration evidence only. It does not prove image
publication, image pull access, cluster admission, storage health, trusted TLS,
backups, or physical iPhone behavior. The `--staged` option tests historical
inactive fixtures. The default checks the private deployment.

## Publish a checked release before activation

Follow [Adding a Service](../04-adding-a-service.md) for shared pipeline ownership.
Complete these release-system changes outside this PR.

1. Merge the shared `uv-pnpm` support in `homelab-workflows`. It reads the
   `pyproject.toml` version and preserves application-owned CI. Use the shared
   injector rather than editing its generated deployment workflow.
2. Preserve the app's backend, frontend, container, and browser checks. Require
   those checks for the exact release revision, including any version commit,
   before publication. Local uncommitted app work is not part of a remote release.
3. Register `workout-tracker` in the shared workflow project matrix. Configure
   the injector's `REPOS_TOKEN`, and the application's `NODE_AUTH_TOKEN`,
   `INFRA_REPO_TOKEN`, and `APP_NAMESPACE=repbook` through the
   approved secret and variable stores. Publishing needs `GITHUB_TOKEN` with
   `packages: write`. Never put credentials in this repository.
4. Set the app repository variable `DEPLOY_ENABLED=false` **before** the initial
   workflow injection. Injection can trigger a main-branch release. Verify that
   the selected shared workflow respects this variable.
5. Inject the supported workflow without replacing app checks. A successful
   same-repository main-push **CI** run triggers publication of that exact
   revision. Keep infrastructure updates disabled throughout initial publication
   and private activation. Rerun CI to retry publication.
6. Verify that the exact checked image was pushed and is pullable from the
   cluster's execution environment. Verify its operating system and CPU
   architecture against the selected node. Record the release revision, image
   tag, and resolved digest in the activation review. A plausible GHCR tag or a
   successful local build is not publication evidence.
7. If the package is private, arrange an External Secrets Operator (ESO) managed
   pull secret in namespace `repbook`. Add the matching `imagePullSecrets`
   reference in the activation PR. A public Git repository does not make its
   container package public.

Keep `manifests/workout-tracker/deployment.yaml` at this path. The shared updater
derives the directory from the source repository name, `workout-tracker`.
Kubernetes resource names and the namespace use the product name, `repbook`.
CPU and memory values are initial, unmeasured defaults from the Family Manager
backend example. They are not measured production requirements.

## Activate privately in a later approved PR

Do not combine this step with public exposure.

1. Inspect the live ArgoCD Application sources for watchers of the staged
   directories or their ancestors. Check both single-source and multi-source
   Applications. Resolve any unexpected watcher before proceeding.
2. Replace the sentinel with the exact verified release image. Keep one replica,
   one server process, and `Recreate` updates. Do not add autoscaling or another
   writer to the SQLite directory. `ReadWriteOnce` alone does not prevent two
   Pods on the same node from writing.
3. Consume `activation/namespace.yaml` into `bootstrap/namespaces.yaml`. Remove
   the parked namespace file in the same PR. Create the namespace through the
   approved bootstrap procedure before the first application sync.
4. On `pablo-ideapad-l340-17irh-gaming`, inspect `/srv/repbook/data` first. If the
   directory is new, create it with owner `10001:10001` and mode `0700`. Preserve
   existing contents. Do not overwrite a database, WAL file, or prior backup.
   If importing data, stop its old writer and take a consistent backup first.
5. Confirm that this node has `homelab/power=battery-backed` and enough free disk
   space. The local persistent volume (PV) binds only to this node. Its 10 GiB
   capacity is scheduling metadata, not a directory quota or disk reservation.
6. Move `activation/application.yaml` to `apps/repbook.yaml`. Leave the public
   IngressRoute parked and leave DNS unchanged. After approval, let ArgoCD
   reconcile the private deployment. Confirm image pull, volume binding,
   readiness, and restart persistence without opening a public route.
7. Configure Authentik and confirm that External Secrets has synchronized the
   provider credentials before testing login. New installations create regular
   accounts on first permitted OIDC login. For existing accounts, follow the
   application's `docs/oidc.md` migration guide and run `backend.link_identity`
   from a trusted terminal. Email matching alone never transfers existing data.

## Authentik configuration

Match Family Manager's native OIDC pattern, without forward-auth middleware:

- Application slug: `repbook`.
- Confidential authorization-code provider with PKCE and RSA/RS256 signing.
- Exact redirect: `https://repbook.pablomarelli.dev/auth/callback`.
- Per-provider issuer: `https://auth.pablomarelli.dev/application/o/repbook/`.
- Stable subject identifier; enable `openid`, `profile`, and `email` scopes.
- Email is contact information, not an account-linking identifier. The default
  Authentik `email` scope with `email_verified=false` is supported. Keep encryption disabled.
- Restrict application access to the intended Authentik group before exposure.
- Store `client-id` and `client-secret` in the `Repbook OIDC` item in the
  `homelab-secrets` vault. The staged ExternalSecret creates `repbook-oidc`.

The app needs outbound HTTPS to discovery, token, and signing-key endpoints.
The current network policy restricts ingress only. App sessions last one hour.
Logout revokes the app session, not Authentik SSO. Removing Authentik access
blocks future logins but does not immediately revoke existing app sessions or
erase offline device data. No back-channel logout is implemented.

The private rollout does not establish browser login over plain HTTP.
`WORKOUT_PUBLIC_ORIGIN` remains `https://repbook.pablomarelli.dev`, and cookies
remain secure. Any private browser acceptance test needs trusted HTTPS and this
same origin. A plain HTTP port-forward is not an equivalent authentication test.

## Expose the approved deployment

Use a separate approved exposure change after provider configuration and private checks.

1. Move `activation/ingressroute.yaml` into `manifests/workout-tracker/`.
2. Add `repbook` to the canonical `subdomains` list in
   `infrastructure/tofu/variables.tf`. DNS apply and deployment each need separate
   approval. Do not modify the shared Traefik routes for this app.
3. Verify trusted external HTTPS through the existing Cloudflare tunnel and
   Traefik `web` entrypoint. Route the whole host to the same Service on port
   8000. The frontend and API must share one origin. Keep
   `WORKOUT_PUBLIC_ORIGIN=https://repbook.pablomarelli.dev` and
   `WORKOUT_SECURE_COOKIE=true`.
4. Disable edge caching for `/api/*` and `/auth/*`. Do not enable permissive cross-origin
   access. Use perimeter rate limits and access controls appropriate for a
   personal service. The app's process-local login limit is not a perimeter
   control. Native Authentik OIDC owns login and callback handling; do not add
   forward-auth middleware or enable password login on this deployment.
5. Test login, logout, secure cookies, rejection of cross-origin mutations,
   account separation, restart persistence, and synchronization on the exact
   deployed image. Local container and WebKit results do not replace these
   production checks.
6. After the first deployment is verified, enable later shared infrastructure
   updates with `DEPLOY_ENABLED=true` under the release policy.

## Protect data and test recovery

Mount the whole `/app/data` directory. SQLite writes its database and
write-ahead log (WAL) files there. Do not copy only a live `workouts.db` file.
Use `backend.backup` for a consistent snapshot that includes committed WAL data.
Choose a new destination name for every run. For example, replace `UNIQUE` before
running this command.

```sh
kubectl -n repbook exec deployment/repbook -- python -m backend.backup /app/data/backups/workouts-UNIQUE.db
```

The backup command refuses to replace an existing file. Schedule backups and
protected off-node copying externally. No backup scheduler is installed here.
Restrict access to snapshots as strictly as the live database. They contain
accounts, password hashes, sessions, and training records. Monitor node disk
usage, free space, backup failures, and off-node copy age.

The PV uses `Retain`. Both the PV and persistent volume claim (PVC) disable
ArgoCD pruning and deletion. Retention is not protection against node loss,
disk loss, operator deletion, or database corruption. The local PV does not
provide failover to another node.

Before storing irreplaceable data, test a restore in a separate private location.
Obtain approval for the following maintenance sequence before production
restoration or schema-incompatible rollback. Do not treat a live scale-to-zero
command as a stop procedure. ArgoCD self-heal can restore the Git replica count.

1. Set `DEPLOY_ENABLED=false` to disable shared release infrastructure updates.
   Inspect in-flight release runs. Cancel them or wait for them to finish, then
   verify that no queued or running job can update the infrastructure revision.
   A variable change does not stop a run that already read the previous value.
2. Commit an approved maintenance desired state in Git. In `apps/repbook.yaml`,
   remove `spec.syncPolicy.automated` to disable child auto-sync and self-heal.
   Set the Deployment's `spec.replicas` to `0` in
   `manifests/workout-tracker/deployment.yaml`. Preserve the current image and
   storage definitions in this maintenance revision.
3. Verify that the parent `app-of-apps` Application has reconciled the approved
   maintenance revision and that the live child Application has no automated
   policy. A live child-only policy edit can be restored by the parent. If a
   manual parent sync is needed, sync only the approved maintenance revision.
   Inspect and finish or cancel any in-flight child sync before proceeding.
4. Explicitly sync the child to only the approved maintenance revision if needed
   to apply zero replicas. Verify that the Deployment has zero desired and live
   replicas and that all Repbook Pods have terminated. Verify that no backup job,
   administrative process, or other writer has the data directory open.
5. Freeze Git changes and pause Repbook reconciliation during the restore.
   Keep Git fixed at the approved maintenance state. Keep child auto-sync and
   self-heal disabled. Prevent parent or manual syncs from applying any other
   revision. Keep shared release updates disabled. Verify these controls again
   before touching storage.
6. Preserve the original directory and retained PV and PVC. Restore a snapshot
   as `workouts.db` into a fresh directory with owner `10001:10001`. Use an
   approved storage change to select the restored copy. Do not delete or recreate
   the retained PV to force a rollout. Run the snapshot's matching image against
   the fresh data in isolation, without public exposure. Verify account login,
   records, and synchronization before use.
7. Stop the isolated recovery writer. Commit the approved restored storage,
   matching image, and replica count in Git while child automation stays off.
   Reconcile the parent policy and explicitly sync the child to only this
   approved recovery revision. Verify one writer, volume binding, readiness,
   restart persistence, login, records, and synchronization.
8. After these checks pass, restore the approved child automated policy in Git
   and verify that the parent has reconciled it. Resume shared release updates
   with `DEPLOY_ENABLED=true` only after Git and the live image and replica count
   agree. Preserve the original storage until recovery acceptance is complete.

Take a consistent backup before each upgrade. Roll back only the image when it
supports the current schema, using an approved Git revision. Otherwise, follow
the maintenance sequence with the pre-upgrade snapshot and its matching image.
Restoration loses writes made since the snapshot.

Removing the Application does not reliably stop workloads because pruning is
disabled. Do not use Application deletion to stop writers.

## Install and verify on an iPhone

No iPhone-specific frontend change is needed for deployment.

1. Open `https://repbook.pablomarelli.dev` in Safari after public HTTPS acceptance.
2. Choose **Share > Add to Home Screen**. Enable **Open as Web App** where shown.
3. Launch the installed app and sign in. Safari and the installed app can have
   separate storage and sessions.
4. Keep the installed app online until it reports **Ready for offline training**.
5. On a physical iPhone, test offline reload, workout edits, app closure, and
   foreground reconnection. Confirm that another signed-in device receives the
   changes. Browser WebKit emulation is not physical-device acceptance.

Keep the origin stable. Browser storage belongs to that origin. iOS background
synchronization is not guaranteed. Open the app and let it synchronize before
relying on another device's latest data.
