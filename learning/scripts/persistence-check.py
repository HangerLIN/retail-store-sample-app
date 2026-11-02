"""Admin-only disruptive checks: regular Pod deletion, never force deletion."""

import pathlib, json, subprocess, time, uuid, urllib.request
from smoke import forward, getjson, verify
from release import kubectl, obj

assert (
    subprocess.check_output(["kubectl", "config", "current-context"], text=True).strip()
    == "kind-retail-lab"
)


def restart(kind, name):
    old = obj("pod", name)["metadata"]["uid"]
    kubectl("delete", "pod", name, "--wait=true", "--timeout=120s")
    kubectl("wait", "pod/" + name, "--for=condition=Ready", "--timeout=240s")
    assert obj("pod", name)["metadata"]["uid"] != old


# The order proof is produced using the release identity before this admin check.
evidence = json.loads(pathlib.Path("reports/smoke.json").read_text())
customer = "retained-" + uuid.uuid4().hex
with forward("carts") as base:
    payload = {"itemId": evidence["productId"], "quantity": 1, "unitPrice": 100}
    request = urllib.request.Request(
        base + "/carts/" + customer + "/items",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=30) as r:
        r.read()
    before = getjson(base + "/carts/" + customer + "/items")
# A normal deletion waits for termination; StatefulSet preserves Pod identity.
restart("sts", "carts-dynamodb-0")
cartpods = json.loads(
    kubectl(
        "get",
        "pods",
        "-l",
        "app.kubernetes.io/name=carts,app.kubernetes.io/component=service",
        "-o",
        "json",
    )
)["items"]
for pod in cartpods:
    kubectl("delete", "pod", pod["metadata"]["name"], "--wait=true", "--timeout=120s")
kubectl("rollout", "status", "deployment/carts", "--timeout=240s")
with forward("carts") as base:
    assert getjson(base + "/carts/" + customer + "/items") == before, (
        "Cart lost on restart"
    )
restart("sts", "orders-postgresql-0")
with forward("orders") as base:
    for _ in range(30):
        try:
            orders = getjson(base + "/orders")
            break
        except Exception:
            time.sleep(1)
    assert evidence["orderId"] in json.dumps(orders), "Order lost on PostgreSQL restart"
restart("sts", "catalog-mysql-0")
restart("sts", "orders-rabbitmq-0")
# Reconnection can lag behind Pod Ready. Retest whole purchase with bounded retries.
for attempt in range(8):
    try:
        verify()
        break
    except Exception:
        if attempt == 7:
            raise
        time.sleep(5)
logs = kubectl("logs", "carts-dynamodb-0")
assert "database is locked" not in logs.lower()
print("Verified cart/order persistence and RabbitMQ reconnection")
