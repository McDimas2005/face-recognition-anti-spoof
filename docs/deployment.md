# Deployment

## Local production-like stack

Use Docker Compose with:

- PostgreSQL 16
- FastAPI API
- Next.js web app
- Caddy reverse proxy

## VPS/cloud path

V1 is designed to move cleanly to a Linux VPS by:

- replacing Compose-managed Postgres with managed Postgres if desired
- mounting persistent API storage for retained review snapshots
- setting strong JWT secrets and admin credentials through environment variables
- terminating TLS at the reverse proxy or external load balancer

## Public deployment path

The recommended zero-cost portfolio deployment is documented in
[Free Portfolio Deployment](DEPLOYMENT_FREE.md):

- Host `apps/web` on Vercel Hobby as the public HTTPS frontend.
- Host the FastAPI backend on Hugging Face Spaces Docker CPU Basic.
- Use Neon Free PostgreSQL for durable state.
- Disable raw enrollment/review image retention unless object storage is added later.

Do not deploy the whole stack as a Vercel-only app. The FastAPI API and PostgreSQL database need their own runtime.

### Vercel frontend settings

For the free portfolio path, use `apps/web` as the Vercel project root.

Recommended Vercel commands:

- Install command: default `npm install`
- Build command: default `npm run build`
- Output directory: default `.next`

Set this frontend environment variable in Vercel:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-hf-space-subdomain.hf.space
```

### External API settings

Set the backend environment on the API host:

```env
API_ENV=production
API_SECRET_KEY=<strong-random-secret>
API_DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>/<database>?sslmode=require
API_CORS_ORIGINS=https://your-vercel-app.vercel.app,https://your-custom-domain.example.com
API_BOOTSTRAP_ADMIN_EMAIL=<initial-admin-email>
API_BOOTSTRAP_ADMIN_PASSWORD=<temporary-strong-password>
API_BOOTSTRAP_ADMIN_NAME=<initial-admin-name>
API_STORAGE_PATH=/tmp/face-attendance
API_RETAIN_ENROLLMENT_IMAGES=false
API_RETAIN_REVIEW_IMAGES=false
```

Run `alembic upgrade head` as part of the backend release or startup command before starting `uvicorn`.

## Deferred

- S3/MinIO storage
- distributed background job orchestration
- hardened production proxy policy
