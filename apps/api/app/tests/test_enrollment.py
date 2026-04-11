from __future__ import annotations

import io
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.domain import AuditLog, EnrollmentBatch, EnrollmentBatchStatus, EnrollmentSample, FaceEmbedding, Person, User, UserRole
from app.services import enrollment as enrollment_service
from app.services.recognition import _candidate_embeddings


@pytest.fixture()
def enrollment_test_env(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True, connect_args={"check_same_thread": False})
    testing_session_local = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    current_user: dict[str, User | None] = {"value": None}

    def override_get_db():
        db = testing_session_local()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: current_user["value"]

    pipeline_state = {
        "face_count": 1,
        "quality_passed": True,
        "quality_reason": None,
        "embedding_vector": np.array([1.0, 0.0, 0.0], dtype=np.float32),
    }

    def fake_detect(_image):
        return [
            SimpleNamespace(x=0, y=0, width=128, height=128, confidence=0.9)
            for _ in range(pipeline_state["face_count"])
        ]

    def fake_assess_quality(_image, _detection):
        return {
            "passed": pipeline_state["quality_passed"],
            "reason": pipeline_state["quality_reason"],
            "face_size": 128,
            "blur_score": 256.0,
            "brightness": 128.0,
            "yaw_score": 0.1,
            "occlusion_score": 0.1,
        }

    class FakeEmbedder:
        name = "test-embedder"

        def embed(self, _image):
            return pipeline_state["embedding_vector"].copy()

    monkeypatch.setattr(enrollment_service.detector, "detect", fake_detect)
    monkeypatch.setattr(enrollment_service, "assess_quality", fake_assess_quality)
    monkeypatch.setattr(enrollment_service, "crop_face", lambda _image, _detection: np.ones((128, 128, 3), dtype=np.uint8))
    monkeypatch.setattr(enrollment_service, "embedder", FakeEmbedder())

    try:
        with TestClient(app) as client:
            yield client, testing_session_local, current_user, pipeline_state
    finally:
        app.dependency_overrides.clear()


def _image_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (200, 200), color=(96, 128, 160)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _upload_frame(client: TestClient, batch_id: str):
    return client.post(
        "/api/me/enrollment/live/frame",
        data={"batch_id": batch_id},
        files={"image": ("frame.jpg", _image_bytes(), "image/jpeg")},
    )


def _create_user(db, *, user_id: str, email: str, full_name: str, role: UserRole) -> User:
    user = User(
        id=user_id,
        email=email,
        full_name=full_name,
        password_hash="not-used",
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def test_evaluate_batch_requires_all_diversity_tags_and_minimum_count():
    samples = [
        SimpleNamespace(quality_passed=True, diversity_tag="frontal_neutral"),
        SimpleNamespace(quality_passed=True, diversity_tag="left_yaw"),
        SimpleNamespace(quality_passed=True, diversity_tag="right_yaw"),
        SimpleNamespace(quality_passed=True, diversity_tag="expression"),
        SimpleNamespace(quality_passed=True, diversity_tag="lighting"),
    ]
    batch = SimpleNamespace(samples=samples, is_self_enrollment=False, target_sample_count=5)

    diversity_status, quality_summary, status = enrollment_service.evaluate_batch(batch)

    assert all(diversity_status.values())
    assert quality_summary["accepted_samples"] == 5
    assert status == EnrollmentBatchStatus.ready


def test_self_enrollment_status_provisions_owned_person_once(enrollment_test_env):
    client, session_local, current_user, _ = enrollment_test_env
    with session_local() as db:
        user = _create_user(db, user_id="user-1", email="user1@example.com", full_name="User One", role=UserRole.viewer)
    current_user["value"] = user

    response = client.get("/api/me/enrollment/live")
    assert response.status_code == 200, response.text
    payload = response.json()

    assert payload["person"]["owner_user_id"] == user.id
    assert payload["draft_batch"] is None
    assert payload["active_batch"] is None
    assert payload["target_sample_count"] == 100

    with session_local() as db:
        people = db.scalars(select(Person).where(Person.owner_user_id == user.id)).all()
        audit_logs = db.scalars(select(AuditLog).where(AuditLog.action == "self_enrollment_person_provisioned")).all()
        assert len(people) == 1
        assert len(audit_logs) == 1


def test_self_enrollment_is_limited_to_logged_in_users_own_batch(enrollment_test_env):
    client, session_local, current_user, _ = enrollment_test_env
    with session_local() as db:
        user_1 = _create_user(db, user_id="user-1", email="user1@example.com", full_name="User One", role=UserRole.viewer)
        user_2 = _create_user(db, user_id="user-2", email="user2@example.com", full_name="User Two", role=UserRole.viewer)

    current_user["value"] = user_1
    start_response = client.post("/api/me/enrollment/live/start", json={"bypass_quality_validation": False})
    assert start_response.status_code == 201, start_response.text
    batch_id = start_response.json()["batch"]["id"]

    current_user["value"] = user_2
    response = _upload_frame(client, batch_id)

    assert response.status_code == 404


def test_self_enrollment_replacement_archives_previous_active_set_and_refreshes_embeddings(enrollment_test_env):
    client, session_local, current_user, pipeline_state = enrollment_test_env
    with session_local() as db:
        user = _create_user(db, user_id="user-1", email="user1@example.com", full_name="User One", role=UserRole.admin)
    current_user["value"] = user

    first_batch = client.post("/api/me/enrollment/live/start", json={"bypass_quality_validation": False}).json()["batch"]
    for _ in range(100):
        response = _upload_frame(client, first_batch["id"])
        assert response.status_code == 200, response.text
        assert response.json()["accepted"] is True

    finalize_response = client.post(
        "/api/me/enrollment/live/finalize",
        json={"batch_id": first_batch["id"], "confirm_replace": False},
    )
    assert finalize_response.status_code == 200, finalize_response.text

    pipeline_state["embedding_vector"] = np.array([0.0, 1.0, 0.0], dtype=np.float32)
    second_batch = client.post("/api/me/enrollment/live/start", json={"bypass_quality_validation": False}).json()["batch"]
    for _ in range(100):
        response = _upload_frame(client, second_batch["id"])
        assert response.status_code == 200, response.text
        assert response.json()["accepted"] is True

    finalize_response = client.post(
        "/api/me/enrollment/live/finalize",
        json={"batch_id": second_batch["id"], "confirm_replace": True},
    )
    assert finalize_response.status_code == 200, finalize_response.text

    with session_local() as db:
        person = db.scalar(select(Person).where(Person.owner_user_id == user.id))
        assert person is not None

        first_batch_db = db.get(EnrollmentBatch, first_batch["id"])
        second_batch_db = db.get(EnrollmentBatch, second_batch["id"])
        assert first_batch_db is not None
        assert second_batch_db is not None
        assert first_batch_db.is_active is False
        assert first_batch_db.status == EnrollmentBatchStatus.archived
        assert second_batch_db.is_active is True
        assert second_batch_db.status == EnrollmentBatchStatus.ready

        active_samples = db.scalars(
            select(EnrollmentSample)
            .join(EnrollmentBatch, EnrollmentSample.batch_id == EnrollmentBatch.id)
            .where(EnrollmentBatch.person_id == person.id, EnrollmentSample.is_active.is_(True))
        ).all()
        assert len(active_samples) == 100
        assert {sample.batch_id for sample in active_samples} == {second_batch["id"]}

        active_embeddings = db.scalars(
            select(FaceEmbedding).where(
                FaceEmbedding.person_id == person.id,
                FaceEmbedding.is_active.is_(True),
            )
        ).all()
        assert len(active_embeddings) == 101
        assert len([embedding for embedding in active_embeddings if embedding.is_centroid]) == 1
        assert all(
            embedding.sample_id is None or embedding.sample_id in {sample.id for sample in active_samples}
            for embedding in active_embeddings
        )

        ranked_candidates = _candidate_embeddings(db, [person.id])
        assert len(ranked_candidates) == 101


def test_self_enrollment_enforces_100_photo_cap(enrollment_test_env):
    client, session_local, current_user, _ = enrollment_test_env
    with session_local() as db:
        user = _create_user(db, user_id="user-1", email="user1@example.com", full_name="User One", role=UserRole.viewer)
    current_user["value"] = user

    batch = client.post("/api/me/enrollment/live/start", json={"bypass_quality_validation": False}).json()["batch"]
    for _ in range(100):
        response = _upload_frame(client, batch["id"])
        assert response.status_code == 200, response.text

    response = _upload_frame(client, batch["id"])
    assert response.status_code == 400
    assert "target sample count" in response.text


def test_quality_bypass_is_explicit_and_multi_face_or_no_face_still_reject(enrollment_test_env):
    client, session_local, current_user, pipeline_state = enrollment_test_env
    with session_local() as db:
        user = _create_user(db, user_id="user-1", email="user1@example.com", full_name="User One", role=UserRole.admin)
    current_user["value"] = user

    batch = client.post("/api/me/enrollment/live/start", json={"bypass_quality_validation": True}).json()["batch"]

    pipeline_state["quality_passed"] = False
    pipeline_state["quality_reason"] = "image_too_blurry"
    response = _upload_frame(client, batch["id"])
    assert response.status_code == 200, response.text
    assert response.json()["accepted"] is True
    assert response.json()["sample"]["metadata_json"]["quality_validation_bypassed"] is True

    pipeline_state["face_count"] = 0
    response = _upload_frame(client, batch["id"])
    assert response.status_code == 200, response.text
    assert response.json()["accepted"] is False
    assert response.json()["sample"]["rejection_reason"] == "no_face_detected"

    pipeline_state["face_count"] = 2
    response = _upload_frame(client, batch["id"])
    assert response.status_code == 200, response.text
    assert response.json()["accepted"] is False
    assert response.json()["sample"]["rejection_reason"] == "multiple_faces_detected"

    with session_local() as db:
        logs = db.scalars(
            select(AuditLog).where(
                AuditLog.action.in_(["self_enrollment_started", "self_enrollment_frame_processed"])
            )
        ).all()
        assert any(log.details.get("bypass_quality_validation") is True for log in logs)


def test_low_quality_single_face_is_rejected_when_bypass_is_disabled(enrollment_test_env):
    client, session_local, current_user, pipeline_state = enrollment_test_env
    with session_local() as db:
        user = _create_user(db, user_id="user-1", email="user1@example.com", full_name="User One", role=UserRole.viewer)
    current_user["value"] = user

    batch = client.post("/api/me/enrollment/live/start", json={"bypass_quality_validation": False}).json()["batch"]
    pipeline_state["quality_passed"] = False
    pipeline_state["quality_reason"] = "image_too_blurry"

    response = _upload_frame(client, batch["id"])

    assert response.status_code == 200, response.text
    assert response.json()["accepted"] is False
    assert response.json()["sample"]["rejection_reason"] == "image_too_blurry"


def test_finalize_writes_replacement_audit_log(enrollment_test_env):
    client, session_local, current_user, _ = enrollment_test_env
    with session_local() as db:
        user = _create_user(db, user_id="user-1", email="user1@example.com", full_name="User One", role=UserRole.admin)
    current_user["value"] = user

    batch = client.post("/api/me/enrollment/live/start", json={"bypass_quality_validation": True}).json()["batch"]
    for _ in range(100):
        response = _upload_frame(client, batch["id"])
        assert response.status_code == 200, response.text

    finalize_response = client.post(
        "/api/me/enrollment/live/finalize",
        json={"batch_id": batch["id"], "confirm_replace": False},
    )
    assert finalize_response.status_code == 200, finalize_response.text

    with session_local() as db:
        audit_log = db.scalar(select(AuditLog).where(AuditLog.action == "self_enrollment_replaced"))
        assert audit_log is not None
        assert audit_log.details["bypass_quality_validation"] is True
        assert audit_log.details["active_sample_count"] == 100
