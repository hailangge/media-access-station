from __future__ import annotations

import argparse
from pathlib import Path

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, Request

from media_access_station.shared.config import ServerConfig
from media_access_station.shared.schemas import HealthRequest, ImportRequest, ResponseEnvelope, ScanRequest, WriteBackRequest
from media_access_station.shared.utils import utc_now
from media_access_station.server.security import verify_request
from media_access_station.server.service import handle_import, handle_scan, handle_writeback

DEFAULT_CONFIG_PATH = Path(__file__).with_name("config.example.yaml")


def create_app(config: ServerConfig) -> FastAPI:
    app = FastAPI(title="Media Access Station", version="0.1.0")
    app.state.mas_config = config

    def guarded(request: Request) -> ServerConfig:
        verify_request(request, config)
        return config

    @app.get("/health")
    def health(request: Request, _: ServerConfig = Depends(guarded)) -> dict:
        return {
            "status": "ok",
            "service": "media-access-station",
            "write_enabled": config.security.write_enabled,
            "lrc_only_mode": config.security.lrc_only_mode,
            "nas_address": config.nas.address,
            "timestamp": utc_now(),
        }

    @app.post("/api/v1/scan", response_model=ResponseEnvelope)
    def scan_endpoint(payload: ScanRequest, _: ServerConfig = Depends(guarded)) -> ResponseEnvelope:
        return handle_scan(payload, config)

    @app.post("/api/v1/import", response_model=ResponseEnvelope)
    def import_endpoint(payload: ImportRequest, _: ServerConfig = Depends(guarded)) -> ResponseEnvelope:
        try:
            return handle_import(payload, config)
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/v1/write-back", response_model=ResponseEnvelope)
    def writeback_endpoint(payload: WriteBackRequest, _: ServerConfig = Depends(guarded)) -> ResponseEnvelope:
        try:
            return handle_writeback(payload, config)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    return app


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default=str(DEFAULT_CONFIG_PATH))
    args = parser.parse_args()
    config = ServerConfig.load(args.config)
    uvicorn.run(create_app(config), host=config.server.host, port=config.server.port)


if __name__ == "__main__":
    main()
