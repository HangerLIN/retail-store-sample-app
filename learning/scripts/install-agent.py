"""Install this user's login Agent, restricted to the local lab workspace."""

import pathlib, plistlib, os, subprocess

root = pathlib.Path(__file__).resolve().parents[2]
p = pathlib.Path.home() / "Library/LaunchAgents/local.retail.jenkins-agent.plist"
p.parent.mkdir(exist_ok=True)
config = {
    "Label": "local.retail.jenkins-agent",
    "ProgramArguments": ["/bin/bash", str(root / "learning/scripts/agent.sh")],
    "WorkingDirectory": str(root),
    "RunAtLoad": True,
    "KeepAlive": True,
    "ThrottleInterval": 10,
    "StandardOutPath": str(root / "env/agent-launchd.log"),
    "StandardErrorPath": str(root / "env/agent-launchd.log"),
}
p.write_bytes(plistlib.dumps(config))
p.chmod(0o600)
subprocess.run(
    ["launchctl", "bootout", f"gui/{os.getuid()}/local.retail.jenkins-agent"],
    stdout=subprocess.DEVNULL,
    stderr=subprocess.DEVNULL,
)
subprocess.run(["launchctl", "bootstrap", f"gui/{os.getuid()}", str(p)], check=True)
print("Installed login Agent:", p)
