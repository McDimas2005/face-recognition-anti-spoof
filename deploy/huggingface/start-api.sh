#!/usr/bin/env sh
set -eu

fail() {
  printf '%s\n' "Startup configuration error: $1" >&2
  exit 1
}

[ -n "${API_DATABASE_URL:-}" ] || fail "API_DATABASE_URL is required. Use a Neon PostgreSQL URL such as postgresql+psycopg://USER:PASSWORD@HOST/DB?sslmode=require."
[ -n "${API_SECRET_KEY:-}" ] || fail "API_SECRET_KEY is required. Generate a long random value and add it as a Hugging Face Space secret."
[ "${API_SECRET_KEY}" != "change-me" ] || fail "API_SECRET_KEY is still the development placeholder."
[ "${API_SECRET_KEY}" != "change-this-development-secret" ] || fail "API_SECRET_KEY is still the development placeholder."
[ -n "${API_BOOTSTRAP_ADMIN_PASSWORD:-}" ] || fail "API_BOOTSTRAP_ADMIN_PASSWORD is required for the initial admin account."
[ "${API_BOOTSTRAP_ADMIN_PASSWORD}" != "ChangeMe123!" ] || fail "API_BOOTSTRAP_ADMIN_PASSWORD is still the development placeholder."

mkdir -p "${API_STORAGE_PATH:-/tmp/face-attendance}"

alembic upgrade head
exec uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-7860}"
