from __future__ import annotations

import io
from pathlib import Path

import cv2
import numpy as np
from fastapi import HTTPException, UploadFile, status
from PIL import Image
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.domain import EnrollmentBatch, EnrollmentBatchStatus, EnrollmentSample, FaceEmbedding, Person
from app.providers.demo import assess_quality, crop_face, detector, embedder

REQUIRED_DIVERSITY_TAGS = [
    "frontal_neutral",
    "left_yaw",
    "right_yaw",
    "expression",
    "lighting",
]


def read_upload_to_bgr(upload: UploadFile) -> tuple[bytes, np.ndarray]:
    content = upload.file.read()
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Empty upload")
    image = Image.open(io.BytesIO(content)).convert("RGB")
    return content, cv2.cvtColor(np.array(image), cv2.COLOR_RGB2BGR)


def persist_image(content: bytes, relative_name: str) -> str:
    target = Path(settings.storage_path) / relative_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return str(target)


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


def evaluate_batch(batch: EnrollmentBatch) -> tuple[dict, dict, EnrollmentBatchStatus]:
    tags_present = {sample.diversity_tag for sample in batch.samples if sample.quality_passed}
    accepted_samples = [sample for sample in batch.samples if sample.quality_passed]
    diversity_status = {tag: tag in tags_present for tag in REQUIRED_DIVERSITY_TAGS}
    quality_summary = {
        "accepted_samples": len(accepted_samples),
        "total_samples": len(batch.samples),
        "required_minimum_met": len(accepted_samples) >= 5,
    }
    ready = quality_summary["required_minimum_met"] and all(diversity_status.values())
    return diversity_status, quality_summary, EnrollmentBatchStatus.ready if ready else EnrollmentBatchStatus.incomplete


def recompute_person_centroid(db: Session, person_id: str) -> None:
    sample_embeddings = db.scalars(
        select(FaceEmbedding).where(FaceEmbedding.person_id == person_id, FaceEmbedding.is_centroid.is_(False))
    ).all()
    if not sample_embeddings:
        return

    vectors = np.array([embedding.vector for embedding in sample_embeddings], dtype=np.float32)
    centroid = np.mean(vectors, axis=0)
    norm = float(np.linalg.norm(centroid) or 1.0)
    centroid = centroid / norm

    db.execute(delete(FaceEmbedding).where(FaceEmbedding.person_id == person_id, FaceEmbedding.is_centroid.is_(True)))
    db.add(
        FaceEmbedding(
            person_id=person_id,
            sample_id=None,
            model_name=embedder.name,
            vector=centroid.tolist(),
            norm=1.0,
            is_centroid=True,
        )
    )


def process_enrollment_sample(
    db: Session,
    batch: EnrollmentBatch,
    upload: UploadFile,
    diversity_tag: str,
) -> EnrollmentSample:
    if diversity_tag not in REQUIRED_DIVERSITY_TAGS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid diversity tag")

    content, image = read_upload_to_bgr(upload)
    detections = detector.detect(image)

    if len(detections) != 1:
        sample = EnrollmentSample(
            batch_id=batch.id,
            diversity_tag=diversity_tag,
            quality_passed=False,
            quality_score=0.0,
            metadata_json={"face_count": len(detections)},
            rejection_reason="exactly_one_face_required",
        )
        db.add(sample)
        db.flush()
        return sample

    quality = assess_quality(image, detections[0])
    sample = EnrollmentSample(
        batch_id=batch.id,
        diversity_tag=diversity_tag,
        quality_passed=bool(quality["passed"]),
        quality_score=1.0 if quality["passed"] else 0.0,
        metadata_json=quality,
        rejection_reason=quality["reason"],
    )

    if quality["passed"]:
        face = crop_face(image, detections[0])
        vector = embedder.embed(face)
        db.add(sample)
        db.flush()
        if settings.retain_enrollment_images:
            sample.storage_path = persist_image(content, f"enrollments/{batch.person_id}/{sample.id}.jpg")
        db.add(
            FaceEmbedding(
                person_id=batch.person_id,
                sample_id=sample.id,
                model_name=embedder.name,
                vector=vector.tolist(),
                norm=float(np.linalg.norm(vector) or 1.0),
                is_centroid=False,
            )
        )
        recompute_person_centroid(db, batch.person_id)
    else:
        db.add(sample)
        db.flush()

    batch.diversity_status, batch.quality_summary, batch.status = evaluate_batch(batch)
    return sample
