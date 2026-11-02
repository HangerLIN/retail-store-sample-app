"""Render non-secret expectations without granting the release identity Secret access."""

import tempfile, shutil, pathlib, subprocess, yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]


def render():
    with tempfile.TemporaryDirectory() as temp:
        p = pathlib.Path(temp) / "k8s"
        shutil.copytree(
            ROOT / "learning/k8s", p, ignore=shutil.ignore_patterns(".secrets")
        )
        (p / ".secrets").mkdir()
        config = yaml.safe_load((p / "kustomization.yaml").read_text())
        for secret in config["secretGenerator"]:
            for name in secret["envs"]:
                (p / name).write_text("PLACEHOLDER=unused\n")
        result = subprocess.check_output(["kubectl", "kustomize", str(p)], text=True)
        return [x for x in yaml.safe_load_all(result) if x and x["kind"] != "Secret"]


if __name__ == "__main__":
    print(yaml.safe_dump_all(render(), sort_keys=False))
