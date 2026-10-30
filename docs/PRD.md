# Product Requirements: robot_api

## Problem
Real robot operations are currently manual and split across terminal commands:
- start/stop runtime launch stack
- inspect runtime status/logs

This increases operator overhead and makes UI-driven operations difficult.

## Current Goals
1. Retain gated legacy lifecycle compatibility; normal controls use Robot Control Plane.
2. Preserve status/log reads while Robot Control Plane owns normal runtime operations.
3. Keep operations safe, auditable, and machine-readable.
4. Mirror `odrive_api` architecture for maintainability.

## Non-Goals
- PD tuning workflow automation.
- Arbitrary remote shell execution.
- Remote git/build/update jobs (removed 2026-09-19).
- Multi-host deployment orchestration.

## Users
- Robot operator using Training UI.
- Developer validating deploy and runtime health.

## Functional Requirements
1. Runtime controls
- Start runtime service.
- Stop runtime service.
- Restart runtime service.
- Query runtime status.
- Read recent runtime logs.

2. API behavior
- `/api/v1/*` routes support token auth.
- Error payload includes stable `code` + `message`.
- Structured operation logs for observability.

## Success Criteria
- Existing status/log reads remain available during the control-plane migration.
- No git/build or update-job endpoints remain exposed.
- All MVP endpoints covered by API + service tests.
