#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source learning/scripts/environment.sh
curl -fsS --retry 120 --retry-delay 2 --retry-connrefused http://127.0.0.1:8080/jnlpJars/agent.jar -o "$LAB_HOME/agent.jar"
exec "$JAVA_HOME/bin/java" -Xmx256m -jar "$LAB_HOME/agent.jar" -url http://127.0.0.1:8080/ -secret "@$LAB_HOME/jenkins-secrets/agent-secret" -name mac-agent -webSocket -workDir "$LAB_HOME/agent-work"
