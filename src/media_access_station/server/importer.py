from __future__ import annotations

from pathlib import Path
import shutil
import subprocess

from media_access_station.shared.config import ServerConfig
from media_access_station.shared.schemas import ImportRequest
from media_access_station.shared.utils import ensure_within_root


def _resolve_device_root(config: ServerConfig, device_id: str) -> Path:
    mount_root = Path(config.devices.mount_root)
    return ensure_within_root(mount_root, mount_root / device_id)


def execute_import(request: ImportRequest, config: ServerConfig) -> tuple[dict, list[str], list[dict]]:
    warnings: list[str] = []
    changed: list[dict] = []
    source_root = _resolve_device_root(config, request.device_id)
    source = ensure_within_root(source_root, source_root / request.source_path)
    if not source.exists():
        raise FileNotFoundError(f"Source path not found: {source}")

    nas_root = Path(config.nas.import_root)
    nas_root.mkdir(parents=True, exist_ok=True)
    destination = ensure_within_root(nas_root, nas_root / request.destination_subdir)

    if request.dry_run:
        planned = [str(p.relative_to(source_root)) for p in ([source] if source.is_file() else source.rglob('*')) if p.is_file()]
        return {"destination": str(destination), "planned_files": planned, "transport": config.transport.method}, warnings, changed

    if config.transport.method == "rsync":
        destination.mkdir(parents=True, exist_ok=True)
        command = [config.transport.rsync.command, *config.transport.rsync.extra_args, str(source), str(destination)]
        subprocess.run(command, check=True)
        changed.append({"source": str(source), "destination": str(destination), "transport": "rsync"})
    else:
        if source.is_dir():
            destination.mkdir(parents=True, exist_ok=True)
            for item in source.rglob('*'):
                if item.is_dir():
                    continue
                rel = item.relative_to(source)
                target = destination / rel
                target.parent.mkdir(parents=True, exist_ok=True)
                if target.exists() and not request.overwrite:
                    warnings.append(f"Skipped existing file: {target}")
                    continue
                shutil.copy2(item, target)
                changed.append({"source": str(item), "destination": str(target), "bytes": target.stat().st_size})
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            final_target = destination if destination.suffix else destination / source.name
            final_target.parent.mkdir(parents=True, exist_ok=True)
            if final_target.exists() and not request.overwrite:
                warnings.append(f"Skipped existing file: {final_target}")
            else:
                shutil.copy2(source, final_target)
                changed.append({"source": str(source), "destination": str(final_target), "bytes": final_target.stat().st_size})

    return {"destination": str(destination), "copied_count": len(changed), "transport": config.transport.method}, warnings, changed
