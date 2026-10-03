import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user, require_admin
from app.db.session import get_db
from app.models.enums import EnquiryStatus, EventCategory, RecordStatus
from app.models.identity import User
from app.schemas.events import (
    EventEnquiryAdmin,
    EventEnquiryCreate,
    EventEnquiryPage,
    EventEnquirySubmitted,
    EventEnquiryUpdate,
    EventServicePage,
    EventServicePublic,
    EventServiceWrite,
)
from app.services import events as event_service

router = APIRouter()


@router.get("", response_model=EventServicePage)
def list_services(
    db: Annotated[Session, Depends(get_db)],
    viewer: Annotated[User | None, Depends(get_optional_user)],
    category: Annotated[EventCategory | None, Query()] = None,
    featured: Annotated[bool | None, Query()] = None,
    status_filter: Annotated[RecordStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EventServicePage:
    return event_service.list_services(
        db,
        viewer=viewer,
        category=category,
        featured=featured,
        status=status_filter,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=EventServicePublic, status_code=status.HTTP_201_CREATED)
def create_service(
    body: EventServiceWrite,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> EventServicePublic:
    return event_service.create_service(db, body)


@router.get("/enquiries", response_model=EventEnquiryPage)
def list_enquiries(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    status_filter: Annotated[EnquiryStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EventEnquiryPage:
    return event_service.list_enquiries(db, status=status_filter, page=page, page_size=page_size)


@router.post("/enquiries", response_model=EventEnquirySubmitted, status_code=status.HTTP_201_CREATED)
def create_enquiry(
    body: EventEnquiryCreate,
    db: Annotated[Session, Depends(get_db)],
    viewer: Annotated[User | None, Depends(get_optional_user)],
) -> EventEnquirySubmitted:
    return event_service.create_enquiry(db, body, viewer)


@router.get("/enquiries/{enquiry_id}", response_model=EventEnquiryAdmin)
def get_enquiry(
    enquiry_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> EventEnquiryAdmin:
    return event_service.get_enquiry(db, enquiry_id)


@router.patch("/enquiries/{enquiry_id}", response_model=EventEnquiryAdmin)
def update_enquiry(
    enquiry_id: uuid.UUID,
    body: EventEnquiryUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> EventEnquiryAdmin:
    return event_service.update_enquiry(db, enquiry_id, body)


@router.delete("/enquiries/{enquiry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_enquiry(
    enquiry_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    event_service.delete_enquiry(db, enquiry_id)


@router.get("/{service_id}", response_model=EventServicePublic)
def get_service(
    service_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    viewer: Annotated[User | None, Depends(get_optional_user)],
) -> EventServicePublic:
    return event_service.get_service(db, service_id, viewer)


@router.put("/{service_id}", response_model=EventServicePublic)
def update_service(
    service_id: uuid.UUID,
    body: EventServiceWrite,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> EventServicePublic:
    return event_service.update_service(db, service_id, body)


@router.delete("/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(
    service_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    event_service.delete_service(db, service_id)
