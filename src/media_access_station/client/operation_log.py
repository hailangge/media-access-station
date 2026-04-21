from __future__ import annotations

from pathlib import Path
import json

from media_access_station.shared.utils import utc_now


def persist_operation_log(log_root: str | Path, request_id: str, payload: dict) -> Path:
    base = Path(log_root)
    stamp = utc_now().split('T')[0].split('-')
    target_dir = base / stamp[0] / stamp[1] / stamp[2]
    target_dir.mkdir(parents=True, exist_ok=True)
    target_path = target_dir / f"{request_id}.json"
    content = {
        "persisted_at": utc_now(),
        **payload,
    }
    target_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding='utf-8')
    return target_path
