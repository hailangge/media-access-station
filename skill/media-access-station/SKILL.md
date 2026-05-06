---
name: media-access-station
description: Use this skill when you need direct command entrypoints for Media Access Station operations. It provides explicit command templates for service startup, health, scan, import, lyrics write-back, metadata sidecar write-back, audio tag write-back, Orange Pi deployment, and Orange Pi validation.
---

# Media Access Station

Use these exact entrypoints. Do not inspect the scripts unless you need to patch them.

## Base paths

- Skill root: `skill/media-access-station/scripts`
- Main runner: `python3 skill/media-access-station/scripts/mas_skill.py`
- Default local log root: `/mnt/data/workspace-media-manager/logs/media-access-station`

## Direct entrypoints

### 1. Start the server
Command:
```bash
skill/media-access-station/scripts/server --config src/media_access_station/server/config.example.yaml
```
Use when:
- starting the local FastAPI service,
- overriding host or port if needed.

### 2. Health check
Command:
```bash
skill/media-access-station/scripts/health --base-url http://127.0.0.1:8765 --token change-me
```
Output:
- prints request JSON,
- prints response JSON,
- writes authoritative local logs under `/mnt/data/workspace-media-manager/logs/media-access-station`.

### 3. Scan devices
Command:
```bash
skill/media-access-station/scripts/scan --base-url http://127.0.0.1:8765 --token change-me
```
Optional flags:
- `--scan-root /path/to/root`
- `--include-hidden`
- `--dry-run`

### 4. Import device content to NAS
Command:
```bash
skill/media-access-station/scripts/import-to-nas DEVICE_ID SOURCE_PATH DEST_SUBDIR --base-url http://127.0.0.1:8765 --token change-me
```
Example:
```bash
skill/media-access-station/scripts/import-to-nas usb-recorder Recordings/meeting.wav imported/recorder --base-url http://192.168.0.160:8765 --token stage1-token
```
Optional flags:
- `--dry-run`
- `--overwrite`

### 5. Write `.lrc` lyrics beside tracks
Command:
```bash
skill/media-access-station/scripts/write-back DEVICE_ID TARGET_FILE --action write_lrc_sidecar --content 'lyric text' --base-url http://127.0.0.1:8765 --token change-me
```

### 6. Write metadata sidecar JSON
Command:
```bash
skill/media-access-station/scripts/write-back DEVICE_ID TARGET_FILE --action write_metadata_sidecar --metadata-json '{"title":"Demo"}' --base-url http://127.0.0.1:8765 --token change-me
```

### 7. Write audio tags into MP3 files
Command:
```bash
skill/media-access-station/scripts/write-back DEVICE_ID TARGET_FILE --action write_audio_tags --metadata-json '{"title":"Demo Song","artist":"Demo Artist","album":"Demo Album","genre":"Speech","year":"2026"}' --base-url http://127.0.0.1:8765 --token change-me
```
Current supported target types:
- `.mp3`

### 8. Deploy to Orange Pi
Command:
```bash
skill/media-access-station/scripts/deploy-orange-pi --host 192.168.0.160 --user root --password 1234567890 --token stage1-token --admin-ip 192.168.0.136
```
Effect:
- syncs repo to `/opt/media-access-station/current`
- writes config to `/etc/media-access-station/config.yaml`
- writes unit to `/etc/systemd/system/media-access-station.service`
- creates venv and installs package
- enables and restarts `media-access-station.service`

### 9. Validate Orange Pi end to end
Command:
```bash
skill/media-access-station/scripts/validate-orange-pi --host 192.168.0.160 --user root --password 1234567890 --token stage1-token
```
Validation scope:
- `systemd enabled/active`
- `health`
- `scan`
- `scan dry-run`
- `import success/partial/failed`
- import 400 paths
- `write-back` blocked when read-only
- lyrics write-back
- metadata sidecar write-back
- audio tag write-back
- crash restart recovery

## Log layout

Authoritative local logs are written under:
```text
/mnt/data/workspace-media-manager/logs/media-access-station/
  operations/YYYY/MM/DD/<request_id>.json
  responses/YYYY/MM/DD/<request_id>.json
  summaries/YYYY/MM/DD/<request_id>.txt
  errors/YYYY/MM/DD/<request_id>.json
```
