from __future__ import annotations

from fastapi import HTTPException, Request, status

from media_access_station.shared.config import ServerConfig


def verify_request(request: Request, config: ServerConfig) -> None:
    auth_header = request.headers.get("authorization", "")
    expected = f"Bearer {config.security.auth_token}"
    if auth_header != expected:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    client_host = request.client.host if request.client else "unknown"
    if client_host not in config.security.client_ip_allowlist:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Client IP {client_host} not allowed")
