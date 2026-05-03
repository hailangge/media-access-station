# Deployment Assets

This directory contains the production deployment templates for the Orange Pi host.

## Files

- `config.orange-pi.yaml`
  - Server runtime configuration template.
  - Intended install path: `/etc/media-access-station/config.yaml`
  - Uses absolute paths for device roots, import storage, temp files, and service logs.
  - Defaults to `write_enabled: false` so write-back stays blocked until explicitly enabled.

- `media-access-station.service`
  - `systemd` unit template.
  - Intended install path: `/etc/systemd/system/media-access-station.service`
  - Starts the API on boot and restarts it automatically on crash with `Restart=always`.

## Expected runtime layout

- Application: `/opt/media-access-station/current`
- Config: `/etc/media-access-station/config.yaml`
- Data root: `/var/lib/media-access-station`
  - Devices: `/var/lib/media-access-station/devices`
  - Imports: `/var/lib/media-access-station/nas-import`
  - Logs: `/var/lib/media-access-station/service-logs`
  - Temp: `/var/lib/media-access-station/tmp`
