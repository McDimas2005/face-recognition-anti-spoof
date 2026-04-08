# Setup

## Local prerequisites

- Python 3.12
- Node.js 20+
- Docker + Docker Compose for the full local stack

## Option A: Docker Compose

1. Copy `.env.example` to `.env`.
2. Run `docker compose up --build`.
3. Open:
   - web: `http://localhost:3000`
   - api docs: `http://localhost:8000/docs`
   - reverse proxy: `http://localhost`

## Option B: Local processes

1. Copy `.env.example` to `.env`.
2. Install API deps:
   - `make api-install`
3. Install web deps:
   - `make web-install`
4. Run PostgreSQL locally and set `API_DATABASE_URL`.
5. Start API:
   - `make api-dev`
6. Start web:
   - `make web-dev`

## Default admin

- email: `admin@example.com`
- password: `ChangeMe123!`

Change these immediately outside development.

