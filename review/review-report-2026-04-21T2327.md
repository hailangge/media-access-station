# Media Access Station — Code Review and Requirements-Alignment Audit

**Date:** 2026-04-21T23:27+08:00  
**Reviewer:** Kimi (persistent review session)  
**Repository:** `/mnt/data/repositories/media-access-station`  
**Commit:** `808880b Implement Media Access Station MVP`  
**Branch:** `main`

---

## 1. Executive Summary

The repository implements a minimal viable Media Access Station with a clean client/server split, typed HTTP/JSON request-response contracts, local operation-log persistence, and safe read-only defaults. The implementation aligns well with the handoff requirements and the local `requirements.md`, `design.md`, and `tasks.md`.

All 6 pytest tests pass. Manual smoke checks confirm path-traversal blocking, dual-enablement write-back protection, dry-run import behavior, and auth enforcement.

**No blockers found.** There are 2 major findings and 6 minor findings, all documented below with file-level evidence.

---

## 2. Validation Commands Executed

| Command | Result |
|---------|--------|
| `pytest -v` | 6 passed |
| `mas-client --help` | OK — 4 commands listed |
| `mas-server --help` | OK — argparse help |
| `python -m py_compile` on key modules | OK |
| Path traversal import (`../../../etc/passwd`) | HTTP 400, blocked |
| Path traversal write-back (`../../../etc/passwd`) | HTTP 403, blocked |
| Write-back with `mode=read_only` (server enabled) | HTTP 403, "Request mode must be 'write' for write-back" |
| Dry-run import | HTTP 200, `planned_files` present |
| Dry-run write-back (server disabled) | HTTP 403 — blocked by safety default |
| Missing auth token | HTTP 401 |
| Wrong auth token | HTTP 401 |

All validation was run inside the repo's `.venv` on Python 3.14.3.

---

## 3. Findings by Severity

### Blockers (0)

None.

### Major (2)

#### M1 — Import destination misclassification when `destination_subdir` contains a dot
- **File:** `src/media_access_station/server/importer.py` (line 54)
- **Evidence:**
  ```python
  final_target = destination if destination.suffix else destination / source.name
  ```
  If `destination_subdir` is a directory name containing a dot (e.g., `archive.v2`), `destination.suffix` is truthy, so the file is copied directly to `archive.v2` instead of `archive.v2/<source_name>`.
- **Impact:** Single-file imports to dotted directory names land at the wrong path.
- **Recommendation:** Remove the `suffix` heuristic; treat `destination_subdir` strictly as a directory segment.

#### M2 — Response status always "success" even when files are skipped or warnings are present
- **Files:** `src/media_access_station/server/service.py` (lines 35–58 for import, lines 61–84 for write-back)
- **Evidence:** `handle_import` and `handle_writeback` hardcode `status="success"` in both the `OperationLog` and the `ResponseEnvelope`, regardless of whether `warnings` contains skipped-file messages or unsupported-action notices.
- **Impact:** Consumers relying on `status` alone may miss partial failures.
- **Recommendation:** Introduce a `"warning"` or `"partial_success"` status (or keep `"success"` but document that `warnings` must always be checked). At minimum, document the behavior in the README.

### Minor (6)

#### m1 — `filesystem` field not populated for real scanned devices
- **File:** `src/media_access_station/server/device_scan.py`
- **Evidence:** `DeviceRecord` is constructed without `filesystem`, so it defaults to `"mockfs"` even for real devices.
- **Impact:** Slight confusion in logs; not a functional issue for MVP.

#### m2 — Write-back error message says "disabled by default" even when explicitly disabled in config
- **File:** `src/media_access_station/server/writeback.py` (line 18)
- **Evidence:** `raise PermissionError("Server write operations are disabled by default")`
- **Impact:** Minor UX inaccuracy when an admin explicitly sets `write_enabled: false`.

#### m3 — `health` CLI command does not persist an operation log
- **File:** `src/media_access_station/client/cli.py` (lines 29–36)
- **Evidence:** `health` echoes JSON directly without calling `_persist`.
- **Impact:** Inconsistent with the design note that client logs every request.

#### m4 — `scan` CLI accepts `--dry-run` but server handler ignores it
- **File:** `src/media_access_station/client/cli.py` (line 52) / `src/media_access_station/server/service.py` (lines 11–32)
- **Evidence:** `ScanRequest` includes `dry_run`, but `handle_scan` does not branch on it.
- **Impact:** Harmless no-op; slightly misleading UX.

#### m5 — Missing automated tests for dry-run write-back, path traversal, and auth failures
- **File:** `tests/test_api.py`
- **Evidence:** 4 API tests cover health, scan, import, and write-back success/blocked. No test for path traversal, wrong token, IP block, or dry-run write-back.
- **Impact:** Regressions in security controls could go undetected.

#### m6 — Relative paths in default config may break when package is installed outside repo root
- **File:** `src/media_access_station/server/config.example.yaml`
- **Evidence:** Paths like `./var/nas-import` and `./fixtures/devices` are relative to the working directory of the server process.
- **Impact:** If `mas-server` is run from a different cwd after `pip install`, paths resolve incorrectly.
- **Recommendation:** Document that config paths should be absolute in production.

---

## 4. Requirements Alignment by Topic

### Business goals and architecture constraints
- **Aligned.** Two-part architecture (local client + Pi-side server) is clearly separated into `client/` and `server/` packages. The local host stores authoritative operation records under `var/operation-logs/`.

### Client/server split and stateless server rule
- **Aligned.** Server keeps only normal app logs and transient per-request data. No durable task state, queue, or business history lives on the server.

### Default safety behavior
- **Aligned.** `mode` defaults to `"read_only"` in `schemas.py`. `write_enabled` defaults to `False` in `config.py`. Write-back requires both `config.security.write_enabled == True` **and** `request.mode == "write"`.

### Config completeness
- **Aligned.** `ServerConfig` includes all required fields: server host/port, auth token, IP allowlist, write enable flag, NAS address/import root, public key name, transport method + rsync subtree, device scan roots, mount root, service log dir, and temp dir.

### Logging and authoritative local history
- **Aligned.** Client persists one JSON file per request under `var/operation-logs/YYYY/MM/DD/<request_id>.json`. Each file contains `persisted_at`, endpoint, request, and raw server response.

### Request/response schema and error model
- **Aligned.** Shared `schemas.py` defines typed `RequestBase`, `HealthRequest`, `ScanRequest`, `ImportRequest`, `WriteBackRequest`, `ResponseEnvelope`, and `OperationLog`. FastAPI validates them automatically. Errors map to HTTP 400 (bad request / path traversal), 401 (invalid token), and 403 (write blocked / IP not allowed).

### Import, write-back, and device-scan behavior
- **Aligned.** Device scan enumerates configured filesystem roots and falls back to a deterministic mock device with a clear warning. Import supports `local_copy` and `rsync` transports, plus dry-run. Write-back supports `.lrc` sidecars and `.meta.json` sidecars, with dry-run support.

### Implementation quality, module boundaries, error handling, path handling
- **Mostly aligned.** Modules are well bounded (`shared/`, `server/`, `client/`). Path traversal is blocked via `ensure_within_root` using `Path.resolve()`. Error handling in `app.py` catches exceptions and maps them to HTTP errors.

### Mock/fallback reasonableness
- **Aligned.** `device_scan.py` returns a synthetic `mock-device` with `mock: true` when no real roots yield subdirectories. This is explicitly documented in the README.

### CLI/API consistency
- **Aligned.** CLI commands (`health`, `scan`, `import`, `write-back`) map 1:1 to API endpoints and use the same shared schemas.

### Tests and smoke validation
- **Partial.** 6 passing tests cover core flows, but security edge cases (path traversal, auth failures, IP block) are only covered by manual smoke checks in this review session, not by automated tests.

---

## 5. Git Status

```
On branch main
Changes not staged for commit:
  modified:   tasks.md
Untracked files:
  .review-kimi-prompt.txt
```

The only uncommitted change at review start was `tasks.md` (implementation agent added audit checklist). The review report itself is an untracked artifact.

---

## 6. Residual Risks

1. **Hardware gap:** The MVP does not integrate with real USB enumeration, udev, or auto-mount. Moving to real SBC hardware will require a new device-scan backend without changing the request/response contract.
2. **No retry logic:** Network failures between client and server are not retried; `httpx` exceptions propagate to the CLI user.
3. **No real NAS/rsync integration tested:** The `rsync` transport path is present in code but only `local_copy` was validated in this session.
4. **No task cancellation / interruption handling:** If a device is unplugged mid-import, the server will raise an exception and return 400; the client will record the failure, but there is no resume or partial-retry logic.
5. **Single shared auth token:** The MVP uses a bearer token plus IP allowlist. Future hardening should move to per-client tokens or mTLS.

---

## 7. Conclusions

- The MVP meets its stated scope and satisfies all mandatory items in `requirements.md`.
- The client/server split, stateless server rule, read-only default, and local authoritative logging are all correctly implemented.
- The two major findings (M1 import path heuristic, M2 always-success status) are low-risk for an MVP but should be addressed before production use.
- No code changes were made by this review session; only audit artifacts (`tasks.md` update and this report) were produced.
