import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import APIError
from app.models.enquiries import TravelEnquiry, TravelPackage, TravelPackageImage
from app.models.enums import EnquiryStatus, RecordStatus, TravelCategory, UserRole
from app.models.identity import User
from app.schemas.travel import (
    TravelEnquiryCreate,
    TravelEnquiryPage,
    TravelEnquiryPublic,
    TravelEnquiryUpdate,
    TravelImagePublic,
    TravelPackagePage,
    TravelPackagePublic,
    TravelPackageWrite,
)


def list_packages(
    db: Session,
    *,
    viewer: User | None,
    category: TravelCategory | None,
    featured: bool | None,
    status: RecordStatus | None,
    page: int,
    page_size: int,
) -> TravelPackagePage:
    admin = _is_admin(viewer)
    filters = []
    if not admin:
        filters.append(TravelPackage.status == RecordStatus.active)
    elif status is not None:
        filters.append(TravelPackage.status == status)
    if category is not None:
        filters.append(TravelPackage.category == category)
    if featured is not None:
        filters.append(TravelPackage.is_featured == featured)
    total = db.scalar(select(func.count()).select_from(TravelPackage).where(*filters)) or 0
    packages = db.scalars(
        select(TravelPackage)
        .where(*filters)
        .order_by(TravelPackage.is_featured.desc(), TravelPackage.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .options(*_package_options())
    ).all()
    return TravelPackagePage(
        items=[_present_package(package) for package in packages],
        page=page,
        page_size=page_size,
        total=total,
    )


def get_package(db: Session, package_id: uuid.UUID, viewer: User | None) -> TravelPackagePublic:
    package = _load_package(db, package_id)
    if package is None or (not _is_admin(viewer) and package.status != RecordStatus.active):
        raise APIError(status_code=404, detail="Package not found")
    return _present_package(package)


def create_package(db: Session, data: TravelPackageWrite) -> TravelPackagePublic:
    _ensure_slug(db, data.slug, None)
    package = TravelPackage(
        title=data.title,
        slug=data.slug,
        category=data.category,
        destination=data.destination,
        country=data.country,
        duration_days=data.duration,
        price_from_paise=data.starting_price,
        description=data.description,
        itinerary=data.itinerary,
        accommodation=data.accommodation,
        transportation=data.transportation,
        activities=data.activities,
        inclusions=data.inclusions,
        exclusions=data.exclusions,
        is_featured=data.featured,
        status=data.status,
    )
    _replace_images(package, data)
    db.add(package)
    _commit(db, "Slug is already in use")
    return _present_package(_reload(db, package.id))


def update_package(db: Session, package_id: uuid.UUID, data: TravelPackageWrite) -> TravelPackagePublic:
    package = _load_package(db, package_id)
    if package is None:
        raise APIError(status_code=404, detail="Package not found")
    _ensure_slug(db, data.slug, package.id)
    package.title = data.title
    package.slug = data.slug
    package.category = data.category
    package.destination = data.destination
    package.country = data.country
    package.duration_days = data.duration
    package.price_from_paise = data.starting_price
    package.description = data.description
    package.itinerary = data.itinerary
    package.accommodation = data.accommodation
    package.transportation = data.transportation
    package.activities = data.activities
    package.inclusions = data.inclusions
    package.exclusions = data.exclusions
    package.is_featured = data.featured
    package.status = data.status
    _replace_images(package, data)
    _commit(db, "Slug is already in use")
    return _present_package(_reload(db, package.id))


def delete_package(db: Session, package_id: uuid.UUID) -> None:
    package = db.get(TravelPackage, package_id)
    if package is None:
        raise APIError(status_code=404, detail="Package not found")
    db.delete(package)
    _commit(db, "The package could not be deleted")


def create_enquiry(db: Session, data: TravelEnquiryCreate, user: User | None) -> TravelEnquiryPublic:
    if data.package_id is not None:
        package = db.get(TravelPackage, data.package_id)
        if package is None or package.status != RecordStatus.active:
            raise APIError(status_code=404, detail="Package not found")
    enquiry = TravelEnquiry(
        user_id=user.id if user is not None else None,
        travel_package_id=data.package_id,
        name=data.name,
        email=data.email,
        phone=data.phone,
        destination=data.destination,
        travel_date=data.travel_date,
        travelers=data.travelers,
        budget_paise=data.budget,
        message=data.message,
        status=EnquiryStatus.new,
    )
    db.add(enquiry)
    _commit(db, "The enquiry could not be saved")
    db.refresh(enquiry)
    return _present_enquiry(enquiry)


def list_enquiries(
    db: Session,
    *,
    status: EnquiryStatus | None,
    page: int,
    page_size: int,
) -> TravelEnquiryPage:
    filters = [] if status is None else [TravelEnquiry.status == status]
    total = db.scalar(select(func.count()).select_from(TravelEnquiry).where(*filters)) or 0
    enquiries = db.scalars(
        select(TravelEnquiry)
        .where(*filters)
        .order_by(TravelEnquiry.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    return TravelEnquiryPage(
        items=[_present_enquiry(enquiry) for enquiry in enquiries],
        page=page,
        page_size=page_size,
        total=total,
    )


def get_enquiry(db: Session, enquiry_id: uuid.UUID) -> TravelEnquiryPublic:
    enquiry = db.get(TravelEnquiry, enquiry_id)
    if enquiry is None:
        raise APIError(status_code=404, detail="Enquiry not found")
    return _present_enquiry(enquiry)


def update_enquiry(db: Session, enquiry_id: uuid.UUID, data: TravelEnquiryUpdate) -> TravelEnquiryPublic:
    enquiry = db.get(TravelEnquiry, enquiry_id)
    if enquiry is None:
        raise APIError(status_code=404, detail="Enquiry not found")
    enquiry.status = data.status
    _commit(db, "The enquiry could not be saved")
    db.refresh(enquiry)
    return _present_enquiry(enquiry)


def delete_enquiry(db: Session, enquiry_id: uuid.UUID) -> None:
    enquiry = db.get(TravelEnquiry, enquiry_id)
    if enquiry is None:
        raise APIError(status_code=404, detail="Enquiry not found")
    db.delete(enquiry)
    _commit(db, "The enquiry could not be deleted")


def _is_admin(viewer: User | None) -> bool:
    return viewer is not None and viewer.role == UserRole.admin


def _load_package(db: Session, package_id: uuid.UUID) -> TravelPackage | None:
    return db.scalar(select(TravelPackage).where(TravelPackage.id == package_id).options(*_package_options()))


def _reload(db: Session, package_id: uuid.UUID) -> TravelPackage:
    package = _load_package(db, package_id)
    if package is None:
        raise APIError(status_code=404, detail="Package not found")
    return package


def _ensure_slug(db: Session, slug: str, package_id: uuid.UUID | None) -> None:
    filters = [TravelPackage.slug == slug]
    if package_id is not None:
        filters.append(TravelPackage.id != package_id)
    if db.scalar(select(TravelPackage.id).where(*filters)) is not None:
        raise APIError(status_code=409, detail="Slug is already in use")


def _replace_images(package: TravelPackage, data: TravelPackageWrite) -> None:
    package.images.clear()
    for image in data.images:
        package.images.append(
            TravelPackageImage(url=image.url, alt_text=image.alt_text, sort_order=image.sort_order)
        )


def _present_package(package: TravelPackage) -> TravelPackagePublic:
    return TravelPackagePublic(
        id=package.id,
        title=package.title,
        slug=package.slug,
        category=package.category,
        destination=package.destination,
        country=package.country,
        duration=package.duration_days,
        starting_price=package.price_from_paise,
        description=package.description,
        itinerary=package.itinerary,
        accommodation=package.accommodation,
        transportation=package.transportation,
        activities=package.activities,
        inclusions=package.inclusions,
        exclusions=package.exclusions,
        images=[
            TravelImagePublic(id=image.id, url=image.url, alt_text=image.alt_text, sort_order=image.sort_order)
            for image in package.images
        ],
        status=package.status,
        featured=package.is_featured,
    )


def _present_enquiry(enquiry: TravelEnquiry) -> TravelEnquiryPublic:
    return TravelEnquiryPublic(
        id=enquiry.id,
        package_id=enquiry.travel_package_id,
        name=enquiry.name,
        email=enquiry.email,
        phone=enquiry.phone,
        destination=enquiry.destination,
        travel_date=enquiry.travel_date,
        travelers=enquiry.travelers,
        budget=enquiry.budget_paise,
        message=enquiry.message,
        status=enquiry.status,
        created_at=enquiry.created_at,
    )


def _package_options():
    return (selectinload(TravelPackage.images),)


def _commit(db: Session, detail: str) -> None:
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(status_code=409, detail=detail)
