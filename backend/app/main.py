from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.cart import router as cart_router
from app.api.categories import router as category_router
from app.api.engagement import review_router, wishlist_router
from app.api.orders import router as order_router
from app.api.payments import router as payment_router
from app.api.products import router as product_router
from app.api.events import router as event_router
from app.api.travel import router as travel_router
from app.api.uploads import router as upload_router
from app.api.router import api_router
from app.core.config import settings
from app.core.exceptions import APIError
from app.services.storage.validate import FOLDERS, MEDIA_TYPES, STORED_NAME

app = FastAPI(title=settings.app_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_origin_regex=r"https://semer(-[a-z0-9-]+)?\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(APIError)
async def handle_api_error(_: Request, exc: APIError) -> JSONResponse:
    headers = {"WWW-Authenticate": "Bearer"} if exc.status_code == 401 else {}
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail}, headers=headers)


app.include_router(api_router, prefix=settings.api_v1_prefix)
app.include_router(auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(category_router, prefix="/api/categories", tags=["categories"])
app.include_router(product_router, prefix="/api/products", tags=["products"])
app.include_router(review_router, prefix="/api/products", tags=["reviews"])
app.include_router(wishlist_router, prefix="/api/wishlist", tags=["wishlist"])
app.include_router(cart_router, prefix="/api/cart", tags=["cart"])
app.include_router(order_router, prefix="/api/orders", tags=["orders"])
app.include_router(payment_router, prefix="/api/payments", tags=["payments"])
app.include_router(travel_router, prefix="/api/travel", tags=["travel"])
app.include_router(event_router, prefix="/api/events", tags=["events"])
app.include_router(admin_router, prefix="/api/admin", tags=["admin"])
app.include_router(upload_router, prefix="/api/admin/uploads", tags=["uploads"])


@app.get("/uploads/{folder}/{name}")
def serve_upload(folder: str, name: str) -> FileResponse:
    if folder not in FOLDERS or not STORED_NAME.fullmatch(name):
        raise APIError(status_code=404, detail="Image not found")
    directory = (settings.resolved_upload_dir / folder).resolve()
    target = (directory / name).resolve()
    if not target.is_relative_to(directory) or not target.is_file():
        raise APIError(status_code=404, detail="Image not found")
    return FileResponse(
        target,
        media_type=MEDIA_TYPES[Path(name).suffix],
        headers={"X-Content-Type-Options": "nosniff"},
    )
