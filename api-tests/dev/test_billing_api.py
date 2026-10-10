import os
import uuid

import httpx


BASE_URL = os.environ.get("BASE_URL", "").rstrip("/")


def client() -> httpx.Client:
    if not BASE_URL:
        raise RuntimeError("BASE_URL must point to the deployed billing-api service")
    return httpx.Client(base_url=BASE_URL, timeout=15.0, follow_redirects=True)


def test_invoice_payment_lifecycle() -> None:
    customer_id = uuid.uuid4().int % 1_000_000_000 + 1
    payload = {"customer_id": customer_id, "amount": "125.50", "currency": "usd"}

    with client() as api:
        created = api.post("/api/billing/", json=payload)
        assert created.status_code == 201, created.text
        invoice = created.json()
        invoice_id = invoice["id"]
        assert invoice["customer_id"] == customer_id
        assert invoice["amount"] == "125.50"
        assert invoice["currency"] == "USD"
        assert invoice["status"] == "PENDING"

        fetched = api.get(f"/api/billing/{invoice_id}")
        assert fetched.status_code == 200, fetched.text
        assert fetched.json()["id"] == invoice_id

        pending = api.get("/api/billing/", params={"status": "PENDING"})
        assert pending.status_code == 200, pending.text
        assert any(item["id"] == invoice_id for item in pending.json())

        paid = api.post(f"/api/billing/{invoice_id}/pay")
        assert paid.status_code == 200, paid.text
        assert paid.json()["status"] == "PAID"

        paid_again = api.post(f"/api/billing/{invoice_id}/pay")
        assert paid_again.status_code == 409, paid_again.text

        paid_invoices = api.get("/api/billing/", params={"status": "PAID"})
        assert paid_invoices.status_code == 200, paid_invoices.text
        assert any(item["id"] == invoice_id for item in paid_invoices.json())


def test_invoice_cancellation_lifecycle() -> None:
    with client() as api:
        created = api.post(
            "/api/billing/",
            json={"customer_id": 42, "amount": "10.00", "currency": "EUR"},
        )
        assert created.status_code == 201, created.text
        invoice_id = created.json()["id"]

        cancelled = api.post(f"/api/billing/{invoice_id}/cancel")
        assert cancelled.status_code == 200, cancelled.text
        assert cancelled.json()["status"] == "CANCELLED"

        pay_cancelled = api.post(f"/api/billing/{invoice_id}/pay")
        assert pay_cancelled.status_code == 409, pay_cancelled.text


def test_billing_api_rejects_invalid_requests() -> None:
    with client() as api:
        invalid = api.post(
            "/api/billing/",
            json={"customer_id": 0, "amount": -1, "currency": "US"},
        )
        assert invalid.status_code == 422, invalid.text

        unknown_status = api.get("/api/billing/", params={"status": "UNKNOWN"})
        assert unknown_status.status_code == 422, unknown_status.text

        unknown_invoice = api.post("/api/billing/999999/cancel")
        assert unknown_invoice.status_code == 404, unknown_invoice.text


def test_routed_openapi_contains_billing_routes() -> None:
    with client() as api:
        response = api.get("/api/billing/openapi.json")

    assert response.status_code == 200, response.text
    paths = response.json()["paths"]
    assert "/api/billing/" in paths
    assert "/api/billing/{invoice_id}" in paths
    assert "/api/billing/{invoice_id}/pay" in paths
    assert "/api/billing/{invoice_id}/cancel" in paths
