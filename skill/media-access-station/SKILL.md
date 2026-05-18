---
name: media-access-station
description: Use this skill when you need direct command entrypoints for Media Access Station operations. It provides explicit command templates for service startup, health, scan, import, lyrics write-back, metadata sidecar write-back, audio tag write-back, restricted Orange Pi SSH setup, restricted remote lsblk or mount calls, Orange Pi deployment, and Orange Pi validation.
---

# Media Access Station

Use these exact entrypoints. Do not inspect the scripts unless you need to patch them.

## Base paths

- Skill root: `skill/media-access-station/scripts`
- Main runner: `python3 skill/media-access-station/scripts/mas_skill.py`
- Default local log root: `/mnt/data/workspace-media-manager/logs/media-access-station`

## Direct entrypoints

### 0. Install restricted SSH mount tooling on Orange Pi
Command:
```bash
skill/media-access-station/scripts/setup-restricted-ssh --host 192.168.0.165 --password 1234567890
```
Effect:
- creates `mas-agent` as the low-privilege SSH user,
- installs fixed remote commands under `/usr/local/libexec/mas`,
- installs `/etc/sudoers.d/mas-agent`,
- writes a forced-command `authorized_keys` for `mas-agent`,
- clears `/root/.ssh/authorized_keys` so the shared key can no longer log in as `root`.

### 0.1. Restricted remote block inventory
Command:
```bash
skill/media-access-station/scripts/remote-lsblk --host 192.168.0.165
```
Effect:
- runs the forced remote `lsblk` wrapper through `mas-agent`,
- returns JSON only,
- does not expose arbitrary shell execution.

### 0.2. Restricted remote mount
Command:
```bash
skill/media-access-station/scripts/remote-mount /dev/sda1 usb-player --host 192.168.0.165
```
Effect:
- mounts only to `/var/lib/media-access-station/devices/<mount-name>`,
- supports `ro` and controlled `rw`,
- rejects unsafe device paths and blocked filesystem types.
- when mounted as `ro`, the returned JSON includes a `message` field explaining that lyric write-back will fail until remounted as `rw`.
For automatic lyric write-back on real USB devices:
```bash
skill/media-access-station/scripts/remote-mount /dev/sda1 usb-player --mode rw --host 192.168.0.165
```
Then keep the server in `lrc_only_mode` so only `.lrc` sidecars may be written.

### 0.3. Restricted remote mount status
Command:
```bash
skill/media-access-station/scripts/remote-status --host 192.168.0.165
```
Optional:
- `skill/media-access-station/scripts/remote-status usb-player --host 192.168.0.165`
Returned fields:
- `mode`: `ro` or `rw` when detectable
- `message`: explicit explanation of what the current mount mode allows or blocks

### 0.4. Restricted remote unmount
Command:
```bash
skill/media-access-station/scripts/remote-umount usb-player --host 192.168.0.165
```

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
skill/media-access-station/scripts/import-to-nas usb-recorder Recordings/meeting.wav imported/recorder --base-url http://192.168.0.165:8765 --token stage1-token
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
Blocked when:
- the server is running with `lrc_only_mode: true`

### 7. Write audio tags into MP3 files
Command:
```bash
skill/media-access-station/scripts/write-back DEVICE_ID TARGET_FILE --action write_audio_tags --metadata-json '{"title":"Demo Song","artist":"Demo Artist","album":"Demo Album","genre":"Speech","year":"2026"}' --base-url http://127.0.0.1:8765 --token change-me
```
Current supported target types:
- `.mp3`
Blocked when:
- the server is running with `lrc_only_mode: true`

### 8. Deploy to Orange Pi
Command:
```bash
skill/media-access-station/scripts/deploy-orange-pi --host 192.168.0.165 --user root --password 1234567890 --token stage1-token --admin-ip 192.168.0.136
```
Effect:
- syncs repo to `/opt/media-access-station/current`
- writes config to `/etc/media-access-station/config.yaml`
- writes unit to `/etc/systemd/system/media-access-station.service`
- creates venv and installs package
- enables and restarts `media-access-station.service`
Useful flags:
- `--write-enabled`
- `--lrc-only-mode`

### 9. Validate Orange Pi end to end
Command:
```bash
skill/media-access-station/scripts/validate-orange-pi --host 192.168.0.165 --user root --password 1234567890 --token stage1-token
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

## Restricted SSH contract

- The shared SSH key must log in as `mas-agent`, not `root`.
- `mas-agent` is restricted to fixed command names: `lsblk`, `mount`, `status`, `umount`.
- Do not attempt arbitrary remote shell commands through this skill.
- Use `deploy-orange-pi` and `validate-orange-pi` only for explicit service maintenance.
- For fully automatic USB lyric write-back, use:
  - a controlled `rw` mount
  - `security.write_enabled: true`
  - `security.lrc_only_mode: true`
- In that mode, only `write_lrc_sidecar` is allowed; metadata sidecars and audio tag writes are rejected.

## Log layout

Authoritative local logs are written under:
```text
/mnt/data/workspace-media-manager/logs/media-access-station/
  operations/YYYY/MM/DD/<request_id>.json
  responses/YYYY/MM/DD/<request_id>.json
  summaries/YYYY/MM/DD/<request_id>.txt
  errors/YYYY/MM/DD/<request_id>.json
```
