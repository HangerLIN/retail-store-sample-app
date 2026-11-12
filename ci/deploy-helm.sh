#!/usr/bin/env bash
# Deploy a single, immutable application version and wait for all workloads to
# become ready. Authentication is supplied by the calling CI system.
set -euo pipefail

: "${IMAGE_REPOSITORY_PREFIX:?Set IMAGE_REPOSITORY_PREFIX}"
: "${IMAGE_TAG:?Set IMAGE_TAG to the immutable Git commit tag}"

K8S_NAMESPACE="${K8S_NAMESPACE:-retail}"
RELEASE_NAME="${RELEASE_NAME:-retail-store}"
IMAGE_REPOSITORY_PREFIX="${IMAGE_REPOSITORY_PREFIX%/}"
IMAGE_PULL_SECRET="${IMAGE_PULL_SECRET:-}"

image_pull_secret_args=()
if [[ -n "${IMAGE_PULL_SECRET}" ]]; then
  for service in cart catalog checkout orders ui; do
    image_pull_secret_args+=(
      --set-string "${service}.imagePullSecrets[0].name=${IMAGE_PULL_SECRET}"
    )
  done
fi

helm dependency build src/app/chart
helm upgrade --install "${RELEASE_NAME}" src/app/chart \
  --namespace "${K8S_NAMESPACE}" \
  --create-namespace \
  --wait \
  --timeout 10m \
  --set-string "cart.image.repository=${IMAGE_REPOSITORY_PREFIX}/retail-store-sample-cart" \
  --set-string "cart.image.tag=${IMAGE_TAG}" \
  --set-string "catalog.image.repository=${IMAGE_REPOSITORY_PREFIX}/retail-store-sample-catalog" \
  --set-string "catalog.image.tag=${IMAGE_TAG}" \
  --set-string "checkout.image.repository=${IMAGE_REPOSITORY_PREFIX}/retail-store-sample-checkout" \
  --set-string "checkout.image.tag=${IMAGE_TAG}" \
  --set-string "orders.image.repository=${IMAGE_REPOSITORY_PREFIX}/retail-store-sample-orders" \
  --set-string "orders.image.tag=${IMAGE_TAG}" \
  --set-string "ui.image.repository=${IMAGE_REPOSITORY_PREFIX}/retail-store-sample-ui" \
  --set-string "ui.image.tag=${IMAGE_TAG}" \
  "${image_pull_secret_args[@]}"

for deployment in catalog carts checkout orders ui; do
  kubectl -n "${K8S_NAMESPACE}" rollout status "deployment/${deployment}" --timeout=10m
done

kubectl -n "${K8S_NAMESPACE}" get pods

