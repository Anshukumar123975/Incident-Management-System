from fastapi import Security, HTTPException, status
from fastapi.security import APIKeyHeader
from app.config import get_settings

settings = get_settings()

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(api_key: str = Security(api_key_header)):
    """
    FastAPI dependency — validates X-API-Key header.
    Apply to any route that requires authentication.
    Usage: @router.post("/signals", dependencies=[Depends(require_api_key)])
    """
    if not api_key or api_key != settings.API_KEY:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key. Include X-API-Key header.",
        )
    return api_key