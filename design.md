# Design

## Technical choice
Use a Python 3.11+ project with FastAPI on the Pi-side and a Typer-based CLI on the local host.

Rationale:
- quick runnable MVP
- strong schema validation via Pydantic
- simple local testability
- clear HTTP/JSON request-response contract

## Project layout
```text
media_access_station/
  pyproject.toml
  README.md
  requirements.md
  design.md
  tasks.md
  src/media_access_station/
    shared/
      schemas.py
      config.py
      utils.py
    server/
      app.py
      service.py
      security.py
      device_scan.py
      importer.py
      writeback.py
      config.example.yaml
    client/
      cli.py
      api_client.py
      operation_log.py
  tests/
    test_api.py
    test_client_cli.py
```

## Runtime model
### Server
- FastAPI app loads YAML config.
- Middleware/security guard checks caller IP against allowlist.
- Handlers call service functions that produce structured `OperationLog` objects.
- Server keeps only normal application logs.

### Client
- CLI builds typed requests.
- CLI sends HTTP calls to server.
- CLI normalizes response and writes operation records under `./var/operation-logs/` by default.
- CLI returns human-readable summaries.

## Config design
Server YAML config fields:
- `server.host`
- `server.port`
- `security.auth_token`
- `security.client_ip_allowlist`
- `security.write_enabled` (default false)
- `nas.address`
- `nas.import_root`
- `transport.public_key_name`
- `transport.method` (`local_copy` or `rsync`)
- `transport.rsync` subtree with command, ssh user, ssh port, extra args
- `devices.scan_roots` for mock/fallback scanning
- `devices.mount_root`
- `operations.service_log_dir`
- `operations.temp_dir`

## Schema design
### Shared base fields
- `request_id`
- `task_type`
- `requested_at`
- `dry_run`
- `mode` (`read_only` or `write`)

### Task requests
- `ScanRequest`: optional scan roots and include hidden flag.
- `ImportRequest`: device id, source path, destination subdir, overwrite flag.
- `WriteBackRequest`: device id, target files, action type, payload, mode.

### Response
- `status`
- `summary`
- `started_at`
- `completed_at`
- `warnings`
- `errors`
- `result`
- `operation_log`

## Device scan strategy
1. Try to inspect configured scan roots and enumerate filesystems from paths present on disk.
2. If no real device markers exist, return a synthetic mock device with `mock: true` and clear warning text.
3. Device identity is derived from path name plus inode/path metadata for MVP.

## Import flow
1. Validate source path under allowed scan roots.
2. Resolve NAS import destination under configured import root.
3. If dry run, produce planned copy list only.
4. If `transport.method=local_copy`, use Python file copy for files and directories.
5. If `transport.method=rsync`, build command from config and run it.
6. Return copied item list and byte counts in operation log.

## Write-back flow
1. Require request mode `write` and config `write_enabled=true`.
2. Validate target files remain under allowed device root.
3. Support actions:
   - `write_lrc_sidecar`: create/update `<track>.lrc`
   - `write_metadata_sidecar`: create/update `<track>.meta.json`
4. If dry run, return proposed change list only.
5. Return changed files with before/after existence hints.

## Safety boundaries
- Path traversal blocked by canonical root checks.
- Import cannot write outside configured NAS import root.
- Write-back cannot write unless explicit dual enablement passes.
- Authentication token required on mutating and non-mutating API calls for uniformity.

## Logging model
Client writes JSON files:
```text
var/operation-logs/YYYY/MM/DD/<request_id>.json
```
Each log stores:
- request metadata
- endpoint
- response payload
- local persisted timestamp

## Test plan
- FastAPI integration tests covering health, scan, import, write-back, and write protection.
- CLI smoke tests using Typer runner and test client.
- Schema/config validation tests indirectly through API tests.

## Known fallback behavior
Because current environment may lack real USB devices or SBC-specific mount tooling, device scanning is implemented with filesystem-root discovery plus deterministic mock device fallback. This is intentional and documented in README.
