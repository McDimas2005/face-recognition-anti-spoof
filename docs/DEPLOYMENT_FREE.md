# Free Portfolio Deployment

This guide deploys the portfolio version with only free, no-credit-card-required services:

- Frontend: Vercel Hobby, serving `apps/web`
- Backend: Hugging Face Spaces Docker CPU Basic, serving `apps/api`
- Database: Neon Free PostgreSQL
- Runtime file storage: disabled for durable image retention; embeddings and records live in PostgreSQL

The current detector, embedder, and passive liveness provider are demo/development-grade. This deployment is suitable for a portfolio demo, not production biometric security.

## Backend Space README Front Matter

Use this front matter in the Hugging Face Space `README.md`:

```yaml
---
title: Face Attendance API
emoji: 🧑‍💻
colorFrom: blue
colorTo: gray
sdk: docker
app_port: 7860
pinned: false
---
```

## 1. Create Neon Free PostgreSQL

1. Create a Neon project on the Free plan.
2. Create or use the default database.
3. Copy the pooled or direct connection string.
4. Use the SQLAlchemy/psycopg form:

```env
API_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require
```

The API also normalizes plain `postgres://` and `postgresql://` URLs to the installed `psycopg` driver, but the explicit `postgresql+psycopg://` format is recommended.

## 2. Create the Hugging Face Docker Space

1. Create a new Hugging Face Space.
2. Select **Docker** as the SDK.
3. Select free CPU Basic hardware.
4. Connect this repository or push the repository contents to the Space.
5. Keep the root `Dockerfile` in place. It is the Hugging Face backend Dockerfile. Local Docker Compose still uses `apps/api/Dockerfile`.

The root Dockerfile:

- uses `python:3.12-slim`
- installs OpenCV/headless runtime libraries
- copies only the API, Alembic migrations, and legacy OpenCV DNN detector assets
- installs API dependencies from `apps/api/pyproject.toml`
- runs `alembic upgrade head`
- starts `uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-7860}`

## 3. Configure Hugging Face Space Secrets

Add these as Space secrets or variables. Do not commit real values.

```env
API_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require
API_SECRET_KEY=replace-with-long-random-secret
API_BOOTSTRAP_ADMIN_EMAIL=admin@example.com
API_BOOTSTRAP_ADMIN_PASSWORD=replace-with-strong-password
API_BOOTSTRAP_ADMIN_NAME=System Admin
API_SEED_DEMO_ACCOUNTS=true
API_CORS_ORIGINS=https://your-vercel-app.vercel.app,http://localhost:3000
API_STORAGE_PATH=/tmp/face-attendance
API_RETAIN_ENROLLMENT_IMAGES=false
API_RETAIN_REVIEW_IMAGES=false
API_ENV=production
```

Use `API_SEED_DEMO_ACCOUNTS=true` for public portfolio demo deployments so visitors can log in without public sign-up. Use `false` for private or real deployments. Demo credentials are intentionally public and must not protect real data.

Generate a local secret with:

```bash
python scripts/generate-secret.py
```

After replacing placeholders in a local env file, check it with:

```bash
python scripts/check-deploy-env.py --env-file .env.production
```

Hugging Face sets `PORT` for Docker Spaces. The image defaults to `7860`, matching `app_port`.

Important storage behavior:

- Do not rely on Hugging Face free ephemeral disk for durable data.
- Enrollment embeddings, people, sessions, attempts, review cases, audit logs, and settings are stored in Neon.
- Raw enrollment image retention is disabled.
- Review image retention is disabled. If enabled later, those files are ephemeral unless object storage is added.

## 4. Deploy and Smoke Test the Backend

After the Space builds, open:

- `https://your-hf-space-subdomain.hf.space/health`
- `https://your-hf-space-subdomain.hf.space/docs`

Expected `/health` shape:

```json
{
  "status": "ok",
  "version": "0.1.0",
  "database": "ok"
}
```

If the app fails at startup, check Space logs first. The startup script fails fast when critical variables such as `API_DATABASE_URL`, `API_SECRET_KEY`, or `API_BOOTSTRAP_ADMIN_PASSWORD` are missing or still set to development placeholders.

## 5. Import the Frontend into Vercel

Use these Vercel settings:

- Framework Preset: Next.js
- Root Directory: `apps/web`
- Install Command: default `npm install`
- Build Command: default `npm run build`
- Output Directory: default `.next`

Set this Vercel environment variable:

```env
NEXT_PUBLIC_API_BASE_URL=https://your-hf-space-subdomain.hf.space
```

The frontend reads API calls from `NEXT_PUBLIC_API_BASE_URL` and falls back to `http://localhost:8000` only when the variable is not set for local development.

## 6. Update Backend CORS

After Vercel gives you a deployment URL, update the Hugging Face backend:

```env
API_CORS_ORIGINS=https://your-vercel-app.vercel.app,http://localhost:3000
```

Restart or rebuild the Space after changing secrets. Avoid hardcoding localhost as the only allowed origin in a public deployment.

## 7. End-to-End Smoke Test

Use this checklist:

- Backend `/health` returns `database: ok`
- Backend `/docs` opens
- Frontend login works with the bootstrap admin
- Create a person
- Enroll samples
- Create an attendance session
- Open live attendance
- Allow webcam access
- Exercise recognize, unknown, and review queue flow

The webcam page must be served over HTTPS for browser camera access. Vercel provides HTTPS automatically.

## Troubleshooting

### CORS Failure

Symptoms: browser console shows blocked requests or preflight errors.

Fix: set `API_CORS_ORIGINS` on Hugging Face to include the exact Vercel origin, for example:

```env
API_CORS_ORIGINS=https://your-vercel-app.vercel.app,http://localhost:3000
```

### OpenCV Import Failure

Symptoms: Space logs show `ImportError` for `cv2` or missing shared libraries.

Fix: rebuild the Space with the root Dockerfile. It installs the Linux libraries needed by OpenCV headless image processing.

### Alembic Migration Failure

Symptoms: Space logs fail at `alembic upgrade head`.

Fixes:

- Confirm `API_DATABASE_URL` points to Neon and not local Docker Compose host `db`.
- Confirm the password is URL-encoded if it contains special characters.
- Confirm the database user can create and alter tables.

### Neon SSL Issue

Symptoms: connection errors mention SSL or connection refused.

Fix: include `?sslmode=require` in the Neon URL:

```env
API_DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require
```

### Hugging Face Wrong Port or 503

Symptoms: Space builds but the app shows 503.

Fixes:

- Confirm Space README front matter has `sdk: docker` and `app_port: 7860`.
- Confirm logs show Uvicorn listening on `0.0.0.0` and port `7860` or Hugging Face's `$PORT`.
- Confirm the root Dockerfile is used by the Space.

### Vercel Wrong Root Directory

Symptoms: Vercel cannot find the Next.js app or builds the wrong package.

Fix: set Vercel Root Directory to `apps/web`. The web package has its own `package.json` and build script.

### Camera Not Available

Symptoms: browser refuses webcam access.

Fixes:

- Use the HTTPS Vercel URL, not an HTTP page.
- Allow camera permissions in the browser.
- Avoid embedding the app in a page that blocks camera permissions.

### Ephemeral File Storage Reset

Symptoms: review snapshot paths disappear after Hugging Face restarts.

Fix: this is expected on the free deployment. Keep `API_RETAIN_ENROLLMENT_IMAGES=false` and `API_RETAIN_REVIEW_IMAGES=false`. Durable V1 state is in Neon PostgreSQL; adding object storage is a future production-hardening step.

## Local Verification Commands

From the repository root:

```bash
docker compose up --build
npm run build:web
cd apps/api && python -m compileall app && pytest
cd apps/api && API_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/attendance alembic upgrade head
docker build -t face-attendance-api-hf -f Dockerfile .
```

For the Alembic command, use a reachable local or Neon PostgreSQL database URL.
