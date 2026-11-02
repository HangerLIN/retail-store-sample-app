#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source learning/scripts/environment.sh
case "${1:-}" in
  start)
    docker start retail-registry retail-lab-control-plane retail-jenkins
    python3 learning/scripts/jenkins-api.py resume
    if [ -f "$HOME/Library/LaunchAgents/local.retail.jenkins-agent.plist" ]; then
      launchctl kickstart "gui/$(id -u)/local.retail.jenkins-agent" || launchctl bootstrap "gui/$(id -u)" "$HOME/Library/LaunchAgents/local.retail.jenkins-agent.plist"
    else
      echo 'Run bash learning/scripts/agent.sh in a terminal to connect the Agent.'
    fi;;
  stop)
    # Refuse to stop mid-release. Jenkins auth stays inside the helper.
    python3 learning/scripts/jenkins-api.py idle
    launchctl bootout "gui/$(id -u)/local.retail.jenkins-agent" 2>/dev/null || true
    docker stop retail-jenkins retail-registry retail-lab-control-plane;;
  reset)
    echo 'This deletes the kind node and ALL retail database data, including Retain PVC data.'
    echo 'Export any data you want to keep first. Jenkins and Registry volumes are retained.'
    read -r -p 'Type DELETE-retail-lab-DATA to continue: ' confirmation
    [ "$confirmation" = DELETE-retail-lab-DATA ] || exit 1
    python3 learning/scripts/jenkins-api.py idle
    kind delete cluster --name retail-lab;;
  *) echo 'Usage: lifecycle.sh start|stop|reset' >&2; exit 2;;
esac
