from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile, status
from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.domain import EnrollmentBatch, EnrollmentBatchStatus, EnrollmentSample, FaceEmbedding, Person, User, UserRole
from app.providers.base import FaceBox
from app.providers.demo import assess_quality, crop_face, detector, embedder
from app.services.settings import DEFAULT_QUALITY_POLICY, get_quality_policy

REQUIRED_DIVERSITY_TAGS = [
    "frontal_neutral",
    "left_yaw",
    "right_yaw",
    "expression",
    "lighting",
]
SELF_ENROLLMENT_TARGET_SAMPLE_COUNT = 100
HARD_QUALITY_REJECTIONS = {"invalid_crop"}


def serialize_face_box(box: FaceBox, image: np.ndarray) -> dict:
    return {
        "x": box.x,
        "y": box.y,
        "width": box.width,
        "height": box.height,
        "image_width": int(image.shape[1]),
        "image_height": int(image.shape[0]),
        "confidence": round(float(box.confidence), 4),
    }


def compute_quality_score(quality: dict, quality_policy: dict | None = None) -> float:
    policy = {**DEFAULT_QUALITY_POLICY, **(quality_policy or {})}
    face_size_score = min(float(quality.get("face_size", 0)) / max(float(policy["min_face_size"]) * 1.5, 1.0), 1.0)
    blur_score = min(float(quality.get("blur_score", 0.0)) / max(float(policy["blur_threshold"]) * 1.5, 1.0), 1.0)
    brightness = float(quality.get("brightness", 0.0))
    brightness_mid = (float(policy["min_brightness"]) + float(policy["max_brightness"])) / 2
    brightness_span = max((float(policy["max_brightness"]) - float(policy["min_brightness"])) / 2, 1.0)
    brightness_score = max(0.0, 1.0 - abs(brightness - brightness_mid) / brightness_span)
    yaw_score = max(0.0, 1.0 - float(quality.get("yaw_score", 1.0)) / max(float(policy["max_yaw_score"]), 0.001))
    occlusion_score = max(0.0, 1.0 - float(quality.get("occlusion_score", 1.0)) / max(float(policy["max_occlusion_score"]), 0.001))
    score = (face_size_score * 0.2) + (blur_score * 0.3) + (brightness_score * 0.2) + (yaw_score * 0.15) + (occlusion_score * 0.15)
    return round(max(0.0, min(score, 1.0)), 4)


def read_upload_to_bgr(upload: UploadFile) -> tuple[bytes, np.ndarray]:
    content = upload.file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload")
    image = Image.open(io.BytesIO(content)).convert("RGB")
    return content, cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def _resolve_storage_target(path_value: str) -> Path | None:
    storage_root = Path(settings.storage_path).resolve()
    target = Path(path_value)
    if not target.is_absolute():
        target = storage_root / target
    try:
        resolved_target = target.resolve()
        resolved_target.relative_to(storage_root)
    except ValueError:
        return None
    return resolved_target


def persist_image(content: bytes, relative_name: str) -> str:
    target = _resolve_storage_target(relative_name)
    if target is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid storage path")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return str(target)


def delete_persisted_image(storage_path: str | None) -> None:
    if not storage_path:
        return
    target = _resolve_storage_target(storage_path)
    if target is not None and target.exists():
        target.unlink()


def ensure_batch(db: Session, batch_id: str) -> EnrollmentBatch:
    batch = db.get(EnrollmentBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment batch not found")
    return batch


def ensure_person(db: Session, person_id: str) -> Person:
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    return person


def allow_quality_bypass(actor: User) -> bool:
    return settings.app_env != "production" or actor.role in {UserRole.superadmin, UserRole.admin}


def get_or_create_owned_person(db: Session, actor: User) -> tuple[Person, bool]:
    person = db.scalar(select(Person).where(Person.owner_user_id == actor.id))
    if person:
        return person, False

    person = Person(
        full_name=actor.full_name,
        notes="Auto-provisioned self-enrollment identity for authenticated user.",
        owner_user_id=actor.id,
        created_by=actor.id,
    )
    db.add(person)
    db.flush()
    return person, True


def next_capture_index(batch: EnrollmentBatch) -> int:
    existing_indexes = [sample.capture_index or 0 for sample in batch.samples]
    return (max(existing_indexes) if existing_indexes else 0) + 1


def derive_diversity_tag(batch: EnrollmentBatch) -> str:
    accepted_count = len([sample for sample in batch.samples if sample.quality_passed])
    if batch.target_sample_count <= len(REQUIRED_DIVERSITY_TAGS):
        return REQUIRED_DIVERSITY_TAGS[min(accepted_count, len(REQUIRED_DIVERSITY_TAGS) - 1)]
    bucket_size = max(1, batch.target_sample_count // len(REQUIRED_DIVERSITY_TAGS))
    bucket = min(accepted_count // bucket_size, len(REQUIRED_DIVERSITY_TAGS) - 1)
    return REQUIRED_DIVERSITY_TAGS[bucket]


def evaluate_batch(batch: EnrollmentBatch) -> tuple[dict, dict, EnrollmentBatchStatus]:
    tags_present = {sample.diversity_tag for sample in batch.samples if sample.quality_passed}
    accepted_samples = [sample for sample in batch.samples if sample.quality_passed]
    diversity_status = {tag: tag in tags_present for tag in REQUIRED_DIVERSITY_TAGS}

    if batch.is_self_enrollment:
        accepted_count = len(accepted_samples)
        quality_summary = {
            "accepted_samples": accepted_count,
            "total_samples": len(batch.samples),
            "target_sample_count": batch.target_sample_count,
            "remaining_samples": max(batch.target_sample_count - accepted_count, 0),
            "required_minimum_met": accepted_count >= batch.target_sample_count,
            "bypass_quality_validation": batch.bypass_quality_validation,
        }
        ready = accepted_count >= batch.target_sample_count
        return diversity_status, quality_summary, EnrollmentBatchStatus.ready if ready else EnrollmentBatchStatus.incomplete

    quality_summary = {
        "accepted_samples": len(accepted_samples),
        "total_samples": len(batch.samples),
        "required_minimum_met": len(accepted_samples) >= 5,
    }
    ready = quality_summary["required_minimum_met"] and all(diversity_status.values())
    return diversity_status, quality_summary, EnrollmentBatchStatus.ready if ready else EnrollmentBatchStatus.incomplete


def recompute_person_centroid(db: Session, person_id: str) -> None:
    sample_embeddings = db.scalars(
        select(FaceEmbedding).where(
            FaceEmbedding.person_id == person_id,
            FaceEmbedding.is_centroid.is_(False),
            FaceEmbedding.is_active.is_(True),
        )
    ).all()

    db.execute(
        delete(FaceEmbedding).where(
            FaceEmbedding.person_id == person_id,
            FaceEmbedding.is_centroid.is_(True),
        )
    )
    if not sample_embeddings:
        return

    embeddings_by_model: dict[str, list[FaceEmbedding]] = {}
    for embedding in sample_embeddings:
        embeddings_by_model.setdefault(embedding.model_name, []).append(embedding)

    for model_name, model_embeddings in embeddings_by_model.items():
        vectors = np.array([embedding.vector for embedding in model_embeddings], dtype=np.float32)
        centroid = np.mean(vectors, axis=0)
        norm = float(np.linalg.norm(centroid) or 1.0)
        centroid = centroid / norm

        db.add(
            FaceEmbedding(
                person_id=person_id,
                sample_id=None,
                model_name=model_name,
                vector=centroid.tolist(),
                norm=1.0,
                is_active=True,
                is_centroid=True,
            )
        )


def process_enrollment_sample(
    db: Session,
    batch: EnrollmentBatch,
    upload: UploadFile,
    diversity_tag: str,
    *,
    capture_index: int | None = None,
    bypass_quality_validation: bool = False,
    activate_immediately: bool = True,
) -> EnrollmentSample:
    if diversity_tag not in REQUIRED_DIVERSITY_TAGS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid diversity tag")

    content, image = read_upload_to_bgr(upload)
    detections = detector.detect(image)

    if len(detections) != 1:
        rejection_reason = "no_face_detected" if len(detections) == 0 else "multiple_faces_detected"
        sample = EnrollmentSample(
            batch=batch,
            diversity_tag=diversity_tag,
            quality_passed=False,
            quality_score=0.0,
            is_active=False,
            capture_index=capture_index,
            metadata_json={
                "face_count": len(detections),
                "quality_validation_passed": False,
                "quality_validation_bypassed": False,
            },
            rejection_reason=rejection_reason,
        )
        db.add(sample)
        db.flush()
        batch.diversity_status, batch.quality_summary, batch.status = evaluate_batch(batch)
        return sample

    quality_policy = get_quality_policy(db)
    quality = assess_quality(image, detections[0], quality_policy)
    quality_score = compute_quality_score(quality, quality_policy)
    actual_quality_passed = bool(quality["passed"])
    quality_bypassed = bypass_quality_validation and not actual_quality_passed and quality.get("reason") not in HARD_QUALITY_REJECTIONS
    accepted = actual_quality_passed or quality_bypassed

    metadata = {
        **quality,
        "face_box": serialize_face_box(detections[0], image),
        "detector_confidence": round(float(detections[0].confidence), 4),
        "quality_score": quality_score,
        "quality_validation_passed": actual_quality_passed,
        "quality_validation_bypassed": quality_bypassed,
    }

    sample = EnrollmentSample(
        batch=batch,
        diversity_tag=diversity_tag,
        quality_passed=accepted,
        quality_score=quality_score if accepted else quality_score,
        is_active=activate_immediately and accepted,
        capture_index=capture_index,
        metadata_json=metadata,
        rejection_reason=None if accepted else quality["reason"],
    )

    db.add(sample)
    db.flush()

    if accepted:
        face = crop_face(image, detections[0])
        if face.size == 0:
            sample.quality_passed = False
            sample.quality_score = 0.0
            sample.is_active = False
            sample.rejection_reason = "invalid_crop"
            sample.metadata_json["quality_validation_bypassed"] = False
            sample.metadata_json["quality_validation_passed"] = False
            batch.diversity_status, batch.quality_summary, batch.status = evaluate_batch(batch)
            return sample

        vector = embedder.embed(face)
        if settings.retain_enrollment_images:
            sample.storage_path = persist_image(content, f"enrollments/{batch.person_id}/{sample.id}.jpg")
        db.add(
            FaceEmbedding(
                person_id=batch.person_id,
                sample_id=sample.id,
                model_name=embedder.name,
                vector=vector.tolist(),
                norm=float(np.linalg.norm(vector) or 1.0),
                is_active=activate_immediately,
                is_centroid=False,
            )
        )
        if activate_immediately:
            recompute_person_centroid(db, batch.person_id)

    batch.diversity_status, batch.quality_summary, batch.status = evaluate_batch(batch)
    return sample


def summarize_batch(batch: EnrollmentBatch) -> dict:
    accepted_samples = [sample for sample in batch.samples if sample.quality_passed]
    last_sample = max(batch.samples, key=lambda sample: sample.capture_index or 0, default=None)
    return {
        "id": batch.id,
        "person_id": batch.person_id,
        "status": batch.status,
        "is_active": batch.is_active,
        "is_self_enrollment": batch.is_self_enrollment,
        "bypass_quality_validation": batch.bypass_quality_validation,
        "target_sample_count": batch.target_sample_count,
        "replacement_for_batch_id": batch.replacement_for_batch_id,
        "diversity_status": batch.diversity_status,
        "quality_summary": batch.quality_summary,
        "accepted_sample_count": len(accepted_samples),
        "total_sample_count": len(batch.samples),
        "remaining_sample_count": max(batch.target_sample_count - len(accepted_samples), 0),
        "last_sample_id": last_sample.id if last_sample else None,
        "created_at": batch.created_at,
        "finalized_at": batch.finalized_at,
    }


def archive_incomplete_self_batches(db: Session, person_id: str, exclude_batch_id: str | None = None) -> None:
    batches = db.scalars(
        select(EnrollmentBatch).where(
            EnrollmentBatch.person_id == person_id,
            EnrollmentBatch.is_self_enrollment.is_(True),
            EnrollmentBatch.status == EnrollmentBatchStatus.incomplete,
        )
    ).all()
    for batch in batches:
        if exclude_batch_id and batch.id == exclude_batch_id:
            continue
        batch.status = EnrollmentBatchStatus.archived
        batch.is_active = False


def create_self_enrollment_batch(db: Session, actor: User, *, bypass_quality_validation: bool) -> tuple[Person, EnrollmentBatch, bool]:
    person, created_person = get_or_create_owned_person(db, actor)
    archive_incomplete_self_batches(db, person.id)
    active_batch = db.scalar(
        select(EnrollmentBatch).where(
            EnrollmentBatch.person_id == person.id,
            EnrollmentBatch.is_active.is_(True),
        )
    )
    batch = EnrollmentBatch(
        person_id=person.id,
        status=EnrollmentBatchStatus.incomplete,
        is_active=False,
        is_self_enrollment=True,
        bypass_quality_validation=bypass_quality_validation,
        target_sample_count=SELF_ENROLLMENT_TARGET_SAMPLE_COUNT,
        replacement_for_batch_id=active_batch.id if active_batch else None,
        diversity_status={tag: False for tag in REQUIRED_DIVERSITY_TAGS},
        quality_summary={
            "accepted_samples": 0,
            "total_samples": 0,
            "target_sample_count": SELF_ENROLLMENT_TARGET_SAMPLE_COUNT,
            "remaining_samples": SELF_ENROLLMENT_TARGET_SAMPLE_COUNT,
            "required_minimum_met": False,
            "bypass_quality_validation": bypass_quality_validation,
        },
        created_by=actor.id,
    )
    db.add(batch)
    db.flush()
    return person, batch, created_person


def deactivate_active_enrollment(db: Session, person_id: str) -> None:
    active_batches = db.scalars(
        select(EnrollmentBatch).where(
            EnrollmentBatch.person_id == person_id,
            EnrollmentBatch.is_active.is_(True),
        )
    ).all()
    for batch in active_batches:
        batch.is_active = False
        batch.status = EnrollmentBatchStatus.archived

    active_samples = db.scalars(
        select(EnrollmentSample)
        .join(EnrollmentBatch, EnrollmentSample.batch_id == EnrollmentBatch.id)
        .where(
            EnrollmentBatch.person_id == person_id,
            EnrollmentSample.is_active.is_(True),
        )
    ).all()
    for sample in active_samples:
        sample.is_active = False

    active_embeddings = db.scalars(
        select(FaceEmbedding).where(
            FaceEmbedding.person_id == person_id,
            FaceEmbedding.is_active.is_(True),
        )
    ).all()
    for embedding in active_embeddings:
        embedding.is_active = False


def activate_self_enrollment_batch(db: Session, batch: EnrollmentBatch) -> EnrollmentBatch:
    batch.diversity_status, batch.quality_summary, batch.status = evaluate_batch(batch)
    if batch.status != EnrollmentBatchStatus.ready:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Self-enrollment batch requires {batch.target_sample_count} accepted samples before finalize",
        )

    deactivate_active_enrollment(db, batch.person_id)

    accepted_samples = [sample for sample in batch.samples if sample.quality_passed]
    for sample in accepted_samples:
        sample.is_active = True

    sample_ids = [sample.id for sample in accepted_samples]
    if sample_ids:
        embeddings = db.scalars(select(FaceEmbedding).where(FaceEmbedding.sample_id.in_(sample_ids))).all()
        for embedding in embeddings:
            embedding.is_active = True

    batch.is_active = True
    batch.finalized_at = datetime.now(UTC)
    recompute_person_centroid(db, batch.person_id)
    return batch


def delete_self_enrollment_sample(db: Session, batch: EnrollmentBatch, sample: EnrollmentSample) -> None:
    if batch.status != EnrollmentBatchStatus.incomplete:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only incomplete batches can be edited")
    delete_persisted_image(sample.storage_path)
    db.delete(sample)
    db.flush()
    batch.diversity_status, batch.quality_summary, batch.status = evaluate_batch(batch)
