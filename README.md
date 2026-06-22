# Climate Product API

FastAPI backend for a multi-tenant climate product management platform. It supports tenant-scoped authentication, product lifecycle data, environmental records, Digital Product Passports, sustainability analytics, AI workflows, and Cloudflare R2 product image uploads.

## Stack

- Python 3.13
- FastAPI
- SQLAlchemy 2
- Alembic
- PostgreSQL
- Redis
- Pytest

## Local Setup

```bash
python -m pip install -e ".[dev]"
uvicorn app.main:app --reload
```

Seed demo data:

```bash
python -m app.seed
```

API docs are available at `http://localhost:8000/docs`.

## Product Image Storage

Product image uploads use Cloudflare R2 through its S3-compatible API. Configure:

```bash
CLOUDFLARE_R2_ACCOUNT_ID=
CLOUDFLARE_R2_ACCESS_KEY_ID=
CLOUDFLARE_R2_SECRET_ACCESS_KEY=
CLOUDFLARE_R2_BUCKET=
CLOUDFLARE_R2_PUBLIC_BASE_URL=
```

`CLOUDFLARE_R2_ENDPOINT_URL` is optional.

## Validation

```bash
ruff check .
pytest
```
