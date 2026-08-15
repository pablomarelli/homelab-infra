#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

python3 - "$ROOT_DIR" <<'PY'
import pathlib
import re
import sys

import yaml

root = pathlib.Path(sys.argv[1])
manifest_path = root / "manifests/traefik/dotfiles-redirect.yaml"
tofu_vars = root / "infrastructure/tofu/variables.tf"
app = root / "apps/traefik-config.yaml"

docs = [doc for doc in yaml.safe_load_all(manifest_path.read_text()) if doc]

def find(kind, name):
    matches = [
        doc
        for doc in docs
        if doc.get("kind") == kind and doc.get("metadata", {}).get("name") == name
    ]
    if len(matches) != 1:
        raise AssertionError(f"expected exactly one {kind}/{name}, found {len(matches)}")
    return matches[0]

middleware = find("Middleware", "dotfiles-install-redirect")
redirect = middleware["spec"]["redirectRegex"]
assert redirect["regex"] == r"^https?://dotfiles\.pablomarelli\.dev/?$"
assert redirect["replacement"] == "https://raw.githubusercontent.com/pablomarelli/dotfiles/main/install.sh"
assert redirect["permanent"] is False

service = find("Service", "dotfiles-redirect-sink")
assert service["spec"]["type"] == "ExternalName"
assert service["spec"]["externalName"] == "example.invalid"
ports = service["spec"]["ports"]
assert ports == [{"name": "http", "port": 80, "targetPort": 80}]

route = find("IngressRoute", "dotfiles-install")
routes = route["spec"]["routes"]
assert len(routes) == 1
route_spec = routes[0]
assert route_spec["match"] == "Host(`dotfiles.pablomarelli.dev`)"
assert route_spec["kind"] == "Rule"
assert route_spec["middlewares"] == [{"name": "dotfiles-install-redirect", "namespace": "monitoring"}]
assert route_spec["services"] == [{"name": "dotfiles-redirect-sink", "port": 80}]

assert '"dotfiles"' in tofu_vars.read_text()
assert "path: manifests/traefik" in app.read_text()

for path in (root / "manifests/traefik").glob("*.yaml"):
    if "noop@internal" in path.read_text():
        raise AssertionError(f"dotfiles redirect must not use noop@internal: {path}")

print("dotfiles redirect contract ok")
PY
