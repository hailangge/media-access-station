from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "skill" / "media-access-station" / "scripts" / "mas_skill.py"


spec = importlib.util.spec_from_file_location("mas_skill", SCRIPT_PATH)
mas_skill = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mas_skill)


class StubClient:
    def __init__(self, response: dict):
        self.response = response
        self.calls: list[tuple[str, dict]] = []

    def health(self) -> dict:
        return {"status": "ok", "service": "media-access-station"}

    def post(self, path: str, payload: dict) -> dict:
        self.calls.append((path, payload))
        return self.response | {"request_id": payload["request_id"]}


def test_skill_parser_exposes_all_entrypoints() -> None:
    parser = mas_skill.build_parser()
    choices = set(parser._subparsers._group_actions[0].choices)
    assert choices == {
        "server",
        "health",
        "scan",
        "import-to-nas",
        "write-back",
        "setup-restricted-ssh",
        "remote-lsblk",
        "remote-mount",
        "remote-status",
        "remote-umount",
        "deploy-orange-pi",
        "validate-orange-pi",
    }


def test_build_orange_pi_config_updates_security_and_nas(tmp_path: Path) -> None:
    template = tmp_path / "config.yaml"
    template.write_text(
        yaml.safe_dump(
            {
                "security": {"auth_token": "x", "client_ip_allowlist": ["127.0.0.1"], "write_enabled": False, "lrc_only_mode": False},
                "nas": {"address": "old", "import_root": "/tmp"},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    result = mas_skill.build_orange_pi_config(
        template,
        token="stage1-token",
        admin_ip="192.168.0.136",
        nas_address="192.168.0.160",
        write_enabled=True,
        lrc_only_mode=True,
    )
    assert result["security"]["auth_token"] == "stage1-token"
    assert result["security"]["client_ip_allowlist"] == ["127.0.0.1", "192.168.0.136"]
    assert result["security"]["write_enabled"] is True
    assert result["security"]["lrc_only_mode"] is True
    assert result["nas"]["address"] == "192.168.0.160"


def test_health_entrypoint_persists_log(tmp_path: Path, monkeypatch, capsys) -> None:
    monkeypatch.setattr(mas_skill, "_client", lambda base_url, token: StubClient({}))
    mas_skill.main(["health", "--token", "x", "--log-root", str(tmp_path)])
    output = json.loads(capsys.readouterr().out)
    assert output["response"]["status"] == "ok"
    assert any(tmp_path.rglob("*.json"))


def test_scan_entrypoint_posts_request_and_persists_log(tmp_path: Path, monkeypatch, capsys) -> None:
    stub = StubClient(
        {
            "status": "success",
            "summary": "Scanned 1 device(s)",
            "started_at": "2026-01-01T00:00:00+00:00",
            "completed_at": "2026-01-01T00:00:01+00:00",
            "warnings": [],
            "errors": [],
            "result": {"devices": []},
            "operation_log": {
                "request_id": "x",
                "task_type": "scan",
                "status": "success",
                "server_timestamp": "2026-01-01T00:00:00+00:00",
                "actions": [],
                "target_paths": [],
                "changed_items": [],
                "warnings": [],
                "errors": [],
                "details": {},
            },
        }
    )
    monkeypatch.setattr(mas_skill, "_client", lambda base_url, token: stub)
    mas_skill.main(["scan", "--token", "x", "--log-root", str(tmp_path), "--dry-run"])
    output = json.loads(capsys.readouterr().out)
    assert output["response"]["status"] == "success"
    assert stub.calls[0][0] == "/api/v1/scan"
    assert stub.calls[0][1]["dry_run"] is True
    assert any((tmp_path / "operations").rglob("*.json"))
    assert any((tmp_path / "responses").rglob("*.json"))


def test_remote_lsblk_uses_restricted_ssh(monkeypatch, capsys) -> None:
    commands: list[tuple[str, str, str, str]] = []

    def fake_ssh_key(host: str, user: str, identity_file: str, command: str, *, capture_output: bool = False):
        commands.append((host, user, identity_file, command))
        class Result:
            stdout = '{"blockdevices":[]}\n'
        return Result()

    monkeypatch.setattr(mas_skill, "_ssh_key", fake_ssh_key)
    mas_skill.main(["remote-lsblk", "--host", "192.168.0.165", "--identity-file", "/tmp/key"])
    output = json.loads(capsys.readouterr().out)
    assert output["blockdevices"] == []
    assert commands == [("192.168.0.165", "mas-agent", "/tmp/key", "lsblk")]


def test_remote_mount_uses_safe_command(monkeypatch, capsys) -> None:
    commands: list[str] = []

    def fake_ssh_key(host: str, user: str, identity_file: str, command: str, *, capture_output: bool = False):
        commands.append(command)
        class Result:
            stdout = '{"status":"mounted","mount_name":"usb-player","mode":"rw","message":null}\n'
        return Result()

    monkeypatch.setattr(mas_skill, "_ssh_key", fake_ssh_key)
    mas_skill.main(["remote-mount", "/dev/sda1", "usb-player", "--mode", "rw"])
    output = json.loads(capsys.readouterr().out)
    assert output["status"] == "mounted"
    assert output["mode"] == "rw"
    assert commands == ["mount /dev/sda1 usb-player rw"]


def test_remote_status_preserves_readonly_message(monkeypatch, capsys) -> None:
    def fake_ssh_key(host: str, user: str, identity_file: str, command: str, *, capture_output: bool = False):
        class Result:
            stdout = '{"mounts":[{"mount_path":"/x","mounted":true,"source":"tmpfs tmpfs ro,nosuid","mode":"ro","message":"Mounted read-only. Read and scan are allowed; lyric write-back and any file modification will fail until remounted as rw."}]}\n'
        return Result()

    monkeypatch.setattr(mas_skill, "_ssh_key", fake_ssh_key)
    mas_skill.main(["remote-status", "usb-player"])
    output = json.loads(capsys.readouterr().out)
    assert output["mounts"][0]["mode"] == "ro"
    assert "lyric write-back" in output["mounts"][0]["message"]


def test_setup_restricted_ssh_reports_expected_summary(tmp_path: Path, monkeypatch, capsys) -> None:
    pub = tmp_path / "media_access.pub"
    pub.write_text("ssh-ed25519 AAAATEST media_access@test\n", encoding="utf-8")
    ssh_calls: list[tuple[str, str, str, bool]] = []
    scp_calls: list[tuple[str, str]] = []

    monkeypatch.setattr(mas_skill, "_require_password", lambda password: "pw")

    def fake_ssh(host: str, user: str, password: str, command: str, *, capture_output: bool = False):
        ssh_calls.append((host, user, command, capture_output))
        class Result:
            stdout = ""
        return Result()

    def fake_scp_to(host: str, user: str, password: str, local_path: Path, remote_path: str) -> None:
        scp_calls.append((local_path.name, remote_path))

    monkeypatch.setattr(mas_skill, "_ssh", fake_ssh)
    monkeypatch.setattr(mas_skill, "_scp_to", fake_scp_to)
    mas_skill.main([
        "setup-restricted-ssh",
        "--host", "192.168.0.165",
        "--password", "pw",
        "--public-key", str(pub),
        "--identity-file", "/tmp/key",
    ])
    output = json.loads(capsys.readouterr().out)
    assert output["ssh_user"] == "mas-agent"
    assert output["root_authorized_keys_cleared"] is True
    assert any(name == "mas-ssh-dispatch" for name, _ in scp_calls)
    assert any("truncate -s 0 /root/.ssh/authorized_keys" in command for _, _, command, _ in ssh_calls)


def test_remote_helper_templates_exist() -> None:
    remote_dir = REPO_ROOT / "deploy" / "remote"
    expected = {
        "mas-ssh-dispatch",
        "mas-lsblk",
        "mas-mount",
        "mas-status",
        "mas-umount",
        "mas-agent.sudoers",
    }
    assert expected.issubset({path.name for path in remote_dir.iterdir()})
