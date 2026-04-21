from __future__ import annotations

import httpx


class MASClient:
    def __init__(self, base_url: str, token: str, timeout: float = 30.0) -> None:
        self.base_url = base_url.rstrip('/')
        self.headers = {"Authorization": f"Bearer {token}"}
        self.timeout = timeout

    def health(self) -> dict:
        response = httpx.get(f"{self.base_url}/health", headers=self.headers, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def post(self, path: str, payload: dict) -> dict:
        response = httpx.post(f"{self.base_url}{path}", headers=self.headers, json=payload, timeout=self.timeout)
        response.raise_for_status()
        return response.json()
