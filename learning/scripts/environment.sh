#!/usr/bin/env bash
# Source in the native macOS Agent. LAB_HOME holds ignored tools and credentials.
export LAB_HOME="${LAB_HOME:-/Users/lth/Documents/ChatGPT/k/retail-store-sample-app/env}"
[ ! -f "$LAB_HOME/network.sh" ] || source "$LAB_HOME/network.sh"
export JAVA_HOME="${JAVA_HOME_21:-/Users/lth/Library/Java/JavaVirtualMachines/corretto-21.0.5/Contents/Home}"
export PATH="$LAB_HOME/node-v22.23.4-darwin-arm64/bin:$JAVA_HOME/bin:$LAB_HOME/bin:/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export DOCKER_HOST="$(docker context inspect --format '{{.Endpoints.docker.Host}}')"
export DOCKER_API_VERSION="$(docker version --format '{{.Server.APIVersion}}')"
export TESTCONTAINERS_DOCKER_SOCKET_OVERRIDE=/var/run/docker.sock
export MAVEN_OPTS="-Xmx512m -Dapi.version=$DOCKER_API_VERSION"
export AWS_ACCESS_KEY_ID=localtest
export AWS_SECRET_ACCESS_KEY=localtest
export AWS_REGION=us-east-1
export AWS_EC2_METADATA_DISABLED=true
export KUBECONFIG="$LAB_HOME/release.kubeconfig"
export GOTOOLCHAIN=auto
