from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = "development"
    app_name: str = Field(default="Face Attendance API", alias="API_APP_NAME")
    host: str = Field(default="0.0.0.0", alias="API_HOST")
    port: int = Field(default=8000, alias="API_PORT")
    secret_key: str = Field(default="change-me", alias="API_SECRET_KEY")
    access_token_expire_minutes: int = Field(default=30, alias="API_ACCESS_TOKEN_EXPIRE_MINUTES")
    refresh_token_expire_minutes: int = Field(default=43200, alias="API_REFRESH_TOKEN_EXPIRE_MINUTES")
    database_url: str = Field(default="sqlite+pysqlite:///./face_attendance.db", alias="API_DATABASE_URL")
    storage_path: Path = Field(default=Path("data"), alias="API_STORAGE_PATH")
    retain_enrollment_images: bool = Field(default=False, alias="API_RETAIN_ENROLLMENT_IMAGES")
    retain_review_images: bool = Field(default=True, alias="API_RETAIN_REVIEW_IMAGES")
    bootstrap_admin_email: str = Field(default="admin@example.com", alias="API_BOOTSTRAP_ADMIN_EMAIL")
    bootstrap_admin_password: str = Field(default="ChangeMe123!", alias="API_BOOTSTRAP_ADMIN_PASSWORD")
    bootstrap_admin_name: str = Field(default="System Admin", alias="API_BOOTSTRAP_ADMIN_NAME")
    cors_origins_raw: str = Field(default="http://localhost:3000", alias="API_CORS_ORIGINS")
    similarity_threshold: float = Field(default=0.82, alias="API_SIMILARITY_THRESHOLD")
    commit_threshold: float = Field(default=0.86, alias="API_COMMIT_THRESHOLD")
    ambiguity_margin: float = Field(default=0.04, alias="API_AMBIGUITY_MARGIN")
    liveness_threshold: float = Field(default=0.55, alias="API_LIVENESS_THRESHOLD")
    consensus_frames: int = Field(default=3, alias="API_CONSENSUS_FRAMES")
    consensus_window_seconds: int = Field(default=5, alias="API_CONSENSUS_WINDOW_SECONDS")
    min_face_size: int = Field(default=96, alias="API_MIN_FACE_SIZE")
    max_yaw_score: float = Field(default=0.35, alias="API_MAX_YAW_SCORE")
    max_occlusion_score: float = Field(default=0.45, alias="API_MAX_OCCLUSION_SCORE")
    min_brightness: float = Field(default=40.0, alias="API_MIN_BRIGHTNESS")
    max_brightness: float = Field(default=210.0, alias="API_MAX_BRIGHTNESS")
    max_blur_score: float = Field(default=180.0, alias="API_MAX_BLUR_SCORE")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins_raw.split(",") if origin.strip()]


settings = Settings()

