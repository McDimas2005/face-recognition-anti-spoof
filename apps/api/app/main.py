from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI
from fastapi import Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import router
from app.api.routes.health import APP_VERSION, health_payload
from app.core.config import settings
from app.core.logging import configure_logging
from app.db.session import create_all, seed_bootstrap_admin, seed_demo_accounts


@asynccontextmanager
async def lifespan(_: FastAPI):
    configure_logging()
    settings.validate_production_settings()
    create_all()
    seed_bootstrap_admin()
    seed_demo_accounts()
    yield


app = FastAPI(title=settings.app_name, version=APP_VERSION, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.middleware("http")
async def attach_request_id(request: Request, call_next):
    request_id = request.headers.get("x-request-id", str(uuid4()))
    response = await call_next(request)
    response.headers["x-request-id"] = request_id
    return response


@app.get("/")
def root() -> dict[str, str]:
    return {"service": settings.app_name, "docs": "/docs"}


@app.get("/health")
def root_health() -> dict[str, str]:
    return health_payload()
