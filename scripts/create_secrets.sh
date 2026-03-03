#!/bin/bash

UMAMI_PASS=$(kubectl get secret postgresql-credentials -n monitoring -o jsonpath='{.data.UMAMI_DB_PASSWORD}' | base64 -d)
UMAMI_PASS_ENCODED=$(python3 -c "import urllib.parse; print(urllib.parse.quote('$UMAMI_PASS', safe=''))")

echo "UMAMI_PASS_ENCODED: $UMAMI_PASS_ENCODED"

# Create new sealed secret with encoded password
kubectl create secret generic umami-secrets \
  --namespace=monitoring \
  --dry-run=client \
  --from-literal=DATABASE_URL="postgresql://umami:${UMAMI_PASS_ENCODED}@postgresql.monitoring.svc.cluster.local:5432/umami" \
  -o yaml | kubeseal --controller-namespace=kube-system --format=yaml > ~/homelab/homelab-infra/manifests/umami/umami-secrets.sealed.yaml
