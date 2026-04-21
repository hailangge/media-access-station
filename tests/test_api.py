from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from media_access_station.server.app import create_app
from media_access_station.shared.config import ServerConfig


def make_config(tmp_path: Path, write_enabled: bool = False) -> ServerConfig:
    devices_root = tmp_path / 'devices'
    recorder = devices_root / 'test-recorder' / 'Recordings'
    player = devices_root / 'test-player' / 'Music'
    recorder.mkdir(parents=True)
    player.mkdir(parents=True)
    (recorder / 'meeting.wav').write_text('recording', encoding='utf-8')
    (player / 'song.mp3').write_text('music', encoding='utf-8')
    return ServerConfig.model_validate({
        'security': {
            'auth_token': 'test-token',
            'client_ip_allowlist': ['testclient'],
            'write_enabled': write_enabled,
        },
        'nas': {
            'address': 'nas.test',
            'import_root': str(tmp_path / 'nas-import'),
        },
        'devices': {
            'scan_roots': [str(devices_root)],
            'mount_root': str(devices_root),
        },
    })


def auth_headers() -> dict[str, str]:
    return {'Authorization': 'Bearer test-token'}


def test_health_and_scan(tmp_path: Path) -> None:
    client = TestClient(create_app(make_config(tmp_path)))
    health = client.get('/health', headers=auth_headers())
    assert health.status_code == 200
    assert health.json()['status'] == 'ok'

    scan = client.post('/api/v1/scan', headers=auth_headers(), json={
        'request_id': 'req-scan',
        'task_type': 'scan',
        'mode': 'read_only',
    })
    assert scan.status_code == 200
    body = scan.json()
    assert body['status'] == 'success'
    assert len(body['result']['devices']) == 2


def test_import_flow(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    client = TestClient(create_app(config))
    response = client.post('/api/v1/import', headers=auth_headers(), json={
        'request_id': 'req-import',
        'task_type': 'import_to_nas',
        'mode': 'read_only',
        'device_id': 'test-recorder',
        'source_path': 'Recordings',
        'destination_subdir': 'recorder-drop',
        'overwrite': True,
    })
    assert response.status_code == 200
    target = Path(config.nas.import_root) / 'recorder-drop' / 'meeting.wav'
    assert target.exists()


def test_write_back_blocked_by_default(tmp_path: Path) -> None:
    client = TestClient(create_app(make_config(tmp_path, write_enabled=False)))
    response = client.post('/api/v1/write-back', headers=auth_headers(), json={
        'request_id': 'req-write',
        'task_type': 'write_back',
        'mode': 'write',
        'device_id': 'test-player',
        'target_files': ['Music/song.mp3'],
        'action': 'write_lrc_sidecar',
        'payload': {'content': 'lyric line'},
    })
    assert response.status_code == 403
    assert 'disabled' in response.json()['detail']


def test_write_back_success_when_enabled(tmp_path: Path) -> None:
    config = make_config(tmp_path, write_enabled=True)
    client = TestClient(create_app(config))
    response = client.post('/api/v1/write-back', headers=auth_headers(), json={
        'request_id': 'req-write',
        'task_type': 'write_back',
        'mode': 'write',
        'device_id': 'test-player',
        'target_files': ['Music/song.mp3'],
        'action': 'write_lrc_sidecar',
        'payload': {'content': 'lyric line'},
    })
    assert response.status_code == 200
    sidecar = Path(config.devices.mount_root) / 'test-player' / 'Music' / 'song.lrc'
    assert sidecar.read_text(encoding='utf-8') == 'lyric line'
