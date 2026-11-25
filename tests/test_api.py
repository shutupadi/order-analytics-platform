"""Integration tests: HTTP request -> Flask API -> services -> database -> JSON response."""


def test_full_order_flow(client):
    # New customer places an order, it ships, then gets delivered
    r = client.post("/customers", json={"name": "Riya", "email": "riya@example.com",
                                        "city": "Pune"})
    assert r.status_code == 201
    customer_id = r.get_json()["customer_id"]

    r = client.post("/orders", json={"customer_id": customer_id,
                                     "items": [{"product_id": 1, "quantity": 3}]})
    assert r.status_code == 201
    order = r.get_json()
    assert order["total_amount"] == 300

    products = {p["product_id"]: p for p in client.get("/products").get_json()}
    assert products[1]["stock"] == 7

    for status in ("SHIPPED", "DELIVERED"):
        r = client.patch(f"/orders/{order['order_id']}/status", json={"status": status})
        assert r.status_code == 200
    assert client.get(f"/orders/{order['order_id']}").get_json()["status"] == "DELIVERED"
    assert len(client.get("/orders?status=delivered").get_json()) == 1


def test_bad_requests_return_clear_errors(client):
    r = client.post("/orders", json={"customer_id": 1, "items": [{"product_id": 2, "quantity": 50}]})
    assert r.status_code == 400 and "Not enough stock" in r.get_json()["error"]

    assert client.post("/orders", json={"customer_id": 999, "items": []}).status_code == 400
    assert client.post("/customers", json={"name": "No email"}).status_code == 400
    assert client.post("/customers", json={"name": "Dup", "email": "test@example.com",
                                           "city": "Delhi"}).status_code == 400
    assert client.get("/orders/12345").status_code == 404
    assert client.get("/reports/does_not_exist").status_code == 404


def test_reports_endpoint(client):
    client.post("/orders", json={"customer_id": 1, "items": [{"product_id": 1, "quantity": 3},
                                                             {"product_id": 2, "quantity": 4}]})
    by_category = client.get("/reports/revenue_by_category").get_json()
    assert [(r["category"], float(r["revenue"])) for r in by_category] == \
        [("Electronics", 300.0), ("Fashion", 200.0)]
    assert float(by_category[0]["revenue_share_pct"]) == 60.0

    low = client.get("/inventory/low-stock").get_json()
    assert [r["sku"] for r in low] == ["SKU-B"]      # 5 - 4 = 1, at or below reorder level 3
