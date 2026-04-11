from types import SimpleNamespace

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user
from app.core.config import settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.domain import UserRole


def _setup_test_app(role: UserRole):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True, connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(
        id="test-user",
        role=role,
        is_active=True,
    )


def test_get_settings_exposes_all_threshold_groups_for_superadmin():
    _setup_test_app(UserRole.superadmin)

    try:
        with TestClient(app) as client:
            response = client.get("/api/settings")

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["recognition_policy"]["similarity_threshold"] == settings.similarity_threshold
        assert payload["quality_policy"]["min_face_size"] == settings.min_face_size
        assert payload["quality_policy"]["blur_threshold"] == settings.max_blur_score
        assert payload["can_edit_settings"] is True
        assert payload["can_edit_all"] is True
    finally:
        app.dependency_overrides.clear()


def test_admin_cannot_update_quality_thresholds():
    _setup_test_app(UserRole.admin)

    try:
        with TestClient(app) as client:
            response = client.put(
                "/api/settings",
                json={
                    "quality_policy": {
                        "min_face_size": 96,
                        "min_brightness": 30.0,
                        "max_brightness": 220.0,
                        "blur_threshold": 125.0,
                        "max_yaw_score": 0.45,
                        "max_occlusion_score": 0.5,
                    }
                },
            )

        assert response.status_code == 403, response.text
        assert response.json()["detail"] == "Only superadmins can update quality thresholds"
    finally:
        app.dependency_overrides.clear()


def test_superadmin_can_update_quality_thresholds():
    _setup_test_app(UserRole.superadmin)

    try:
        with TestClient(app) as client:
            response = client.put(
                "/api/settings",
                json={
                    "quality_policy": {
                        "min_face_size": 96,
                        "min_brightness": 32.0,
                        "max_brightness": 210.0,
                        "blur_threshold": 140.0,
                        "max_yaw_score": 0.42,
                        "max_occlusion_score": 0.48,
                    }
                },
            )

        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["quality_policy"]["min_face_size"] == 96
        assert payload["quality_policy"]["blur_threshold"] == 140.0
        assert payload["can_edit_all"] is True
    finally:
        app.dependency_overrides.clear()
