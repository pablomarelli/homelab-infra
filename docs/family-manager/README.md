# Family Manager deployment

The ArgoCD applications are defined in `apps/family-manager.yaml` and run in
namespace `family-manager`. Both source repositories and container packages must
stay private. This public repository contains only deployment configuration and
references to secrets.

The shared release pipeline publishes checked semantic image tags. Set
`DEPLOY_ENABLED=true` in each application repository after verifying the first
deployment to enable later infrastructure image updates.

The local data directory `/srv/family-manager/data` on the battery-backed node
must have owner `10001:10001` and mode `0700`. Preserve existing data. If importing
a previous database, stop its writer and take a backup first. Do not copy only
the `.db` file from a live writer.

The backend uses one replica and `Recreate` updates because SQLite uses a local
disk. The PV has `Retain` policy and is excluded from ArgoCD pruning/deletion.
Its 10 GiB capacity is scheduling metadata, not a directory quota. Monitor disk
usage. `/api/` and `/auth/` go directly to the backend; all other paths serve the
frontend. Native OIDC replaces forward-auth middleware for this application.

## Authentik configuration

- Application slug: `family-manager`.
- OAuth2/OIDC provider: confidential client, authorization code flow.
- Exact redirect: `https://family.pablomarelli.dev/auth/callback`.
- Issuer mode: per-provider, giving
  `https://auth.pablomarelli.dev/application/o/family-manager/`.
- Select an asymmetric signing key, such as RSA/RS256. Keep encryption disabled.
- Include `openid` and `profile` scope mappings. Use a stable subject mapping;
  do not use email or a changeable username as the subject identifier.
- Restrict application access to a group containing the intended two accounts.
  Configure this group in Authentik, not in Git. Authentication does not itself
  grant access to a household.
- Allow the backend to reach discovery, token, and signing-key endpoints over
  HTTPS. Interactive Cloudflare challenges on these endpoints break OIDC.

The application uses one-hour local sessions by default. Local sign-out revokes
the current Family Manager session, not the Authentik SSO session. Authentik
disable/logout does not revoke existing local sessions immediately. For immediate
removal, use `admin disable-user` or `admin revoke` in addition to changing
Authentik access. Back-channel logout and refresh tokens are not implemented.

## Secret references

Create these items in the existing `homelab-secrets` 1Password vault:

| Item | Fields | Use |
| --- | --- | --- |
| `Family Manager OIDC` | `client-id`, `client-secret` | Authentik confidential client |
| `Family Manager GHCR` | `dockerconfigjson` | Complete Docker config JSON with a read-only credential for both private GHCR packages |

External Secrets creates `family-manager-oidc` and the
`kubernetes.io/dockerconfigjson` secret `family-manager-ghcr`. Both deployments
reference the latter. Do not commit a Kubernetes Secret, token, credential-bearing
URL, kubeconfig, database, session, email address, or user/subject ID. The public
hostnames, namespace, image names, and 1Password item/field names are configuration,
not credential values. Restart the backend after rotating its OIDC environment
secret; existing local sessions remain valid until expiration or explicit removal.

## Grant access

Each person signs in with their own Authentik account first. The frontend shows
their local account ID while membership is pending. From a trusted terminal:

```sh
kubectl -n family-manager exec deployment/family-manager-backend -- /server admin users
kubectl -n family-manager exec deployment/family-manager-backend -- /server admin grant --user '<first-local-user-id>' --household default --role owner
kubectl -n family-manager exec deployment/family-manager-backend -- /server admin grant --user '<second-local-user-id>' --household default --role owner
```

These are local administrative operations, not public HTTP endpoints. Membership
changes take effect on the next request. Both users access the same default
household. Existing schema-v1 data is migrated into that household without
granting anyone access. Keep command output and real account IDs out of this repo.

## Backups, verification, and rollback

`BACKUP_DIR=/data/backups` enables a consistent SQLite snapshot at startup and
every 24 hours, retaining seven successful snapshots. This protects against
application mistakes, not loss of the node or disk. Configure protected off-node
copying before storing irreplaceable data. Backups contain records and sessions;
restrict access as strictly as the live database.

Before first production use, restore a snapshot to a separate private directory
and run the application against it without exposing it publicly. Confirm both
users see the same data and an unrelated account sees no household data. Test
logout, restart persistence, record creation, and immediate membership revocation.

Schema-v2 upgrades are transactional. A v1 binary cannot read a v2 database.
For rollback across that migration, stop all writers and restore the pre-upgrade
backup with the matching old image. This loses writes made after that backup;
prefer a forward fix where possible. Do not delete or recreate the retained PV.
