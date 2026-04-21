from __future__ import annotations

from pathlib import Path
import json

from media_access_station.shared.config import ServerConfig
from media_access_station.shared.schemas import WriteBackRequest
from media_access_station.shared.utils import ensure_within_root


def _resolve_device_root(config: ServerConfig, device_id: str) -> Path:
    mount_root = Path(config.devices.mount_root)
    return ensure_within_root(mount_root, mount_root / device_id)


def execute_writeback(request: WriteBackRequest, config: ServerConfig) -> tuple[dict, list[str], list[dict]]:
    if not config.security.write_enabled:
        raise PermissionError("Server write operations are disabled by default")
    if request.mode != "write":
        raise PermissionError("Request mode must be 'write' for write-back")

    warnings: list[str] = []
    changes: list[dict] = []
    root = _resolve_device_root(config, request.device_id)

    for target_file in request.target_files:
        target = ensure_within_root(root, root / target_file)
        if target.is_dir():
            warnings.append(f"Skipped directory target: {target}")
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        if request.action == "write_lrc_sidecar":
            sidecar = target.with_suffix('.lrc')
            if request.dry_run:
                changes.append({"target": str(target), "sidecar": str(sidecar), "action": request.action, "dry_run": True})
                continue
            sidecar.write_text(request.payload.content or "", encoding='utf-8')
            changes.append({"target": str(target), "sidecar": str(sidecar), "action": request.action})
        elif request.action == "write_metadata_sidecar":
            sidecar = target.with_suffix(target.suffix + '.meta.json')
            if request.dry_run:
                changes.append({"target": str(target), "sidecar": str(sidecar), "action": request.action, "dry_run": True})
                continue
            sidecar.write_text(json.dumps(request.payload.metadata, ensure_ascii=False, indent=2), encoding='utf-8')
            changes.append({"target": str(target), "sidecar": str(sidecar), "action": request.action})
        else:
            warnings.append(f"Unsupported action skipped: {request.action}")

    return {"changed_count": len(changes), "action": request.action}, warnings, changes
