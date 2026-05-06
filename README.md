# Media Access Station

Minimal runnable MVP of a Media Access Station with:
- local host CLI client
- Pi-side FastAPI server
- shared typed request/response schemas
- local authoritative operation-log persistence
- read-only default safety posture
- explicit write enablement for write-back
- filesystem-based device scan plus mock fallback for hardware-limited environments

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

## Mock and fallback behavior
This environment may not expose real USB devices, udev events, or SBC mount tooling. For that reason the MVP scans configured filesystem roots and, if nothing usable is found, returns a deterministic `mock-device` entry with warning text. This keeps protocol and logging flows testable without pretending real hardware validation occurred.

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
```

Note: write-back will be blocked until `security.write_enabled` is set to `true` in the config.

## Skill entrypoints
The root `skill/` folder exposes the Media Access Station feature surface through scripts:

```bash
skill/media-access-station/scripts/health --token change-me
skill/media-access-station/scripts/scan --token change-me
skill/media-access-station/scripts/import-to-nas test-recorder Recordings imported/recorder --token change-me
skill/media-access-station/scripts/write-back test-player Music/song.mp3 --action write_lrc_sidecar --content 'demo lyric' --token change-me
skill/media-access-station/scripts/deploy-orange-pi --host 192.168.0.160 --user root --token stage1-token --admin-ip 192.168.0.136
skill/media-access-station/scripts/validate-orange-pi --host 192.168.0.160 --user root --token stage1-token
```

These wrappers call `skill/media-access-station/scripts/mas_skill.py`, which exposes:
- `server`
- `health`
- `scan`
- `import-to-nas`
- `write-back`
- `deploy-orange-pi`
- `validate-orange-pi`

## API endpoints
- `GET /health`
- `POST /api/v1/scan`
- `POST /api/v1/import`
- `POST /api/v1/write-back`

## Operation log format
Client logs are written under:
```text
var/operation-logs/YYYY/MM/DD/<request_id>.json
```
Each entry contains the endpoint, request payload, response payload, and local persistence timestamp.
This now includes `health` requests as well as `scan`, `import`, and `write-back`.

## Test
```bash
pytest
```
