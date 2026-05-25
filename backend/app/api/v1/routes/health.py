from fastapi import APIRouter

from app.schemas.health import HealthResponse

router = APIRouter()


@router.get("", response_model=HealthResponse)
def read_health() -> HealthResponse:
    """Small endpoint used by local dev, Docker healthchecks, and deployment probes."""
    return HealthResponse(status="ok")
