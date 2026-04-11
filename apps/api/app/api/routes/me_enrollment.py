from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.domain import EnrollmentBatch, EnrollmentBatchStatus, EnrollmentSample
from app.schemas.self_enrollment import (
    OwnedPersonSummary,
    SelfEnrollmentFinalizeRequest,
    SelfEnrollmentFinalizeResponse,
    SelfEnrollmentFrameResponse,
    SelfEnrollmentRetakeResponse,
    SelfEnrollmentStartRequest,
    SelfEnrollmentStartResponse,
    SelfEnrollmentStatusResponse,
)
from app.services.audit import write_audit_log
from app.services.enrollment import (
    SELF_ENROLLMENT_TARGET_SAMPLE_COUNT,
    activate_self_enrollment_batch,
    allow_quality_bypass,
    create_self_enrollment_batch,
    delete_self_enrollment_sample,
    derive_diversity_tag,
    get_or_create_owned_person,
    next_capture_index,
    process_enrollment_sample,
    summarize_batch,
)

router = APIRouter()


def _person_summary(person) -> OwnedPersonSummary:
    return OwnedPersonSummary(
        id=person.id,
        full_name=person.full_name,
        owner_user_id=person.owner_user_id,
    )


def _load_active_batch(db: Session, person_id: str) -> EnrollmentBatch | None:
    return db.scalar(
        select(EnrollmentBatch)
        .where(
            EnrollmentBatch.person_id == person_id,
            EnrollmentBatch.is_active.is_(True),
        )
        .options(selectinload(EnrollmentBatch.samples))
        .order_by(EnrollmentBatch.created_at.desc())
    )


def _load_draft_batch(db: Session, person_id: str) -> EnrollmentBatch | None:
    return db.scalar(
        select(EnrollmentBatch)
        .where(
            EnrollmentBatch.person_id == person_id,
            EnrollmentBatch.is_self_enrollment.is_(True),
            EnrollmentBatch.status == EnrollmentBatchStatus.incomplete,
        )
        .options(selectinload(EnrollmentBatch.samples))
        .order_by(EnrollmentBatch.created_at.desc())
    )


def _load_owned_self_batch(db: Session, actor_id: str, batch_id: str) -> EnrollmentBatch:
    batch = db.scalar(
        select(EnrollmentBatch)
        .where(EnrollmentBatch.id == batch_id)
        .options(selectinload(EnrollmentBatch.samples), selectinload(EnrollmentBatch.person))
    )
    if not batch or not batch.person or batch.person.owner_user_id != actor_id or not batch.is_self_enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Self-enrollment batch not found")
    return batch


def _load_owned_self_sample(db: Session, actor_id: str, sample_id: str) -> tuple[EnrollmentSample, EnrollmentBatch]:
    sample = db.scalar(
        select(EnrollmentSample)
        .where(EnrollmentSample.id == sample_id)
        .options(selectinload(EnrollmentSample.batch).selectinload(EnrollmentBatch.person), selectinload(EnrollmentSample.batch).selectinload(EnrollmentBatch.samples))
    )
    if not sample or not sample.batch or not sample.batch.person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment sample not found")
    batch = sample.batch
    if batch.person.owner_user_id != actor_id or not batch.is_self_enrollment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment sample not found")
    return sample, batch


@router.get("/enrollment/live", response_model=SelfEnrollmentStatusResponse)
def get_self_enrollment_status(
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> SelfEnrollmentStatusResponse:
    person, created_person = get_or_create_owned_person(db, actor)
    if created_person:
        write_audit_log(
            db,
            actor.id,
            "person",
            person.id,
            "self_enrollment_person_provisioned",
            {"owner_user_id": actor.id},
        )
        db.commit()

    active_batch = _load_active_batch(db, person.id)
    draft_batch = _load_draft_batch(db, person.id)
    return SelfEnrollmentStatusResponse(
        person=_person_summary(person),
        active_batch=summarize_batch(active_batch) if active_batch else None,
        draft_batch=summarize_batch(draft_batch) if draft_batch else None,
        quality_bypass_allowed=allow_quality_bypass(actor),
        target_sample_count=SELF_ENROLLMENT_TARGET_SAMPLE_COUNT,
    )


@router.post("/enrollment/live/start", response_model=SelfEnrollmentStartResponse, status_code=status.HTTP_201_CREATED)
def start_self_enrollment(
    payload: SelfEnrollmentStartRequest,
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> SelfEnrollmentStartResponse:
    if payload.bypass_quality_validation and not allow_quality_bypass(actor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Quality bypass is not allowed in this environment")

    person, batch, created_person = create_self_enrollment_batch(
        db,
        actor,
        bypass_quality_validation=payload.bypass_quality_validation,
    )
    if created_person:
        write_audit_log(
            db,
            actor.id,
            "person",
            person.id,
            "self_enrollment_person_provisioned",
            {"owner_user_id": actor.id},
        )
    write_audit_log(
        db,
        actor.id,
        "enrollment_batch",
        batch.id,
        "self_enrollment_started",
        {
            "person_id": person.id,
            "replacement_for_batch_id": batch.replacement_for_batch_id,
            "bypass_quality_validation": batch.bypass_quality_validation,
        },
    )
    db.commit()
    db.refresh(batch)
    batch = _load_owned_self_batch(db, actor.id, batch.id)
    return SelfEnrollmentStartResponse(
        person=_person_summary(person),
        batch=summarize_batch(batch),
        created_person=created_person,
    )


@router.post("/enrollment/live/frame", response_model=SelfEnrollmentFrameResponse)
def upload_self_enrollment_frame(
    batch_id: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> SelfEnrollmentFrameResponse:
    batch = _load_owned_self_batch(db, actor.id, batch_id)
    accepted_count = len([sample for sample in batch.samples if sample.quality_passed])
    if batch.status != EnrollmentBatchStatus.incomplete:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Self-enrollment batch is no longer accepting frames")
    if accepted_count >= batch.target_sample_count:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Self-enrollment batch already reached its target sample count")

    sample = process_enrollment_sample(
        db,
        batch,
        image,
        derive_diversity_tag(batch),
        capture_index=next_capture_index(batch),
        bypass_quality_validation=batch.bypass_quality_validation,
        activate_immediately=False,
    )
    message = "Frame accepted for self-enrollment" if sample.quality_passed else "Frame rejected"
    write_audit_log(
        db,
        actor.id,
        "enrollment_batch",
        batch.id,
        "self_enrollment_frame_processed",
        {
            "sample_id": sample.id,
            "accepted": sample.quality_passed,
            "rejection_reason": sample.rejection_reason,
            "capture_index": sample.capture_index,
            "bypass_quality_validation": batch.bypass_quality_validation,
        },
    )
    db.commit()
    db.refresh(sample)
    batch = _load_owned_self_batch(db, actor.id, batch.id)
    return SelfEnrollmentFrameResponse(
        batch=summarize_batch(batch),
        sample=sample,
        accepted=sample.quality_passed,
        message=message,
    )


@router.post("/enrollment/live/finalize", response_model=SelfEnrollmentFinalizeResponse)
def finalize_self_enrollment(
    payload: SelfEnrollmentFinalizeRequest,
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> SelfEnrollmentFinalizeResponse:
    batch = _load_owned_self_batch(db, actor.id, payload.batch_id)
    active_batch = _load_active_batch(db, batch.person_id)
    if active_batch and active_batch.id != batch.id and not payload.confirm_replace:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Existing enrollment must be explicitly confirmed before replacement")

    replaced_batch_id = active_batch.id if active_batch and active_batch.id != batch.id else batch.replacement_for_batch_id
    activate_self_enrollment_batch(db, batch)
    write_audit_log(
        db,
        actor.id,
        "enrollment_batch",
        batch.id,
        "self_enrollment_replaced",
        {
            "person_id": batch.person_id,
            "replaced_batch_id": replaced_batch_id,
            "bypass_quality_validation": batch.bypass_quality_validation,
            "active_sample_count": len([sample for sample in batch.samples if sample.quality_passed]),
        },
    )
    db.commit()
    batch = _load_owned_self_batch(db, actor.id, batch.id)
    return SelfEnrollmentFinalizeResponse(
        batch=summarize_batch(batch),
        replaced_batch_id=replaced_batch_id,
        active_sample_count=len([sample for sample in batch.samples if sample.is_active]),
    )


@router.delete("/enrollment/live/samples/{sample_id}", response_model=SelfEnrollmentRetakeResponse)
def retake_self_enrollment_frame(
    sample_id: str,
    db: Session = Depends(get_db),
    actor=Depends(get_current_user),
) -> SelfEnrollmentRetakeResponse:
    sample, batch = _load_owned_self_sample(db, actor.id, sample_id)
    delete_self_enrollment_sample(db, batch, sample)
    write_audit_log(
        db,
        actor.id,
        "enrollment_batch",
        batch.id,
        "self_enrollment_frame_deleted",
        {"sample_id": sample_id},
    )
    db.commit()
    batch = _load_owned_self_batch(db, actor.id, batch.id)
    return SelfEnrollmentRetakeResponse(batch=summarize_batch(batch), removed_sample_id=sample_id)
