"""Cache dependencies locally; node runtime needs only the local registry."""

import subprocess, urllib.request, yaml, pathlib

mapping = {
    "public.ecr.aws/docker/library/mysql:8.0": "mysql:8.0",
    "public.ecr.aws/docker/library/postgres:16.1": "postgres:16.1",
    "public.ecr.aws/docker/library/rabbitmq:3-management": "rabbitmq:3-management",
    "public.ecr.aws/aws-dynamodb-local/aws-dynamodb-local:1.25.1": "amazon/dynamodb-local:1.25.1",
    "redis:6.0-alpine": "redis:6.0-alpine",
}
images = []
for original, source in mapping.items():
    if subprocess.run(
        ["docker", "image", "inspect", source],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ).returncode:
        subprocess.run(["docker", "pull", source], check=True)
    name = source.split("/")[-1].split(":")[0]
    repo = "dependencies/" + name
    tag = "baseline"
    target = "localhost:5001/" + repo
    subprocess.run(["docker", "tag", source, target + ":" + tag], check=True)
    subprocess.run(["docker", "push", target + ":" + tag], check=True)
    r = urllib.request.urlopen(
        urllib.request.Request(
            f"http://127.0.0.1:5001/v2/{repo}/manifests/{tag}",
            method="HEAD",
            headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
        )
    )
    images.append(
        {
            "name": original,
            "newName": target,
            "digest": r.headers["Docker-Content-Digest"],
        }
    )
p = pathlib.Path("learning/k8s/kustomization.yaml")
config = yaml.safe_load(p.read_text())
config["images"] = images
p.write_text(yaml.safe_dump(config, sort_keys=False))
