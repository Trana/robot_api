# TKT-003: Retire legacy CAN reset by default

Status: implemented and locally verified, 2026-09-19; not deployed to the robot.

Scope: CAN reset moves to durable Robot Control Plane operations. Authenticate
then return 410 from the legacy route by default; guard the service method too.
An explicit rollback flag is available only while control-plane maintenance is
disabled. Logs, status and update APIs remain unchanged. No deployment in this task.
