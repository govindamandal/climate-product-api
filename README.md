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
FRONTEND_BASE_URL=https://climate-product-web.vercel.app
EMAIL_PROVIDER=resend
RESEND_API_KEY=
EMAIL_FROM="Material Passport OS <onboarding@yourdomain.com>"
REDIS_URL=rediss://default:PASSWORD@HOST:PORT
ANALYTICS_CACHE_TTL_SECONDS=120
CLOUDFLARE_R2_ACCOUNT_ID=
CLOUDFLARE_R2_ACCESS_KEY_ID=
CLOUDFLARE_R2_SECRET_ACCESS_KEY=
CLOUDFLARE_R2_BUCKET=
CLOUDFLARE_R2_PUBLIC_BASE_URL=
```

`CLOUDFLARE_R2_PUBLIC_URL` is also supported as an alias for `CLOUDFLARE_R2_PUBLIC_BASE_URL`.

Use the bucket's public `r2.dev` URL or your custom domain for the public URL. Do not use the private S3 API endpoint:

```bash
# Correct examples
CLOUDFLARE_R2_PUBLIC_URL=https://pub-abc123.r2.dev
CLOUDFLARE_R2_PUBLIC_URL=https://assets.yourdomain.com

# Incorrect: this is the private S3 API endpoint and browser images will fail
CLOUDFLARE_R2_PUBLIC_URL=https://ACCOUNT_ID.r2.cloudflarestorage.com
```

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

## Email And Cache

Password reset and organization invite emails use Resend when `EMAIL_PROVIDER=resend` and `RESEND_API_KEY` are set. Without those values, delivery is skipped safely for local development.

Sustainability analytics are cached in Redis-compatible storage, such as Aiven for Valkey, using `REDIS_URL`. Product mutations invalidate the organization analytics cache.

## System Checks

- `/health`: API liveness.
- `/ready`: database and cache readiness report.

Responses also include `x-request-id` and `x-process-time-ms` headers.

## Validation

```bash
ruff check .
pytest
```
