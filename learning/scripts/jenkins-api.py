"""Local admin CLI; credentials never appear in arguments or output."""

import pathlib, urllib.request, urllib.parse, json, http.cookiejar, sys, base64

ROOT = pathlib.Path(__file__).resolve().parents[2]
password = (ROOT / "env/jenkins-secrets/admin-password").read_text().strip()
browser = urllib.request.build_opener(
    urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
)
browser.addheaders = [
    (
        "Authorization",
        "Basic " + base64.b64encode(("learner:" + password).encode()).decode(),
    )
]
base = "http://127.0.0.1:8080"


def request(path, data=None):
    req = urllib.request.Request(base + path)
    if data is not None:
        crumb = json.load(browser.open(base + "/crumbIssuer/api/json"))
        req.add_header(crumb["crumbRequestField"], crumb["crumb"])
        req.data = urllib.parse.urlencode(data).encode()
    return browser.open(req, timeout=30)


action = sys.argv[1]
if action == "build":
    r = request(
        "/job/retail-local/buildWithParameters",
        {"ACTION": sys.argv[2] if len(sys.argv) > 2 else "deploy"},
    )
    print(r.status, r.headers.get("Location"))
elif action == "resume":
    import time

    for attempt in range(60):
        try:
            request("/cancelQuietDown", {})
            break
        except Exception:
            if attempt == 59:
                raise
            time.sleep(2)
elif action == "idle":
    data = json.load(request("/computer/api/json?depth=2"))
    assert not any(
        e.get("currentExecutable")
        for c in data["computer"]
        for e in c.get("executors", [])
    ), "A build is running; wait for it before stopping"
    request("/quietDown", {})
    print("No active build; Jenkins is quiet")
elif action == "validate":
    print(
        request(
            "/pipeline-model-converter/validate",
            {"jenkinsfile": (ROOT / "Jenkinsfile").read_text()},
        )
        .read()
        .decode()
    )
elif action == "status":
    data = json.load(request("/job/retail-local/lastBuild/api/json"))
    print(
        json.dumps(
            {k: data.get(k) for k in ["number", "result", "building", "url"]}, indent=2
        )
    )
elif action == "log":
    print(request("/job/retail-local/lastBuild/consoleText").read().decode()[-16000:])
elif action == "script":
    code = pathlib.Path(sys.argv[2]).read_text()
    print(request("/scriptText", {"script": code}).read().decode())
else:
    raise SystemExit("Unknown action")
