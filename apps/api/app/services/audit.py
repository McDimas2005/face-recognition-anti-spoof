from typing import Any

from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.models.domain import AuditLog


def write_audit_log(
    db: Session,
    actor_user_id: str | None,
    entity_type: str,
    entity_id: str,
    action: str,
    details: Any,
) -> AuditLog:
    normalized_details = jsonable_encoder(details)
    record = AuditLog(
        actor_user_id=actor_user_id,
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        details=normalized_details,
    )
    db.add(record)
    db.flush()
    return record
