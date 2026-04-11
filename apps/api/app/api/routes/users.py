from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.models.domain import User, UserRole
from app.schemas.common import MessageResponse
from app.schemas.user import UserCreate, UserResponse, UserUpdate
from app.services.admin_cleanup import delete_user_graph, ensure_user_can_be_deleted
from app.services.audit import write_audit_log
from app.services.auth import create_user
from app.core.security import hash_password

router = APIRouter()


@router.get("", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
) -> list[User]:
    return list(db.scalars(select(User).order_by(User.created_at.desc())).all())


@router.post("", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user_route(
    payload: UserCreate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin)),
) -> User:
    existing = db.scalar(select(User).where(User.email == payload.email))
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")
    user = create_user(db, payload.email, payload.full_name, payload.password, payload.role)
    write_audit_log(db, actor.id, "user", user.id, "user_created", {"email": user.email, "role": user.role.value})
    db.commit()
    db.refresh(user)
    return user


@router.patch("/{user_id}", response_model=UserResponse)
def update_user_route(
    user_id: str,
    payload: UserUpdate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin)),
) -> User:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    if payload.email is not None and payload.email != user.email:
        existing = db.scalar(select(User).where(User.email == payload.email, User.id != user_id))
        if existing:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists")
        user.email = payload.email
    if payload.full_name is not None:
        user.full_name = payload.full_name
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)
        user.refresh_version += 1
    if payload.role is not None:
        user.role = payload.role
    if payload.is_active is not None:
        user.is_active = payload.is_active
    write_audit_log(db, actor.id, "user", user.id, "user_updated", jsonable_encoder(payload, exclude_none=True))
    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}", response_model=MessageResponse)
def delete_user_route(
    user_id: str,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin)),
    current_user=Depends(get_current_user),
) -> MessageResponse:
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    try:
        ensure_user_can_be_deleted(db, current_user, user)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    user_details = {"email": user.email, "role": user.role.value}
    delete_user_graph(db, user)
    write_audit_log(db, actor.id, "user", user_id, "user_deleted", user_details)
    db.commit()
    return MessageResponse(message="User deleted")
