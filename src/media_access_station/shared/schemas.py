from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field

from media_access_station.shared.utils import utc_now

TaskType = Literal["health_check", "scan", "import_to_nas", "write_back"]
ModeType = Literal["read_only", "write"]
WriteActionType = Literal["write_lrc_sidecar", "write_metadata_sidecar"]
StatusType = Literal["success", "error", "blocked"]


class RequestBase(BaseModel):
    request_id: str
    task_type: TaskType
    requested_at: str = Field(default_factory=utc_now)
    dry_run: bool = False
    mode: ModeType = "read_only"


class HealthRequest(RequestBase):
    task_type: Literal["health_check"] = "health_check"


class ScanRequest(RequestBase):
    task_type: Literal["scan"] = "scan"
    scan_roots: list[str] | None = None
    include_hidden: bool = False


class ImportRequest(RequestBase):
    task_type: Literal["import_to_nas"] = "import_to_nas"
    device_id: str
    source_path: str
    destination_subdir: str
    overwrite: bool = False


class WriteBackPayload(BaseModel):
    content: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class WriteBackRequest(RequestBase):
    task_type: Literal["write_back"] = "write_back"
    device_id: str
    target_files: list[str]
    action: WriteActionType
    payload: WriteBackPayload = Field(default_factory=WriteBackPayload)


class DeviceRecord(BaseModel):
    device_id: str
    path: str
    label: str
    filesystem: str = "mockfs"
    mock: bool = False
    files_sample: list[str] = Field(default_factory=list)


class OperationLog(BaseModel):
    request_id: str
    task_type: TaskType
    status: StatusType
    server_timestamp: str = Field(default_factory=utc_now)
    target_device: str | None = None
    target_paths: list[str] = Field(default_factory=list)
    actions: list[str] = Field(default_factory=list)
    changed_items: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    details: dict[str, Any] = Field(default_factory=dict)


class ResponseEnvelope(BaseModel):
    request_id: str
    status: StatusType
    started_at: str
    completed_at: str
    summary: str
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    result: dict[str, Any] = Field(default_factory=dict)
    operation_log: OperationLog
