import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user, require_admin
from app.db.session import get_db
from app.models.enums import RecordStatus
from app.models.identity import User
from app.schemas.catalog import ProductPage, ProductPublic, ProductUpdate, ProductWrite
from app.services import catalog as catalog_service

router = APIRouter()


@router.get("", response_model=ProductPage)
def list_products(
    db: Annotated[Session, Depends(get_db)],
    viewer: Annotated[User | None, Depends(get_optional_user)],
    category: Annotated[uuid.UUID | None, Query()] = None,
    search: Annotated[str | None, Query()] = None,
    min_price: Annotated[int | None, Query(ge=0)] = None,
    max_price: Annotated[int | None, Query(ge=0)] = None,
    available: Annotated[bool | None, Query()] = None,
    status_filter: Annotated[RecordStatus | None, Query(alias="status")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
    sort: Annotated[str, Query()] = "-created_at",
) -> ProductPage:
    return catalog_service.list_products(
        db,
        viewer=viewer,
        category_id=category,
        search=search,
        min_price=min_price,
        max_price=max_price,
        available=available,
        status=status_filter,
        page=page,
        page_size=page_size,
        sort=sort,
    )


@router.get("/{product_id}", response_model=ProductPublic)
def get_product(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    viewer: Annotated[User | None, Depends(get_optional_user)],
) -> ProductPublic:
    return catalog_service.get_product(db, product_id, viewer)


@router.post("", response_model=ProductPublic, status_code=status.HTTP_201_CREATED)
def create_product(
    body: ProductWrite,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> ProductPublic:
    return catalog_service.create_product(db, body)


@router.put("/{product_id}", response_model=ProductPublic)
def update_product(
    product_id: uuid.UUID,
    body: ProductUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> ProductPublic:
    return catalog_service.update_product(db, product_id, body)


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(
    product_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    catalog_service.delete_product(db, product_id)
