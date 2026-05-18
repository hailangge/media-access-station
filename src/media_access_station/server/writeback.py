from __future__ import annotations

import json
from pathlib import Path

from mutagen.id3 import ID3, ID3NoHeaderError, TALB, TCON, TDRC, TIT2, TPE1

from media_access_station.shared.config import ServerConfig
from media_access_station.shared.schemas import WriteBackRequest
from media_access_station.shared.utils import ensure_within_root


def _resolve_device_root(config: ServerConfig, device_id: str) -> Path:
    mount_root = Path(config.devices.mount_root)
    return ensure_within_root(mount_root, mount_root / device_id)


def _normalize_text_list(value: object) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item is not None]
    return [str(value)]


def _write_mp3_tags(target: Path, metadata: dict) -> dict[str, object]:
    try:
        tags = ID3(str(target))
    except ID3NoHeaderError:
        tags = ID3()
    changed_fields: dict[str, object] = {}

    title = metadata.get("title")
    if title is not None:
        tags.delall("TIT2")
        tags.add(TIT2(encoding=3, text=_normalize_text_list(title)))
        changed_fields["title"] = title

    artist = metadata.get("artist")
    if artist is not None:
        tags.delall("TPE1")
        tags.add(TPE1(encoding=3, text=_normalize_text_list(artist)))
        changed_fields["artist"] = artist

    album = metadata.get("album")
    if album is not None:
        tags.delall("TALB")
        tags.add(TALB(encoding=3, text=_normalize_text_list(album)))
        changed_fields["album"] = album

    genre = metadata.get("genre")
    if genre is not None:
        tags.delall("TCON")
        tags.add(TCON(encoding=3, text=_normalize_text_list(genre)))
        changed_fields["genre"] = genre

    year = metadata.get("year")
    if year is not None:
        tags.delall("TDRC")
        tags.add(TDRC(encoding=3, text=_normalize_text_list(year)))
        changed_fields["year"] = year

    if changed_fields:
        tags.save(str(target))
    return changed_fields


def _write_audio_tags(target: Path, metadata: dict, dry_run: bool) -> dict[str, object]:
    supported_suffixes = {".mp3"}
    if target.suffix.lower() not in supported_suffixes:
        raise ValueError(f"Unsupported audio tag target type: {target.suffix or '<none>'}")
    if dry_run:
        return {
            "target": str(target),
            "action": "write_audio_tags",
            "metadata": metadata,
            "dry_run": True,
        }
    changed_fields = _write_mp3_tags(target, metadata)
    if not changed_fields:
        return {
            "target": str(target),
            "action": "write_audio_tags",
            "metadata": metadata,
            "warning": "No supported metadata fields provided",
        }
    return {
        "target": str(target),
        "action": "write_audio_tags",
        "metadata": changed_fields,
    }


def execute_writeback(request: WriteBackRequest, config: ServerConfig) -> tuple[dict, list[str], list[dict]]:
    if not config.security.write_enabled:
        raise PermissionError("Server write operations are disabled in config")
    if request.mode != "write":
        raise PermissionError("Request mode must be 'write' for write-back")
    if config.security.lrc_only_mode and request.action != "write_lrc_sidecar":
        raise PermissionError("Server is in lrc_only_mode; only write_lrc_sidecar is allowed")

    warnings: list[str] = []
    changes: list[dict] = []
    root = _resolve_device_root(config, request.device_id)

    for target_file in request.target_files:
        target = ensure_within_root(root, root / target_file)
        if not target.exists():
            warnings.append(f"Skipped missing target file: {target}")
            continue
        if target.is_dir():
            warnings.append(f"Skipped directory target: {target}")
            continue
        if request.action == "write_lrc_sidecar":
            sidecar = target.with_suffix('.lrc')
            if request.dry_run:
                changes.append({"target": str(target), "sidecar": str(sidecar), "action": request.action, "dry_run": True})
                continue
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_text(request.payload.content or "", encoding='utf-8')
            changes.append({"target": str(target), "sidecar": str(sidecar), "action": request.action})
        elif request.action == "write_metadata_sidecar":
            if config.security.lrc_only_mode:
                warnings.append("Skipped write_metadata_sidecar because lrc_only_mode is enabled")
                continue
            sidecar = target.with_suffix(target.suffix + '.meta.json')
            if request.dry_run:
                changes.append({"target": str(target), "sidecar": str(sidecar), "action": request.action, "dry_run": True})
                continue
            sidecar.parent.mkdir(parents=True, exist_ok=True)
            sidecar.write_text(json.dumps(request.payload.metadata, ensure_ascii=False, indent=2), encoding='utf-8')
            changes.append({"target": str(target), "sidecar": str(sidecar), "action": request.action})
        elif request.action == "write_audio_tags":
            if config.security.lrc_only_mode:
                warnings.append("Skipped write_audio_tags because lrc_only_mode is enabled")
                continue
            try:
                result = _write_audio_tags(target, request.payload.metadata, request.dry_run)
            except ValueError as exc:
                warnings.append(str(exc))
                continue
            if result.get("warning"):
                warnings.append(str(result["warning"]))
            changes.append(result)
        else:
            warnings.append(f"Unsupported action skipped: {request.action}")

    return {"changed_count": len(changes), "action": request.action}, warnings, changes
