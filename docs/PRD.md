# Product Requirements: robot_api

## Problem
Real robot operations are currently manual and split across terminal commands:
- start/stop runtime launch stack
- inspect runtime status/logs
- pull/build/restart after repo updates

This increases operator overhead and makes UI-driven operations difficult.

## Goals (MVP)
1. Provide a stable HTTP API for real robot runtime lifecycle.
2. Provide an async update API for `git pull + build + optional restart`.
3. Keep operations safe, auditable, and machine-readable.
4. Mirror `odrive_api` architecture for maintainability.

## Non-Goals (MVP)
- PD tuning workflow automation.
- Arbitrary remote shell execution.
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

2. Update operation
- Start update job.
- Report in-progress step and logs.
- Return job history and final status.
- Reject concurrent updates.

3. API behavior
- `/api/v1/*` routes support token auth.
- Error payload includes stable `code` + `message`.
- Structured operation logs for observability.

## Success Criteria
- Operator can fully control runtime lifecycle from UI without shell access.
- Operator can trigger update flow and monitor completion from UI.
- All MVP endpoints covered by API + service tests.
