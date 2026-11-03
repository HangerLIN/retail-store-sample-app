"""Serialized five-service releases, persisted intent and last verified rollback point."""

import subprocess, json, hashlib, pathlib, urllib.request, urllib.error, sys, datetime, copy, http.client
from render import render
from smoke import verify


class UnhealthyRelease(RuntimeError):
    pass


def business_verify():
    try:
        return verify()
    except (urllib.error.URLError, http.client.HTTPException, OSError, TimeoutError, AssertionError) as e:
        raise UnhealthyRelease(str(e)) from e


SERVICES = ["orders", "checkout", "carts", "catalog", "ui"]


def kubectl(*args):
    return subprocess.check_output(["kubectl", "-n", "retail", *args], text=True)


def obj(kind, name):
    return json.loads(kubectl("get", kind, name, "-o", "json"))


def readstate():
    o = obj("cm", "release-state")
    return o, json.loads(o["data"]["state.json"])


def write(state, base):
    # Compare against the version read before the operation, not a fresh snapshot.
    return json.loads(
        kubectl(
            "patch",
            "cm",
            "release-state",
            "--type=merge",
            "-o",
            "json",
            "-p",
            json.dumps(
                {
                    "metadata": {
                        "resourceVersion": base["metadata"]["resourceVersion"]
                    },
                    "data": {"state.json": json.dumps(state)},
                }
            ),
        )
    )


def checkimages(images):
    assert set(images) == set(SERVICES), "Release must specify all five images"
    for name, ref in images.items():
        assert ref.startswith("localhost:5001/retail/" + name + "@sha256:"), (
            "Untrusted registry or mutable image"
        )
        repo, digest = ref[len("localhost:5001/") :].split("@")
        r = urllib.request.urlopen(
            urllib.request.Request(
                f"http://127.0.0.1:5001/v2/{repo}/manifests/{digest}",
                method="HEAD",
                headers={
                    "Accept": "application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json, application/vnd.oci.image.index.v1+json"
                },
            ),
            timeout=15,
        )
        assert r.headers["Docker-Content-Digest"] == digest, "Registry digest mismatch"


def settings(c):
    c = copy.deepcopy(c)
    for e in c.get("env", []):
        if "fieldRef" in e.get("valueFrom", {}):
            e["valueFrom"]["fieldRef"].setdefault("apiVersion", "v1")
    return {k: c.get(k, []) for k in ["env", "envFrom", "command", "args"]}


def preflight(adopt=False):
    assert (
        subprocess.check_output(
            ["kubectl", "config", "current-context"], text=True
        ).strip()
        == ("kind-retail-lab" if adopt else "retail-release")
    ), "Wrong release context"
    expected = render()
    fingerprint = {}
    for o in expected:
        name = o["metadata"]["name"]
        if o["kind"] == "Deployment" and name in SERVICES:
            live = obj("deployment", name)
            cs = o["spec"]["template"]["spec"]["containers"]
            ls = live["spec"]["template"]["spec"]["containers"]
            assert len(cs) == len(ls) == 1, "Unexpected sidecar"
            assert settings(cs[0]) == settings(ls[0]), (
                "Live configuration drift: " + name
            )
            assert ls[0].get("readinessProbe"), "Missing readiness probe"
            fingerprint[name] = settings(cs[0])
        if o["kind"] == "ConfigMap" and name != "release-state":
            assert obj("cm", name).get("data", {}) == o.get("data", {}), (
                "ConfigMap drift: " + name
            )
            fingerprint[name] = o.get("data", {})
    digest = hashlib.sha256(
        json.dumps(fingerprint, sort_keys=True).encode()
    ).hexdigest()
    _, state = readstate()
    if state.get("lastGood"):
        assert adopt or state["lastGood"]["configFingerprint"] == digest, (
            "Admin config changed: establish a new verified baseline before CI"
        )
        checkimages(state["lastGood"]["images"])
    return digest


def adopt_config():
    """Admin-only workflow: accept verified config without changing release provenance."""
    fingerprint = preflight(adopt=True)
    base, state = readstate()
    good = state.get("lastGood")
    assert good and not state.get("pending") and not state.get("recoveryFailed"), (
        "Resolve pending/recovery state before adopting config"
    )
    assert imageslive() == good["images"], "Image drift: restore lastGood before adoption"
    for service in SERVICES:
        subprocess.run(
            ["kubectl", "-n", "retail", "rollout", "status",
             "deployment/" + service, "--timeout=240s"], check=True,
        )
    business_verify()
    evidence(good["images"])
    assert imageslive() == good["images"], "Images changed during adoption"
    assert preflight(adopt=True) == fingerprint, "Config changed during adoption"
    good["configFingerprint"] = fingerprint
    # Preserve sourceSha, images and release verification time. This is a config event.
    write(state, base)
    pathlib.Path("reports").mkdir(exist_ok=True)
    pathlib.Path("reports/config-adoption.json").write_text(json.dumps({
        "configFingerprint": fingerprint,
        "sourceSha": good["sourceSha"],
        "images": good["images"],
        "adoptedAt": datetime.datetime.now(datetime.timezone.utc).isoformat(),
    }, indent=2))
    print("Adopted verified configuration; image and source baseline unchanged")


def imageslive():
    return {
        s: obj("deployment", s)["spec"]["template"]["spec"]["containers"][0]["image"]
        for s in SERVICES
    }


def deploy(images):
    checkimages(images)
    for s in SERVICES:
        kubectl("set", "image", "deployment/" + s, s + "=" + images[s])
        result = subprocess.run(
            [
                "kubectl",
                "-n",
                "retail",
                "rollout",
                "status",
                "deployment/" + s,
                "--timeout=240s",
            ],
            text=True,
            capture_output=True,
        )
        if result.returncode:
            text = result.stdout + result.stderr
            if "timed out" in text or "exceeded its progress deadline" in text:
                raise UnhealthyRelease(text)
            raise RuntimeError(text)


def evidence(images):
    pods = json.loads(kubectl("get", "pods", "-o", "json"))["items"]
    result = {}
    for s, ref in images.items():
        matches = [
            p
            for p in pods
            if not p["metadata"].get("deletionTimestamp")
            and any(c["image"] == ref for c in p["spec"]["containers"])
        ]
        ready = [
            p
            for p in matches
            if all(
                c.get("ready") for c in p.get("status", {}).get("containerStatuses", [])
            )
            and p.get("status", {}).get("containerStatuses")
        ]
        assert ready, "No ready Pod for " + s
        expected = ref.split("@")[1]
        allowed = {expected}
        repo = ref[len("localhost:5001/") :].split("@")[0]
        request = urllib.request.Request(
            f"http://127.0.0.1:5001/v2/{repo}/manifests/{expected}",
            headers={
                "Accept": "application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.v2+json"
            },
        )
        manifest = json.load(urllib.request.urlopen(request, timeout=15))
        allowed.update(
            m["digest"]
            for m in manifest.get("manifests", [])
            if m.get("platform", {}).get("architecture") == "arm64"
        )
        for pod in ready:
            for c in pod["status"]["containerStatuses"]:
                actual = c["imageID"].split("@")[-1].removeprefix("docker-pullable://")
                assert actual in allowed, (
                    "Running image digest differs from approved manifest: " + s
                )
        result[s] = {
            "spec": ref,
            "imageIDs": [
                c["imageID"] for p in ready for c in p["status"]["containerStatuses"]
            ],
        }
    pathlib.Path("reports/image-evidence.json").write_text(json.dumps(result, indent=2))


def reconcile(allow_unhealthy=False):
    preflight()
    base, state = readstate()
    good = state.get("lastGood")
    if not good:
        assert not state.get("pending"), (
            "No verified rollback point; complete admin bootstrap"
        )
        return
    if state.get("pending") or imageslive() != good["images"]:
        try:
            deploy(good["images"])
            business_verify()
            evidence(good["images"])
        except UnhealthyRelease:
            if not allow_unhealthy:
                raise
            state["recoveryFailed"] = True
            write(state, base)
            print(
                "Previous release unhealthy; a fully tested repair candidate may proceed"
            )
            return
        state.pop("pending", None)
        state.pop("recoveryFailed", None)
        write(state, base)
        print("Restored last verified release")


def needed():
    _, state = readstate()
    sha = state.get("lastGood", {}).get("sourceSha")
    if state.get("recoveryFailed") or not sha:
        return True
    try:
        files = subprocess.check_output(
            ["git", "diff", "--name-only", sha, "HEAD"], text=True
        ).splitlines()
    except subprocess.CalledProcessError:
        return True
    return any(
        not (f.endswith((".md", ".mmd")) or f.startswith("screenshots/")) for f in files
    )


def publish(bootstrap=False):
    fingerprint = preflight()
    if not bootstrap:
        reconcile(allow_unhealthy=True)
    images = {
        s: json.loads(pathlib.Path(f"reports/{s}-image.json").read_text())["image"]
        for s in SERVICES
    }
    checkimages(images)
    base, state = readstate()
    candidate = {
        "images": images,
        "sourceSha": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], text=True
        ).strip(),
        "configFingerprint": fingerprint,
        "verifiedAt": None,
        "recoveryFailed": bool(state.get("recoveryFailed")),
    }
    if (
        bootstrap
        and subprocess.check_output(["git", "status", "--porcelain"], text=True).strip()
    ):
        candidate["sourceSha"] = None
    state["pending"] = candidate
    base = write(state, base)
    try:
        deploy(images)
        business_verify()
        evidence(images)
    except BaseException:
        if state.get("lastGood"):
            deploy(state["lastGood"]["images"])
            business_verify()
            state.pop("pending", None)
            base = write(state, base)
        raise
    candidate["verifiedAt"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
    state["lastGood"] = candidate
    state.pop("pending", None)
    state.pop("recoveryFailed", None)
    base = write(state, base)
    pathlib.Path("reports/release.json").write_text(json.dumps(state, indent=2))
    print("Recorded verified release")


if __name__ == "__main__":
    action = sys.argv[1]
    if action == "preflight":
        preflight()
    elif action == "reconcile":
        reconcile()
    elif action == "prepare":
        reconcile(allow_unhealthy=True)
    elif action == "needed":
        print("yes" if needed() else "no")
    elif action == "publish":
        publish()
    elif action == "bootstrap":
        publish(True)
    elif action == "adopt-config":
        adopt_config()
    else:
        raise SystemExit("Unknown release action")
