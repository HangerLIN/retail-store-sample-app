"""Mirror pinned build bases as ARM64 manifests for offline local packaging."""

import pathlib, subprocess, urllib.request, json

ROOT = pathlib.Path(__file__).resolve().parents[2]
lock = ROOT / "learning/docker/upstream-bases.json"
if not lock.exists():
    refs = {
        p.stem: p.read_text().splitlines()[0].split()[1]
        for p in (ROOT / "learning/docker").glob("*.Dockerfile")
    }
    lock.write_text(json.dumps(refs, indent=2) + "\n")
for name, ref in json.loads(lock.read_text()).items():
    subprocess.run(["docker", "pull", ref], check=True)
    target = "localhost:5001/bases/" + name
    subprocess.run(["docker", "tag", ref, target + ":pinned"], check=True)
    subprocess.run(["docker", "push", target + ":pinned"], check=True)
    request = urllib.request.Request(
        f"http://127.0.0.1:5001/v2/bases/{name}/manifests/pinned",
        method="HEAD",
        headers={"Accept": "application/vnd.docker.distribution.manifest.v2+json"},
    )
    digest = urllib.request.urlopen(request).headers["Docker-Content-Digest"]
    p = ROOT / "learning/docker" / (name + ".Dockerfile")
    lines = p.read_text().splitlines()
    lines[0] = "FROM " + target + "@" + digest
    p.write_text("\n".join(lines) + "\n")
