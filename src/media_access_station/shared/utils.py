from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
import uuid


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


def ensure_within_root(root: Path, candidate: Path) -> Path:
    root_resolved = root.resolve()
    candidate_resolved = candidate.resolve()
    if candidate_resolved != root_resolved and root_resolved not in candidate_resolved.parents:
        raise ValueError(f"Path {candidate_resolved} escapes root {root_resolved}")
    return candidate_resolved


def new_request_id(prefix: str = "mas") -> str:
    return f"{prefix}-{uuid.uuid4()}"


def derive_status(warnings: list[str], changed_items: list[dict], result: dict | None = None) -> str:
    result = result or {}
    had_work = (
        bool(changed_items)
        or result.get("copied_count", 0) > 0
        or result.get("changed_count", 0) > 0
        or len(result.get("planned_files", [])) > 0
    )
    if not warnings and had_work:
        return "success"
    if had_work:
        return "partial"
    return "failed"
