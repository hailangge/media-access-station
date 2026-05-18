# Design

## Summary
The project keeps the existing Media Access Station HTTP service for business operations and adds a minimal restricted SSH layer for physical block-device access on the Orange Pi.

The design is intentionally simple:
- `mas-agent` is the only remote SSH login for the shared key.
- `mas-agent` cannot execute arbitrary shell commands.
- fixed helper scripts on the Orange Pi handle `lsblk`, `mount`, `status`, and `umount`.
- the existing HTTP service continues to handle scan, import, and write-back once a device is mounted under the managed device root.
- for fully automatic lyric workflows, the service can be switched to `lrc_only_mode`, where only `.lrc` sidecar write-back is permitted even if the device is mounted read-write.

## 1. Remote access model

### 1.1 Low-privilege SSH account
- Create `mas-agent` on the Orange Pi.
- The shared key logs in as `mas-agent`, not `root`.
- `mas-agent` uses forced-command dispatch through `authorized_keys`.

### 1.2 Forced-command dispatch
- `authorized_keys` runs `/usr/local/libexec/mas/mas-ssh-dispatch`.
- The dispatcher accepts only:
  - `lsblk`
  - `mount DEVICE_PATH MOUNT_NAME`
  - `status [MOUNT_NAME]`
  - `umount MOUNT_NAME`
- Any other command is rejected.

### 1.3 Restricted elevation
- `mas-agent` uses `sudo` only for the fixed helper scripts.
- `sudoers` grants `NOPASSWD` access only to:
  - `/usr/local/libexec/mas/mas-lsblk`
  - `/usr/local/libexec/mas/mas-mount`
  - `/usr/local/libexec/mas/mas-status`
- `/usr/local/libexec/mas/mas-umount`

## 2. Helper script rules

### 2.1 `mas-lsblk`
- Returns JSON block inventory only.
- Does not accept free-form user arguments.

### 2.2 `mas-mount`
- Accepts only a partition path, a safe mount name, and `ro`.
- Also supports `rw` for explicitly controlled write-back workflows.
- Mount target is always:
  - `/var/lib/media-access-station/devices/<mount_name>`
- Mount flags are fixed:
  - `ro,nodev,nosuid,noexec`
  - `rw,nodev,nosuid,noexec`
- Unsafe filesystem types and non-partition device paths are rejected.

### 2.3 `mas-status`
- Returns current managed mount state.
- Can report all managed mount points or one named mount.

### 2.4 `mas-umount`
- Unmounts only the managed target under the device root.
- Removes its state file after successful unmount.

## 3. Business-operation boundary

### 3.1 What restricted SSH is for
- physical device discovery
- read-only mounting
- managed unmount
- mount-state inspection

### 3.2 What restricted SSH is not for
- service deployment
- system configuration editing
- arbitrary shell access
- network or boot configuration
- general filesystem browsing outside the managed device root

### 3.3 Existing HTTP service role
The Media Access Station HTTP service remains responsible for:
- `health`
- directory-level `scan`
- `import-to-nas`
- `write-back`

### 3.4 Automatic lyric-only write mode
When `security.lrc_only_mode` is enabled:
- `write_lrc_sidecar` remains allowed
- `write_metadata_sidecar` is rejected
- `write_audio_tags` is rejected
- the intended use is fully automatic lyric download and `.lrc` write-back on a controlled read-write mounted USB device
- logging and response normalization

## 4. Root-key retirement
- Setup installs the restricted SSH path first.
- After verification, `/root/.ssh/authorized_keys` is truncated.
- The shared key can no longer log in as `root`.

## 5. Validation plan
- unit tests cover the new skill parser entrypoints
- local tests exercise the existing service behavior
- Orange Pi validation uses fake mounted fixtures under the managed device root
- remote verification confirms:
  - `mas-agent` SSH access works
  - `root` SSH by shared key is blocked
  - restricted `lsblk` and `status` work
  - a fake bind mount can be scanned by the HTTP service
