#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source learning/scripts/environment.sh
service="$1"; tag="$2"
case "$service" in carts|orders|ui|catalog|checkout) ;; *) exit 2;; esac
context="reports/image-$service"
rm -rf "$context"
mkdir -p "$context"
case "$service" in
  carts|orders|ui)
    folder="$service"; [ "$service" != carts ] || folder=cart
    cp "src/$folder/target/"*-SNAPSHOT.jar "$context/app.jar"
    recipe=java;;
  catalog) cp reports/catalog "$context/catalog"; recipe=catalog;;
  checkout)
    # Copy only production packages, leaving the tested checkout dependencies intact.
    cp -R src/checkout/dist "$context/"
    cp src/checkout/package.json src/checkout/yarn.lock "$context/"
    printf 'nodeLinker: node-modules\n' > "$context/.yarnrc.yml"
    (cd "$context"; node ../../.yarn/releases/yarn-4.11.0.cjs install --immutable; node ../../.yarn/releases/yarn-4.11.0.cjs workspaces focus --all --production)
    "$LAB_HOME/python/bin/python" - "$context/node_modules" <<'PY'
import pathlib, sys
native = list(pathlib.Path(sys.argv[1]).rglob('*.node'))
assert not native, 'Native Node addons found: install production dependencies in Linux before packaging: ' + str(native[:5])
PY
    recipe=checkout;;
  *) exit 2;;
esac
ref="localhost:5001/retail/$service:$tag"
docker build -f "learning/docker/$recipe.Dockerfile" -t "$ref" "$context"
docker push "$ref"
python3 - "$service" "$tag" <<'PY'
import urllib.request,json,sys
service,tag=sys.argv[1:]
r=urllib.request.urlopen(urllib.request.Request(f'http://127.0.0.1:5001/v2/retail/{service}/manifests/{tag}',method='HEAD',headers={'Accept':'application/vnd.docker.distribution.manifest.v2+json, application/vnd.oci.image.manifest.v1+json'}))
digest=r.headers['Docker-Content-Digest']; assert digest and digest.startswith('sha256:')
json.dump({'service':service,'image':f'localhost:5001/retail/{service}@{digest}'},open(f'reports/{service}-image.json','w'))
PY
