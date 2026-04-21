from __future__ import annotations

from media_access_station.shared.config import ServerConfig
from media_access_station.shared.schemas import ImportRequest, OperationLog, ResponseEnvelope, ScanRequest, WriteBackRequest
from media_access_station.shared.utils import utc_now
from media_access_station.server.device_scan import scan_devices
from media_access_station.server.importer import execute_import
from media_access_station.server.writeback import execute_writeback


def handle_scan(request: ScanRequest, config: ServerConfig) -> ResponseEnvelope:
    started = utc_now()
    devices, warnings = scan_devices(config, request.scan_roots, request.include_hidden)
    operation_log = OperationLog(
        request_id=request.request_id,
        task_type=request.task_type,
        status="success",
        target_paths=[device.path for device in devices],
        actions=["scan_devices"],
        warnings=warnings,
        details={"device_count": len(devices)},
    )
    return ResponseEnvelope(
        request_id=request.request_id,
        status="success",
        started_at=started,
        completed_at=utc_now(),
        summary=f"Scanned {len(devices)} device(s)",
        warnings=warnings,
        result={"devices": [device.model_dump() for device in devices]},
        operation_log=operation_log,
    )


def handle_import(request: ImportRequest, config: ServerConfig) -> ResponseEnvelope:
    started = utc_now()
    result, warnings, changed = execute_import(request, config)
    operation_log = OperationLog(
        request_id=request.request_id,
        task_type=request.task_type,
        status="success",
        target_device=request.device_id,
        target_paths=[request.source_path],
        actions=["import_to_nas"],
        changed_items=changed,
        warnings=warnings,
        details=result,
    )
    return ResponseEnvelope(
        request_id=request.request_id,
        status="success",
        started_at=started,
        completed_at=utc_now(),
        summary=f"Import completed for {request.device_id}",
        warnings=warnings,
        result=result,
        operation_log=operation_log,
    )


def handle_writeback(request: WriteBackRequest, config: ServerConfig) -> ResponseEnvelope:
    started = utc_now()
    result, warnings, changed = execute_writeback(request, config)
    operation_log = OperationLog(
        request_id=request.request_id,
        task_type=request.task_type,
        status="success",
        target_device=request.device_id,
        target_paths=request.target_files,
        actions=[request.action],
        changed_items=changed,
        warnings=warnings,
        details=result,
    )
    return ResponseEnvelope(
        request_id=request.request_id,
        status="success",
        started_at=started,
        completed_at=utc_now(),
        summary=f"Write-back completed for {len(changed)} target(s)",
        warnings=warnings,
        result=result,
        operation_log=operation_log,
    )
