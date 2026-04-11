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
    AttendanceEvent,
    AttendanceSession,
    AttendanceSource,
    AttendanceStatus,
    FaceEmbedding,
    RecognitionAttempt,
    RecognitionOutcome,
    ReviewCase,
    ReviewReason,
    Person,
    SessionAllowedPerson,
)
from app.providers.demo import assess_quality, crop_face, detector, index, liveness, supported_embedders
from app.services.audit import write_audit_log
from app.services.enrollment import compute_quality_score, serialize_face_box
from app.services.settings import DEFAULT_QUALITY_POLICY, get_quality_policy, get_recognition_policy, get_retention_policy


@dataclass
class CandidateFrame:
    timestamp: datetime
    person_id: str
    similarity: float
    second_score: float


class TemporalConsensusStore:
    def __init__(self) -> None:
        self._items: dict[str, list[CandidateFrame]] = defaultdict(list)

    def add(self, session_id: str, client_key: str, frame: CandidateFrame, *, window_seconds: int = settings.consensus_window_seconds) -> list[CandidateFrame]:
        key = f"{session_id}:{client_key}"
        self._items[key].append(frame)
        cutoff = frame.timestamp - timedelta(seconds=window_seconds)
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


def _allowed_person_ids(db: Session, session_id: str) -> list[str]:
    allowed = db.scalars(select(SessionAllowedPerson.person_id).where(SessionAllowedPerson.session_id == session_id)).all()
    return list(allowed)


def _person_name_map(db: Session, person_ids: list[str]) -> dict[str, str]:
    ids = list(dict.fromkeys(person_id for person_id in person_ids if person_id))
    if not ids:
        return {}
    rows = db.execute(select(Person.id, Person.full_name).where(Person.id.in_(ids))).all()
    return {person_id: full_name for person_id, full_name in rows}


def _candidate_embeddings(db: Session, person_ids: list[str]) -> list[tuple[str, np.ndarray, bool, str]]:
    if not person_ids:
        embeddings = db.scalars(select(FaceEmbedding).where(FaceEmbedding.is_active.is_(True))).all()
    else:
        embeddings = db.scalars(
            select(FaceEmbedding).where(
                FaceEmbedding.person_id.in_(person_ids),
                FaceEmbedding.is_active.is_(True),
            )
        ).all()
    return [
        (embedding.person_id, np.array(embedding.vector, dtype=np.float32), embedding.is_centroid, embedding.model_name)
        for embedding in embeddings
    ]


def _recognition_thresholds(policy: dict) -> dict:
    return {
        "similarity_threshold": round(float(policy["similarity_threshold"]), 4),
        "commit_threshold": round(float(policy["commit_threshold"]), 4),
        "ambiguity_margin": round(float(policy["ambiguity_margin"]), 4),
        "liveness_threshold": round(float(policy["liveness_threshold"]), 4),
        "consensus_frames": int(policy["consensus_frames"]),
        "consensus_window_seconds": int(policy["consensus_window_seconds"]),
    }


def _quality_thresholds(policy: dict) -> dict:
    merged_policy = {**DEFAULT_QUALITY_POLICY, **policy}
    return {
        "min_face_size": int(merged_policy["min_face_size"]),
        "min_brightness": round(float(merged_policy["min_brightness"]), 4),
        "max_brightness": round(float(merged_policy["max_brightness"]), 4),
        "blur_threshold": round(float(merged_policy["blur_threshold"]), 4),
        "max_yaw_score": round(float(merged_policy["max_yaw_score"]), 4),
        "max_occlusion_score": round(float(merged_policy["max_occlusion_score"]), 4),
    }


def _breakdown_context(policy: dict, quality_policy: dict) -> dict:
    return {
        "recognition_thresholds": _recognition_thresholds(policy),
        "quality_thresholds": _quality_thresholds(quality_policy),
    }


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

    policy = get_recognition_policy(db)
    quality_policy = get_quality_policy(db)
    retention_policy = get_retention_policy(db)
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
            breakdown={"message": "No face detected", **_breakdown_context(policy, quality_policy)},
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
            breakdown={
                "message": "Multiple faces detected; attendance rejected",
                "detected_faces": len(detections),
                **_breakdown_context(policy, quality_policy),
            },
            snapshot_path=None,
        )
        _create_review_case(db, attempt_id=attempt.id, session_id=session_id, reason=ReviewReason.multiple_faces, proposed_person_id=None)
        return {"attempt": attempt}

    face_breakdown = {
        "face_box": serialize_face_box(detections[0], image),
        "detector_confidence": round(float(detections[0].confidence), 4),
    }
    quality = assess_quality(image, detections[0], quality_policy)
    quality_score = compute_quality_score(quality, quality_policy)
    quality = {**quality, "quality_score": quality_score, **face_breakdown}
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
            breakdown={**quality, **_breakdown_context(policy, quality_policy)},
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
            breakdown={"message": "Passive liveness threshold not met", **quality, **_breakdown_context(policy, quality_policy)},
            snapshot_path=None,
        )
        if session.review_unknowns:
            _create_review_case(db, attempt_id=attempt.id, session_id=session_id, reason=ReviewReason.spoof, proposed_person_id=None)
        return {"attempt": attempt}

    person_ids = _allowed_person_ids(db, session_id)
    candidates = _candidate_embeddings(db, person_ids)
    ranked: list[dict] = []
    if candidates:
        candidates_by_model: dict[str, list[tuple[str, np.ndarray, bool]]] = defaultdict(list)
        for person_id, vector, is_centroid, model_name in candidates:
            candidates_by_model[model_name].append((person_id, vector, is_centroid))
        for model_name, model_candidates in candidates_by_model.items():
            model_embedder = supported_embedders.get(model_name)
            if not model_embedder:
                continue
            probe = model_embedder.embed(face)
            compatible_candidates = [
                (person_id, candidate_vector, is_centroid)
                for person_id, candidate_vector, is_centroid in model_candidates
                if candidate_vector.shape == probe.shape
            ]
            if not compatible_candidates:
                continue
            ranked.extend(
                {
                    **candidate,
                    "model_name": model_name,
                }
                for candidate in index.score(probe, compatible_candidates)
            )
        ranked.sort(key=lambda item: item["similarity"], reverse=True)

    person_aggregates: dict[str, dict[str, float]] = {}
    for candidate in ranked:
        person_id = candidate["person_id"]
        current = person_aggregates.setdefault(
            person_id,
            {"sample_best": -1.0, "centroid": -1.0, "best_similarity": -1.0, "best_model_name": ""},
        )
        if candidate["is_centroid"]:
            current["centroid"] = max(current["centroid"], candidate["similarity"])
        else:
            current["sample_best"] = max(current["sample_best"], candidate["similarity"])
        if candidate["similarity"] > current["best_similarity"]:
            current["best_similarity"] = candidate["similarity"]
            current["best_model_name"] = candidate["model_name"]

    final_ranked = []
    for person_id, aggregate in person_aggregates.items():
        score = max(aggregate["sample_best"], 0.0) * 0.7 + max(aggregate["centroid"], 0.0) * 0.3
        final_ranked.append({"person_id": person_id, "score": score, "model_name": aggregate["best_model_name"]})
    final_ranked.sort(key=lambda item: item["score"], reverse=True)
    person_names = _person_name_map(db, [item["person_id"] for item in final_ranked])
    candidate_scores = [
        {
            "person_id": candidate["person_id"],
            "person_name": person_names.get(candidate["person_id"]),
            "score": round(float(candidate["score"]), 4),
            "match_percent": round(float(candidate["score"]) * 100, 2),
            "model_name": candidate["model_name"],
        }
        for candidate in final_ranked[:5]
    ]

    top = final_ranked[0] if final_ranked else None
    second = final_ranked[1] if len(final_ranked) > 1 else None
    top_score = top["score"] if top else None
    second_score = second["score"] if second else None
    margin = (top_score - second_score) if top_score is not None and second_score is not None else None
    top_person_name = person_names.get(top["person_id"]) if top else None
    second_person_name = person_names.get(second["person_id"]) if second else None
    recognition_context = {
        "candidate_scores": candidate_scores,
        "top_person_name": top_person_name,
        "top_score_raw": round(float(top_score), 4) if top_score is not None else None,
        "second_person_id": second["person_id"] if second else None,
        "second_person_name": second_person_name,
        "second_score_raw": round(float(second_score), 4) if second_score is not None else None,
        "margin_raw": round(float(margin), 4) if margin is not None else None,
        **_breakdown_context(policy, quality_policy),
    }

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
            breakdown={
                "message": "Unknown face",
                "margin": margin,
                "match_percent": round(top_score * 100, 2) if top_score is not None else None,
                "top_model_name": top["model_name"] if top else None,
                **quality,
                **recognition_context,
            },
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
            breakdown={
                "message": "Identity margin too small",
                "margin": margin,
                "match_percent": round(top_score * 100, 2),
                "top_model_name": top["model_name"],
                **quality,
                **recognition_context,
            },
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
        window_seconds=int(policy["consensus_window_seconds"]),
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
                "match_percent": round(top_score * 100, 2),
                "top_model_name": top["model_name"],
                **quality,
                **recognition_context,
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
            breakdown={
                "message": "Duplicate attendance prevented",
                "match_percent": round(top_score * 100, 2),
                "top_model_name": top["model_name"],
                **quality,
                **recognition_context,
            },
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
            "match_percent": round(top_score * 100, 2),
            "top_model_name": top["model_name"],
            "liveness_note": "Passive liveness reduces spoofing risk; it does not guarantee spoof prevention.",
            **quality,
            **recognition_context,
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
