import pytest
from httpx import AsyncClient


@pytest.mark.anyio
async def test_health_and_openapi(client: AsyncClient) -> None:
    assert (await client.get("/health")).json() == {"status": "ok"}
    contract = (await client.get("/openapi.json")).json()
    assert {"/invoices", "/invoices/{invoice_id}", "/invoices/{invoice_id}/pay", "/invoices/{invoice_id}/cancel"} <= set(contract["paths"])
    assert "PENDING" in str(contract)


@pytest.mark.anyio
async def test_invoice_lifecycle_and_listing(client: AsyncClient) -> None:
    created = await client.post("/invoices", json={"customer_id": 42, "amount": "125.50", "currency": "usd"})
    assert created.status_code == 201
    invoice = created.json()
    assert invoice["status"] == "PENDING"
    assert invoice["currency"] == "USD"

    assert (await client.get(f"/invoices/{invoice['id']}")).json()["id"] == invoice["id"]
    assert (await client.get("/invoices?status=PENDING")).json()[0]["id"] == invoice["id"]
    paid = await client.post(f"/invoices/{invoice['id']}/pay")
    assert paid.status_code == 200
    assert paid.json()["status"] == "PAID"
    assert (await client.post(f"/invoices/{invoice['id']}/pay")).status_code == 409


@pytest.mark.anyio
async def test_cancellation_and_invalid_transitions(client: AsyncClient) -> None:
    invoice = (await client.post("/invoices", json={"customer_id": 7, "amount": 10, "currency": "EUR"})).json()
    cancelled = await client.post(f"/invoices/{invoice['id']}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "CANCELLED"
    assert (await client.post(f"/invoices/{invoice['id']}/pay")).status_code == 409
    assert (await client.post("/invoices/9999/cancel")).status_code == 404


@pytest.mark.anyio
async def test_validation_errors(client: AsyncClient) -> None:
    response = await client.post("/invoices", json={"customer_id": 0, "amount": -1, "currency": "US"})
    assert response.status_code == 422
    assert (await client.get("/invoices?status=UNKNOWN")).status_code == 422
