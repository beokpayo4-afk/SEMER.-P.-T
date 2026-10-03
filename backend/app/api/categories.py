import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.deps import get_optional_user, require_admin
from app.db.session import get_db
from app.models.identity import User
from app.schemas.catalog import CategoryCreate, CategoryPublic, CategoryUpdate
from app.services import catalog as catalog_service

router = APIRouter()


@router.get("", response_model=list[CategoryPublic])
def list_categories(
    db: Annotated[Session, Depends(get_db)],
    viewer: Annotated[User | None, Depends(get_optional_user)],
) -> list[CategoryPublic]:
    return catalog_service.list_categories(db, viewer)


@router.get("/{category_id}", response_model=CategoryPublic)
def get_category(
    category_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    viewer: Annotated[User | None, Depends(get_optional_user)],
) -> CategoryPublic:
    return catalog_service.get_category(db, category_id, viewer)


@router.post("", response_model=CategoryPublic, status_code=status.HTTP_201_CREATED)
def create_category(
    body: CategoryCreate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> CategoryPublic:
    return catalog_service.create_category(db, body)


@router.put("/{category_id}", response_model=CategoryPublic)
def update_category(
    category_id: uuid.UUID,
    body: CategoryUpdate,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> CategoryPublic:
    return catalog_service.update_category(db, category_id, body)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_category(
    category_id: uuid.UUID,
    db: Annotated[Session, Depends(get_db)],
    _: Annotated[User, Depends(require_admin)],
) -> None:
    catalog_service.delete_category(db, category_id)
