# Argo CD Upgrade Runbook

Argo CD is bootstrapped from `bootstrap/argocd/install.yaml`. That file is an upstream-generated manifest, so do not hand-edit embedded component images such as Redis or Dex.

## Upgrade Strategy

Update Argo CD by replacing the whole generated manifest with the official manifest for the target Argo CD release.

This preserves Argo CD's tested dependency set:

- The `quay.io/argoproj/argocd` image tag comes from the selected Argo CD release.
- The `ghcr.io/dexidp/dex` image tag comes from the selected Argo CD release.
- The `public.ecr.aws/docker/library/redis` image tag comes from the selected Argo CD release.

If one of those embedded dependencies looks old, verify upstream first. Do not override it unless we intentionally create and maintain a separate overlay.

## Before Upgrading

1. Read the target release notes and the matching upgrade guide.
2. Confirm Argo CD is healthy.
3. Confirm all critical Applications are `Synced` and `Healthy`.
4. Save the current target version and the new target version in the PR or commit message.

## Update The Manifest

Replace the file from upstream. The version must be the exact Git tag, including the leading `v`:

```bash
VERSION=v3.4.2
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
kubectl apply -n argocd --server-side --force-conflicts -f bootstrap/argocd/install.yaml
kubectl rollout status deployment/argocd-server -n argocd --timeout=180s
kubectl rollout status deployment/argocd-repo-server -n argocd --timeout=180s
kubectl rollout status statefulset/argocd-application-controller -n argocd --timeout=180s
```

## After Upgrading

1. Confirm Argo CD UI and CLI login still work.
2. Confirm repo-server can render Helm and Kustomize applications.
3. Confirm app-of-apps reconciliation still works.
4. Check for unexpected `OutOfSync`, `Degraded`, or `Missing` health changes.

## Rollback

Rollback means replacing `bootstrap/argocd/install.yaml` with the previous official release manifest and applying it manually again. Do not roll back only selected embedded images.
