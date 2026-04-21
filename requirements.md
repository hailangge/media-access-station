# Requirements

## Goal
Build a runnable minimal viable Media Access Station in `/mnt/data/repositories/media-access-station` with a split architecture:
- local-host client and operation-record keeper
- Pi-side stateless execution server

## Source constraints distilled from handoff docs
- Local host is the source of truth for operation history.
- Pi-side service executes device-facing work and only keeps diagnostic logs.
- Two workflow families must exist: import to NAS and in-place write-back.
- Safe default is read-only. Any write behavior must require explicit enablement.
- Request and response payloads must be explicit, structured, and validated.
- Hardware-dependent capabilities must have clear mock/fallback behavior for development environments.

## MVP scope for this implementation
### Must implement
1. Health check endpoint and client flow.
2. Device scan request/response flow.
3. Import-to-NAS request/response flow.
4. Write-back request/response flow.
5. Local persistent operation log on the client side.
6. Server config file with at least:
   - client IP allowlist
   - NAS address
   - public key name
   - transport settings for any ssh/rsync/sftp usage
   - explicit read-only default and write enable flag
7. Runnable CLI entrypoints for local client and Pi-side server.
8. Tests run by this session, not deferred.
9. Git repo initialized and changes committed.

### Acceptable MVP simplifications
- Real USB enumeration may be replaced by a deterministic mock/fallback scanner when system tools or hardware are unavailable.
- Import may use local filesystem copy plus optional rsync-compatible configuration rather than requiring a real NAS.
- Write-back may initially support sidecar `.lrc` and JSON metadata sidecar update flows, with audio-tag mutation represented by a safe placeholder/fallback.
- Authentication may be shared-token plus IP allowlist for HTTP MVP, while still carrying SSH/rsync config for future transport hardening.

## Out of scope for MVP
- Full udev integration and auto-mount daemon.
- Long-running task queue on the server.
- Durable business state on the server.
- Heavy media analysis or online metadata fetching.
- Full real-device compatibility matrix.

## Functional requirements
### Local client
- Build validated request payloads for `scan`, `import_to_nas`, `write_back`, and `health_check`.
- Call the server over HTTP JSON.
- Persist one JSON operation record per request under a local log directory.
- Print concise summaries for CLI use.

### Pi-side server
- Expose HTTP endpoints:
  - `GET /health`
  - `POST /api/v1/scan`
  - `POST /api/v1/import`
  - `POST /api/v1/write-back`
- Validate request schemas.
- Enforce IP allowlist.
- Enforce read-only-by-default policy.
- Return structured response objects including operation logs.

## Data and schema requirements
- Use shared typed schema definitions for requests, responses, operation logs, config, devices, import items, and write-back changes.
- Every response must include request id, status, timestamps, summary, warnings/errors, and embedded operation log payload.
- Client log persistence should store both normalized request metadata and raw server response.

## Safety requirements
- Scan and import operate without server write enable.
- Write-back requires both:
  - server config `write_enabled: true`
  - request mode explicitly set to write
- Dry-run should be supported for import and write-back.
- All file writes must remain inside configured roots.

## Deliverables
- Source code for client/server/shared modules.
- Example server config file.
- README with run/test instructions.
- `requirements.md`, `design.md`, `tasks.md` reflecting actual implementation.
