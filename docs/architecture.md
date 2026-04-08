# Architecture

## V1 stack

- `apps/api`: FastAPI, SQLAlchemy, Alembic, PostgreSQL
- `apps/web`: Next.js App Router admin console
- `packages/shared`: shared TS enums and contracts
- `infra`: Compose and Caddy local reverse proxy

## Recognition flow

1. Browser captures webcam frame.
2. Frame is posted to `/api/recognition/evaluate`.
3. API runs:
   - face count gate
   - quality gates
   - passive liveness score
   - embedding extraction
   - exact cosine match
   - temporal consensus
   - duplicate prevention
4. API logs the attempt and, when policy passes, writes an attendance event.

## Product rules

- Multiple faces in frame are rejected immediately.
- One frame is never enough to mark attendance.
- Manual overrides are separate attendance sources and always audited.
- Enrollment remains incomplete until all five required diversity tags are satisfied.

