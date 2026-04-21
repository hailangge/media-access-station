# Design

## Change summary
This round is a targeted corrective patch over the MVP. The goal is to preserve the existing API shape while fixing two correctness issues and tightening regression coverage.

## 1. Import destination handling
### Current defect
Single-file import currently uses `destination.suffix` to guess whether `destination_subdir` is a filename. That misclassifies dotted directory names like `archive.v2`.

### Intended behavior
`destination_subdir` is always a directory-like relative destination chosen by the caller. For single-file imports:
- resolve `<nas_import_root>/<destination_subdir>` as the destination directory
- create it if needed
- copy the source file to `<destination_dir>/<source.name>`

For directory imports, keep recursive copy behavior unchanged.

### Implementation direction
- Remove suffix-based file-path guessing from `execute_import`
- Normalize the return payload so `destination` still refers to the destination directory
- Preserve overwrite handling and warnings for skipped files

## 2. Status modeling for import and write-back
### Problem
Handlers currently hardcode `success` even when warnings indicate skipped files or unsupported work.

### Intended semantics
Use one consistent status computation helper for service-layer responses:
- `success`: no warnings, no errors, and the operation completed as intended
- `partial`: some useful work completed or the request was processed, but warnings/skips/unsupported items mean the outcome is mixed
- `failed`: operation produced no useful result or encountered an error-dominant outcome

### Practical mapping for this repo
- Import:
  - successful copy or dry-run with no warnings => `success`
  - any skipped files/warnings with at least some processed result => `partial`
  - no copied/planned items, or explicit failed indicator from executor => `failed`
- Write-back:
  - requested targets all handled cleanly => `success`
  - warnings such as unsupported action/target with some handled work => `partial`
  - zero changed/planned items because nothing could be handled => `failed`

### Implementation direction
- Expand shared `StatusType` to include `partial` and `failed`
- Add a small service helper that derives both envelope status and operation-log status from executor outputs
- Avoid changing endpoint error mapping for true exceptions; keep HTTP errors for permission/path failures

## 3. Test strategy
Add/extend tests to cover:
- dotted `destination_subdir` on single-file import
- import partial status when an existing file is skipped
- write-back partial status when warnings occur alongside handled work
- write-back failed status when nothing can be applied
- smoke-level API/CLI regression remains green under full `pytest`

## 4. Risk control
- Keep the change localized to schemas, importer/service logic, and tests
- Do not redesign transport or endpoint contracts beyond status values already returned in responses
- If a minor issue requires broader product semantics, defer it and report it instead of expanding scope
