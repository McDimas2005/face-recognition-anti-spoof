from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.domain import EnrollmentBatch, EnrollmentBatchStatus, UserRole
from app.schemas.person import EnrollmentBatchCreate, EnrollmentBatchResponse, EnrollmentSampleResponse
from app.services.audit import write_audit_log
from app.services.enrollment import ensure_person, next_capture_index, process_enrollment_sample

router = APIRouter()


@router.post("/batches", response_model=EnrollmentBatchResponse, status_code=status.HTTP_201_CREATED)
def create_batch(
    payload: EnrollmentBatchCreate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
) -> EnrollmentBatch:
    ensure_person(db, payload.person_id)
    batch = EnrollmentBatch(
        person_id=payload.person_id,
        status=EnrollmentBatchStatus.incomplete,
        is_active=False,
        is_self_enrollment=False,
        bypass_quality_validation=False,
        target_sample_count=5,
        diversity_status={},
        quality_summary={},
        created_by=actor.id,
    )
    db.add(batch)
    db.flush()
    write_audit_log(db, actor.id, "enrollment_batch", batch.id, "enrollment_batch_created", {"person_id": payload.person_id})
    db.commit()
    db.refresh(batch)
    return batch


@router.get("/batches/{batch_id}", response_model=EnrollmentBatchResponse)
def get_batch(
    batch_id: str,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer, UserRole.viewer)),
) -> EnrollmentBatch:
    batch = db.scalar(select(EnrollmentBatch).where(EnrollmentBatch.id == batch_id))
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment batch not found")
    return batch


@router.get("/batches/{batch_id}/samples", response_model=list[EnrollmentSampleResponse])
def list_batch_samples(
    batch_id: str,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer, UserRole.viewer)),
):
    batch = db.scalar(
        select(EnrollmentBatch).where(EnrollmentBatch.id == batch_id).options(selectinload(EnrollmentBatch.samples))
    )
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment batch not found")
    return batch.samples


@router.post("/batches/{batch_id}/samples", response_model=EnrollmentSampleResponse, status_code=status.HTTP_201_CREATED)
def upload_sample(
    batch_id: str,
    diversity_tag: str = Form(...),
    image: UploadFile = File(...),
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
):
    batch = db.scalar(
        select(EnrollmentBatch).where(EnrollmentBatch.id == batch_id).options(selectinload(EnrollmentBatch.samples))
    )
    if not batch:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment batch not found")
    sample = process_enrollment_sample(
        db,
        batch,
        image,
        diversity_tag,
        capture_index=next_capture_index(batch),
        bypass_quality_validation=batch.bypass_quality_validation,
        activate_immediately=True,
    )
    write_audit_log(
        db,
        actor.id,
        "enrollment_batch",
        batch.id,
        "enrollment_sample_uploaded",
        {"sample_id": sample.id, "diversity_tag": diversity_tag, "quality_passed": sample.quality_passed},
    )
    db.commit()
    db.refresh(sample)
    return sample
