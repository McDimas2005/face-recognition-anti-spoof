from pathlib import Path

from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.models.domain import AppSetting, User, UserRole
from app.services.settings import DEFAULT_RECOGNITION_POLICY, LEGACY_DEMO_POLICY

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

DEMO_ACCOUNTS = (
    {
        "email": "demo.superadmin@example.com",
        "password": "DemoSuperadmin123!",
        "full_name": "Demo Super Admin",
        "role": UserRole.superadmin,
    },
    {
        "email": "demo.admin@example.com",
        "password": "DemoAdmin123!",
        "full_name": "Demo Admin",
        "role": UserRole.admin,
    },
    {
        "email": "demo.reviewer@example.com",
        "password": "DemoReviewer123!",
        "full_name": "Demo Reviewer",
        "role": UserRole.reviewer,
    },
    {
        "email": "demo.viewer@example.com",
        "password": "DemoViewer123!",
        "full_name": "Demo Viewer",
        "role": UserRole.viewer,
    },
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all() -> None:
    Path(settings.storage_path).mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


def seed_bootstrap_admin() -> None:
    with SessionLocal() as db:
        existing = db.scalar(select(User).where(User.email == settings.bootstrap_admin_email))
        if not existing:
            admin = User(
                email=settings.bootstrap_admin_email,
                full_name=settings.bootstrap_admin_name,
                role=UserRole.superadmin,
                password_hash=hash_password(settings.bootstrap_admin_password),
            )
            db.add(admin)

        recognition_policy = db.get(AppSetting, "recognition_policy")
        if not recognition_policy:
            db.add(
                AppSetting(
                    key="recognition_policy",
                    value=DEFAULT_RECOGNITION_POLICY,
                    updated_by=None,
                )
            )
        elif recognition_policy.value == LEGACY_DEMO_POLICY:
            recognition_policy.value = DEFAULT_RECOGNITION_POLICY

        db.commit()


def seed_demo_accounts(*, enabled: bool | None = None, session_factory=None) -> None:
    should_seed = settings.seed_demo_accounts if enabled is None else enabled
    if not should_seed:
        return

    factory = session_factory or SessionLocal
    with factory() as db:
        for account in DEMO_ACCOUNTS:
            existing = db.scalar(select(User).where(User.email == account["email"]))
            if existing:
                continue
            db.add(
                User(
                    email=account["email"],
                    full_name=account["full_name"],
                    role=account["role"],
                    password_hash=hash_password(account["password"]),
                    is_active=True,
                )
            )
        db.commit()
