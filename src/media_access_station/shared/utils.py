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
