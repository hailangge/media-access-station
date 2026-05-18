from __future__ import annotations

import csv
import importlib.util
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

from media_access_station.shared.config import ServerConfig
from media_access_station.shared.schemas import LyricsAlignRequest


def _safe_request_id(value: str) -> str:
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in value) or "lyrics-align"


def check_gpu_capability() -> dict[str, Any]:
    nvidia_smi = shutil.which("nvidia-smi")
    nvidia_smi_available = False
    nvidia_smi_error: str | None = None
    if nvidia_smi:
        try:
            subprocess.run(
                [nvidia_smi, "--query-gpu=name", "--format=csv,noheader"],
                check=True,
                capture_output=True,
                text=True,
                timeout=5,
            )
            nvidia_smi_available = True
        except Exception as exc:  # noqa: BLE001
            nvidia_smi_error = str(exc)

    torch_installed = importlib.util.find_spec("torch") is not None
    torch_cuda_available = False
    torch_cuda_error: str | None = None
    if torch_installed:
        try:
            import torch  # type: ignore[import-not-found]

            torch_cuda_available = bool(torch.cuda.is_available())
        except Exception as exc:  # noqa: BLE001
            torch_cuda_error = str(exc)

    return {
        "nvidia_smi_available": nvidia_smi_available,
        "nvidia_smi_path": nvidia_smi,
        "nvidia_smi_error": nvidia_smi_error,
        "torch_installed": torch_installed,
        "torch_cuda_available": torch_cuda_available,
        "torch_cuda_error": torch_cuda_error,
        "gpu_available": nvidia_smi_available or torch_cuda_available,
    }


def _request_rows(request: LyricsAlignRequest, status: str, code: str, message: str, capability: dict[str, Any]) -> list[dict[str, Any]]:
    audio_paths = request.server_audio_paths or [""]
    rows: list[dict[str, Any]] = []
    for index, audio_path in enumerate(audio_paths):
        lrc_path = request.server_lrc_paths[index] if index < len(request.server_lrc_paths) else ""
        rows.append(
            {
                "request_id": request.request_id,
                "status": status,
                "code": code,
                "message": message,
                "server_audio_path": audio_path,
                "server_lrc_path": lrc_path,
                "gpu_available": capability["gpu_available"],
                "nvidia_smi_available": capability["nvidia_smi_available"],
                "torch_installed": capability["torch_installed"],
                "torch_cuda_available": capability["torch_cuda_available"],
            }
        )
    return rows


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "request_id",
        "status",
        "code",
        "message",
        "server_audio_path",
        "server_lrc_path",
        "gpu_available",
        "nvidia_smi_available",
        "torch_installed",
        "torch_cuda_available",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_markdown(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Lyrics Alignment Report",
        "",
        "| status | code | server_audio_path | server_lrc_path | message |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {status} | {code} | {server_audio_path} | {server_lrc_path} | {message} |".format(
                status=row["status"],
                code=row["code"],
                server_audio_path=row["server_audio_path"],
                server_lrc_path=row["server_lrc_path"],
                message=str(row["message"]).replace("|", "\\|"),
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_reports(config: ServerConfig, request: LyricsAlignRequest, rows: list[dict[str, Any]]) -> dict[str, str]:
    report_dir = Path(config.operations.service_log_dir) / "lyrics-alignment"
    stem = _safe_request_id(request.request_id)
    csv_path = report_dir / f"{stem}.csv"
    markdown_path = report_dir / f"{stem}.md"
    _write_csv(csv_path, rows)
    _write_markdown(markdown_path, rows)
    return {"report_csv_path": str(csv_path.resolve()), "report_markdown_path": str(markdown_path.resolve())}


def execute_lyrics_alignment(request: LyricsAlignRequest, config: ServerConfig) -> tuple[dict[str, Any], list[str], list[dict[str, Any]], list[str]]:
    capability = check_gpu_capability()
    warnings: list[str] = []
    errors: list[str] = []

    if not config.lyrics_alignment.enabled:
        message = "Lyrics alignment is disabled in config"
        rows = _request_rows(request, "failed", "lyrics_alignment_disabled", message, capability)
        reports = _write_reports(config, request, rows)
        return {"code": "lyrics_alignment_disabled", "message": message, "capability": capability, **reports}, warnings, [], [message]

    if config.lyrics_alignment.require_cuda and not capability["gpu_available"]:
        message = "Lyrics alignment requires CUDA GPU on this media server"
        rows = _request_rows(request, "failed", "gpu_unavailable", message, capability)
        reports = _write_reports(config, request, rows)
        return {"code": "gpu_unavailable", "message": message, "capability": capability, **reports}, warnings, [], [message]

    if not config.lyrics_alignment.runner_command:
        message = "Lyrics alignment runner_command is not configured on this media server"
        rows = _request_rows(request, "failed", "runner_unconfigured", message, capability)
        reports = _write_reports(config, request, rows)
        return {"code": "runner_unconfigured", "message": message, "capability": capability, **reports}, warnings, [], [message]

    report_dir = Path(config.operations.service_log_dir) / "lyrics-alignment"
    report_dir.mkdir(parents=True, exist_ok=True)
    request_json = report_dir / f"{_safe_request_id(request.request_id)}.request.json"
    request_json.write_text(json.dumps(request.model_dump(), ensure_ascii=False, indent=2), encoding="utf-8")
    command = [*config.lyrics_alignment.runner_command, str(request_json), str(report_dir)]
    completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=None)
    if completed.returncode != 0:
        message = completed.stderr.strip() or f"Lyrics alignment runner failed with exit code {completed.returncode}"
        rows = _request_rows(request, "failed", "runner_failed", message, capability)
        reports = _write_reports(config, request, rows)
        return {"code": "runner_failed", "message": message, "capability": capability, "stdout": completed.stdout, **reports}, warnings, [], [message]

    result = json.loads(completed.stdout) if completed.stdout.strip().startswith("{") else {"stdout": completed.stdout}
    changed = result.get("changed_items", []) if isinstance(result.get("changed_items"), list) else []
    return {"code": "completed", "message": "Lyrics alignment runner completed", "capability": capability, **result}, warnings, changed, errors
