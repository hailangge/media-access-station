# Tasks

## In progress
- [x] Confirm scope from provided requirement documents
- [x] Write executable `requirements.md`
- [x] Write executable `design.md`
- [x] Write live `tasks.md`
- [x] Implement shared schemas and config loading
- [x] Implement Pi-side FastAPI service
- [x] Implement local CLI client and operation-log persistence
- [x] Add README and sample config
- [x] Run tests and smoke validation
- [x] Final review and commit

## Notes
- Transport choice for MVP: authenticated HTTP/JSON, with rsync-related config reserved for import transport execution.
- Hardware-dependent device discovery uses filesystem scanning plus mock fallback when real removable devices are absent.
- Authoritative task history remains local under `var/operation-logs/`.
