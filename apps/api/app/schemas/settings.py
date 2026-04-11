from pydantic import BaseModel, Field


class RecognitionPolicy(BaseModel):
    similarity_threshold: float = Field(ge=0.0, le=1.0)
    commit_threshold: float = Field(ge=0.0, le=1.0)
    ambiguity_margin: float = Field(ge=0.0, le=1.0)
    liveness_threshold: float = Field(ge=0.0, le=1.0)
    consensus_frames: int = Field(ge=1)
    consensus_window_seconds: int = Field(ge=1)


class QualityPolicy(BaseModel):
    min_face_size: int = Field(ge=1)
    min_brightness: float = Field(ge=0.0)
    max_brightness: float = Field(ge=0.0)
    blur_threshold: float = Field(ge=0.0)
    max_yaw_score: float = Field(ge=0.0)
    max_occlusion_score: float = Field(ge=0.0)


class RetentionPolicy(BaseModel):
    retain_enrollment_images: bool
    retain_review_images: bool
    privacy_notice: str


class RecognitionPolicyUpdate(BaseModel):
    similarity_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    commit_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    ambiguity_margin: float | None = Field(default=None, ge=0.0, le=1.0)
    liveness_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    consensus_frames: int | None = Field(default=None, ge=1)
    consensus_window_seconds: int | None = Field(default=None, ge=1)


class QualityPolicyUpdate(BaseModel):
    min_face_size: int | None = Field(default=None, ge=1)
    min_brightness: float | None = Field(default=None, ge=0.0)
    max_brightness: float | None = Field(default=None, ge=0.0)
    blur_threshold: float | None = Field(default=None, ge=0.0)
    max_yaw_score: float | None = Field(default=None, ge=0.0)
    max_occlusion_score: float | None = Field(default=None, ge=0.0)


class RetentionPolicyUpdate(BaseModel):
    retain_enrollment_images: bool | None = None
    retain_review_images: bool | None = None
    privacy_notice: str | None = None


class SettingsResponse(BaseModel):
    recognition_policy: RecognitionPolicy
    quality_policy: QualityPolicy
    retention_policy: RetentionPolicy
    can_edit_settings: bool
    can_edit_all: bool


class SettingsUpdate(BaseModel):
    recognition_policy: RecognitionPolicyUpdate | None = None
    quality_policy: QualityPolicyUpdate | None = None
    retention_policy: RetentionPolicyUpdate | None = None
