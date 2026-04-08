from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.domain import AppSetting


DEFAULT_RETENTION_POLICY = {
    "retain_enrollment_images": settings.retain_enrollment_images,
    "retain_review_images": settings.retain_review_images,
    "privacy_notice": "Liveness checks reduce spoofing risk but do not guarantee spoof prevention.",
}


def get_setting(db: Session, key: str, default: dict) -> dict:
    record = db.get(AppSetting, key)
    return record.value if record else default


def upsert_setting(db: Session, key: str, value: dict, updated_by: str | None) -> AppSetting:
    record = db.get(AppSetting, key)
    if record:
        record.value = value
        record.updated_by = updated_by
    else:
        record = AppSetting(key=key, value=value, updated_by=updated_by)
        db.add(record)
    db.flush()
    return record

