#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import tempfile
from typing import Any

import httpx
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from media_access_station.client.api_client import MASClient
from media_access_station.client.operation_log import persist_operation_log
from media_access_station.shared.config import ServerConfig
from media_access_station.shared.schemas import HealthRequest, ImportRequest, ScanRequest, WriteBackPayload, WriteBackRequest
from media_access_station.shared.utils import new_request_id

DEFAULT_BASE_URL = "http://127.0.0.1:8765"
DEFAULT_LOG_ROOT = "/mnt/data/workspace-media-manager/logs/media-access-station"
DEFAULT_REMOTE_HOST = "192.168.0.160"
DEFAULT_REMOTE_USER = "root"
DEFAULT_REMOTE_PORT = 8765
DEFAULT_REMOTE_APP_DIR = "/opt/media-access-station/current"
DEFAULT_REMOTE_CONFIG = "/etc/media-access-station/config.yaml"
DEFAULT_REMOTE_SERVICE = "/etc/systemd/system/media-access-station.service"
DEFAULT_REMOTE_DATA_ROOT = "/var/lib/media-access-station"


def _client(base_url: str, token: str) -> MASClient:
    return MASClient(base_url=base_url, token=token)


def _persist(log_root: str, endpoint: str, request_payload: dict[str, Any], response_payload: dict[str, Any]) -> Path:
    return persist_operation_log(log_root, request_payload["request_id"], {
        "endpoint": endpoint,
        "request": request_payload,
        "response": response_payload,
    })


def _print_json(payload: dict[str, Any]) -> None:
    print(json.dumps(payload, ensure_ascii=False, indent=2))


def _dump_model(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


def _require_password(password: str | None) -> str:
    resolved = password or os.environ.get("MAS_ORANGE_PI_PASSWORD")
    if not resolved:
        raise SystemExit("Orange Pi password is required via --password or MAS_ORANGE_PI_PASSWORD")
    return resolved


def _run(
    command: list[str],
    *,
    capture_output: bool = False,
    check: bool = True,
    input_text: str | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=check,
        text=True,
        capture_output=capture_output,
        input=input_text,
    )


def _ssh_prefix(host: str, user: str, password: str) -> list[str]:
    return [
        "sshpass",
        "-p",
        password,
        "ssh",
        "-o",
        "StrictHostKeyChecking=no",
        f"{user}@{host}",
    ]


def _scp_prefix(password: str) -> list[str]:
    return [
        "sshpass",
        "-p",
        password,
        "scp",
        "-o",
        "StrictHostKeyChecking=no",
    ]


def _ssh(host: str, user: str, password: str, command: str, *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return _run(_ssh_prefix(host, user, password) + [command], capture_output=capture_output)


def _scp_to(host: str, user: str, password: str, local_path: Path, remote_path: str) -> None:
    _run(_scp_prefix(password) + [str(local_path), f"{user}@{host}:{remote_path}"])


def _scp_from(host: str, user: str, password: str, remote_path: str, local_path: Path) -> None:
    _run(_scp_prefix(password) + [f"{user}@{host}:{remote_path}", str(local_path)])


def _rsync_repo(host: str, user: str, password: str, remote_app_dir: str) -> None:
    command = [
        "sshpass",
        "-p",
        password,
        "rsync",
        "-az",
        "--delete",
        "--exclude",
        ".git",
        "--exclude",
        ".pytest_cache",
        "--exclude",
        ".venv-review",
        "--exclude",
        ".venv",
        "--exclude",
        "__pycache__",
        "--exclude",
        "var/operation-logs",
        "--exclude",
        "var/service-logs",
        "-e",
        "ssh -o StrictHostKeyChecking=no",
        f"{REPO_ROOT}/",
        f"{user}@{host}:{remote_app_dir}/",
    ]
    _run(command)


def _remote_python(host: str, user: str, password: str, script: str) -> subprocess.CompletedProcess[str]:
    command = "python3 - <<'PY'\n" + script + "\nPY"
    return _ssh(host, user, password, command, capture_output=True)


def _wait_remote_health(host: str, user: str, password: str, token: str, port: int, timeout_seconds: int = 60) -> dict[str, Any]:
    command = (
        "for i in $(seq 1 "
        + str(timeout_seconds)
        + "); do "
        + "resp=$(curl -fsS -H "
        + shlex.quote(f"Authorization: Bearer {token}")
        + f" http://127.0.0.1:{port}/health 2>/dev/null) && echo \"$resp\" && exit 0; "
        + "sleep 1; "
        + "done; exit 1"
    )
    output = _ssh(host, user, password, command, capture_output=True).stdout.strip()
    return json.loads(output)


def _http_request(method: str, base_url: str, token: str, path: str, payload: dict[str, Any] | None = None) -> httpx.Response:
    return httpx.request(
        method,
        f"{base_url.rstrip('/')}{path}",
        headers={"Authorization": f"Bearer {token}"},
        json=payload,
        timeout=30.0,
    )


def build_orange_pi_config(
    template_path: Path,
    *,
    token: str,
    admin_ip: str,
    nas_address: str,
    write_enabled: bool,
) -> dict[str, Any]:
    data = yaml.safe_load(template_path.read_text(encoding="utf-8")) or {}
    data["security"]["auth_token"] = token
    data["security"]["client_ip_allowlist"] = ["127.0.0.1", admin_ip]
    data["security"]["write_enabled"] = write_enabled
    data["nas"]["address"] = nas_address
    return data


def run_server(args: argparse.Namespace) -> None:
    import uvicorn

    from media_access_station.server.app import create_app

    config = ServerConfig.load(args.config)
    if args.host:
        config.server.host = args.host
    if args.port:
        config.server.port = args.port
    uvicorn.run(create_app(config), host=config.server.host, port=config.server.port)


def run_health(args: argparse.Namespace) -> None:
    payload = _dump_model(HealthRequest(request_id=new_request_id()))
    response = _client(args.base_url, args.token).health()
    log_path = _persist(args.log_root, "/health", payload, response)
    _print_json({"request": payload, "response": response, "log_path": str(log_path)})


def run_scan(args: argparse.Namespace) -> None:
    payload = _dump_model(ScanRequest(
        request_id=new_request_id(),
        scan_roots=[args.scan_root] if args.scan_root else None,
        include_hidden=args.include_hidden,
        dry_run=args.dry_run,
    ))
    response = _client(args.base_url, args.token).post("/api/v1/scan", payload)
    log_path = _persist(args.log_root, "/api/v1/scan", payload, response)
    _print_json({"request": payload, "response": response, "log_path": str(log_path)})


def run_import(args: argparse.Namespace) -> None:
    payload = _dump_model(ImportRequest(
        request_id=new_request_id(),
        device_id=args.device_id,
        source_path=args.source_path,
        destination_subdir=args.destination_subdir,
        dry_run=args.dry_run,
        overwrite=args.overwrite,
    ))
    response = _client(args.base_url, args.token).post("/api/v1/import", payload)
    log_path = _persist(args.log_root, "/api/v1/import", payload, response)
    _print_json({"request": payload, "response": response, "log_path": str(log_path)})


def run_write_back(args: argparse.Namespace) -> None:
    metadata = json.loads(args.metadata_json) if args.metadata_json else {}
    payload = _dump_model(WriteBackRequest(
        request_id=new_request_id(),
        device_id=args.device_id,
        target_files=args.target_file,
        action=args.action,
        payload=WriteBackPayload(content=args.content, metadata=metadata),
        mode="write",
        dry_run=args.dry_run,
    ))
    response = _client(args.base_url, args.token).post("/api/v1/write-back", payload)
    log_path = _persist(args.log_root, "/api/v1/write-back", payload, response)
    _print_json({"request": payload, "response": response, "log_path": str(log_path)})


def _set_remote_write_enabled(
    host: str,
    user: str,
    password: str,
    config_path: str,
    enabled: bool,
) -> None:
    script = f"""
from pathlib import Path
import yaml

path = Path({config_path!r})
data = yaml.safe_load(path.read_text()) or {{}}
data.setdefault("security", {{}})["write_enabled"] = {str(enabled)}
path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
"""
    _remote_python(host, user, password, script)
    _ssh(host, user, password, "systemctl restart media-access-station.service")


def run_deploy_orange_pi(args: argparse.Namespace) -> None:
    password = _require_password(args.password)
    template_path = REPO_ROOT / "deploy" / "config.orange-pi.yaml"
    config_data = build_orange_pi_config(
        template_path,
        token=args.token,
        admin_ip=args.admin_ip,
        nas_address=args.host,
        write_enabled=args.write_enabled,
    )
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False) as config_file:
        yaml.safe_dump(config_data, config_file, sort_keys=False)
        config_path = Path(config_file.name)

    try:
        _ssh(
            args.host,
            args.user,
            password,
            (
                f"mkdir -p {shlex.quote(args.remote_app_dir)} "
                f"{shlex.quote(Path(args.remote_config).parent.as_posix())} "
                f"{shlex.quote(args.remote_data_root)}/devices "
                f"{shlex.quote(args.remote_data_root)}/nas-import "
                f"{shlex.quote(args.remote_data_root)}/service-logs "
                f"{shlex.quote(args.remote_data_root)}/tmp"
            ),
        )
        _rsync_repo(args.host, args.user, password, args.remote_app_dir)
        _scp_to(args.host, args.user, password, config_path, args.remote_config)
        _scp_to(args.host, args.user, password, REPO_ROOT / "deploy" / "media-access-station.service", args.remote_service)
        _ssh(
            args.host,
            args.user,
            password,
            (
                "systemctl stop media-access-station.service || true && "
                f"rm -rf {shlex.quote(args.remote_app_dir)}/.venv && "
                f"python3 -m venv {shlex.quote(args.remote_app_dir)}/.venv && "
                f"{shlex.quote(args.remote_app_dir)}/.venv/bin/pip install --upgrade pip setuptools wheel && "
                f"{shlex.quote(args.remote_app_dir)}/.venv/bin/pip install --no-build-isolation -e {shlex.quote(args.remote_app_dir)} && "
                "systemctl daemon-reload && "
                "systemctl enable media-access-station.service && "
                "systemctl restart media-access-station.service"
            ),
        )
        enabled = _ssh(args.host, args.user, password, "systemctl is-enabled media-access-station.service", capture_output=True).stdout.strip()
        active = _ssh(args.host, args.user, password, "systemctl is-active media-access-station.service", capture_output=True).stdout.strip()
        remote_health = _wait_remote_health(args.host, args.user, password, args.token, args.port)
        _print_json({
            "host": args.host,
            "service_enabled": enabled,
            "service_active": active,
            "remote_health": remote_health,
        })
    finally:
        config_path.unlink(missing_ok=True)


def _prepare_remote_validation_assets(host: str, user: str, password: str, data_root: str) -> None:
    script = f"""
from pathlib import Path
import shutil

data_root = Path({data_root!r})
devices = data_root / "devices"
imports = data_root / "nas-import" / "validation-suite-skill"
shutil.rmtree(imports, ignore_errors=True)

(devices / "usb-player" / "Music").mkdir(parents=True, exist_ok=True)
(devices / "usb-recorder" / "Recordings").mkdir(parents=True, exist_ok=True)
(devices / "usb-batch" / "Batch").mkdir(parents=True, exist_ok=True)

(devices / "usb-player" / "Music" / "song.mp3").write_text("music", encoding="utf-8")
(devices / "usb-recorder" / "Recordings" / "meeting.wav").write_text("recording", encoding="utf-8")
(devices / "usb-batch" / "Batch" / "file1.txt").write_text("one", encoding="utf-8")
(devices / "usb-batch" / "Batch" / "file2.txt").write_text("two", encoding="utf-8")

(imports / "import-partial").mkdir(parents=True, exist_ok=True)
(imports / "import-failed").mkdir(parents=True, exist_ok=True)
(imports / "import-partial" / "file1.txt").write_text("existing", encoding="utf-8")
(imports / "import-failed" / "meeting.wav").write_text("existing", encoding="utf-8")
"""
    _remote_python(host, user, password, script)


def _assert_status(response: httpx.Response, expected_status: int, label: str) -> dict[str, Any]:
    if response.status_code != expected_status:
        raise AssertionError(f"{label}: expected HTTP {expected_status}, got {response.status_code}: {response.text}")
    if response.content:
        return response.json()
    return {}


def _assert_result_status(body: dict[str, Any], expected_status: str, label: str) -> None:
    actual = body.get("status")
    if actual != expected_status:
        raise AssertionError(f"{label}: expected status {expected_status}, got {actual}: {body}")


def run_validate_orange_pi(args: argparse.Namespace) -> None:
    password = _require_password(args.password)
    base_url = args.base_url or f"http://{args.host}:{args.port}"
    results: list[dict[str, Any]] = []

    with tempfile.NamedTemporaryFile("w+b", delete=False) as backup_file:
        backup_path = Path(backup_file.name)
    _scp_from(args.host, args.user, password, args.remote_config, backup_path)

    try:
        _prepare_remote_validation_assets(args.host, args.user, password, args.remote_data_root)

        enabled = _ssh(args.host, args.user, password, "systemctl is-enabled media-access-station.service", capture_output=True).stdout.strip()
        active = _ssh(args.host, args.user, password, "systemctl is-active media-access-station.service", capture_output=True).stdout.strip()
        results.append({"check": "systemd-enabled", "result": enabled})
        results.append({"check": "systemd-active", "result": active})

        health = _assert_status(_http_request("GET", base_url, args.token, "/health"), 200, "health")
        results.append({"check": "health", "result": health["status"]})

        scan_payload = _dump_model(ScanRequest(request_id=new_request_id(), mode="read_only"))
        scan_body = _assert_status(_http_request("POST", base_url, args.token, "/api/v1/scan", scan_payload), 200, "scan")
        _assert_result_status(scan_body, "success", "scan")
        results.append({"check": "scan", "result": scan_body["status"]})

        scan_dry_payload = _dump_model(ScanRequest(request_id=new_request_id(), mode="read_only", dry_run=True))
        scan_dry_body = _assert_status(_http_request("POST", base_url, args.token, "/api/v1/scan", scan_dry_payload), 200, "scan-dry-run")
        results.append({"check": "scan-dry-run", "result": scan_dry_body["status"]})

        import_success = _dump_model(ImportRequest(
            request_id=new_request_id(),
            device_id="usb-recorder",
            source_path="Recordings/meeting.wav",
            destination_subdir="validation-suite-skill/import-success",
            overwrite=True,
        ))
        import_success_body = _assert_status(_http_request("POST", base_url, args.token, "/api/v1/import", import_success), 200, "import-success")
        _assert_result_status(import_success_body, "success", "import-success")
        results.append({"check": "import-success", "result": import_success_body["status"]})

        import_partial = _dump_model(ImportRequest(
            request_id=new_request_id(),
            device_id="usb-batch",
            source_path="Batch",
            destination_subdir="validation-suite-skill/import-partial",
            overwrite=False,
        ))
        import_partial_body = _assert_status(_http_request("POST", base_url, args.token, "/api/v1/import", import_partial), 200, "import-partial")
        _assert_result_status(import_partial_body, "partial", "import-partial")
        results.append({"check": "import-partial", "result": import_partial_body["status"]})

        import_failed = _dump_model(ImportRequest(
            request_id=new_request_id(),
            device_id="usb-recorder",
            source_path="Recordings/meeting.wav",
            destination_subdir="validation-suite-skill/import-failed",
            overwrite=False,
        ))
        import_failed_body = _assert_status(_http_request("POST", base_url, args.token, "/api/v1/import", import_failed), 200, "import-failed")
        _assert_result_status(import_failed_body, "failed", "import-failed")
        results.append({"check": "import-failed", "result": import_failed_body["status"]})

        import_missing = _dump_model(ImportRequest(
            request_id=new_request_id(),
            device_id="usb-recorder",
            source_path="Recordings/missing.wav",
            destination_subdir="validation-suite-skill/import-missing",
            overwrite=True,
        ))
        _assert_status(_http_request("POST", base_url, args.token, "/api/v1/import", import_missing), 400, "import-missing")
        results.append({"check": "import-missing", "result": "400"})

        import_escape = _dump_model(ImportRequest(
            request_id=new_request_id(),
            device_id="usb-recorder",
            source_path="../etc/passwd",
            destination_subdir="validation-suite-skill/import-escape",
            overwrite=True,
        ))
        _assert_status(_http_request("POST", base_url, args.token, "/api/v1/import", import_escape), 400, "import-path-escape")
        results.append({"check": "import-path-escape", "result": "400"})

        write_blocked = _dump_model(WriteBackRequest(
            request_id=new_request_id(),
            device_id="usb-player",
            target_files=["Music/song.mp3"],
            action="write_lrc_sidecar",
            payload=WriteBackPayload(content="blocked"),
            mode="write",
        ))
        _assert_status(_http_request("POST", base_url, args.token, "/api/v1/write-back", write_blocked), 403, "write-back-disabled")
        results.append({"check": "write-back-disabled", "result": "403"})

        _set_remote_write_enabled(args.host, args.user, password, args.remote_config, True)

        write_success = _dump_model(WriteBackRequest(
            request_id=new_request_id(),
            device_id="usb-player",
            target_files=["Music/song.mp3"],
            action="write_lrc_sidecar",
            payload=WriteBackPayload(content="skill lyric"),
            mode="write",
        ))
        write_success_body = _assert_status(_http_request("POST", base_url, args.token, "/api/v1/write-back", write_success), 200, "write-success")
        _assert_result_status(write_success_body, "success", "write-success")
        results.append({"check": "write-success", "result": write_success_body["status"]})

        write_partial = _dump_model(WriteBackRequest(
            request_id=new_request_id(),
            device_id="usb-player",
            target_files=["Music", "Music/song.mp3"],
            action="write_lrc_sidecar",
            payload=WriteBackPayload(content="skill lyric"),
            mode="write",
        ))
        write_partial_body = _assert_status(_http_request("POST", base_url, args.token, "/api/v1/write-back", write_partial), 200, "write-partial")
        _assert_result_status(write_partial_body, "partial", "write-partial")
        results.append({"check": "write-partial", "result": write_partial_body["status"]})

        write_failed = _dump_model(WriteBackRequest(
            request_id=new_request_id(),
            device_id="usb-player",
            target_files=["Music"],
            action="write_lrc_sidecar",
            payload=WriteBackPayload(content="skill lyric"),
            mode="write",
        ))
        write_failed_body = _assert_status(_http_request("POST", base_url, args.token, "/api/v1/write-back", write_failed), 200, "write-failed")
        _assert_result_status(write_failed_body, "failed", "write-failed")
        results.append({"check": "write-failed", "result": write_failed_body["status"]})

        write_dry = _dump_model(WriteBackRequest(
            request_id=new_request_id(),
            device_id="usb-player",
            target_files=["Music/song.mp3"],
            action="write_metadata_sidecar",
            payload=WriteBackPayload(metadata={"title": "dry"}),
            mode="write",
            dry_run=True,
        ))
        write_dry_body = _assert_status(_http_request("POST", base_url, args.token, "/api/v1/write-back", write_dry), 200, "write-dry-run")
        results.append({"check": "write-dry-run", "result": write_dry_body["status"]})

        write_tags = _dump_model(WriteBackRequest(
            request_id=new_request_id(),
            device_id="usb-player",
            target_files=["Music/song.mp3"],
            action="write_audio_tags",
            payload=WriteBackPayload(metadata={"title": "Skill Song", "artist": "Skill Artist", "genre": "Speech"}),
            mode="write",
        ))
        write_tags_body = _assert_status(_http_request("POST", base_url, args.token, "/api/v1/write-back", write_tags), 200, "write-audio-tags")
        _assert_result_status(write_tags_body, "success", "write-audio-tags")
        results.append({"check": "write-audio-tags", "result": write_tags_body["status"]})

        write_escape = _dump_model(WriteBackRequest(
            request_id=new_request_id(),
            device_id="usb-player",
            target_files=["../escape.mp3"],
            action="write_lrc_sidecar",
            payload=WriteBackPayload(content="escape"),
            mode="write",
        ))
        _assert_status(_http_request("POST", base_url, args.token, "/api/v1/write-back", write_escape), 400, "write-path-escape")
        results.append({"check": "write-path-escape", "result": "400"})

        pid_before = _ssh(args.host, args.user, password, "systemctl show -p MainPID --value media-access-station.service", capture_output=True).stdout.strip()
        _ssh(args.host, args.user, password, f"kill -9 {shlex.quote(pid_before)}")
        pid_after = _ssh(
            args.host,
            args.user,
            password,
            "for i in 1 2 3 4 5 6 7 8 9 10; do "
            "pid=$(systemctl show -p MainPID --value media-access-station.service); "
            "state=$(systemctl is-active media-access-station.service); "
            f"if [ \"$state\" = active ] && [ \"$pid\" != {shlex.quote(pid_before)} ] && [ \"$pid\" != 0 ]; then echo \"$pid\"; exit 0; fi; "
            "sleep 1; "
            "done; exit 1",
            capture_output=True,
        ).stdout.strip()
        results.append({"check": "crash-restart", "result": {"before": pid_before, "after": pid_after}})
    finally:
        _scp_to(args.host, args.user, password, backup_path, args.remote_config)
        _ssh(args.host, args.user, password, "systemctl restart media-access-station.service")
        backup_path.unlink(missing_ok=True)

    _print_json({"host": args.host, "base_url": base_url, "checks": results})


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Media Access Station skill entrypoints")
    subparsers = parser.add_subparsers(dest="command", required=True)

    server = subparsers.add_parser("server", help="Start the Media Access Station server")
    server.add_argument("--config", default=str(REPO_ROOT / "src" / "media_access_station" / "server" / "config.example.yaml"))
    server.add_argument("--host")
    server.add_argument("--port", type=int)
    server.set_defaults(func=run_server)

    health = subparsers.add_parser("health", help="Call GET /health")
    health.add_argument("--base-url", default=DEFAULT_BASE_URL)
    health.add_argument("--token", default="change-me")
    health.add_argument("--log-root", default=DEFAULT_LOG_ROOT)
    health.set_defaults(func=run_health)

    scan = subparsers.add_parser("scan", help="Call POST /api/v1/scan")
    scan.add_argument("--base-url", default=DEFAULT_BASE_URL)
    scan.add_argument("--token", default="change-me")
    scan.add_argument("--log-root", default=DEFAULT_LOG_ROOT)
    scan.add_argument("--scan-root")
    scan.add_argument("--include-hidden", action="store_true")
    scan.add_argument("--dry-run", action="store_true")
    scan.set_defaults(func=run_scan)

    import_cmd = subparsers.add_parser("import-to-nas", help="Call POST /api/v1/import")
    import_cmd.add_argument("device_id")
    import_cmd.add_argument("source_path")
    import_cmd.add_argument("destination_subdir")
    import_cmd.add_argument("--base-url", default=DEFAULT_BASE_URL)
    import_cmd.add_argument("--token", default="change-me")
    import_cmd.add_argument("--log-root", default=DEFAULT_LOG_ROOT)
    import_cmd.add_argument("--dry-run", action="store_true")
    import_cmd.add_argument("--overwrite", action="store_true")
    import_cmd.set_defaults(func=run_import)

    write_back = subparsers.add_parser("write-back", help="Call POST /api/v1/write-back")
    write_back.add_argument("device_id")
    write_back.add_argument("target_file", nargs="+")
    write_back.add_argument("--action", required=True, choices=["write_lrc_sidecar", "write_metadata_sidecar", "write_audio_tags"])
    write_back.add_argument("--content")
    write_back.add_argument("--metadata-json")
    write_back.add_argument("--base-url", default=DEFAULT_BASE_URL)
    write_back.add_argument("--token", default="change-me")
    write_back.add_argument("--log-root", default=DEFAULT_LOG_ROOT)
    write_back.add_argument("--dry-run", action="store_true")
    write_back.set_defaults(func=run_write_back)

    deploy = subparsers.add_parser("deploy-orange-pi", help="Deploy the project to an Orange Pi host")
    deploy.add_argument("--host", default=DEFAULT_REMOTE_HOST)
    deploy.add_argument("--user", default=DEFAULT_REMOTE_USER)
    deploy.add_argument("--password")
    deploy.add_argument("--token", required=True)
    deploy.add_argument("--admin-ip", required=True)
    deploy.add_argument("--port", type=int, default=DEFAULT_REMOTE_PORT)
    deploy.add_argument("--write-enabled", action="store_true")
    deploy.add_argument("--remote-app-dir", default=DEFAULT_REMOTE_APP_DIR)
    deploy.add_argument("--remote-config", default=DEFAULT_REMOTE_CONFIG)
    deploy.add_argument("--remote-service", default=DEFAULT_REMOTE_SERVICE)
    deploy.add_argument("--remote-data-root", default=DEFAULT_REMOTE_DATA_ROOT)
    deploy.set_defaults(func=run_deploy_orange_pi)

    validate = subparsers.add_parser("validate-orange-pi", help="Run end-to-end validation against the Orange Pi service")
    validate.add_argument("--host", default=DEFAULT_REMOTE_HOST)
    validate.add_argument("--user", default=DEFAULT_REMOTE_USER)
    validate.add_argument("--password")
    validate.add_argument("--token", required=True)
    validate.add_argument("--base-url")
    validate.add_argument("--port", type=int, default=DEFAULT_REMOTE_PORT)
    validate.add_argument("--remote-config", default=DEFAULT_REMOTE_CONFIG)
    validate.add_argument("--remote-data-root", default=DEFAULT_REMOTE_DATA_ROOT)
    validate.set_defaults(func=run_validate_orange_pi)

    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
