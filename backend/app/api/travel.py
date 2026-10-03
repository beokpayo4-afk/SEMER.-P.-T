import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user, require_admin
from app.db.session import get_db
from app.models.enums import EnquiryStatus, PackageType, RecordStatus, TravelCategory
from app.models.identity import User
from app.schemas.travel import (
    TravelEnquiryCreate,
    TravelEnquiryPage,
    TravelEnquiryPublic,
    TravelEnquiryUpdate,
    TravelPackagePage,
    TravelPackagePublic,
    TravelPackageWrite,
)
from app.services import travel as travel_service

router = APIRouter()


@router.get("", response_model=TravelPackagePage)
def list_packages(
    db: Annotated[Session, Depends(get_db)],
    viewer: Annotated[User | None, Depends(get_optional_user)],
    category: Annotated[TravelCategory | None, Query()] = None,
    package_type: Annotated[PackageType | None, Query()] = None,
    featured: Annotated[bool | None, Query()] = None,
    status_filter: Annotated[RecordStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TravelPackagePage:
    return travel_service.list_packages(
        db,
        viewer=viewer,
        category=category,
        package_type=package_type,
        featured=featured,
        status=status_filter,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=TravelPackagePublic, status_code=status.HTTP_201_CREATED)
def create_package(
    body: TravelPackageWrite,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> TravelPackagePublic:
    return travel_service.create_package(db, body)


@router.get("/enquiries", response_model=TravelEnquiryPage)
def list_enquiries(
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
    status_filter: Annotated[EnquiryStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> TravelEnquiryPage:
    return travel_service.list_enquiries(db, status=status_filter, page=page, page_size=page_size)


@router.post("/enquiries", response_model=TravelEnquiryPublic, status_code=status.HTTP_201_CREATED)
def create_enquiry(
    body: TravelEnquiryCreate,
    db: Annotated[Session, Depends(get_db)],
    viewer: Annotated[User | None, Depends(get_optional_user)],
) -> TravelEnquiryPublic:
    return travel_service.create_enquiry(db, body, viewer)


@router.get("/enquiries/{enquiry_id}", response_model=TravelEnquiryPublic)
def get_enquiry(
    enquiry_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> TravelEnquiryPublic:
    return travel_service.get_enquiry(db, enquiry_id)


@router.patch("/enquiries/{enquiry_id}", response_model=TravelEnquiryPublic)
def update_enquiry(
    enquiry_id: uuid.UUID,
    body: TravelEnquiryUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> TravelEnquiryPublic:
    return travel_service.update_enquiry(db, enquiry_id, body)


@router.delete("/enquiries/{enquiry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_enquiry(
    enquiry_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    travel_service.delete_enquiry(db, enquiry_id)


@router.get("/by-slug/{slug}", response_model=TravelPackagePublic)
def get_package_by_slug(
    slug: str,
    db: Annotated[Session, Depends(get_db)],
    viewer: Annotated[User | None, Depends(get_optional_user)],
) -> TravelPackagePublic:
    return travel_service.get_package_by_slug(db, slug, viewer)


@router.get("/{package_id}", response_model=TravelPackagePublic)
def get_package(
    package_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    viewer: Annotated[User | None, Depends(get_optional_user)],
) -> TravelPackagePublic:
    return travel_service.get_package(db, package_id, viewer)


@router.put("/{package_id}", response_model=TravelPackagePublic)
def update_package(
    package_id: uuid.UUID,
    body: TravelPackageWrite,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> TravelPackagePublic:
    return travel_service.update_package(db, package_id, body)


@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_package(
    package_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    travel_service.delete_package(db, package_id)
