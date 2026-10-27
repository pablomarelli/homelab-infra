# Argo CD Upgrade Runbook

Argo CD is bootstrapped from `bootstrap/argocd/install.yaml`. That file is an upstream-generated manifest, so do not hand-edit embedded component images such as Redis or Dex.

## Upgrade Strategy

Update Argo CD by replacing the whole generated manifest with the official manifest for the target Argo CD release.

This preserves Argo CD's tested dependency set:

- The `quay.io/argoproj/argocd` image tag comes from the selected Argo CD release.
- The `ghcr.io/dexidp/dex` image tag comes from the selected Argo CD release.
- The `public.ecr.aws/docker/library/redis` image tag comes from the selected Argo CD release.

If one of those embedded dependencies looks old, verify upstream first. Do not override it unless we intentionally create and maintain a separate overlay.

Apply through `bootstrap/argocd/kustomization.yaml`. It excludes the empty upstream notification ConfigMap and Secret because the `argocd-notifications` Application and External Secrets own those resources. Applying the raw install manifest can empty the notification Secret during apply-ownership migration, even when server-side dry-run appears to preserve it. The upstream-generated file remains unmodified.

## Before Upgrading

1. Read the target release notes and the matching upgrade guide.
2. Confirm Argo CD is healthy.
3. Confirm all critical Applications are `Synced` and `Healthy`.
4. Save the current target version and the new target version in the PR or commit message.

## Update The Manifest

Replace the file from upstream. The version must be the exact Git tag, including the leading `v`:

```bash
VERSION=v3.5.6
curl -fsSL \
  "https://raw.githubusercontent.com/argoproj/argo-cd/${VERSION}/manifests/install.yaml" \
  -o bootstrap/argocd/install.yaml
```

If this returns `404`, the tag is wrong or unpublished. Check the release tag before changing the manifest.

Then verify the embedded images:

```bash
rg 'image: (quay.io/argoproj/argocd|ghcr.io/dexidp/dex|public.ecr.aws/docker/library/redis)' bootstrap/argocd/install.yaml
```

## Apply The Upgrade

Argo CD is the GitOps controller, so this bootstrap manifest is applied manually:

```bash
kubectl apply -n argocd --server-side --force-conflicts --dry-run=server -k bootstrap/argocd
kubectl apply -n argocd --server-side --force-conflicts -k bootstrap/argocd
kubectl rollout status deployment/argocd-server -n argocd --timeout=180s
kubectl rollout status deployment/argocd-repo-server -n argocd --timeout=180s
kubectl rollout status statefulset/argocd-application-controller -n argocd --timeout=180s
```

## After Upgrading

1. Confirm Argo CD UI and CLI login still work.
2. Confirm repo-server can render Helm and Kustomize applications.
3. Confirm app-of-apps reconciliation still works.
4. Check for unexpected `OutOfSync`, `Degraded`, or `Missing` health changes.
5. Verify the notification ConfigMap and Secret retain their data and the ExternalSecret is Ready. If recovering from a raw-manifest apply, force reconciliation and verify delivery:
   ```bash
   kubectl annotate externalsecret argocd-notifications-secret -n argocd \
     force-sync="$(date +%s)" --overwrite
   ```
   Inspect notification HTTP outcomes: the notification CLI can exit zero after a delivery error. Keep verbose logs private because they include webhook credentials.

## Rollback

Rollback means replacing `bootstrap/argocd/install.yaml` with the previous official release manifest and applying `-k bootstrap/argocd` manually again, preserving the notification exclusions. Do not roll back only selected embedded images.
