from __future__ import annotations

import hashlib
from pathlib import Path
import subprocess

from media_access_station.shared.config import ServerConfig
from media_access_station.shared.schemas import DeviceRecord


def _detect_filesystem(path: Path) -> str:
    try:
        result = subprocess.run(
            ["stat", "-f", "-c", "%T", str(path)],
            capture_output=True,
            check=True,
            text=True,
        )
    except (FileNotFoundError, subprocess.CalledProcessError):
        return "localfs"
    filesystem = result.stdout.strip()
    return filesystem or "localfs"


def scan_devices(config: ServerConfig, requested_roots: list[str] | None = None, include_hidden: bool = False) -> tuple[list[DeviceRecord], list[str]]:
    warnings: list[str] = []
    roots = requested_roots or config.devices.scan_roots
    devices: list[DeviceRecord] = []

    for root_str in roots:
        root = Path(root_str)
        if not root.exists():
            warnings.append(f"Scan root missing: {root}")
            continue
        for entry in sorted(root.iterdir()):
            if not include_hidden and entry.name.startswith('.'):
                continue
            if not entry.is_dir():
                continue
            sample = sorted(str(p.relative_to(entry)) for p in entry.rglob('*') if p.is_file())[:5]
            devices.append(
                DeviceRecord(
                    device_id=entry.name,
                    path=str(entry.resolve()),
                    mount_path=str(entry.resolve()),
                    label=entry.name,
                    filesystem=_detect_filesystem(entry),
                    device_uuid=hashlib.sha1(str(entry.resolve()).encode("utf-8")).hexdigest()[:16],
                    vendor="virtual-usb",
                    mock=False,
                    files_sample=sample,
                )
            )

    if not devices:
        warnings.append("No real device roots found, returning mock fallback device")
        devices.append(
            DeviceRecord(
                device_id="mock-device",
                path=str(Path(config.devices.mount_root).resolve() / "mock-device"),
                mount_path=str(Path(config.devices.mount_root).resolve() / "mock-device"),
                label="Mock Device",
                device_uuid="mock-device",
                vendor="mock",
                mock=True,
                files_sample=["Music/example.mp3", "Recordings/example.wav"],
            )
        )

    return devices, warnings
