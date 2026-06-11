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

The intended public deployment shape is split by service:

- Host `apps/web` on Vercel as the public frontend.
- Host `apps/api` on a backend platform such as Railway, Render, Fly.io, or a VPS.
- Use managed PostgreSQL such as Neon, Supabase, Railway Postgres, or another hosted Postgres provider.
- Keep retained review/enrollment images on backend-local persistent storage for V1, or add object storage before retaining images at scale.

Do not deploy the whole stack as a Vercel-only app. The FastAPI API and PostgreSQL database need their own runtime.

### Vercel frontend settings

Use the repository root as the Vercel project root so npm workspaces can resolve `packages/shared`.

Recommended Vercel commands:

- Install command: `npm install`
- Build command: `npm run build:web`
- Output directory: `apps/web/.next`

Set this frontend environment variable in Vercel:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-api.example.com
```

### External API settings

Set the backend environment on the API host:

```env
APP_ENV=production
API_SECRET_KEY=<strong-random-secret>
API_DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:5432/<database>
API_CORS_ORIGINS=https://your-vercel-app.vercel.app,https://your-custom-domain.example.com
API_BOOTSTRAP_ADMIN_EMAIL=<initial-admin-email>
API_BOOTSTRAP_ADMIN_PASSWORD=<temporary-strong-password>
API_BOOTSTRAP_ADMIN_NAME=<initial-admin-name>
API_STORAGE_PATH=/app/data
```

Run `alembic upgrade head` as part of the backend release or startup command before starting `uvicorn`.

## Deferred

- S3/MinIO storage
- distributed background job orchestration
- hardened production proxy policy
