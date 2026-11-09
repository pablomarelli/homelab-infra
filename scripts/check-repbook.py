# /// script
# requires-python = ">=3.12"
# dependencies = ["PyYAML==6.0.3"]
# ///
"""Check Repbook deployment configuration without contacting a cluster."""

import argparse
import posixpath
import re
import sys
from collections.abc import Hashable
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import yaml

RUNTIME = "manifests/workout-tracker"
PARKED = "docs/repbook/activation"
FILES = {
    f"{RUNTIME}/deployment.yaml": ("Deployment",),
    f"{RUNTIME}/storage.yaml": (
        "StorageClass",
        "PersistentVolume",
        "PersistentVolumeClaim",
    ),
    f"{RUNTIME}/service.yaml": ("Service",),
    f"{RUNTIME}/network-policy.yaml": ("NetworkPolicy",),
    f"{RUNTIME}/oidc.external.yaml": ("ExternalSecret",),
    f"{PARKED}/application.yaml": ("Application",),
    f"{PARKED}/namespace.yaml": ("Namespace",),
    f"{PARKED}/ingressroute.yaml": ("IngressRoute",),
}
IDENTITIES = {
    "Deployment": ("apps/v1", "repbook", "repbook"),
    "StorageClass": ("storage.k8s.io/v1", "", "repbook-local"),
    "PersistentVolume": ("v1", "", "repbook-data"),
    "PersistentVolumeClaim": ("v1", "repbook", "repbook-data"),
    "Service": ("v1", "repbook", "repbook"),
    "NetworkPolicy": ("networking.k8s.io/v1", "repbook", "repbook"),
    "ExternalSecret": ("external-secrets.io/v1", "repbook", "repbook-oidc"),
    "Application": ("argoproj.io/v1alpha1", "argocd", "repbook"),
    "Namespace": ("v1", "", "repbook"),
    "IngressRoute": ("traefik.io/v1alpha1", "repbook", "repbook"),
}
Resource = dict[str, Any]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


class UniqueKeyLoader(yaml.SafeLoader):
    def construct_mapping(self, node: yaml.Node, deep: bool = False) -> dict[Hashable, Any]:
        if not isinstance(node, yaml.MappingNode):
            raise TypeError("Expected a YAML mapping")
        result: dict[Hashable, Any] = {}
        for key_node, value_node in node.value:
            key = self.construct_object(key_node, deep=deep)
            require(isinstance(key, str), "YAML mapping keys must be strings")
            require(key not in result, f"Duplicate YAML key: {key}")
            result[key] = self.construct_object(value_node, deep=deep)
        return result


def documents(path: Path) -> list[Resource]:
    result = []
    for doc in yaml.load_all(path.read_text(), Loader=UniqueKeyLoader):
        if doc is None:
            continue
        require(isinstance(doc, dict), f"{path}: expected a resource mapping")
        require(isinstance(doc.get("metadata"), dict), f"{path}: missing metadata")
        for value in (
            doc.get("apiVersion"),
            doc.get("kind"),
            doc["metadata"].get("name"),
        ):
            require(isinstance(value, str) and bool(value), f"{path}: malformed resource")
        result.append(doc)
    return result


def is_infra_repo(repo: str) -> bool:
    require(isinstance(repo, str), "Application repoURL must be a string")
    if "://" not in repo:
        require(bool(re.match(r"[^/]+:[^/].*", repo)), "Unsupported local repository URL")
        repo = "ssh://" + repo.replace(":", "/", 1)
    parsed = urlsplit(repo)
    if not parsed.hostname:
        raise ValueError("Unsupported repository URL")
    repository = posixpath.normpath(unquote(parsed.path)).strip("/").lower().removesuffix(".git")
    return parsed.hostname.lower() in {
        "github.com",
        "ssh.github.com",
    } and repository == ("pablomarelli/homelab-infra")


def references_repbook(value: object) -> bool:
    if isinstance(value, str):
        return "repbook" in value.lower()
    if isinstance(value, dict):
        return any(
            references_repbook(key) or references_repbook(item) for key, item in value.items()
        )
    if isinstance(value, list):
        return any(references_repbook(item) for item in value)
    return False


def terraform_static_values(path: Path) -> list[str]:
    values = []
    for token in re.findall(
        r'#[^\n]*|//[^\n]*|/\*.*?\*/|"(?:\\.|[^"\\])*"|[^#"/]+',
        path.read_text(),
        flags=re.DOTALL,
    ):
        if token.startswith(("#", "//", "/*")):
            continue
        if token.startswith('"'):
            token = re.sub(
                r"\\(u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|.)",
                lambda match: (
                    chr(int(match[1][1:], 16))
                    if match[1][0] in "uU"
                    else {"n": "\n", "r": "\r", "t": "\t", '"': '"', "\\": "\\"}[match[1]]
                ),
                token[1:-1],
            )
        values.append(token)
    return values


def check_registration(root: Path, active: bool = False) -> None:
    for required in (
        "apps",
        "bootstrap/namespaces.yaml",
        "infrastructure/tofu/variables.tf",
    ):
        require((root / required).exists(), f"Missing repository input: {required}")
    protected = [(root / RUNTIME).resolve(), (root / "docs/repbook").resolve()]
    for path in (root / "apps").rglob("*"):
        if path.suffix not in {".yaml", ".yml", ".json"}:
            continue
        for app in documents(path):
            if active and path == root / "apps/repbook.yaml":
                continue
            require(
                app["kind"] == "Application",
                f"{path}: unsupported registration resource",
            )
            spec = app["spec"]
            require(
                app["metadata"]["name"] != "repbook"
                and spec["destination"].get("namespace") != "repbook",
                f"{path}: Repbook Application is already registered",
            )
            require(
                not ("source" in spec and "sources" in spec),
                f"{path}: ambiguous sources",
            )
            sources = spec.get("sources", [spec.get("source")])
            require(isinstance(sources, list) and bool(sources), f"{path}: missing sources")
            for source in sources:
                require(isinstance(source, dict), f"{path}: malformed source")
                if not is_infra_repo(source["repoURL"]):
                    continue
                require(
                    set(source) <= {"repoURL", "targetRevision", "path", "directory", "ref"},
                    f"{path}: unsupported local source mechanism",
                )
                if "path" not in source and source.get("ref"):
                    require(
                        "directory" not in source,
                        f"{path}: malformed values-only source",
                    )
                    continue
                raw_path = source.get("path", ".")
                require(isinstance(raw_path, str), f"{path}: source path must be a string")
                normalized = posixpath.normpath(raw_path)
                require(
                    not normalized.startswith("/") and normalized.split("/")[0] != "..",
                    f"{path}: source path escapes the repository",
                )
                local = (root / normalized).resolve()
                require(
                    local.is_relative_to(root),
                    f"{path}: source path escapes the repository",
                )
                require(
                    all(
                        not (target.is_relative_to(local) or local.is_relative_to(target))
                        for target in protected
                    ),
                    f"{path}: source path can include staged Repbook files",
                )
                require(
                    set(source.get("directory", {})) <= {"recurse", "include", "exclude"}
                    and not any(
                        (local / marker).exists()
                        for marker in (
                            "kustomization.yaml",
                            "kustomization.yml",
                            "Kustomization",
                            "Chart.yaml",
                        )
                    ),
                    f"{path}: unsupported local source mechanism",
                )
                require(
                    not any(
                        item.is_symlink() or item.suffix in {".jsonnet", ".libsonnet"}
                        for item in local.rglob("*")
                    ),
                    f"{path}: unsupported local source mechanism",
                )
    for directory in ("manifests", "bootstrap", "infrastructure"):
        for path in (root / directory).rglob("*"):
            if path.suffix not in {
                ".yaml",
                ".yml",
                ".json",
                ".tf",
            } or path.is_relative_to(root / RUNTIME):
                continue
            values = (
                terraform_static_values(path)
                if path.suffix == ".tf"
                else list(yaml.load_all(path.read_text(), Loader=UniqueKeyLoader))
            )
            if active and path == root / "bootstrap/namespaces.yaml":
                values = [
                    doc
                    for doc in values
                    if doc and doc.get("metadata", {}).get("name") != "repbook"
                ]
            require(
                not references_repbook(values),
                f"{path}: active Repbook reference",
            )


def check_staged(root: Path, active: bool = False) -> None:
    bundle: dict[str, Resource] = {}
    files = dict(FILES)
    if active:
        files["apps/repbook.yaml"] = files.pop(f"{PARKED}/application.yaml")
        files.pop(f"{PARKED}/namespace.yaml")
        namespaces = [
            doc
            for doc in documents(root / "bootstrap/namespaces.yaml")
            if doc["metadata"]["name"] == "repbook"
        ]
        require(
            len(namespaces) == 1
            and namespaces[0]
            == {"apiVersion": "v1", "kind": "Namespace", "metadata": {"name": "repbook"}},
            "Require one canonical Repbook namespace",
        )
        bundle["Namespace"] = namespaces[0]
        pull = documents(root / RUNTIME / "ghcr.external.yaml")
        require(
            pull
            == [
                {
                    "apiVersion": "external-secrets.io/v1",
                    "kind": "ExternalSecret",
                    "metadata": {"name": "repbook-ghcr", "namespace": "repbook"},
                    "spec": {
                        "refreshInterval": "1h",
                        "secretStoreRef": {"name": "onepassword", "kind": "ClusterSecretStore"},
                        "target": {
                            "name": "repbook-ghcr",
                            "creationPolicy": "Owner",
                            "template": {"type": "kubernetes.io/dockerconfigjson"},
                        },
                        "data": [
                            {
                                "secretKey": ".dockerconfigjson",
                                "remoteRef": {"key": "Family Manager GHCR/dockerconfigjson"},
                            }
                        ],
                    },
                }
            ],
            "Require the vault-managed registry credential",
        )
    for directory in (RUNTIME, PARKED):
        require(
            {
                str(path.relative_to(root))
                for path in (root / directory).iterdir()
                if not (active and path.name == "ghcr.external.yaml")
            }
            == {path for path in files if str(Path(path).parent) == directory},
            f"{directory}: unexpected files or missing staged files",
        )
    for filename, kinds in files.items():
        resources = documents(root / filename)
        require(
            tuple(doc["kind"] for doc in resources) == kinds,
            f"{filename}: unexpected resources",
        )
        for doc in resources:
            kind = doc["kind"]
            metadata = doc["metadata"]
            require(
                (doc["apiVersion"], metadata.get("namespace", ""), metadata["name"])
                == IDENTITIES[kind],
                f"{filename}: wrong resource identity",
            )
            bundle[kind] = doc

    labels = {"app.kubernetes.io/name": "repbook"}
    deployment = bundle["Deployment"]["spec"]
    require(
        type(deployment["replicas"]) is int and deployment["replicas"] == 1,
        "Require one SQLite writer",
    )
    require(deployment["strategy"] == {"type": "Recreate"}, "Require Recreate updates")
    require(
        deployment["selector"] == {"matchLabels": labels}
        and deployment["template"]["metadata"]["labels"] == labels,
        "Deployment selectors must match",
    )
    pod = deployment["template"]["spec"]
    require(
        pod["automountServiceAccountToken"] is False,
        "Do not mount a service-account token",
    )
    require(
        pod["nodeSelector"] == {"homelab/power": "battery-backed"},
        "Require battery-backed placement",
    )
    require(
        not any(
            pod.get(key)
            for key in (
                "initContainers",
                "ephemeralContainers",
                "hostNetwork",
                "hostPID",
                "hostIPC",
            )
        ),
        "Unexpected containers or host access",
    )
    require(
        pod["securityContext"]
        == {
            "runAsNonRoot": True,
            "runAsUser": 10001,
            "runAsGroup": 10001,
            "fsGroup": 10001,
            "fsGroupChangePolicy": "OnRootMismatch",
            "seccompProfile": {"type": "RuntimeDefault"},
        },
        "Require restricted pod identity and seccomp",
    )
    require(len(pod["containers"]) == 1, "Require one server container")
    container = pod["containers"][0]
    if active:
        require(
            pod.get("imagePullSecrets") == [{"name": "repbook-ghcr"}],
            "Require the Repbook pull secret",
        )
    require(
        container["name"] == "repbook"
        and (
            bool(
                re.fullmatch(
                    r"ghcr.io/pablomarelli/workout-tracker:\d+\.\d+\.\d+-[0-9a-f]{40}",
                    container["image"],
                )
            )
            if active
            else container["image"] == "unpublished.invalid/repbook:blocked"
        ),
        "Require the unpublished image sentinel; a tag is not publication evidence",
    )
    require(
        not any(key in container for key in ("command", "args", "envFrom", "lifecycle")),
        "Do not override the single-process image entry point or environment",
    )
    require(
        container["ports"] == [{"name": "http", "containerPort": 8000}],
        "Require named HTTP port 8000",
    )
    expected_env = {
        "WORKOUT_DATABASE_URL": "sqlite:////app/data/workouts.db",
        "WORKOUT_PUBLIC_ORIGIN": "https://repbook.pablomarelli.dev",
        "WORKOUT_SECURE_COOKIE": "true",
        "WORKOUT_AUTH_MODE": "oidc",
        "WORKOUT_OIDC_ISSUER": "https://auth.pablomarelli.dev/application/o/repbook/",
        "WORKOUT_OIDC_SESSION_SECONDS": "3600",
    }
    env = container["env"]
    require(
        env
        == [
            *({"name": name, "value": value} for name, value in expected_env.items()),
            {
                "name": "WORKOUT_OIDC_CLIENT_ID",
                "valueFrom": {"secretKeyRef": {"name": "repbook-oidc", "key": "client-id"}},
            },
            {
                "name": "WORKOUT_OIDC_CLIENT_SECRET",
                "valueFrom": {"secretKeyRef": {"name": "repbook-oidc", "key": "client-secret"}},
            },
        ],
        "Require the SQLite path, exact HTTPS origin, and secure cookies",
    )
    require(
        bundle["ExternalSecret"]["spec"]
        == {
            "refreshInterval": "1h",
            "secretStoreRef": {"name": "onepassword", "kind": "ClusterSecretStore"},
            "target": {"name": "repbook-oidc", "creationPolicy": "Owner"},
            "data": [
                {"secretKey": field, "remoteRef": {"key": f"Repbook OIDC/{field}"}}
                for field in ("client-id", "client-secret")
            ],
        },
        "Require OIDC credentials from the existing 1Password secret store",
    )
    require(
        container["securityContext"]
        == {
            "allowPrivilegeEscalation": False,
            "readOnlyRootFilesystem": True,
            "capabilities": {"drop": ["ALL"]},
        },
        "Require restricted container security",
    )
    require(
        container["volumeMounts"]
        == [
            {"name": "data", "mountPath": "/app/data"},
            {"name": "tmp", "mountPath": "/tmp"},
        ],
        "Mount the whole SQLite directory and tmp volume",
    )
    require(
        pod["volumes"]
        == [
            {"name": "data", "persistentVolumeClaim": {"claimName": "repbook-data"}},
            {"name": "tmp", "emptyDir": {"sizeLimit": "64Mi"}},
        ],
        "Require the bound data claim and 64 MiB tmp volume",
    )
    for name in ("startupProbe", "readinessProbe", "livenessProbe"):
        probe = container[name]
        require(
            probe["httpGet"] == {"path": "/api/health", "port": "http"}
            and not any(key in probe for key in ("exec", "tcpSocket", "grpc")),
            f"{name}: require the HTTP health endpoint",
        )
    require(
        container["resources"]
        == {
            "requests": {"cpu": "100m", "memory": "128Mi"},
            "limits": {"cpu": "1", "memory": "512Mi"},
        },
        "Keep the initial unmeasured resource defaults",
    )

    storage_class = bundle["StorageClass"]
    require(
        (
            storage_class["provisioner"],
            storage_class["reclaimPolicy"],
            storage_class["volumeBindingMode"],
        )
        == ("kubernetes.io/no-provisioner", "Retain", "WaitForFirstConsumer"),
        "Require retained static local storage",
    )
    for kind in ("PersistentVolume", "PersistentVolumeClaim"):
        require(
            bundle[kind]["metadata"]["annotations"]["argocd.argoproj.io/sync-options"]
            == "Prune=false,Delete=false",
            f"{kind}: require prune and deletion protection",
        )
    require(
        bundle["PersistentVolume"]["spec"]
        == {
            "capacity": {"storage": "10Gi"},
            "volumeMode": "Filesystem",
            "accessModes": ["ReadWriteOnce"],
            "persistentVolumeReclaimPolicy": "Retain",
            "storageClassName": "repbook-local",
            "claimRef": {"namespace": "repbook", "name": "repbook-data"},
            "local": {"path": "/srv/repbook/data"},
            "nodeAffinity": {
                "required": {
                    "nodeSelectorTerms": [
                        {
                            "matchExpressions": [
                                {
                                    "key": "kubernetes.io/hostname",
                                    "operator": "In",
                                    "values": ["pablo-ideapad-l340-17irh-gaming"],
                                }
                            ]
                        }
                    ]
                }
            },
        },
        "Require retained PV binding, directory, and node affinity",
    )
    require(
        bundle["PersistentVolumeClaim"]["spec"]
        == {
            "accessModes": ["ReadWriteOnce"],
            "volumeMode": "Filesystem",
            "storageClassName": "repbook-local",
            "volumeName": "repbook-data",
            "resources": {"requests": {"storage": "10Gi"}},
        },
        "Require explicit PVC binding and capacity",
    )
    require(
        bundle["Service"]["spec"]
        == {
            "type": "ClusterIP",
            "selector": labels,
            "ports": [{"name": "http", "port": 8000, "targetPort": "http"}],
        },
        "Service selectors and ports must match the server",
    )
    require(
        bundle["NetworkPolicy"]["spec"]
        == {
            "podSelector": {"matchLabels": labels},
            "policyTypes": ["Ingress"],
            "ingress": [
                {
                    "from": [
                        {
                            "namespaceSelector": {
                                "matchLabels": {"kubernetes.io/metadata.name": "kube-system"}
                            },
                            "podSelector": {"matchLabels": {"app.kubernetes.io/name": "traefik"}},
                        }
                    ],
                    "ports": [{"protocol": "TCP", "port": 8000}],
                }
            ],
        },
        "Allow ingress only from Traefik Pods in kube-system",
    )

    app = bundle["Application"]["spec"]
    require(
        app["source"]
        == {
            "repoURL": "https://github.com/pablomarelli/homelab-infra.git",
            "targetRevision": "main",
            "path": RUNTIME,
        }
        and "sources" not in app,
        "Parked Application must watch the canonical directory at main",
    )
    require(
        app["project"] == "default"
        and app["destination"]
        == {"server": "https://kubernetes.default.svc", "namespace": "repbook"},
        "Parked Application destination must match",
    )
    require(
        app["syncPolicy"]
        == {
            "automated": {"prune": False, "selfHeal": True},
            "syncOptions": ["CreateNamespace=false"],
        },
        "Keep namespace creation explicit and pruning disabled",
    )
    require(
        bundle["IngressRoute"]["spec"]
        == {
            "entryPoints": ["web"],
            "routes": [
                {
                    "match": "Host(`repbook.pablomarelli.dev`)",
                    "kind": "Rule",
                    "services": [{"name": "repbook", "port": 8000}],
                }
            ],
        },
        "Park the whole-host same-origin route without forward auth",
    )
    check_registration(root, active)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--staged", action="store_true", help="Validate an inactive staging fixture"
    )
    args = parser.parse_args()
    try:
        check_staged(args.root.resolve(), active=not args.staged)
    except (
        OSError,
        ValueError,
        KeyError,
        TypeError,
        IndexError,
        AttributeError,
        yaml.YAMLError,
    ) as error:
        print(f"Repbook configuration check failed: {error}", file=sys.stderr)
        return 1
    print(
        "Repbook static configuration passed. "
        "No image, cluster, DNS, TLS, backup, or device validation was performed."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
