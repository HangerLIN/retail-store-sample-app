"""Admin-only installation. Run with the kind admin kubeconfig, never from Jenkins."""

import pathlib, subprocess, json, yaml, secrets, os, base64

ROOT = pathlib.Path(__file__).resolve().parents[2]
os.chdir(ROOT)


def run(*args, **kwargs):
    return subprocess.check_output(args, text=True, **kwargs)


assert run("kubectl", "config", "current-context").strip() == "kind-retail-lab"
p = ROOT / "learning/k8s/.secrets"
p.mkdir(exist_ok=True, mode=0o700)
values = {
    "catalog-db": {
        "RETAIL_CATALOG_PERSISTENCE_USER": "catalog",
        "RETAIL_CATALOG_PERSISTENCE_PASSWORD": secrets.token_hex(16),
        "MYSQL_ROOT_PASSWORD": secrets.token_hex(16),
    },
    "orders-db": {
        "RETAIL_ORDERS_PERSISTENCE_USERNAME": "orders",
        "RETAIL_ORDERS_PERSISTENCE_PASSWORD": secrets.token_hex(16),
    },
    "orders-rabbitmq": {
        "RETAIL_ORDERS_MESSAGING_RABBITMQ_USERNAME": "retail",
        "RETAIL_ORDERS_MESSAGING_RABBITMQ_PASSWORD": secrets.token_hex(16),
    },
    "carts-local": {
        "AWS_ACCESS_KEY_ID": "localkey",
        "AWS_SECRET_ACCESS_KEY": secrets.token_hex(16),
    },
}
for name, data in values.items():
    f = p / (name + ".env")
    if not f.exists():
        f.write_text("".join(f"{k}={v}\n" for k, v in data.items()))
        f.chmod(0o600)
objs = list(yaml.safe_load_all(run("kubectl", "kustomize", "learning/k8s")))
for o in objs:
    if o["kind"] == "Secret":
        assert set(o.get("data", {})) == set(values[o["metadata"]["name"]]), (
            "Unexpected Secret configuration key"
        )
    if o["kind"] in ["Deployment", "StatefulSet"]:
        for c in o["spec"]["template"]["spec"]["containers"]:
            for e in c.get("env", []):
                assert not (
                    "value" in e
                    and any(
                        x in e["name"].upper() for x in ["PASSWORD", "SECRET", "TOKEN"]
                    )
                ), "Literal credential in Pod spec"
    if o["kind"] == "Deployment" and o["metadata"]["name"] in [
        "carts",
        "catalog",
        "checkout",
        "orders",
        "ui",
    ]:
        name = o["metadata"]["name"]
        o["spec"]["template"]["spec"]["containers"][0]["image"] = json.load(
            open(f"reports/{name}-image.json")
        )["image"]
# Never overwrite the last-known-good state during an admin re-apply.
existing = (
    subprocess.run(
        ["kubectl", "-n", "retail", "get", "cm", "release-state"], capture_output=True
    ).returncode
    == 0
)
objs = [
    o
    for o in objs
    if not (
        existing
        and o["kind"] == "ConfigMap"
        and o["metadata"]["name"] == "release-state"
    )
]
subprocess.run(
    ["kubectl", "apply", "-f", "-"],
    input=yaml.safe_dump_all(objs),
    text=True,
    check=True,
)
# Explicit long-lived local lab token; no token in command arguments, Git, or logs.
token = {
    "apiVersion": "v1",
    "kind": "Secret",
    "metadata": {
        "name": "jenkins-release-token",
        "namespace": "retail",
        "annotations": {"kubernetes.io/service-account.name": "jenkins-release"},
    },
    "type": "kubernetes.io/service-account-token",
}
subprocess.run(
    ["kubectl", "apply", "-f", "-"],
    input=yaml.safe_dump(token),
    text=True,
    check=True,
    stdout=subprocess.DEVNULL,
)
import time

for _ in range(30):
    s = json.loads(
        run(
            "kubectl",
            "-n",
            "retail",
            "get",
            "secret",
            "jenkins-release-token",
            "-o",
            "json",
        )
    )
    if s.get("data", {}).get("token"):
        break
    time.sleep(1)
else:
    raise RuntimeError("Token controller did not populate Secret")
admin = json.loads(
    run("kubectl", "config", "view", "--minify", "--flatten", "--raw", "-o", "json")
)
config = {
    "apiVersion": "v1",
    "kind": "Config",
    "clusters": admin["clusters"],
    "users": [
        {
            "name": "jenkins-release",
            "user": {"token": base64.b64decode(s["data"]["token"]).decode()},
        }
    ],
    "contexts": [
        {
            "name": "retail-release",
            "context": {
                "cluster": admin["clusters"][0]["name"],
                "user": "jenkins-release",
                "namespace": "retail",
            },
        }
    ],
    "current-context": "retail-release",
}
f = ROOT / "env/release.kubeconfig"
f.touch(mode=0o600)
f.write_text(yaml.safe_dump(config))
f.chmod(0o600)
print("Installed retail namespace and restricted release kubeconfig")
