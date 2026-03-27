# ADR-001: robot_api Boundary

## Status
Accepted

## Context
The real robot needs a dedicated operational API for lifecycle and deployment actions.
`odrive_api` already handles low-level ODrive settings and should remain focused.

## Decision
- Create a separate `robot_api` service.
- Keep `robot_api` focused on runtime lifecycle + update jobs.
- Keep tuning and motor-level control out of MVP.

## Consequences
Pros:
- Clear separation of concerns.
- Easier permission model and auditing.
- Independent release cadence from `odrive_api`.

Cons:
- Additional service deployment and monitoring overhead.
