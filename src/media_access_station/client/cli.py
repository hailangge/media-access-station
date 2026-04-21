from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

import typer

from media_access_station.client.api_client import MASClient
from media_access_station.client.operation_log import persist_operation_log
from media_access_station.shared.schemas import HealthRequest, ImportRequest, ScanRequest, WriteBackPayload, WriteBackRequest
from media_access_station.shared.utils import new_request_id

app = typer.Typer(help="Media Access Station local client")


def _client(base_url: str, token: str) -> MASClient:
    return MASClient(base_url=base_url, token=token)


def _persist(log_root: str, endpoint: str, request_payload: dict, response_payload: dict) -> Path:
    return persist_operation_log(log_root, request_payload["request_id"], {
        "endpoint": endpoint,
        "request": request_payload,
        "response": response_payload,
    })


@app.command()
def health(
    base_url: str = typer.Option("http://127.0.0.1:8765"),
    token: str = typer.Option("change-me"),
) -> None:
    payload = HealthRequest(request_id=new_request_id()).model_dump()
    response = _client(base_url, token).health()
    typer.echo(json.dumps({"request": payload, "response": response}, ensure_ascii=False, indent=2))


@app.command("scan")
def scan_cmd(
    base_url: str = typer.Option("http://127.0.0.1:8765"),
    token: str = typer.Option("change-me"),
    log_root: str = typer.Option("./var/operation-logs"),
    scan_root: Optional[str] = typer.Option(None),
    include_hidden: bool = typer.Option(False),
    dry_run: bool = typer.Option(False),
) -> None:
    payload = ScanRequest(
        request_id=new_request_id(),
        scan_roots=[scan_root] if scan_root else None,
        include_hidden=include_hidden,
        dry_run=dry_run,
    ).model_dump()
    response = _client(base_url, token).post("/api/v1/scan", payload)
    log_path = _persist(log_root, "/api/v1/scan", payload, response)
    typer.echo(f"{response['summary']} | log={log_path}")


@app.command("import")
def import_cmd(
    device_id: str = typer.Argument(...),
    source_path: str = typer.Argument(...),
    destination_subdir: str = typer.Argument(...),
    base_url: str = typer.Option("http://127.0.0.1:8765"),
    token: str = typer.Option("change-me"),
    log_root: str = typer.Option("./var/operation-logs"),
    dry_run: bool = typer.Option(False),
    overwrite: bool = typer.Option(False),
) -> None:
    payload = ImportRequest(
        request_id=new_request_id(),
        device_id=device_id,
        source_path=source_path,
        destination_subdir=destination_subdir,
        dry_run=dry_run,
        overwrite=overwrite,
    ).model_dump()
    response = _client(base_url, token).post("/api/v1/import", payload)
    log_path = _persist(log_root, "/api/v1/import", payload, response)
    typer.echo(f"{response['summary']} | log={log_path}")


@app.command("write-back")
def write_back_cmd(
    device_id: str = typer.Argument(...),
    target_file: list[str] = typer.Argument(...),
    action: str = typer.Option(..., help="write_lrc_sidecar or write_metadata_sidecar"),
    content: Optional[str] = typer.Option(None),
    metadata_json: Optional[str] = typer.Option(None),
    base_url: str = typer.Option("http://127.0.0.1:8765"),
    token: str = typer.Option("change-me"),
    log_root: str = typer.Option("./var/operation-logs"),
    dry_run: bool = typer.Option(False),
) -> None:
    metadata = json.loads(metadata_json) if metadata_json else {}
    payload = WriteBackRequest(
        request_id=new_request_id(),
        device_id=device_id,
        target_files=target_file,
        action=action,
        payload=WriteBackPayload(content=content, metadata=metadata),
        mode="write",
        dry_run=dry_run,
    ).model_dump()
    response = _client(base_url, token).post("/api/v1/write-back", payload)
    log_path = _persist(log_root, "/api/v1/write-back", payload, response)
    typer.echo(f"{response['summary']} | log={log_path}")
