from fastapi import Header, HTTPException, Request, status

from config.settings import get_settings


def verify_internal_request(
    request: Request,
    x_internal_key: str | None = Header(default=None, alias="X-Internal-Key"),
) -> str:
    settings = get_settings()
    expected_key = settings.internal_service_key
    if expected_key and x_internal_key != expected_key:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid internal key")

    user_name = request.headers.get("X-User-Name", "")
    session_id = request.headers.get("X-Session-Id", "")
    request.state.user_name = user_name
    request.state.session_id = session_id
    return user_name
