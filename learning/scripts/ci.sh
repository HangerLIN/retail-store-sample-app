#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source learning/scripts/environment.sh
[ -s "$KUBECONFIG" ] || { echo 'Release kubeconfig missing'; exit 1; }
mkdir -p reports
case "$1" in
  preflight)
    {
      java -version; node --version; (cd src/catalog; go version); kubectl version --client
      node .yarn/releases/yarn-4.11.0.cjs --version
      docker info --format '{{.ServerVersion}} {{.MemTotal}}'
    } 2>&1 | tee reports/tool-versions.log
    "$LAB_HOME/python/bin/python" -m unittest discover -s learning/tests -v 2>&1 | tee reports/release-tests.log
    "$LAB_HOME/python/bin/python" learning/scripts/release.py preflight;;
  build)
    tag="$(git rev-parse HEAD)-${BUILD_NUMBER:-manual}"
    docker events --filter event=oom --format '{{json .}}' > reports/docker-oom.jsonl &
    events_pid=$!
    (while true; do
      date -u
      docker stats --no-stream --format '{{.Name}} {{.MemUsage}}'
      memory_pressure -Q
      sysctl vm.swapusage
      sleep 5
    done) > reports/memory.log &
    stats_pid=$!
    snapshot_pods() {
      kubectl -n retail get pods -o json | "$LAB_HOME/python/bin/python" -c 'import json,sys; print(json.dumps([{ "name":p["metadata"]["name"], "phase":p["status"].get("phase"), "containers":p["status"].get("containerStatuses",[])} for p in json.load(sys.stdin)["items"]],indent=2))'
    }
    trap 'kill "$events_pid" "$stats_pid" 2>/dev/null || true; snapshot_pods > reports/pods-after.json || true' EXIT
    snapshot_pods > reports/pods-before.json
    for service in orders checkout carts catalog ui; do
      bash learning/scripts/test-build.sh "$service"
    done
    # No candidate image is pushed until all five test suites have passed.
    for service in orders checkout carts catalog ui; do
      bash learning/scripts/image.sh "$service" "$tag"
      rm -rf "reports/image-$service"
    done
    [ ! -s reports/docker-oom.jsonl ] || { echo 'Docker OOM during build'; exit 1; };;
  reconcile|prepare|needed|publish)
    "$LAB_HOME/python/bin/python" learning/scripts/release.py "$1";;
  *) exit 2;;
esac
