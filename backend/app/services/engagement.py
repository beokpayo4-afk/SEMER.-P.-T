import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.exceptions import APIError
from app.models.catalog import Review
from app.models.commerce import Wishlist, WishlistItem
from app.models.enums import RecordStatus
from app.models.identity import User
from app.repositories.products import ProductRepository
from app.schemas.engagement import ReviewCreate, ReviewPage, ReviewPublic, WishlistResponse
from app.services.catalog import review_stats


def list_reviews(db: Session, product_id: uuid.UUID) -> ReviewPage:
    _active_product(db, product_id)
    reviews = list(
        db.scalars(
            select(Review)
            .where(Review.product_id == product_id)
            .options(selectinload(Review.user))
            .order_by(Review.created_at.desc())
        ).all()
    )
    stats = review_stats(db, [product_id]).get(product_id, (None, 0))
    return ReviewPage(
        items=[_review_public(review) for review in reviews],
        total=len(reviews),
        rating_average=stats[0],
        review_count=stats[1],
    )


def create_review(db: Session, product_id: uuid.UUID, user: User, data: ReviewCreate) -> ReviewPage:
    _active_product(db, product_id)
    existing = db.scalar(
        select(Review.id).where(Review.product_id == product_id, Review.user_id == user.id)
    )
    if existing is not None:
        raise APIError(status_code=409, detail="You have already reviewed this product")
    comment = data.comment.strip() if data.comment else None
    review = Review(
        product_id=product_id,
        user_id=user.id,
        rating=data.rating,
        comment=comment or None,
    )
    db.add(review)
    db.commit()
    return list_reviews(db, product_id)


def list_wishlist(db: Session, user: User) -> WishlistResponse:
    wishlist = _wishlist(db, user)
    return WishlistResponse(product_ids=[item.product_id for item in wishlist.items])


def add_wishlist_item(db: Session, user: User, product_id: uuid.UUID) -> WishlistResponse:
    _active_product(db, product_id)
    wishlist = _wishlist(db, user)
    if any(item.product_id == product_id for item in wishlist.items):
        return WishlistResponse(product_ids=[item.product_id for item in wishlist.items])
    wishlist.items.append(WishlistItem(product_id=product_id))
    db.commit()
    db.refresh(wishlist)
    return list_wishlist(db, user)


def remove_wishlist_item(db: Session, user: User, product_id: uuid.UUID) -> None:
    wishlist = db.scalar(
        select(Wishlist).where(Wishlist.user_id == user.id).options(selectinload(Wishlist.items))
    )
    if wishlist is None:
        raise APIError(status_code=404, detail="Product is not in the wishlist")
    item = next((entry for entry in wishlist.items if entry.product_id == product_id), None)
    if item is None:
        raise APIError(status_code=404, detail="Product is not in the wishlist")
    db.delete(item)
    db.commit()


def _active_product(db: Session, product_id: uuid.UUID) -> None:
    product = ProductRepository(db).get(product_id)
    if product is None or product.status != RecordStatus.active:
        raise APIError(status_code=404, detail="Product not found")


def _wishlist(db: Session, user: User) -> Wishlist:
    wishlist = db.scalar(
        select(Wishlist).where(Wishlist.user_id == user.id).options(selectinload(Wishlist.items))
    )
    if wishlist is not None:
        return wishlist
    wishlist = Wishlist(user_id=user.id)
    db.add(wishlist)
    db.flush()
    return wishlist


def _review_public(review: Review) -> ReviewPublic:
    return ReviewPublic(
        id=review.id,
        product_id=review.product_id,
        rating=review.rating,
        comment=review.comment,
        author_name=review.user.full_name,
        created_at=review.created_at,
    )
