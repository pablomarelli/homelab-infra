#!/bin/bash

# Get the umami password from postgresql-credentials
   UMAMI_PASS=$(kubectl get secret postgresql-credentials -n monitoring -o jsonpath='{.data.UMAMI_DB_PASSWORD}' | base64 -d)

echo "UMAMI_PASS: $UMAMI_PASS"
  
# Create secret with DATABASE_URL
kubectl create secret generic umami-secrets \
  --namespace=monitoring \
  --dry-run=client \
  --from-literal=DATABASE_URL="postgresql://umami:${UMAMI_PASS}@postgresql.monitoring.svc.cluster.local:5432/umami" \
  -o yaml | kubeseal --controller-namespace=kube-system --format=yaml > manifests/umami/umami-secrets.sealed.yaml
