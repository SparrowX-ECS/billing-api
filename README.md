# SparrowX Labs Billing API

The Finance Platform team's lightweight invoice service, owned by Sophie Wilson. It uses Python 3.12+, FastAPI, SQLModel, and PostgreSQL.

## API contract

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/billing/` | Create an invoice (`customer_id`, `amount`, `currency`) |
| `GET` | `/api/billing/` | List invoices; optionally filter by `status` |
| `GET` | `/api/billing/{id}` | Retrieve an invoice |
| `POST` | `/api/billing/{id}/pay` | Mark a pending invoice as paid |
| `POST` | `/api/billing/{id}/cancel` | Cancel a pending invoice |

Invoices start as `PENDING` and can transition once to `PAID` or `CANCELLED`. Amounts must be positive with at most two decimal places; customer IDs must be positive; currency is a three-letter code and is returned uppercase. Missing invoices return `404`, invalid input returns `422`, invalid state transitions return `409`, and creation returns `201`.

## Local development

From this directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
pytest -q
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

The application reads `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USERNAME`, and `DB_PASSWORD` from the environment.

- OpenAPI UI: <http://localhost:8000/docs>
- OpenAPI JSON: <http://localhost:8000/openapi.json>
- Health: `GET /health` returns `{"status":"ok"}`
- Metrics: <http://localhost:8000/metrics>

## Docker

```bash
docker build -t billing-api .
docker run --rm --network sparrowx-local -p 8000:8000 \
  -e DB_HOST=local-customer-postgres-db \
  -e DB_PORT=5432 \
  -e DB_NAME=billingdb \
  -e DB_USERNAME=postgres \
  -e DB_PASSWORD=postgres \
  billing-api
```
