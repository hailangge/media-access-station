from __future__ import annotations

from pathlib import Path
from pydantic import BaseModel, Field
import yaml


class ServerSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 8765


class SecuritySettings(BaseModel):
    auth_token: str = "change-me"
    client_ip_allowlist: list[str] = Field(default_factory=lambda: ["127.0.0.1"])
    write_enabled: bool = False
    lrc_only_mode: bool = False


class NASSettings(BaseModel):
    address: str = "nas.local"
    import_root: str = "./var/nas"


class RsyncSettings(BaseModel):
    command: str = "rsync"
    ssh_user: str = "pi"
    ssh_port: int = 22
    extra_args: list[str] = Field(default_factory=lambda: ["-a"])


class TransportSettings(BaseModel):
    public_key_name: str = "media-access-station"
    method: str = "local_copy"
    rsync: RsyncSettings = Field(default_factory=RsyncSettings)


class DeviceSettings(BaseModel):
    scan_roots: list[str] = Field(default_factory=lambda: ["./fixtures/devices"])
    mount_root: str = "./fixtures/devices"


class OperationSettings(BaseModel):
    service_log_dir: str = "./var/service-logs"
    temp_dir: str = "./var/tmp"


class LyricsAlignmentSettings(BaseModel):
    enabled: bool = True
    require_cuda: bool = True
    runner_command: list[str] = Field(default_factory=list)


class ServerConfig(BaseModel):
    server: ServerSettings = Field(default_factory=ServerSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    nas: NASSettings = Field(default_factory=NASSettings)
    transport: TransportSettings = Field(default_factory=TransportSettings)
    devices: DeviceSettings = Field(default_factory=DeviceSettings)
    operations: OperationSettings = Field(default_factory=OperationSettings)
    lyrics_alignment: LyricsAlignmentSettings = Field(default_factory=LyricsAlignmentSettings)

    @classmethod
    def load(cls, path: str | Path) -> "ServerConfig":
        config_path = Path(path)
        data = yaml.safe_load(config_path.read_text()) or {}
        return cls.model_validate(data)
