from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.domain import UserRole
from app.schemas.settings import SettingsResponse, SettingsUpdate
from app.services.audit import write_audit_log
from app.services.settings import get_quality_policy, get_recognition_policy, get_retention_policy, upsert_setting

router = APIRouter()


@router.get("", response_model=SettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer, UserRole.viewer)),
) -> SettingsResponse:
    return SettingsResponse(
        recognition_policy=get_recognition_policy(db),
        quality_policy=get_quality_policy(db),
        retention_policy=get_retention_policy(db),
        can_edit_settings=actor.role in {UserRole.superadmin, UserRole.admin},
        can_edit_all=actor.role == UserRole.superadmin,
    )


@router.put("", response_model=SettingsResponse)
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
) -> SettingsResponse:
    if payload.recognition_policy is not None:
        recognition_policy = {
            **get_recognition_policy(db),
            **jsonable_encoder(payload.recognition_policy, exclude_none=True),
        }
        upsert_setting(db, "recognition_policy", recognition_policy, actor.id)
    if payload.quality_policy is not None:
        if actor.role != UserRole.superadmin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Only superadmins can update quality thresholds",
            )
        quality_policy = {
            **get_quality_policy(db),
            **jsonable_encoder(payload.quality_policy, exclude_none=True),
        }
        upsert_setting(db, "quality_policy", quality_policy, actor.id)
    if payload.retention_policy is not None:
        retention_policy = {
            **get_retention_policy(db),
            **jsonable_encoder(payload.retention_policy, exclude_none=True),
        }
        upsert_setting(db, "retention_policy", retention_policy, actor.id)
    write_audit_log(db, actor.id, "settings", "global", "settings_updated", jsonable_encoder(payload, exclude_none=True))
    db.commit()
    return SettingsResponse(
        recognition_policy=get_recognition_policy(db),
        quality_policy=get_quality_policy(db),
        retention_policy=get_retention_policy(db),
        can_edit_settings=True,
        can_edit_all=actor.role == UserRole.superadmin,
    )
