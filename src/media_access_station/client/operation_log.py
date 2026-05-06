from __future__ import annotations

from pathlib import Path
import json

from media_access_station.shared.utils import utc_now


def persist_operation_log(log_root: str | Path, request_id: str, payload: dict) -> Path:
    base = Path(log_root)
    stamp = utc_now().split('T')[0].split('-')
    op_dir = base / "operations" / stamp[0] / stamp[1] / stamp[2]
    op_dir.mkdir(parents=True, exist_ok=True)
    target_path = op_dir / f"{request_id}.json"
    content = {
        "persisted_at": utc_now(),
        **payload,
    }
    target_path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding='utf-8')
    response = payload.get("response", {})
    response_dir = base / "responses" / stamp[0] / stamp[1] / stamp[2]
    response_dir.mkdir(parents=True, exist_ok=True)
    (response_dir / f"{request_id}.json").write_text(
        json.dumps(response, ensure_ascii=False, indent=2),
        encoding='utf-8',
    )
    summary_dir = base / "summaries" / stamp[0] / stamp[1] / stamp[2]
    summary_dir.mkdir(parents=True, exist_ok=True)
    summary = response.get("summary") or payload.get("endpoint") or "operation"
    (summary_dir / f"{request_id}.txt").write_text(str(summary), encoding='utf-8')
    if response.get("status") == "failed" or response.get("errors"):
        error_dir = base / "errors" / stamp[0] / stamp[1] / stamp[2]
        error_dir.mkdir(parents=True, exist_ok=True)
        (error_dir / f"{request_id}.json").write_text(
            json.dumps(content, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
    return target_path
