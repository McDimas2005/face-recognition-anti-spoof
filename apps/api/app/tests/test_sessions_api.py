from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.domain import AuditLog, UserRole


def test_create_session_audit_log_serializes_datetime_fields():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="test-admin",
        role=UserRole.superadmin,
        is_active=True,
    )

    try:
        with TestClient(app) as client:
            starts_at = datetime.now(UTC) + timedelta(minutes=5)
            ends_at = starts_at + timedelta(hours=1)
            response = client.post(
                "/api/sessions",
                json={
                    "name": "CV Lab Attendance",
                    "description": "Regression coverage",
                    "starts_at": starts_at.isoformat(),
                    "ends_at": ends_at.isoformat(),
                    "late_after_minutes": 10,
                    "review_unknowns": True,
                    "review_ambiguous": True,
                    "allowed_person_ids": [],
                },
            )

        assert response.status_code == 201, response.text

        with TestingSessionLocal() as db:
            audit_logs = db.scalars(select(AuditLog).where(AuditLog.action == "session_created")).all()
            assert len(audit_logs) == 1
            assert audit_logs[0].details["starts_at"] == starts_at.isoformat()
            assert audit_logs[0].details["ends_at"] == ends_at.isoformat()
    finally:
        app.dependency_overrides.clear()

