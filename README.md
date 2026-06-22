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

## Vercel Deployment

This repository includes a Vercel serverless entrypoint at `api/index.py`.

Set these required environment variables in Vercel:

```bash
DATABASE_URL=postgresql://USER:PASSWORD@HOST/DB?sslmode=require
JWT_SECRET_KEY=use-a-long-random-secret
CORS_ORIGINS=https://your-frontend.vercel.app,http://localhost:5173
```

Neon usually gives a `postgresql://...` URI. You can paste it directly into `DATABASE_URL`; the app converts it to SQLAlchemy's `postgresql+psycopg://...` driver internally.

Optional environment variables:

```bash
OPENAI_API_KEY=
ANTHROPIC_API_KEY=
CLOUDFLARE_R2_ACCOUNT_ID=
CLOUDFLARE_R2_ACCESS_KEY_ID=
CLOUDFLARE_R2_SECRET_ACCESS_KEY=
CLOUDFLARE_R2_BUCKET=
CLOUDFLARE_R2_PUBLIC_BASE_URL=
```

`CLOUDFLARE_R2_PUBLIC_URL` is also supported as an alias for `CLOUDFLARE_R2_PUBLIC_BASE_URL`.

After the backend deploys, set the frontend Vercel project variable:

```bash
VITE_API_URL=https://your-backend.vercel.app/api/v1
```

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
