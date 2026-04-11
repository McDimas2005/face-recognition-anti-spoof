from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.domain import AppSetting


LEGACY_DEMO_POLICY = {
    "similarity_threshold": 0.82,
    "commit_threshold": 0.86,
    "ambiguity_margin": 0.04,
    "liveness_threshold": 0.55,
    "consensus_frames": 3,
    "consensus_window_seconds": 5,
}
DEFAULT_RECOGNITION_POLICY = {
    "similarity_threshold": settings.similarity_threshold,
    "commit_threshold": settings.commit_threshold,
    "ambiguity_margin": settings.ambiguity_margin,
    "liveness_threshold": settings.liveness_threshold,
    "consensus_frames": settings.consensus_frames,
    "consensus_window_seconds": settings.consensus_window_seconds,
}
DEFAULT_QUALITY_POLICY = {
    "min_face_size": settings.min_face_size,
    "min_brightness": settings.min_brightness,
    "max_brightness": settings.max_brightness,
    "blur_threshold": settings.max_blur_score,
    "max_yaw_score": settings.max_yaw_score,
    "max_occlusion_score": settings.max_occlusion_score,
}
RECOMMENDED_DEMO_POLICY = DEFAULT_RECOGNITION_POLICY.copy()

DEFAULT_RETENTION_POLICY = {
    "retain_enrollment_images": settings.retain_enrollment_images,
    "retain_review_images": settings.retain_review_images,
    "privacy_notice": "Liveness checks reduce spoofing risk but do not guarantee spoof prevention.",
}


def get_setting(db: Session, key: str, default: dict) -> dict:
    record = db.get(AppSetting, key)
    return record.value.copy() if record else default.copy()


def get_recognition_policy(db: Session) -> dict:
    policy = get_setting(db, "recognition_policy", DEFAULT_RECOGNITION_POLICY)
    if policy == LEGACY_DEMO_POLICY:
        return RECOMMENDED_DEMO_POLICY.copy()
    return {**DEFAULT_RECOGNITION_POLICY, **policy}


def get_quality_policy(db: Session) -> dict:
    policy = get_setting(db, "quality_policy", DEFAULT_QUALITY_POLICY)
    if "max_blur_score" in policy and "blur_threshold" not in policy:
        policy["blur_threshold"] = policy.pop("max_blur_score")
    return {**DEFAULT_QUALITY_POLICY, **policy}


def get_retention_policy(db: Session) -> dict:
    policy = get_setting(db, "retention_policy", DEFAULT_RETENTION_POLICY)
    return {**DEFAULT_RETENTION_POLICY, **policy}


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
