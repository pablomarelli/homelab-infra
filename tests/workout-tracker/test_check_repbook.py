import hashlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/check-repbook.py"
RUNTIME = "manifests/workout-tracker"
DEPLOYMENT = f"{RUNTIME}/deployment.yaml"
STORAGE = f"{RUNTIME}/storage.yaml"
POD = ("spec", "template", "spec")
CONTAINER = (*POD, "containers", 0)


@pytest.mark.parametrize(
    "fault", [None, "image", "pull-secret", "namespace", "credential", "second-writer"]
)
def test_private_activation(tmp_path: Path, fault: str | None) -> None:
    for directory in ("apps", "bootstrap", "infrastructure", "manifests", "docs/repbook"):
        shutil.copytree(ROOT / directory, tmp_path / directory)
    path = tmp_path / DEPLOYMENT
    deployment = yaml.safe_load(path.read_text())
    pod = deployment["spec"]["template"]["spec"]
    if fault == "image":
        pod["containers"][0]["image"] = "unpublished.invalid/repbook:blocked"
    elif fault == "pull-secret":
        pod.pop("imagePullSecrets")
    elif fault == "second-writer":
        deployment["spec"]["replicas"] = 2
    elif fault == "namespace":
        namespaces = tmp_path / "bootstrap/namespaces.yaml"
        namespaces.write_text(namespaces.read_text().replace("name: repbook", "name: other"))
    elif fault == "credential":
        secret = tmp_path / RUNTIME / "ghcr.external.yaml"
        secret.write_text(secret.read_text().replace("Family Manager GHCR", "Other"))
    path.write_text(yaml.safe_dump(deployment))
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(tmp_path)],
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert (result.returncode == 0) == (fault is None), result.stderr


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    for directory in (
        "apps",
        "bootstrap",
        "infrastructure",
        "manifests",
        "docs/repbook",
    ):
        shutil.copytree(ROOT / directory, tmp_path / directory)
    (tmp_path / "apps/repbook.yaml").rename(tmp_path / "docs/repbook/activation/application.yaml")
    namespaces = list(yaml.safe_load_all((tmp_path / "bootstrap/namespaces.yaml").read_text()))
    namespace = next(doc for doc in namespaces if doc["metadata"]["name"] == "repbook")
    (tmp_path / "docs/repbook/activation/namespace.yaml").write_text(yaml.safe_dump(namespace))
    (tmp_path / "bootstrap/namespaces.yaml").write_text(
        yaml.safe_dump_all([doc for doc in namespaces if doc != namespace])
    )
    (tmp_path / RUNTIME / "ghcr.external.yaml").unlink()
    deployment = yaml.safe_load((tmp_path / DEPLOYMENT).read_text())
    pod = deployment["spec"]["template"]["spec"]
    pod.pop("imagePullSecrets")
    pod["containers"][0]["image"] = "unpublished.invalid/repbook:blocked"
    (tmp_path / DEPLOYMENT).write_text(yaml.safe_dump(deployment))
    return tmp_path


def run_check(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--staged", "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
        timeout=10,
    )


def reject(root: Path, diagnostic: str) -> None:
    result = run_check(root)
    assert result.returncode == 1, result.stdout + result.stderr
    assert diagnostic in result.stderr
    assert "Traceback" not in result.stderr
    assert "passed" not in result.stdout


def test_checked_in_bundle(repo: Path) -> None:
    result = run_check(repo)
    assert result.returncode == 0, result.stderr
    assert "static configuration passed" in result.stdout
    assert "No image, cluster, DNS, TLS, backup, or device validation" in result.stdout


def test_temporary_repository_is_read_only_and_repeatable(repo: Path) -> None:
    def snapshot() -> dict[str, str]:
        return {
            str(path.relative_to(repo)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in repo.rglob("*")
            if path.is_file()
        }

    before = snapshot()
    for _ in range(2):
        result = run_check(repo)
        assert result.returncode == 0, result.stderr
    assert snapshot() == before


@pytest.mark.parametrize(
    ("filename", "document", "keys", "value", "diagnostic"),
    [
        (
            DEPLOYMENT,
            0,
            ("apiVersion",),
            "extensions/v1beta1",
            "wrong resource identity",
        ),
        (DEPLOYMENT, 0, ("spec", "replicas"), 2, "one SQLite writer"),
        (DEPLOYMENT, 0, ("spec", "strategy", "type"), "RollingUpdate", "Recreate"),
        (
            DEPLOYMENT,
            0,
            (*CONTAINER, "image"),
            "ghcr.io/pablomarelli/workout-tracker:1.0.0",
            "sentinel",
        ),
        (STORAGE, 0, ("reclaimPolicy",), "Delete", "retained static"),
        (
            STORAGE,
            1,
            ("spec", "persistentVolumeReclaimPolicy"),
            "Delete",
            "retained PV binding",
        ),
        (STORAGE, 1, ("spec", "claimRef", "name"), "other-data", "retained PV binding"),
        (STORAGE, 2, ("spec", "volumeName"), "other-data", "explicit PVC binding"),
        (STORAGE, 2, ("metadata", "annotations"), {}, "sync-options"),
        (
            f"{RUNTIME}/service.yaml",
            0,
            ("spec", "selector"),
            {"app": "other"},
            "Service selectors",
        ),
        (
            DEPLOYMENT,
            0,
            (*CONTAINER, "env", 1, "value"),
            "http://repbook.pablomarelli.dev",
            "exact HTTPS origin",
        ),
        (DEPLOYMENT, 0, (*CONTAINER, "env", 2, "value"), "false", "secure cookies"),
        (DEPLOYMENT, 0, (*CONTAINER, "env", 3, "value"), "local", "secure cookies"),
        (
            DEPLOYMENT,
            0,
            (*CONTAINER, "env", 6, "valueFrom", "secretKeyRef", "name"),
            "other",
            "secure cookies",
        ),
        (
            f"{RUNTIME}/oidc.external.yaml",
            0,
            ("spec", "data", 1, "remoteRef", "key"),
            "Other/client-secret",
            "OIDC credentials",
        ),
        (DEPLOYMENT, 0, (*CONTAINER, "ports", 0, "containerPort"), 8080, "port 8000"),
        (
            DEPLOYMENT,
            0,
            (*CONTAINER, "readinessProbe", "httpGet", "path"),
            "/",
            "health endpoint",
        ),
        (
            DEPLOYMENT,
            0,
            (*POD, "securityContext", "fsGroup"),
            0,
            "restricted pod identity",
        ),
        (
            DEPLOYMENT,
            0,
            (*CONTAINER, "securityContext", "readOnlyRootFilesystem"),
            False,
            "restricted container",
        ),
        (
            DEPLOYMENT,
            0,
            (*CONTAINER, "volumeMounts", 0, "mountPath"),
            "/app/data/workouts.db",
            "whole SQLite directory",
        ),
        (
            f"{RUNTIME}/network-policy.yaml",
            0,
            ("spec", "ingress"),
            [{}],
            "only from Traefik",
        ),
    ],
)
def test_unsafe_resource_mutations(
    repo: Path,
    filename: str,
    document: int,
    keys: tuple[str | int, ...],
    value: Any,
    diagnostic: str,
) -> None:
    path = repo / filename
    resources = list(yaml.safe_load_all(path.read_text()))
    target = resources[document]
    for key in keys[:-1]:
        target = target[key]
    target[keys[-1]] = value
    path.write_text(yaml.safe_dump_all(resources, sort_keys=False))
    reject(repo, diagnostic)


def test_early_application_registration(repo: Path) -> None:
    shutil.copyfile(repo / "docs/repbook/activation/application.yaml", repo / "apps/repbook.yaml")
    reject(repo, "already registered")


@pytest.mark.parametrize("form", ["source", "sources"])
@pytest.mark.parametrize(
    "url",
    [
        "https://github.com/PabloMarelli/homelab-infra.git",
        "https://github.com/pablomarelli/homelab-infra/",
        "git@github.com:PabloMarelli/homelab-infra.git",
        "ssh://git@github.com/PabloMarelli/homelab-infra.git",
        "ssh://git@ssh.github.com:443/pablomarelli/homelab-infra.git",
    ],
)
@pytest.mark.parametrize("watched", [".", "manifests", "docs", RUNTIME, "docs/repbook/activation"])
def test_watcher_aliases_and_ancestor_paths(repo: Path, form: str, url: str, watched: str) -> None:
    app = yaml.safe_load((repo / "docs/repbook/activation/application.yaml").read_text())
    app["metadata"]["name"] = "unrelated-watcher"
    app["spec"]["destination"]["namespace"] = "default"
    source = {"repoURL": url, "targetRevision": "main", "path": watched}
    app["spec"].pop("source")
    app["spec"][form] = source if form == "source" else [source]
    (repo / "apps/watcher.yaml").write_text(yaml.safe_dump(app))
    reject(repo, "can include staged Repbook files")


@pytest.mark.parametrize("mechanism", ["plugin", "helm", "kustomize"])
def test_unsupported_local_source_mechanism(repo: Path, mechanism: str) -> None:
    path = repo / "apps/dev-portfolio.yaml"
    app = yaml.safe_load(path.read_text())
    app["spec"]["source"][mechanism] = {}
    path.write_text(yaml.safe_dump(app))
    reject(repo, "unsupported local source mechanism")


@pytest.mark.parametrize("marker", ["kustomization.yaml", "Chart.yaml", "include.jsonnet"])
def test_implicit_local_source_mechanism(repo: Path, marker: str) -> None:
    (repo / "manifests/dev-portfolio" / marker).write_text("{}\n")
    reject(repo, "unsupported local source mechanism")


def test_local_source_symlink_to_parked_resources(repo: Path) -> None:
    (repo / "manifests/dev-portfolio/parked.yaml").symlink_to(
        repo / "docs/repbook/activation/application.yaml"
    )
    reject(repo, "unsupported local source mechanism")


@pytest.mark.parametrize("registration", ["namespace", "route", "dns"])
def test_no_active_namespace_route_or_dns(repo: Path, registration: str) -> None:
    if registration == "dns":
        path = repo / "infrastructure/tofu/variables.tf"
        path.write_text(path.read_text() + '\nlocals { forbidden = "repbook" }\n')
    else:
        source = "namespace" if registration == "namespace" else "ingressroute"
        destination = (
            "bootstrap/repbook.yaml"
            if registration == "namespace"
            else "manifests/traefik/repbook.yaml"
        )
        shutil.copyfile(repo / f"docs/repbook/activation/{source}.yaml", repo / destination)
    reject(repo, "active Repbook reference")


@pytest.mark.parametrize(
    ("filename", "contents"),
    [
        (
            "bootstrap/escaped.yaml",
            'apiVersion: v1\nkind: Namespace\nmetadata:\n  name: "rep\\u0062ook"\n',
        ),
        (
            "bootstrap/escaped.json",
            '{"apiVersion":"v1","kind":"Namespace","metadata":{"name":"rep\\u0062ook"}}',
        ),
        (
            "manifests/traefik/escaped.yaml",
            'routes:\n  - match: "Host(`rep\\u0062ook.pablomarelli.dev`)"\n',
        ),
        (
            "manifests/alloy/escaped-values.yaml",
            'hosts: ["rep\\u0062ook.pablomarelli.dev"]\n',
        ),
    ],
)
def test_decoded_yaml_and_json_references(repo: Path, filename: str, contents: str) -> None:
    (repo / filename).write_text(contents)
    reject(repo, "active Repbook reference")


@pytest.mark.parametrize(
    "contents",
    [
        "# Repbook remains staged outside bootstrap.\n",
        "enabled: true\nreplicas: 1\n",
        "- ordinary-host\n- 8000\n",
        '"ordinary scalar"\n',
        "host: 'rep\\u0062ook.pablomarelli.dev'\n",
    ],
)
def test_unrelated_yaml_comments_and_values_are_allowed(repo: Path, contents: str) -> None:
    (repo / "bootstrap/unrelated.yaml").write_text(contents)
    result = run_check(repo)
    assert result.returncode == 0, result.stderr


def test_active_tree_yaml_still_rejects_duplicate_keys(repo: Path) -> None:
    (repo / "manifests/alloy/duplicate-values.yaml").write_text("enabled: true\nenabled: true\n")
    reject(repo, "Duplicate YAML key: enabled")


@pytest.mark.parametrize("name", [r"rep\u0062ook", r"rep\U00000062ook"])
def test_decoded_terraform_dns_strings(repo: Path, name: str) -> None:
    path = repo / "infrastructure/tofu/variables.tf"
    path.write_text(path.read_text() + f'\nlocals {{ forbidden = "{name}" }}\n')
    reject(repo, "active Repbook reference")


@pytest.mark.parametrize(
    "contents",
    [
        "# Repbook remains staged outside DNS.\n",
        "// Repbook remains staged outside DNS.\n",
        "/* Repbook remains\n   staged outside DNS. */\n",
        'locals { unrelated = "rep\\\\u0062ook" }\n',
    ],
)
def test_unrelated_terraform_comments_and_literal_escapes_are_allowed(
    repo: Path, contents: str
) -> None:
    path = repo / "infrastructure/tofu/variables.tf"
    path.write_text(path.read_text() + contents)
    result = run_check(repo)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "value",
    [
        "https://repbook.pablomarelli.dev",
        "#repbook",
        "/*repbook*/",
        r"\"rep\u0062ook\"",
    ],
)
def test_terraform_comment_markers_inside_strings_are_values(repo: Path, value: str) -> None:
    path = repo / "infrastructure/tofu/variables.tf"
    path.write_text(path.read_text() + f'locals {{ host = "{value}" }}\n')
    reject(repo, "active Repbook reference")


def test_rejects_duplicate_keys_in_an_otherwise_valid_bundle(repo: Path) -> None:
    path = repo / DEPLOYMENT
    image = next(line for line in path.read_text().splitlines(keepends=True) if "image:" in line)
    path.write_text(path.read_text().replace(image, image + image))
    reject(repo, "Duplicate YAML key: image")


@pytest.mark.parametrize("contents", ["kind: [\n", "- not-a-resource\n"])
def test_rejects_malformed_documents(repo: Path, contents: str) -> None:
    (repo / DEPLOYMENT).write_text(contents)
    reject(repo, "Repbook configuration check failed")


def test_rejects_an_extra_runtime_resource(repo: Path) -> None:
    (repo / f"{RUNTIME}/extra.yaml").write_text("kind: Deployment\n")
    reject(repo, "unexpected files")
