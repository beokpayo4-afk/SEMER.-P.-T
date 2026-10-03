import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import APIError
from app.models.enquiries import EventEnquiry, EventService, EventServiceImage
from app.models.enums import EnquiryStatus, EventCategory, RecordStatus, UserRole
from app.models.identity import User
from app.schemas.events import (
    EventEnquiryAdmin,
    EventEnquiryCreate,
    EventEnquiryPage,
    EventEnquirySubmitted,
    EventEnquiryUpdate,
    EventImagePublic,
    EventServicePage,
    EventServicePublic,
    EventServiceWrite,
)


def list_services(
    db: Session,
    *,
    viewer: User | None,
    category: EventCategory | None,
    featured: bool | None,
    status: RecordStatus | None,
    page: int,
    page_size: int,
) -> EventServicePage:
    admin = _is_admin(viewer)
    filters = []
    if not admin:
        filters.append(EventService.status == RecordStatus.active)
    elif status is not None:
        filters.append(EventService.status == status)
    if category is not None:
        filters.append(EventService.category == category)
    if featured is not None:
        filters.append(EventService.is_featured == featured)
    total = db.scalar(select(func.count()).select_from(EventService).where(*filters)) or 0
    services = db.scalars(
        select(EventService)
        .where(*filters)
        .order_by(EventService.is_featured.desc(), EventService.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .options(*_service_options())
    ).all()
    return EventServicePage(
        items=[_present_service(service) for service in services],
        page=page,
        page_size=page_size,
        total=total,
    )


def get_service(db: Session, service_id: uuid.UUID, viewer: User | None) -> EventServicePublic:
    service = _load_service(db, service_id)
    if service is None or (not _is_admin(viewer) and service.status != RecordStatus.active):
        raise APIError(status_code=404, detail="Service not found")
    return _present_service(service)


def create_service(db: Session, data: EventServiceWrite) -> EventServicePublic:
    _ensure_slug(db, data.slug, None)
    service = EventService(
        title=data.title,
        slug=data.slug,
        category=data.category,
        description=data.description,
        services=data.services,
        is_featured=data.featured,
        status=data.status,
    )
    _replace_images(service, data)
    db.add(service)
    _commit(db, "Slug is already in use")
    return _present_service(_reload(db, service.id))


def update_service(db: Session, service_id: uuid.UUID, data: EventServiceWrite) -> EventServicePublic:
    service = _load_service(db, service_id)
    if service is None:
        raise APIError(status_code=404, detail="Service not found")
    _ensure_slug(db, data.slug, service.id)
    service.title = data.title
    service.slug = data.slug
    service.category = data.category
    service.description = data.description
    service.services = data.services
    service.is_featured = data.featured
    service.status = data.status
    _replace_images(service, data)
    _commit(db, "Slug is already in use")
    return _present_service(_reload(db, service.id))


def delete_service(db: Session, service_id: uuid.UUID) -> None:
    service = db.get(EventService, service_id)
    if service is None:
        raise APIError(status_code=404, detail="Service not found")
    db.delete(service)
    _commit(db, "The service could not be deleted")


def create_enquiry(db: Session, data: EventEnquiryCreate, user: User | None) -> EventEnquirySubmitted:
    if data.service_id is not None:
        service = db.get(EventService, data.service_id)
        if service is None or service.status != RecordStatus.active:
            raise APIError(status_code=404, detail="Service not found")
    enquiry = EventEnquiry(
        user_id=user.id if user is not None else None,
        event_service_id=data.service_id,
        name=data.name,
        email=data.email,
        phone=data.phone,
        event_type=data.event_type,
        event_date=data.event_date,
        location=data.location,
        expected_guests=data.expected_guests,
        budget_paise=data.budget,
        requirements=data.requirements,
        message=data.message,
        internal_notes="",
        status=EnquiryStatus.new,
    )
    db.add(enquiry)
    _commit(db, "The enquiry could not be saved")
    db.refresh(enquiry)
    return _present_submitted(enquiry)


def list_enquiries(
    db: Session,
    *,
    status: EnquiryStatus | None,
    page: int,
    page_size: int,
) -> EventEnquiryPage:
    filters = [] if status is None else [EventEnquiry.status == status]
    total = db.scalar(select(func.count()).select_from(EventEnquiry).where(*filters)) or 0
    enquiries = db.scalars(
        select(EventEnquiry)
        .where(*filters)
        .order_by(EventEnquiry.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return EventEnquiryPage(
        items=[_present_admin(enquiry) for enquiry in enquiries],
        page=page,
        page_size=page_size,
        total=total,
    )


def get_enquiry(db: Session, enquiry_id: uuid.UUID) -> EventEnquiryAdmin:
    enquiry = db.get(EventEnquiry, enquiry_id)
    if enquiry is None:
        raise APIError(status_code=404, detail="Enquiry not found")
    return _present_admin(enquiry)


def update_enquiry(db: Session, enquiry_id: uuid.UUID, data: EventEnquiryUpdate) -> EventEnquiryAdmin:
    enquiry = db.get(EventEnquiry, enquiry_id)
    if enquiry is None:
        raise APIError(status_code=404, detail="Enquiry not found")
    if data.status is not None:
        enquiry.status = data.status
    if data.internal_notes is not None:
        enquiry.internal_notes = data.internal_notes
    _commit(db, "The enquiry could not be saved")
    db.refresh(enquiry)
    return _present_admin(enquiry)


def delete_enquiry(db: Session, enquiry_id: uuid.UUID) -> None:
    enquiry = db.get(EventEnquiry, enquiry_id)
    if enquiry is None:
        raise APIError(status_code=404, detail="Enquiry not found")
    db.delete(enquiry)
    _commit(db, "The enquiry could not be deleted")


def _is_admin(viewer: User | None) -> bool:
    return viewer is not None and viewer.role == UserRole.admin


def _load_service(db: Session, service_id: uuid.UUID) -> EventService | None:
    return db.scalar(select(EventService).where(EventService.id == service_id).options(*_service_options()))


def _reload(db: Session, service_id: uuid.UUID) -> EventService:
    service = _load_service(db, service_id)
    if service is None:
        raise APIError(status_code=404, detail="Service not found")
    return service


def _ensure_slug(db: Session, slug: str, service_id: uuid.UUID | None) -> None:
    filters = [EventService.slug == slug]
    if service_id is not None:
        filters.append(EventService.id != service_id)
    if db.scalar(select(EventService.id).where(*filters)) is not None:
        raise APIError(status_code=409, detail="Slug is already in use")


def _replace_images(service: EventService, data: EventServiceWrite) -> None:
    service.images.clear()
    for image in data.images:
        service.images.append(
            EventServiceImage(url=image.url, alt_text=image.alt_text, sort_order=image.sort_order)
        )


def _present_service(service: EventService) -> EventServicePublic:
    return EventServicePublic(
        id=service.id,
        title=service.title,
        slug=service.slug,
        category=service.category,
        description=service.description,
        services=service.services,
        images=[
            EventImagePublic(id=image.id, url=image.url, alt_text=image.alt_text, sort_order=image.sort_order)
            for image in service.images
        ],
        status=service.status,
        featured=service.is_featured,
    )


def _present_submitted(enquiry: EventEnquiry) -> EventEnquirySubmitted:
    return EventEnquirySubmitted(
        id=enquiry.id,
        service_id=enquiry.event_service_id,
        name=enquiry.name,
        email=enquiry.email,
        phone=enquiry.phone,
        event_type=enquiry.event_type,
        event_date=enquiry.event_date,
        location=enquiry.location,
        expected_guests=enquiry.expected_guests,
        budget=enquiry.budget_paise,
        requirements=enquiry.requirements,
        message=enquiry.message,
        status=enquiry.status,
        created_at=enquiry.created_at,
    )


def _present_admin(enquiry: EventEnquiry) -> EventEnquiryAdmin:
    submitted = _present_submitted(enquiry)
    return EventEnquiryAdmin(**submitted.model_dump(), internal_notes=enquiry.internal_notes)


def _service_options():
    return (selectinload(EventService.images),)


def _commit(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(status_code=409, detail=detail)
