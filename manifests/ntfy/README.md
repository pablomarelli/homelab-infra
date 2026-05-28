# ntfy Secrets

This deployment uses External Secrets Operator to read ntfy credentials from the
`homelab-secrets` 1Password vault. Do not commit real credentials or tokens.

Create two bcrypt password hashes and two ntfy tokens:

```bash
docker run --rm -it binwiederhier/ntfy:v2.14.0 user hash
docker run --rm binwiederhier/ntfy:v2.14.0 token generate
```

Store these fields in the 1Password item named `ntfy` in the `homelab-secrets`
vault. The ExternalSecret uses 1Password SDK references in the format
`<item>/<field>`, so `ntfy/NTFY_AUTH_USERS` means item `ntfy`, field
`NTFY_AUTH_USERS`.

```text
NTFY_AUTH_USERS=ntfy-publisher:<publisher-bcrypt-hash>:user,ntfy-subscriber:<subscriber-bcrypt-hash>:user
NTFY_AUTH_TOKENS=ntfy-publisher:<publisher-token>:Scripts and OpenCode,ntfy-subscriber:<subscriber-token>:Devices
```

The committed ACL grants `ntfy-publisher` write-only access to all topics and
`ntfy-subscriber` read-only access to all topics. Anonymous access is denied by
`NTFY_AUTH_DEFAULT_ACCESS=deny-all`.

If you use the 1Password CLI, create the item like this:

```bash
op item create \
  --vault homelab-secrets \
  --category secure-note \
  --title ntfy \
  'NTFY_AUTH_USERS=ntfy-publisher:<publisher-bcrypt-hash>:user,ntfy-subscriber:<subscriber-bcrypt-hash>:user' \
  'NTFY_AUTH_TOKENS=ntfy-publisher:<publisher-token>:Scripts and OpenCode,ntfy-subscriber:<subscriber-token>:Devices'
```
