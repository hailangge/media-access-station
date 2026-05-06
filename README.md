# Media Access Station

Client/server Media Access Station for offline USB media devices with:
- local invocation entry on the current host
- Pi-side FastAPI execution service
- authoritative workspace-side operation logging
- import-to-NAS workflows
- in-place write-back workflows for lyrics, metadata sidecars, and MP3 tags
- read-only default safety posture with explicit write enablement

## Repo deliverables
- `src/media_access_station/server/`: Pi-side service
- `src/media_access_station/client/`: local host CLI
- `src/media_access_station/shared/`: schemas, config, helpers
- `skill/media-access-station/`: skill packaging with script entrypoints for runtime, deployment, and validation
- `src/media_access_station/server/config.example.yaml`: sample server config
- `fixtures/devices/`: local mock devices for validation
- `var/operation-logs/`: local authoritative request logs written by the client

## Safety defaults
- Server defaults to `write_enabled: false`.
- Scan and import use `read_only` mode by default.
- Write-back requires both request mode `write` and config `write_enabled: true`.
- Import and write-back both support `dry_run`.

## Architecture
- Current host: client, orchestration, and authoritative operation record storage
- Pi-side host: stateless execution service with service-local diagnostics only
- Local workspace logs are written under `/mnt/data/workspace-media-manager/logs/media-access-station`

## Mock and fallback behavior
This repo can validate through filesystem-backed virtual USB-style roots when real mount enumeration is unavailable. Scan returns real filesystem-backed devices when present and falls back to a deterministic `mock-device` only when no usable roots are found.

## Install
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -e '.[dev]'
```

## Run server
```bash
mas-server --config src/media_access_station/server/config.example.yaml
```

Production note: prefer absolute filesystem paths in the server config. Relative paths like `./fixtures/devices` and `./var/nas-import` resolve from the server process working directory.

## Deploy on Orange Pi
- Production config template: `deploy/config.orange-pi.yaml`
- `systemd` unit template: `deploy/media-access-station.service`
- Recommended runtime paths:
  - app: `/opt/media-access-station/current`
  - config: `/etc/media-access-station/config.yaml`
  - data root: `/var/lib/media-access-station`
- The provided unit enables boot-time startup and crash restart via `Restart=always`.

## Run client examples
```bash
mas-client health --token change-me
mas-client scan --token change-me
mas-client import test-recorder Recordings imported/recorder --token change-me
mas-client write-back test-player Music/song.mp3 --action write_lrc_sidecar --content 'demo lyric' --token change-me
mas-client write-back test-player Music/song.mp3 --action write_audio_tags --metadata-json '{"title":"Demo Song","artist":"Demo Artist","genre":"Speech"}' --token change-me
```

Note: write-back will be blocked until `security.write_enabled` is set to `true` in the config.

## Skill entrypoints
The root `skill/` folder exposes the Media Access Station feature surface through scripts:

```bash
skill/media-access-station/scripts/health --token change-me
skill/media-access-station/scripts/scan --token change-me
skill/media-access-station/scripts/import-to-nas test-recorder Recordings imported/recorder --token change-me
skill/media-access-station/scripts/write-back test-player Music/song.mp3 --action write_lrc_sidecar --content 'demo lyric' --token change-me
skill/media-access-station/scripts/write-back test-player Music/song.mp3 --action write_audio_tags --metadata-json '{"title":"Demo Song","artist":"Demo Artist","genre":"Speech"}' --token change-me
skill/media-access-station/scripts/deploy-orange-pi --host 192.168.0.160 --user root --password 1234567890 --token stage1-token --admin-ip 192.168.0.136
skill/media-access-station/scripts/validate-orange-pi --host 192.168.0.160 --user root --password 1234567890 --token stage1-token
```

## API endpoints
- `GET /health`
- `POST /api/v1/scan`
- `POST /api/v1/import`
- `POST /api/v1/write-back`

## Operation log format
Client logs are written under:
```text
/mnt/data/workspace-media-manager/logs/media-access-station/
  operations/YYYY/MM/DD/<request_id>.json
  responses/YYYY/MM/DD/<request_id>.json
  summaries/YYYY/MM/DD/<request_id>.txt
  errors/YYYY/MM/DD/<request_id>.json
```
Each operation persists the authoritative local record, the normalized response payload, and a summary artifact.

## Test
```bash
pytest
```
