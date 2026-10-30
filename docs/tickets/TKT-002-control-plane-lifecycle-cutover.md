# TKT-002: Retire competing lifecycle writes during control-plane cutover

Scope: optional configuration gate for legacy start/stop/restart and update jobs
requesting restart. Preserve status, logs, CAN maintenance and build-only updates.
Default remains compatible until explicitly disabled on the robot. This is not
a new runtime owner or a logging migration.

Ownership: config, API/service guard, focused tests and runbook. Acceptance:
authenticated retired writes return 410 before any commands/jobs; service calls
also reject; auth still precedes rejection; reads and non-restarting updates work.
