# SparrowX Labs Billing API

The Finance Platform team's lightweight invoice service, owned by Sophie Wilson. It uses Python 3.12+, FastAPI, SQLModel, and SQLite.

## API contract

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/invoices` | Create an invoice (`customer_id`, `amount`, `currency`) |
| `GET` | `/invoices` | List invoices; optionally filter by `status` |
| `GET` | `/invoices/{id}` | Retrieve an invoice |
| `POST` | `/invoices/{id}/pay` | Mark a pending invoice as paid |
| `POST` | `/invoices/{id}/cancel` | Cancel a pending invoice |

Invoices start as `PENDING` and can transition once to `PAID` or `CANCELLED`. Amounts must be positive with at most two decimal places; customer IDs must be positive; currency is a three-letter code and is returned uppercase. Missing invoices return `404`, invalid input returns `422`, invalid state transitions return `409`, and creation returns `201`.

## Local development

From this directory:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
pytest -q
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

The default database is `./billing.db`. Set `BILLING_API_DATABASE_URL` to another SQLite URL, such as `sqlite:///./local.db`.

- OpenAPI UI: <http://localhost:8000/docs>
- OpenAPI JSON: <http://localhost:8000/openapi.json>
- Health: `GET /health` returns `{"status":"ok"}`
- Metrics: <http://localhost:8000/metrics>

## Docker

```bash
docker build -t billing-api .
docker run --rm -p 8000:8000 -v billing-api-data:/data billing-api
```

The container runs as a non-root user and persists SQLite data in `/data`.
