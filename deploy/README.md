# Deployment Assets

This directory contains the production deployment templates for the Orange Pi host.

## Files

- `remote/mas-ssh-dispatch`
  - Forced-command SSH dispatcher for the low-privilege `mas-agent` account.
  - Accepts only `lsblk`, `mount`, `status`, and `umount`.

- `remote/mas-lsblk`
  - Fixed JSON block inventory wrapper.

- `remote/mas-mount`
  - Read-only mount wrapper.
  - Restricts device path patterns, filesystem types, and mount target path.

- `remote/mas-status`
  - Returns current managed mount state.

- `remote/mas-umount`
  - Unmounts only managed mount points.

- `remote/mas-agent.sudoers`
  - Restricts `mas-agent` to the managed wrappers only.

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
- Restricted SSH helpers: `/usr/local/libexec/mas`
- Restricted SSH sudoers: `/etc/sudoers.d/mas-agent`
- Data root: `/var/lib/media-access-station`
  - Devices: `/var/lib/media-access-station/devices`
  - Imports: `/var/lib/media-access-station/nas-import`
  - Logs: `/var/lib/media-access-station/service-logs`
  - Temp: `/var/lib/media-access-station/tmp`
  - State: `/var/lib/media-access-station/state`

## Restricted SSH model

- The shared SSH key is intended to log in as `mas-agent`.
- `mas-agent` is not allowed to execute arbitrary shell commands.
- `authorized_keys` uses a forced command that dispatches only:
  - `lsblk`
  - `mount DEVICE_PATH MOUNT_NAME`
  - `status [MOUNT_NAME]`
  - `umount MOUNT_NAME`
- Root key login is removed after setup by clearing `/root/.ssh/authorized_keys`.
