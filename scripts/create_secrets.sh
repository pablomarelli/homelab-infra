#!/bin/bash

POSTGRES_PASSWORD=$(openssl rand -base64 24)
AUTHENTIK_DB_PASSWORD=$(openssl rand -base64 24)
UMAMI_DB_PASSWORD=$(openssl rand -base64 24)

echo "POSTGRES_PASSWORD: $POSTGRES_PASSWORD"
echo "AUTHENTIK_DB_PASSWORD: $AUTHENTIK_DB_PASSWORD"
echo "UMAMI_DB_PASSWORD: $UMAMI_DB_PASSWORD"

kubectl create secret generic postgresql-credentials \
  --from-literal=POSTGRES_PASSWORD=$POSTGRES_PASSWORD \
  --from-literal=AUTHENTIK_DB_PASSWORD=$AUTHENTIK_DB_PASSWORD \
  --from-literal=UMAMI_DB_PASSWORD=$UMAMI_DB_PASSWORD \
  --namespace monitoring \
  --dry-run=client -o yaml | kubeseal --format yaml > ~/homelab/homelab-infra/manifests/postgresql/postgresql-credentials.sealed.yaml
