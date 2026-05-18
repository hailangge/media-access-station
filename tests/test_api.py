from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from media_access_station.server.app import create_app
from media_access_station.shared.config import ServerConfig


def make_config(tmp_path: Path, write_enabled: bool = False, lrc_only_mode: bool = False) -> ServerConfig:
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
            'lrc_only_mode': lrc_only_mode,
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
    assert all(device['filesystem'] != 'mockfs' for device in body['result']['devices'])
    assert all(device['mount_path'] for device in body['result']['devices'])
    assert all(device['device_uuid'] for device in body['result']['devices'])
    assert all(device['vendor'] == 'virtual-usb' for device in body['result']['devices'])


def test_scan_dry_run_reports_no_effect_warning(tmp_path: Path) -> None:
    client = TestClient(create_app(make_config(tmp_path)))
    scan = client.post('/api/v1/scan', headers=auth_headers(), json={
        'request_id': 'req-scan-dry-run',
        'task_type': 'scan',
        'mode': 'read_only',
        'dry_run': True,
    })
    assert scan.status_code == 200
    body = scan.json()
    assert body['status'] == 'success'
    assert body['result']['dry_run'] is True
    assert any('dry_run had no additional effect' in warning for warning in body['warnings'])


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
    body = response.json()
    assert body['status'] == 'success'
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
    assert 'disabled in config' in response.json()['detail']


def test_invalid_auth_token_rejected(tmp_path: Path) -> None:
    client = TestClient(create_app(make_config(tmp_path)))
    response = client.get('/health', headers={'Authorization': 'Bearer wrong-token'})
    assert response.status_code == 401
    assert response.json()['detail'] == 'Invalid token'


def test_client_ip_not_allowlisted(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.security.client_ip_allowlist = ['127.0.0.1']
    client = TestClient(create_app(config))
    response = client.get('/health', headers=auth_headers())
    assert response.status_code == 403
    assert 'not allowed' in response.json()['detail']


def test_import_single_file_to_dotted_subdir(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    client = TestClient(create_app(config))
    response = client.post('/api/v1/import', headers=auth_headers(), json={
        'request_id': 'req-import-dot',
        'task_type': 'import_to_nas',
        'mode': 'read_only',
        'device_id': 'test-recorder',
        'source_path': 'Recordings/meeting.wav',
        'destination_subdir': 'archive.v2',
        'overwrite': True,
    })
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'success'
    target = Path(config.nas.import_root) / 'archive.v2' / 'meeting.wav'
    assert target.exists()
    assert target.read_text(encoding='utf-8') == 'recording'


def test_import_partial_when_existing_file_skipped(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    source_dir = Path(config.devices.mount_root) / 'test-recorder' / 'Batch'
    source_dir.mkdir(parents=True)
    (source_dir / 'file1.txt').write_text('one', encoding='utf-8')
    (source_dir / 'file2.txt').write_text('two', encoding='utf-8')
    dest_dir = Path(config.nas.import_root) / 'batch-drop'
    dest_dir.mkdir(parents=True)
    (dest_dir / 'file1.txt').write_text('existing', encoding='utf-8')
    client = TestClient(create_app(config))
    response = client.post('/api/v1/import', headers=auth_headers(), json={
        'request_id': 'req-import-partial',
        'task_type': 'import_to_nas',
        'mode': 'read_only',
        'device_id': 'test-recorder',
        'source_path': 'Batch',
        'destination_subdir': 'batch-drop',
        'overwrite': False,
    })
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'partial'
    assert any('Skipped existing file' in w for w in body['warnings'])
    assert (dest_dir / 'file2.txt').exists()


def test_import_failed_when_all_existing_files_skipped(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    dest_dir = Path(config.nas.import_root) / 'recorder-drop'
    dest_dir.mkdir(parents=True)
    (dest_dir / 'meeting.wav').write_text('existing', encoding='utf-8')
    client = TestClient(create_app(config))
    response = client.post('/api/v1/import', headers=auth_headers(), json={
        'request_id': 'req-import-failed',
        'task_type': 'import_to_nas',
        'mode': 'read_only',
        'device_id': 'test-recorder',
        'source_path': 'Recordings/meeting.wav',
        'destination_subdir': 'recorder-drop',
        'overwrite': False,
    })
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'failed'
    assert any('Skipped existing file' in w for w in body['warnings'])


def test_write_back_partial_when_some_targets_unsupported(tmp_path: Path) -> None:
    config = make_config(tmp_path, write_enabled=True)
    client = TestClient(create_app(config))
    response = client.post('/api/v1/write-back', headers=auth_headers(), json={
        'request_id': 'req-write-partial',
        'task_type': 'write_back',
        'mode': 'write',
        'device_id': 'test-player',
        'target_files': ['Music', 'Music/song.mp3'],
        'action': 'write_lrc_sidecar',
        'payload': {'content': 'lyric line'},
    })
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'partial'
    assert any('Skipped directory target' in w for w in body['warnings'])
    sidecar = Path(config.devices.mount_root) / 'test-player' / 'Music' / 'song.lrc'
    assert sidecar.read_text(encoding='utf-8') == 'lyric line'


def test_write_back_failed_when_all_targets_unsupported(tmp_path: Path) -> None:
    config = make_config(tmp_path, write_enabled=True)
    client = TestClient(create_app(config))
    response = client.post('/api/v1/write-back', headers=auth_headers(), json={
        'request_id': 'req-write-failed',
        'task_type': 'write_back',
        'mode': 'write',
        'device_id': 'test-player',
        'target_files': ['Music'],
        'action': 'write_lrc_sidecar',
        'payload': {'content': 'lyric line'},
    })
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'failed'
    assert any('Skipped directory target' in w for w in body['warnings'])


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
    body = response.json()
    assert body['status'] == 'success'
    sidecar = Path(config.devices.mount_root) / 'test-player' / 'Music' / 'song.lrc'
    assert sidecar.read_text(encoding='utf-8') == 'lyric line'


def test_write_back_lrc_only_mode_blocks_metadata_sidecar(tmp_path: Path) -> None:
    config = make_config(tmp_path, write_enabled=True, lrc_only_mode=True)
    client = TestClient(create_app(config))
    response = client.post('/api/v1/write-back', headers=auth_headers(), json={
        'request_id': 'req-write-lrc-only-meta',
        'task_type': 'write_back',
        'mode': 'write',
        'device_id': 'test-player',
        'target_files': ['Music/song.mp3'],
        'action': 'write_metadata_sidecar',
        'payload': {'metadata': {'title': 'demo'}},
    })
    assert response.status_code == 403
    assert 'lrc_only_mode' in response.json()['detail']


def test_write_back_lrc_only_mode_blocks_audio_tags(tmp_path: Path) -> None:
    config = make_config(tmp_path, write_enabled=True, lrc_only_mode=True)
    client = TestClient(create_app(config))
    response = client.post('/api/v1/write-back', headers=auth_headers(), json={
        'request_id': 'req-write-lrc-only-tags',
        'task_type': 'write_back',
        'mode': 'write',
        'device_id': 'test-player',
        'target_files': ['Music/song.mp3'],
        'action': 'write_audio_tags',
        'payload': {'metadata': {'genre': 'Speech'}},
    })
    assert response.status_code == 403
    assert 'lrc_only_mode' in response.json()['detail']


def test_write_back_lrc_only_mode_allows_lrc_sidecar(tmp_path: Path) -> None:
    config = make_config(tmp_path, write_enabled=True, lrc_only_mode=True)
    client = TestClient(create_app(config))
    response = client.post('/api/v1/write-back', headers=auth_headers(), json={
        'request_id': 'req-write-lrc-only-lrc',
        'task_type': 'write_back',
        'mode': 'write',
        'device_id': 'test-player',
        'target_files': ['Music/song.mp3'],
        'action': 'write_lrc_sidecar',
        'payload': {'content': 'lyric line'},
    })
    assert response.status_code == 200
    assert response.json()['status'] == 'success'


def test_write_back_failed_when_target_file_missing(tmp_path: Path) -> None:
    config = make_config(tmp_path, write_enabled=True)
    client = TestClient(create_app(config))
    response = client.post('/api/v1/write-back', headers=auth_headers(), json={
        'request_id': 'req-write-missing',
        'task_type': 'write_back',
        'mode': 'write',
        'device_id': 'test-player',
        'target_files': ['Music/missing.mp3'],
        'action': 'write_lrc_sidecar',
        'payload': {'content': 'lyric line'},
    })
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'failed'
    assert any('Skipped missing target file' in w for w in body['warnings'])
    sidecar = Path(config.devices.mount_root) / 'test-player' / 'Music' / 'missing.lrc'
    assert not sidecar.exists()


def test_write_back_dry_run_does_not_create_parent_dirs(tmp_path: Path) -> None:
    config = make_config(tmp_path, write_enabled=True)
    client = TestClient(create_app(config))
    response = client.post('/api/v1/write-back', headers=auth_headers(), json={
        'request_id': 'req-write-dry-run',
        'task_type': 'write_back',
        'mode': 'write',
        'device_id': 'test-player',
        'target_files': ['NewFolder/song.mp3'],
        'action': 'write_metadata_sidecar',
        'dry_run': True,
        'payload': {'metadata': {'title': 'demo'}},
    })
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'failed'
    assert any('Skipped missing target file' in w for w in body['warnings'])
    new_dir = Path(config.devices.mount_root) / 'test-player' / 'NewFolder'
    assert not new_dir.exists()


def test_write_back_dry_run_existing_target_reports_success_without_sidecar(tmp_path: Path) -> None:
    config = make_config(tmp_path, write_enabled=True)
    client = TestClient(create_app(config))
    response = client.post('/api/v1/write-back', headers=auth_headers(), json={
        'request_id': 'req-write-dry-run-existing',
        'task_type': 'write_back',
        'mode': 'write',
        'device_id': 'test-player',
        'target_files': ['Music/song.mp3'],
        'action': 'write_metadata_sidecar',
        'dry_run': True,
        'payload': {'metadata': {'title': 'demo'}},
    })
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'success'
    sidecar = Path(config.devices.mount_root) / 'test-player' / 'Music' / 'song.mp3.meta.json'
    assert not sidecar.exists()


def test_write_back_audio_tags_success_when_enabled(tmp_path: Path) -> None:
    config = make_config(tmp_path, write_enabled=True)
    client = TestClient(create_app(config))
    response = client.post('/api/v1/write-back', headers=auth_headers(), json={
        'request_id': 'req-write-tags',
        'task_type': 'write_back',
        'mode': 'write',
        'device_id': 'test-player',
        'target_files': ['Music/song.mp3'],
        'action': 'write_audio_tags',
        'payload': {'metadata': {'title': 'Demo Song', 'artist': 'Demo Artist', 'genre': 'Speech'}},
    })
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'success'
    changed = body['result']['changed_count']
    assert changed == 1
    metadata = body['operation_log']['changed_items'][0]['metadata']
    assert metadata['title'] == 'Demo Song'
    assert metadata['artist'] == 'Demo Artist'
    assert metadata['genre'] == 'Speech'


def test_write_back_audio_tags_unsupported_file_type_is_failed(tmp_path: Path) -> None:
    config = make_config(tmp_path, write_enabled=True)
    notes = Path(config.devices.mount_root) / 'test-player' / 'Music' / 'notes.txt'
    notes.write_text('plain text', encoding='utf-8')
    client = TestClient(create_app(config))
    response = client.post('/api/v1/write-back', headers=auth_headers(), json={
        'request_id': 'req-write-tags-unsupported',
        'task_type': 'write_back',
        'mode': 'write',
        'device_id': 'test-player',
        'target_files': ['Music/notes.txt'],
        'action': 'write_audio_tags',
        'payload': {'metadata': {'genre': 'Speech'}},
    })
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'failed'
    assert any('Unsupported audio tag target type' in w for w in body['warnings'])


def test_import_path_traversal_blocked(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    client = TestClient(create_app(config))
    response = client.post('/api/v1/import', headers=auth_headers(), json={
        'request_id': 'req-import-traversal',
        'task_type': 'import_to_nas',
        'mode': 'read_only',
        'device_id': 'test-recorder',
        'source_path': '../test-player/Music/song.mp3',
        'destination_subdir': 'escape',
        'overwrite': True,
    })
    assert response.status_code == 400
    assert 'escapes root' in response.json()['detail']


def test_write_back_path_traversal_blocked(tmp_path: Path) -> None:
    config = make_config(tmp_path, write_enabled=True)
    client = TestClient(create_app(config))
    response = client.post('/api/v1/write-back', headers=auth_headers(), json={
        'request_id': 'req-write-traversal',
        'task_type': 'write_back',
        'mode': 'write',
        'device_id': 'test-player',
        'target_files': ['../test-recorder/Recordings/meeting.wav'],
        'action': 'write_lrc_sidecar',
        'payload': {'content': 'blocked'},
    })
    assert response.status_code == 400
    assert 'escapes root' in response.json()['detail']


def test_lyrics_align_returns_gpu_unavailable_with_report(tmp_path: Path) -> None:
    config = make_config(tmp_path)
    config.operations.service_log_dir = str(tmp_path / 'service-logs')
    client = TestClient(create_app(config))
    response = client.post('/api/v1/lyrics/align', headers=auth_headers(), json={
        'request_id': 'req-align-no-gpu',
        'task_type': 'lyrics_align',
        'mode': 'read_only',
        'server_audio_paths': ['/mnt/media/music/song.flac'],
        'server_lrc_paths': ['/mnt/media/music/song.lrc'],
    })
    assert response.status_code == 200
    body = response.json()
    assert body['status'] == 'failed'
    assert body['result']['code'] == 'gpu_unavailable'
    assert body['operation_log']['task_type'] == 'lyrics_align'
    assert body['operation_log']['target_paths'] == ['/mnt/media/music/song.flac', '/mnt/media/music/song.lrc']
    report_csv = Path(body['result']['report_csv_path'])
    assert report_csv.exists()
    report_text = report_csv.read_text(encoding='utf-8')
    assert 'server_audio_path' in report_text
    assert '/mnt/media/music/song.flac' in report_text
