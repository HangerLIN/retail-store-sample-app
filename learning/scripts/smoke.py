"""Real storefront purchase plus Orders readback, using only the release identity."""

import contextlib, subprocess, socket, time, urllib.request, urllib.parse, http.cookiejar, json, re, uuid, pathlib


@contextlib.contextmanager
def forward(service):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen(
        [
            "kubectl",
            "-n",
            "retail",
            "port-forward",
            "--address=127.0.0.1",
            "svc/" + service,
            f"{port}:80",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        for _ in range(60):
            if proc.poll() is not None:
                raise RuntimeError("port-forward failed for " + service)
            try:
                with socket.create_connection(("127.0.0.1", port), timeout=0.2):
                    break
            except OSError:
                time.sleep(0.25)
        else:
            raise RuntimeError("port-forward timeout")
        yield f"http://127.0.0.1:{port}"
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


def getjson(url):
    with urllib.request.urlopen(url, timeout=25) as r:
        return json.load(r)


def verify():
    topology = {}
    expected = {
        "catalog": {
            "persistenceProvider": "mysql",
            "databaseEndpoint": "catalog-mysql:3306",
        },
        "carts": {
            "persistenceProvider": "dynamodb",
            "dynamodbEndpoint": "http://carts-dynamodb:8000",
            "dynamodbTable": "Items",
        },
        "checkout": {
            "persistenceProvider": "redis",
            "databaseEndpoint": "redis://checkout-redis:6379",
        },
        "orders": {
            "persistenceProvider": "postgres",
            "databaseEndpoint": "orders-postgresql:5432",
            "messagingProvider": "rabbitmq",
            "messagingEndpoint": "orders-rabbitmq:5672",
        },
    }
    for service, values in expected.items():
        with forward(service) as base:
            topology[service] = getjson(base + "/topology")
        if not all(topology[service].get(k) == v for k, v in values.items()):
            raise RuntimeError("Runtime provider/endpoint drift: " + service)
    browser = urllib.request.build_opener(
        urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar())
    )

    def page(path, data=None):
        body = None if data is None else urllib.parse.urlencode(data).encode()
        with browser.open("http://127.0.0.1:8888" + path, body, timeout=45) as r:
            return r.read().decode()

    page("/")
    products = page("/catalog")
    match = re.search(r'href="/catalog/([a-zA-Z0-9-]+)"', products)
    assert match, "No products from Catalog/MySQL"
    product = match.group(1)
    cart = page("/cart", {"productId": product, "quantity": 1})
    assert product in cart, "Cart item missing"
    page("/checkout")
    marker = "smoke-" + uuid.uuid4().hex[:12]
    delivery = page(
        "/checkout",
        {
            "firstName": marker,
            "lastName": "Learning",
            "email": marker + "@example.invalid",
            "address1": "100 Demo Street",
            "city": "Anytown",
            "state": "CA",
            "zipCode": "11111",
        },
    )
    token = re.search(r'name="token"[^>]*value="([^"]+)"', delivery)
    if not token:
        token = re.search(r'value="([^"]+)"[^>]*name="token"', delivery)
    assert token, "Shipping did not reach delivery"
    page("/checkout/delivery", {"token": token.group(1)})
    order = page(
        "/checkout/payment",
        {
            "cardHolder": "Demo Learner",
            "cardNumber": "1234567890123456",
            "expiryDate": "01/35",
            "cvc": "123",
        },
    )
    match = re.search(r"Order ID</p>\s*<p[^>]*>\s*([^<\s]+)", order)
    assert match, "Checkout did not return order ID"
    orderid = match.group(1)
    with forward("orders") as base:
        orders = getjson(base + "/orders")
    evidence = json.dumps(orders)
    assert orderid in evidence and marker in evidence, (
        "New order missing from Orders/PostgreSQL"
    )
    result = {
        "orderId": orderid,
        "marker": marker,
        "productId": product,
        "topology": topology,
    }
    pathlib.Path("reports").mkdir(exist_ok=True)
    pathlib.Path("reports/smoke.json").write_text(json.dumps(result, indent=2))
    print("Verified storefront checkout and persisted order:", orderid)
    return result


if __name__ == "__main__":
    verify()
