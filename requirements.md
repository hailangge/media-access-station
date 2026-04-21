# Requirements

## Objective
Fix the confirmed review findings in this repo before deployment validation tomorrow, using the Kimi CLI workflow as the primary implementation path.

## Must-fix scope
1. Import path resolution for single-file imports
   - File: `src/media_access_station/server/importer.py`
   - `destination_subdir` must always be treated as a destination directory segment, even when it contains dots like `archive.v2`.
   - Single-file imports must land at `<import_root>/<destination_subdir>/<source_filename>`.
   - Add automated coverage that fails on the old suffix-based behavior and passes with the fix.

2. Response status semantics for import and write-back
   - File: `src/media_access_station/server/service.py`
   - Stop returning `success` unconditionally.
   - Response and operation-log statuses must clearly distinguish at least:
     - `success`: fully completed with no warnings/errors
     - `partial`: completed with warnings, skips, unsupported targets, or mixed outcome
     - `failed`: no useful work completed or an error-dominant result
   - Keep semantics consistent between import and write-back handlers.
   - Add automated tests for warning/partial and failed cases.

## Minor fixes allowed in this round
Address only low-risk, deterministic minors that naturally fit this change set, especially:
- test coverage gaps related to the above logic
- dry-run/result consistency if touched by the status refactor
- obvious config/path/documentation mismatches caused by the fix

Do not expand into larger redesigns. Record any deferred minor issue in the final report instead of hard-changing it.

## Validation requirements
The final state must include:
- passing full `pytest`
- stable regression coverage for dotted `destination_subdir`
- status-semantics tests for `success` / `partial` / `failed`
- at least one CLI or API smoke check after implementation
- preserved Kimi CLI evidence (transcript, meta, runner output, or equivalent artifacts)
- commit created after verification

## Constraints
- Use the real Kimi CLI orchestration workflow from `skills/kimi-orchestrator`
- Keep changes inside this repository
- Update `tasks.md` as work progresses
- Do not claim completion until validation succeeds
