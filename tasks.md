# Tasks

## In progress
- [x] Confirm audit findings and target repo state
- [x] Refresh `requirements.md`, `design.md`, and `tasks.md` for the fix round
- [x] Launch persistent Kimi session for implementation
- [x] Fix dotted `destination_subdir` handling for single-file import
- [x] Refactor import/write-back status semantics to `success` / `partial` / `failed`
- [x] Add regression tests for dotted destination and status outcomes
- [x] Run full `pytest`
- [x] Run CLI/API smoke checks
- [x] Final review, commit, and collect Kimi evidence

## Notes
- Scope is limited to the two confirmed major findings plus low-risk adjacent cleanup only.
- Need preserved Kimi CLI evidence for the implementation workflow.
- Repo had pre-existing review artifacts under `review/` and a modified `tasks.md`; this round supersedes the task tracker with the repair checklist above.
- 2026-04-25 verification hardening found an extra write-back flaw: missing target files were incorrectly treated as successful writes, and `dry_run` could still create parent directories. Fixed with regression coverage before Orange Pi validation.
- 2026-04-25 end-to-end validation executed against Orange Pi `192.168.0.160` using virtual USB-style mount folders plus downloaded MP3/WAV/MP4/JPG sample assets.
- 2026-04-25 remaining review minors were closed: real device filesystem labeling, clearer write-disabled messaging, persisted `health` logs, explicit `scan --dry-run` semantics, automated auth/IP/path-traversal coverage, and production path guidance.
- 2026-05-03 deployment follow-up requires a formal Orange Pi runtime layout, production config, `systemd` boot startup, and crash auto-restart validation on `192.168.0.160`.
