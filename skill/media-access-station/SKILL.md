---
name: media-access-station
description: Use this skill when you need to operate, deploy, or validate the Media Access Station project through script-based entrypoints, including starting the server, calling health/scan/import/write-back flows, deploying to Orange Pi, and running end-to-end validation against the remote device.
---

# Media Access Station

Use this skill for any task that should be driven through the project's script entrypoints instead of ad hoc shell commands.

## Available entrypoints

All supported entrypoints are exposed under `skill/media-access-station/scripts/`.

- `server`: start the FastAPI service from a config file
- `health`: call `GET /health` and persist the client-side operation log
- `scan`: call `POST /api/v1/scan`
- `import-to-nas`: call `POST /api/v1/import`
- `write-back`: call `POST /api/v1/write-back`
- `deploy-orange-pi`: deploy the repo, config, venv, and `systemd` unit to an Orange Pi host
- `validate-orange-pi`: run an end-to-end validation sweep against the Orange Pi service

## Workflow

1. Prefer the script entrypoints over handcrafted `curl`, `ssh`, or `mas-client` commands.
2. For local API operations, use `health`, `scan`, `import-to-nas`, and `write-back`.
3. For service runtime work, use `server`.
4. For production rollout on the Orange Pi, use `deploy-orange-pi`.
5. For regression and environment checks on the Orange Pi, use `validate-orange-pi`.

## Notes

- The scripts use the same request schemas and log persistence model as the main project.
- Orange Pi deployment uses `deploy/config.orange-pi.yaml` and `deploy/media-access-station.service`.
- `validate-orange-pi` temporarily enables write-back when it needs to exercise write paths, then restores the original remote config.
