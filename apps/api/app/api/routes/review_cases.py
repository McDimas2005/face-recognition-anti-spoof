from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.domain import AttendanceEvent, AttendanceSource, AttendanceStatus, ReviewCase, ReviewStatus, UserRole
from app.schemas.common import MessageResponse
from app.schemas.review import ReviewCaseResponse, ReviewResolveRequest
from app.services.audit import write_audit_log

router = APIRouter()


@router.get("", response_model=list[ReviewCaseResponse])
def list_review_cases(
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer, UserRole.viewer)),
):
    return list(db.scalars(select(ReviewCase).order_by(ReviewCase.created_at.desc())).all())


@router.delete("", response_model=MessageResponse)
def clear_review_cases_route(
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer)),
) -> MessageResponse:
    db.execute(delete(ReviewCase))
    write_audit_log(db, actor.id, "review_case", "all", "review_cases_cleared", {})
    db.commit()
    return MessageResponse(message="Review queue cleared")


@router.delete("/{review_id}", response_model=MessageResponse)
def delete_review_case(
    review_id: str,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer)),
) -> MessageResponse:
    review = db.get(ReviewCase, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review case not found")
    review_details = {"reason": review.reason.value, "status": review.status.value}
    db.delete(review)
    write_audit_log(db, actor.id, "review_case", review_id, "review_case_deleted", review_details)
    db.commit()
    return MessageResponse(message="Review case deleted")


@router.post("/{review_id}/resolve", response_model=ReviewCaseResponse)
def resolve_review_case(
    review_id: str,
    payload: ReviewResolveRequest,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer)),
):
    review = db.get(ReviewCase, review_id)
    if not review:
        raise HTTPException(status_code=404, detail="Review case not found")

    review.resolution_notes = payload.notes
    review.resolved_by = actor.id
    review.resolved_at = datetime.now(UTC)

    if payload.action == "approve":
        review.status = ReviewStatus.approved
        review.resolved_person_id = payload.resolved_person_id or review.proposed_person_id
    elif payload.action == "reject":
        review.status = ReviewStatus.rejected
    elif payload.action == "manual_mark":
        if not payload.resolved_person_id:
            raise HTTPException(status_code=400, detail="resolved_person_id is required for manual_mark")
        existing = db.scalar(
            select(AttendanceEvent).where(
                AttendanceEvent.session_id == review.session_id,
                AttendanceEvent.person_id == payload.resolved_person_id,
            )
        )
        if existing:
            raise HTTPException(status_code=400, detail="Attendance already exists for this person in the session")
        attendance = AttendanceEvent(
            session_id=review.session_id,
            person_id=payload.resolved_person_id,
            source=AttendanceSource.manual_override,
            status=AttendanceStatus.on_time,
            manual_reason=payload.notes,
            created_by=actor.id,
        )
        db.add(attendance)
        db.flush()
        review.status = ReviewStatus.manual_marked
        review.resolved_person_id = payload.resolved_person_id
        write_audit_log(
            db,
            actor.id,
            "attendance_event",
            attendance.id,
            "attendance_marked_manual_override",
            {"review_case_id": review.id, "person_id": payload.resolved_person_id, "notes": payload.notes},
        )
    else:
        raise HTTPException(status_code=400, detail="Unsupported review action")

    write_audit_log(
        db,
        actor.id,
        "review_case",
        review.id,
        "review_case_resolved",
        {"action": payload.action, "resolved_person_id": payload.resolved_person_id, "notes": payload.notes},
    )
    db.commit()
    db.refresh(review)
    return review
