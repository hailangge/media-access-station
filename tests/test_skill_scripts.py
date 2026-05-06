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
        "deploy-orange-pi",
        "validate-orange-pi",
    }


def test_build_orange_pi_config_updates_security_and_nas(tmp_path: Path) -> None:
    template = tmp_path / "config.yaml"
    template.write_text(
        yaml.safe_dump(
            {
                "security": {"auth_token": "x", "client_ip_allowlist": ["127.0.0.1"], "write_enabled": False},
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
    )
    assert result["security"]["auth_token"] == "stage1-token"
    assert result["security"]["client_ip_allowlist"] == ["127.0.0.1", "192.168.0.136"]
    assert result["security"]["write_enabled"] is True
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
    assert any(tmp_path.rglob("*.json"))
