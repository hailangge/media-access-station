from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from media_access_station.client.cli import app


class StubClient:
    def __init__(self, response: dict):
        self.response = response

    def health(self) -> dict:
        return {'status': 'ok'}

    def post(self, path: str, payload: dict) -> dict:
        return self.response | {'request_id': payload['request_id']}


def test_scan_cli_persists_operation_log(tmp_path: Path, monkeypatch) -> None:
    response = {
        'status': 'success',
        'summary': 'Scanned 1 device(s)',
        'started_at': '2026-01-01T00:00:00+00:00',
        'completed_at': '2026-01-01T00:00:01+00:00',
        'warnings': [],
        'errors': [],
        'result': {'devices': []},
        'operation_log': {'request_id': 'x', 'task_type': 'scan', 'status': 'success', 'server_timestamp': '2026-01-01T00:00:00+00:00', 'actions': [], 'target_paths': [], 'changed_items': [], 'warnings': [], 'errors': [], 'details': {}},
    }
    monkeypatch.setattr('media_access_station.client.cli._client', lambda base_url, token: StubClient(response))
    runner = CliRunner()
    result = runner.invoke(app, ['scan', '--log-root', str(tmp_path), '--token', 'x'])
    assert result.exit_code == 0
    assert 'Scanned 1 device(s)' in result.stdout
    assert any(tmp_path.rglob('*.json'))


def test_health_cli_outputs_json(monkeypatch) -> None:
    monkeypatch.setattr('media_access_station.client.cli._client', lambda base_url, token: StubClient({}))
    runner = CliRunner()
    result = runner.invoke(app, ['health', '--token', 'x'])
    assert result.exit_code == 0
    assert '"status": "ok"' in result.stdout


def test_health_cli_persists_operation_log(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr('media_access_station.client.cli._client', lambda base_url, token: StubClient({}))
    runner = CliRunner()
    result = runner.invoke(app, ['health', '--token', 'x', '--log-root', str(tmp_path)])
    assert result.exit_code == 0
    assert '"log_path":' in result.stdout
    assert any(tmp_path.rglob('*.json'))
