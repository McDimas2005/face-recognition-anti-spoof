from datetime import datetime

from pydantic import BaseModel


class MessageResponse(BaseModel):
    message: str


class AuditInfo(BaseModel):
    created_at: datetime

