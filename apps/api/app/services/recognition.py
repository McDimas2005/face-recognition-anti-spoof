from __future__ import annotations

import io
from collections import defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile, status
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.domain import (
    AppSetting,
    AttendanceEvent,
    AttendanceSession,
    AttendanceSource,
    AttendanceStatus,
    FaceEmbedding,
    RecognitionAttempt,
    RecognitionOutcome,
    ReviewCase,
    ReviewReason,
    SessionAllowedPerson,
)
from app.providers.demo import assess_quality, crop_face, detector, embedder, index, liveness
from app.services.audit import write_audit_log
from app.services.settings import DEFAULT_RETENTION_POLICY


@dataclass
class CandidateFrame:
    timestamp: datetime
    person_id: str
    similarity: float
    second_score: float


class TemporalConsensusStore:
    def __init__(self) -> None:
        self._items: dict[str, list[CandidateFrame]] = defaultdict(list)

    def add(self, session_id: str, client_key: str, frame: CandidateFrame) -> list[CandidateFrame]:
        key = f"{session_id}:{client_key}"
        self._items[key].append(frame)
        cutoff = frame.timestamp - timedelta(seconds=settings.consensus_window_seconds)
        self._items[key] = [item for item in self._items[key] if item.timestamp >= cutoff]
        return self._items[key]

    def clear(self, session_id: str, client_key: str) -> None:
        self._items.pop(f"{session_id}:{client_key}", None)


consensus_store = TemporalConsensusStore()


def _read_upload(upload: UploadFile) -> tuple[bytes, np.ndarray]:
    content = upload.file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty frame upload")
    image = Image.open(io.BytesIO(content)).convert("RGB")
    return content, cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _get_policy(db: Session) -> dict:
    policy = db.get(AppSetting, "recognition_policy")
    if policy:
        return policy.value
    return {
        "similarity_threshold": settings.similarity_threshold,
        "commit_threshold": settings.commit_threshold,
        "ambiguity_margin": settings.ambiguity_margin,
        "liveness_threshold": settings.liveness_threshold,
        "consensus_frames": settings.consensus_frames,
        "consensus_window_seconds": settings.consensus_window_seconds,
    }


def _allowed_person_ids(db: Session, session_id: str) -> list[str]:
    allowed = db.scalars(select(SessionAllowedPerson.person_id).where(SessionAllowedPerson.session_id == session_id)).all()
    return list(allowed)


def _candidate_embeddings(db: Session, person_ids: list[str]) -> list[tuple[str, np.ndarray, bool]]:
    if not person_ids:
        embeddings = db.scalars(select(FaceEmbedding)).all()
    else:
        embeddings = db.scalars(select(FaceEmbedding).where(FaceEmbedding.person_id.in_(person_ids))).all()
    return [(embedding.person_id, np.array(embedding.vector, dtype=np.float32), embedding.is_centroid) for embedding in embeddings]


def _create_attempt(
    db: Session,
    *,
    session_id: str,
    client_key: str,
    outcome: RecognitionOutcome,
    face_count: int,
    quality_passed: bool,
    liveness_score: float | None,
    top_person_id: str | None,
    top_score: float | None,
    second_score: float | None,
    breakdown: dict,
    snapshot_path: str | None,
) -> RecognitionAttempt:
    attempt = RecognitionAttempt(
        session_id=session_id,
        client_key=client_key,
        outcome=outcome,
        face_count=face_count,
        quality_passed=quality_passed,
        liveness_score=liveness_score,
        top_person_id=top_person_id,
        top_score=top_score,
        second_score=second_score,
        breakdown=breakdown,
        snapshot_path=snapshot_path,
    )
    db.add(attempt)
    db.flush()
    return attempt


def _create_review_case(
    db: Session,
    *,
    attempt_id: str,
    session_id: str,
    reason: ReviewReason,
    proposed_person_id: str | None,
) -> ReviewCase:
    review = ReviewCase(
        attempt_id=attempt_id,
        session_id=session_id,
        reason=reason,
        proposed_person_id=proposed_person_id,
    )
    db.add(review)
    db.flush()
    return review


def _persist_snapshot(content: bytes, session_id: str, attempt_type: str, attempt_id: str) -> str:
    target = Path(settings.storage_path) / "review" / session_id / f"{attempt_type}-{attempt_id}.jpg"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return str(target)


def _attendance_status(session: AttendanceSession, observed_at: datetime) -> AttendanceStatus:
    late_boundary = session.starts_at + timedelta(minutes=session.late_after_minutes)
    return AttendanceStatus.on_time if observed_at <= late_boundary else AttendanceStatus.late


def evaluate_frame(
    db: Session,
    *,
    session_id: str,
    client_key: str,
    upload: UploadFile,
    actor_user_id: str | None = None,
) -> dict:
    session = db.get(AttendanceSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attendance session not found")

    now = datetime.now(UTC)
    if now < session.starts_at or now > session.ends_at:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Session is not active")

    policy = _get_policy(db)
    retention = db.get(AppSetting, "retention_policy")
    retention_policy = retention.value if retention else DEFAULT_RETENTION_POLICY
    content, image = _read_upload(upload)
    detections = detector.detect(image)

    if len(detections) == 0:
        attempt = _create_attempt(
            db,
            session_id=session_id,
            client_key=client_key,
            outcome=RecognitionOutcome.no_face,
            face_count=0,
            quality_passed=False,
            liveness_score=None,
            top_person_id=None,
            top_score=None,
            second_score=None,
            breakdown={"message": "No face detected"},
            snapshot_path=None,
        )
        return {"attempt": attempt}

    if len(detections) > 1:
        attempt = _create_attempt(
            db,
            session_id=session_id,
            client_key=client_key,
            outcome=RecognitionOutcome.multiple_faces_rejected,
            face_count=len(detections),
            quality_passed=False,
            liveness_score=None,
            top_person_id=None,
            top_score=None,
            second_score=None,
            breakdown={"message": "Multiple faces detected; attendance rejected"},
            snapshot_path=None,
        )
        _create_review_case(db, attempt_id=attempt.id, session_id=session_id, reason=ReviewReason.multiple_faces, proposed_person_id=None)
        return {"attempt": attempt}

    quality = assess_quality(image, detections[0])
    if not quality["passed"]:
        attempt = _create_attempt(
            db,
            session_id=session_id,
            client_key=client_key,
            outcome=RecognitionOutcome.quality_rejected,
            face_count=1,
            quality_passed=False,
            liveness_score=None,
            top_person_id=None,
            top_score=None,
            second_score=None,
            breakdown=quality,
            snapshot_path=None,
        )
        return {"attempt": attempt}

    face = crop_face(image, detections[0])
    liveness_score = liveness.score(face)
    if liveness_score < policy["liveness_threshold"]:
        attempt = _create_attempt(
            db,
            session_id=session_id,
            client_key=client_key,
            outcome=RecognitionOutcome.spoof_rejected,
            face_count=1,
            quality_passed=True,
            liveness_score=liveness_score,
            top_person_id=None,
            top_score=None,
            second_score=None,
            breakdown={"message": "Passive liveness threshold not met", **quality},
            snapshot_path=None,
        )
        if session.review_unknowns:
            _create_review_case(db, attempt_id=attempt.id, session_id=session_id, reason=ReviewReason.spoof, proposed_person_id=None)
        return {"attempt": attempt}

    probe = embedder.embed(face)
    person_ids = _allowed_person_ids(db, session_id)
    candidates = _candidate_embeddings(db, person_ids)
    ranked = index.score(probe, candidates) if candidates else []

    person_aggregates: dict[str, dict[str, float]] = {}
    for candidate in ranked:
        person_id = candidate["person_id"]
        current = person_aggregates.setdefault(person_id, {"sample_best": -1.0, "centroid": -1.0})
        if candidate["is_centroid"]:
            current["centroid"] = max(current["centroid"], candidate["similarity"])
        else:
            current["sample_best"] = max(current["sample_best"], candidate["similarity"])

    final_ranked = []
    for person_id, aggregate in person_aggregates.items():
        score = max(aggregate["sample_best"], 0.0) * 0.7 + max(aggregate["centroid"], 0.0) * 0.3
        final_ranked.append({"person_id": person_id, "score": score})
    final_ranked.sort(key=lambda item: item["score"], reverse=True)

    top = final_ranked[0] if final_ranked else None
    second = final_ranked[1] if len(final_ranked) > 1 else None
    top_score = top["score"] if top else None
    second_score = second["score"] if second else None
    margin = (top_score - second_score) if top_score is not None and second_score is not None else None

    if not top or top_score is None or top_score < policy["similarity_threshold"]:
        attempt = _create_attempt(
            db,
            session_id=session_id,
            client_key=client_key,
            outcome=RecognitionOutcome.unknown,
            face_count=1,
            quality_passed=True,
            liveness_score=liveness_score,
            top_person_id=top["person_id"] if top else None,
            top_score=top_score,
            second_score=second_score,
            breakdown={"message": "Unknown face", "margin": margin, **quality},
            snapshot_path=None,
        )
        if session.review_unknowns:
            snapshot_path = _persist_snapshot(content, session_id, "unknown", attempt.id) if retention_policy["retain_review_images"] else None
            attempt.snapshot_path = snapshot_path
            _create_review_case(
                db,
                attempt_id=attempt.id,
                session_id=session_id,
                reason=ReviewReason.unknown,
                proposed_person_id=top["person_id"] if top else None,
            )
        return {"attempt": attempt}

    if margin is not None and margin < policy["ambiguity_margin"]:
        attempt = _create_attempt(
            db,
            session_id=session_id,
            client_key=client_key,
            outcome=RecognitionOutcome.ambiguous,
            face_count=1,
            quality_passed=True,
            liveness_score=liveness_score,
            top_person_id=top["person_id"],
            top_score=top_score,
            second_score=second_score,
            breakdown={"message": "Identity margin too small", "margin": margin, **quality},
            snapshot_path=None,
        )
        if session.review_ambiguous:
            snapshot_path = _persist_snapshot(content, session_id, "ambiguous", attempt.id) if retention_policy["retain_review_images"] else None
            attempt.snapshot_path = snapshot_path
            _create_review_case(
                db,
                attempt_id=attempt.id,
                session_id=session_id,
                reason=ReviewReason.ambiguous,
                proposed_person_id=top["person_id"],
            )
        return {"attempt": attempt}

    window = consensus_store.add(
        session_id,
        client_key,
        CandidateFrame(timestamp=now, person_id=top["person_id"], similarity=top_score, second_score=second_score or 0.0),
    )
    matching_frames = [frame for frame in window if frame.person_id == top["person_id"] and frame.similarity >= policy["similarity_threshold"]]
    average_similarity = sum(frame.similarity for frame in matching_frames) / len(matching_frames)

    if len(matching_frames) < policy["consensus_frames"] or average_similarity < policy["commit_threshold"]:
        attempt = _create_attempt(
            db,
            session_id=session_id,
            client_key=client_key,
            outcome=RecognitionOutcome.candidate_tracking,
            face_count=1,
            quality_passed=True,
            liveness_score=liveness_score,
            top_person_id=top["person_id"],
            top_score=top_score,
            second_score=second_score,
            breakdown={
                "message": "Stable candidate observed but not committed",
                "matching_frames": len(matching_frames),
                "average_similarity": average_similarity,
                **quality,
            },
            snapshot_path=None,
        )
        return {"attempt": attempt}

    existing_event = db.scalar(
        select(AttendanceEvent).where(
            AttendanceEvent.session_id == session_id,
            AttendanceEvent.person_id == top["person_id"],
        )
    )
    if existing_event:
        consensus_store.clear(session_id, client_key)
        attempt = _create_attempt(
            db,
            session_id=session_id,
            client_key=client_key,
            outcome=RecognitionOutcome.duplicate,
            face_count=1,
            quality_passed=True,
            liveness_score=liveness_score,
            top_person_id=top["person_id"],
            top_score=top_score,
            second_score=second_score,
            breakdown={"message": "Duplicate attendance prevented", **quality},
            snapshot_path=None,
        )
        return {"attempt": attempt, "attendance_event": existing_event}

    attempt = _create_attempt(
        db,
        session_id=session_id,
        client_key=client_key,
        outcome=RecognitionOutcome.attendance_marked,
        face_count=1,
        quality_passed=True,
        liveness_score=liveness_score,
        top_person_id=top["person_id"],
        top_score=top_score,
        second_score=second_score,
        breakdown={
            "message": "Attendance committed",
            "matching_frames": len(matching_frames),
            "average_similarity": average_similarity,
            "liveness_note": "Passive liveness reduces spoofing risk; it does not guarantee spoof prevention.",
            **quality,
        },
        snapshot_path=None,
    )
    attendance = AttendanceEvent(
        session_id=session_id,
        person_id=top["person_id"],
        source=AttendanceSource.ai_confirmed,
        status=_attendance_status(session, now),
        recognized_at=now,
        recognition_attempt_id=attempt.id,
        created_by=actor_user_id,
    )
    db.add(attendance)
    db.flush()
    consensus_store.clear(session_id, client_key)
    write_audit_log(
        db,
        actor_user_id=actor_user_id,
        entity_type="attendance_event",
        entity_id=attendance.id,
        action="attendance_marked_ai",
        details={"session_id": session_id, "person_id": top["person_id"], "attempt_id": attempt.id},
    )
    return {"attempt": attempt, "attendance_event": attendance}

