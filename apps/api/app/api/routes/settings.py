from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.domain import UserRole
from app.schemas.settings import SettingsResponse, SettingsUpdate
from app.services.audit import write_audit_log
from app.services.settings import DEFAULT_RETENTION_POLICY, get_setting, upsert_setting

router = APIRouter()


@router.get("", response_model=SettingsResponse)
def get_settings(
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer, UserRole.viewer)),
) -> SettingsResponse:
    return SettingsResponse(
        recognition_policy=get_setting(db, "recognition_policy", {}),
        retention_policy=get_setting(db, "retention_policy", DEFAULT_RETENTION_POLICY),
    )


@router.put("", response_model=SettingsResponse)
def update_settings(
    payload: SettingsUpdate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
) -> SettingsResponse:
    if payload.recognition_policy is not None:
        upsert_setting(db, "recognition_policy", payload.recognition_policy, actor.id)
    if payload.retention_policy is not None:
        upsert_setting(db, "retention_policy", payload.retention_policy, actor.id)
    write_audit_log(db, actor.id, "settings", "global", "settings_updated", jsonable_encoder(payload, exclude_none=True))
    db.commit()
    return SettingsResponse(
        recognition_policy=get_setting(db, "recognition_policy", {}),
        retention_policy=get_setting(db, "retention_policy", DEFAULT_RETENTION_POLICY),
    )
