# Requirements

## Objective
Harden Media Access Station so media operations can use real Orange Pi USB access without exposing unrestricted root SSH.

## Must-build scope
1. Restricted remote SSH execution
   - The shared key must stop logging in as `root`.
   - A low-privilege SSH account must be used instead.
   - The low-privilege account must be limited to fixed command entrypoints for:
     - block inventory,
     - read-only mount,
     - mount status,
     - unmount.

2. Script-first operator surface
   - All supported Media Access Station capabilities must remain reachable through explicit scripts.
   - The skill must state the entrypoints directly instead of telling another agent to inspect code.
   - Existing service operations must stay available:
     - `health`
     - `scan`
     - `import-to-nas`
     - `write-back`
     - deployment
     - validation

3. Remote privilege minimization
   - No administrator password should be embedded into the normal workflow.
   - `sudoers` must restrict the low-privilege SSH account to fixed helper scripts only.
   - The helper scripts must reject unsafe device paths, unsupported filesystem types, arbitrary mount targets, and non-read-only mounts.
   - Controlled read-write mounts may be allowed only for explicit lyric write-back workflows.

4. Automatic lyric-only write-back
   - The system must support a mode where a real USB device can be mounted read-write for automation.
   - In that mode, the server must allow only `.lrc` lyric sidecar creation or overwrite.
   - Metadata JSON sidecars and audio tag modifications must be blocked.
   - The workflow target is fully automatic lyric download and write-back without exposing broader write privileges.

5. Documentation sync
   - The repo-local requirements and design docs must match the implementation direction.
   - The handoff docs under `/mnt/data/requirements/media access station` must be updated to the same design.

## Validation requirements
The final state must include:
- passing `pytest`
- coverage for the new skill entrypoints or helper logic
- a restricted SSH setup path that can be applied to `192.168.0.165`
- closed-loop verification using fake mount fixtures
- confirmation that `/root/.ssh/authorized_keys` on `192.168.0.165` is cleared after setup

## Constraints
- Keep the design simple and script-oriented.
- Do not redesign the system into a new privileged service layer just for mount management.
- Use the existing Media Access Station HTTP service for business operations.
- Use restricted SSH wrappers only for host-level block discovery and mount control.
