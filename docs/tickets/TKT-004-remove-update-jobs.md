# TKT-004: Remove robot update jobs

Scope: remove git pull/build/restart update jobs, their HTTP routes, worker,
in-memory store, models and configuration. Preserve status/log reads and existing
guarded runtime/CAN compatibility routes. No robot deployment or service restart.

Ownership: src/robot_api, tests, deployment environment example and API docs.

Acceptance: removed routes return 404 and disappear from OpenAPI; no command can
be executed through them, with or without the lifecycle compatibility flag.
Read/log and compatibility regression tests pass.

Outcome: implemented locally; 29 Python tests and fatal-error Ruff pass. Robot
upgrade/restart intentionally not performed. See EXECUTION_LOG.md for evidence.
