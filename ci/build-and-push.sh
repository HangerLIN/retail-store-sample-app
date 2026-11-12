#!/usr/bin/env bash
# Build the five application images from their source Dockerfiles and publish
# every image under one immutable source-derived tag.
set -euo pipefail

: "${IMAGE_REPOSITORY_PREFIX:?Set IMAGE_REPOSITORY_PREFIX, for example registry.example.com/team}"
: "${IMAGE_TAG:?Set IMAGE_TAG to the immutable Git commit tag}"

IMAGE_REPOSITORY_PREFIX="${IMAGE_REPOSITORY_PREFIX%/}"

for service in cart catalog checkout orders ui; do
  image="${IMAGE_REPOSITORY_PREFIX}/retail-store-sample-${service}:${IMAGE_TAG}"
  echo "Building ${image}"
  docker build --pull --tag "${image}" "src/${service}"
  docker push "${image}"
done

