#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."
source learning/scripts/environment.sh
mkdir -p reports
service="$1"
case "$service" in
  carts|orders|ui)
    folder="$service"; [ "$service" != carts ] || folder=cart
    (cd "src/$folder"; ./mvnw -s "../../learning/maven-settings.xml" --no-transfer-progress -Dapi.version="$DOCKER_API_VERSION" package -Dspring-boot.start.skip=true -Dspring-boot.stop.skip=true)
    "$LAB_HOME/python/bin/python" - "$folder" <<'PY'
import sys, glob, xml.etree.ElementTree as E
files=glob.glob('src/'+sys.argv[1]+'/target/surefire-reports/TEST-*.xml')
tests=[E.parse(f).getroot() for f in files]
assert sum(int(x.get('tests',0))-int(x.get('skipped',0)) for x in tests)>0,'No executed tests'
assert not any(int(x.get('failures',0))+int(x.get('errors',0)) for x in tests)
PY
    ;;
  catalog)
    (cd src/catalog; go test -count=1 -json ./... > ../../reports/catalog-tests.jsonl; CGO_ENABLED=0 GOOS=linux GOARCH=arm64 go build -o ../../reports/catalog main.go)
    "$LAB_HOME/python/bin/python" - <<'PY'
import json
assert any(x.get('Action')=='pass' and x.get('Test') for x in map(json.loads,open('reports/catalog-tests.jsonl'))),'No executed Go tests'
PY
    ;;
  checkout)
    (cd src/checkout; node ../../.yarn/releases/yarn-4.11.0.cjs install --immutable; node ../../.yarn/releases/yarn-4.11.0.cjs test:integration --runInBand --json --outputFile=../../reports/checkout-tests.json; node ../../.yarn/releases/yarn-4.11.0.cjs build)
    "$LAB_HOME/python/bin/python" - <<'PY'
import json
r=json.load(open('reports/checkout-tests.json'));assert r['numPassedTests']>0 and r['numFailedTests']==0 and r['success']
PY
    ;;
  *) echo "Unknown service: $service" >&2; exit 2;;
esac
