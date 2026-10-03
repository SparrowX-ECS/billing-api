# Billing API

Invoice and payment-state service for the fictional SparrowX SaaS platform. This demonstration workload shows how a database-backed billing service can be deployed independently to `dev` and `prod` on AWS ECS/Fargate.

## Service responsibilities

- Create and list invoices.
- Retrieve invoices and transition them to paid or cancelled states.
- Persist data in the dedicated private RDS database `billingdb`.
- Expose health and Prometheus-compatible metrics endpoints.

## API documentation

FastAPI documentation is available at `/docs` (Swagger UI), `/redoc` (ReDoc), and `/openapi.json` (OpenAPI schema). The main API prefix is `/api/billing`:

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/billing/` | Create an invoice |
| `GET` | `/api/billing/` | List invoices |
| `GET` | `/api/billing/{invoice_id}` | Retrieve an invoice |
| `POST` | `/api/billing/{invoice_id}/pay` | Mark an invoice paid |
| `POST` | `/api/billing/{invoice_id}/cancel` | Cancel an invoice |
| `GET` | `/health` | Container/target-group health check |
| `GET` | `/api/billing/health` | API smoke-test health check |
| `GET` | `/metrics` | Prometheus metrics |

## Runtime environment variables

| Variable | Required | Description |
| --- | --- | --- |
| `DB_HOST` | Yes | Private RDS PostgreSQL endpoint for `billingdb`. |
| `DB_PORT` | No | PostgreSQL port; defaults to `5432`. |
| `DB_NAME` | Yes | Database name, normally `billingdb`. |
| `DB_USERNAME` | Yes | Database username injected from the service secret. |
| `DB_PASSWORD` | Yes | Database password injected from the service secret. |
| `CORS_ALLOW_ORIGINS` | No | Comma-separated browser origins; defaults to local development origins. |

## Local development

```bash
python -m pip install -r requirements-dev.txt
pytest
uvicorn src.main:app --reload --port 8000
```

Open <http://localhost:8000/docs> after configuring the database variables.

## CI/CD cycle

Pull requests run Python/database tests, build one commit-SHA image, scan it with Trivy, and publish immutable metadata. A merge to `main` resolves and deploys that exact image to `dev`, runs the smoke test, and publishes the tag and digest as the production candidate.

The manually confirmed production workflow verifies the candidate digest, copies the same image from the `dev` ECR namespace to `prod`, deploys it, smoke-tests it, and publishes production metadata. This is **Build Once, Promote Many**; production is not rebuilt.

## Environments and deployment tracking

`dev` is automated from `main`; `prod` is promoted manually after successful development validation. Each has separate ECS resources, ECR namespace, parameter file, URL, SSM metadata path, and GitHub deployment history. See [`ecs-parameters-dev.yaml`](ecs-parameters-dev.yaml) and [`ecs-parameters-prod.yaml`](ecs-parameters-prod.yaml).

## Rollback options

### Git revert

Revert the source or deployment change and merge the revert. The standard pipeline will deploy the corrective commit.

### Quicker manual image rollback

1. Open **Deployments**, choose the `prod` environment, and open the desired previous deployment.
2. Copy its image tag.
3. Open **Actions → Manual Rollback Production To Selected Image Tag → Run workflow**.
4. Enter `ROLLBACK`, paste the tag, and run the workflow.

The selected image is redeployed and smoke-tested without rebuilding. ECS deployment circuit-breaker rollback is also enabled.

## Repository variables

| Variable | Description |
| --- | --- |
| `AWS_ACCOUNT_ID` | AWS account containing the platform resources. |
| `AWS_REGION` | AWS region used by the workflows. |
| `AWS_ROLE_NAME` | IAM role assumed through GitHub OIDC. |
| `DEV_BASE_URL` | Development smoke-test origin with protocol and domain only. |
| `DEV_DEPLOYED_PARAM_STORE_PATH` | SSM path for the last successful `dev` image. |
| `PROD_BASE_URL` | Production smoke-test origin with protocol and domain only. |
| `PROD_CANDIDATE_PARAM_STORE_PATH` | SSM path for the production candidate image. |
| `PROD_DEPLOYED_PARAM_STORE_PATH` | SSM path for the last successful `prod` image. |

The smoke-test workflow appends the service smoke-test path to each base URL.

## Container and deployment configuration

- Container port: `8000`.
- ALB path: `/api/billing/*`.
- Health check: `/health`.
- Smoke-test path: `/api/billing/health`.
- Database: enabled in both environments.

## License

This is a proprietary portfolio project. It is publicly viewable but not open source. All rights are reserved. See [LICENSE.md](LICENSE.md).
