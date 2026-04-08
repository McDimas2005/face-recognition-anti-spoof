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

## Deferred

- S3/MinIO storage
- distributed background job orchestration
- hardened production proxy policy

