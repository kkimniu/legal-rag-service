from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Response body for service health checks."""

    status: str
