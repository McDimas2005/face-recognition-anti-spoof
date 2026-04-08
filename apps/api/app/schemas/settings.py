from pydantic import BaseModel


class SettingsResponse(BaseModel):
    recognition_policy: dict
    retention_policy: dict


class SettingsUpdate(BaseModel):
    recognition_policy: dict | None = None
    retention_policy: dict | None = None

