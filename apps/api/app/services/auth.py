from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import create_token, hash_password, verify_password, decode_token
from app.models.domain import User


def authenticate_user(db: Session, email: str, password: str) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid credentials")
    return user


def issue_tokens(user: User) -> dict[str, str]:
    access = create_token(user.id, settings.access_token_expire_minutes, "access", extra={"role": user.role.value})
    refresh = create_token(user.id, settings.refresh_token_expire_minutes, "refresh", extra={"version": user.refresh_version})
    return {"access_token": access, "refresh_token": refresh}


def refresh_access_token(db: Session, refresh_token: str) -> dict[str, str]:
    try:
        payload = decode_token(refresh_token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    if payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user = db.get(User, payload["sub"])
    if not user or payload.get("version") != user.refresh_version:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token revoked")
    return issue_tokens(user)


def create_user(db: Session, email: str, full_name: str, password: str, role) -> User:
    user = User(email=email, full_name=full_name, password_hash=hash_password(password), role=role)
    db.add(user)
    db.flush()
    return user

