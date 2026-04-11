from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.encoders import jsonable_encoder
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.db.session import get_db
from app.models.domain import Person, UserRole
from app.schemas.common import MessageResponse
from app.schemas.person import PersonCreate, PersonResponse, PersonUpdate
from app.services.admin_cleanup import delete_person_graph
from app.services.audit import write_audit_log

router = APIRouter()


@router.get("", response_model=list[PersonResponse])
def list_people(
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin, UserRole.reviewer, UserRole.viewer)),
) -> list[Person]:
    return list(db.scalars(select(Person).order_by(Person.created_at.desc())).all())


@router.post("", response_model=PersonResponse, status_code=status.HTTP_201_CREATED)
def create_person(
    payload: PersonCreate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
) -> Person:
    person = Person(
        full_name=payload.full_name,
        external_id=payload.external_id,
        notes=payload.notes,
        created_by=actor.id,
    )
    db.add(person)
    db.flush()
    write_audit_log(db, actor.id, "person", person.id, "person_created", jsonable_encoder(payload))
    db.commit()
    db.refresh(person)
    return person


@router.delete("/{person_id}", response_model=MessageResponse)
def delete_person(
    person_id: str,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
) -> MessageResponse:
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    person_details = {"full_name": person.full_name, "external_id": person.external_id}
    delete_person_graph(db, person)
    write_audit_log(db, actor.id, "person", person_id, "person_deleted", person_details)
    db.commit()
    return MessageResponse(message="Person deleted")


@router.patch("/{person_id}", response_model=PersonResponse)
def update_person(
    person_id: str,
    payload: PersonUpdate,
    db: Session = Depends(get_db),
    actor=Depends(require_roles(UserRole.superadmin, UserRole.admin)),
) -> Person:
    person = db.get(Person, person_id)
    if not person:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Person not found")
    for key, value in payload.model_dump(exclude_none=True).items():
        setattr(person, key, value)
    write_audit_log(db, actor.id, "person", person.id, "person_updated", jsonable_encoder(payload, exclude_none=True))
    db.commit()
    db.refresh(person)
    return person
