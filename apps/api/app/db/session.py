from pathlib import Path

from sqlalchemy import select
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.core.security import hash_password
from app.db.base import Base
from app.models.domain import AppSetting, User, UserRole

connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, future=True, connect_args=connect_args)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


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
        if existing:
            return
        admin = User(
            email=settings.bootstrap_admin_email,
            full_name=settings.bootstrap_admin_name,
            role=UserRole.superadmin,
            password_hash=hash_password(settings.bootstrap_admin_password),
        )
        db.add(admin)
        db.add(
            AppSetting(
                key="recognition_policy",
                value={
                    "similarity_threshold": settings.similarity_threshold,
                    "commit_threshold": settings.commit_threshold,
                    "ambiguity_margin": settings.ambiguity_margin,
                    "liveness_threshold": settings.liveness_threshold,
                    "consensus_frames": settings.consensus_frames,
                    "consensus_window_seconds": settings.consensus_window_seconds,
                },
                updated_by=None,
            )
        )
        db.commit()

