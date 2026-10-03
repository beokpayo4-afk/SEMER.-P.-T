from app.core.config import settings
from app.schemas.health import HealthResponse


def get_health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.app_name)
