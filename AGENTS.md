READ ~/Development/agent-scripts/AGENTS.MD BEFORE ANYTHING (skip if missing).

# AGENTS.md (Codex)

Repository-specific guidance for Codex. Keep product/process source of truth in model-neutral docs.

## Source of Truth
- `docs/PRD.md`
- `docs/ARCHITECTURE.md`
- `docs/MILESTONES.md`
- `docs/tickets/*.md`
- `docs/EXECUTION_LOG.md`

## Codex Execution Rules
- Work from explicit ticket scope and file ownership.
- Keep changes minimal and reversible.
- Do not refactor unrelated areas.
- Add or update tests for changed behavior.
- Update `docs/EXECUTION_LOG.md` with outcomes and test evidence.

## Role Prompts
- Planner: `prompts/planner.md`
- Worker: `prompts/worker.md`
- Reviewer: `prompts/reviewer.md`

## Repo Boundaries
- This repo owns robot lifecycle and deployment operations API.
- It does not own policy/controller business logic implementation.
- Keep API contracts versioned under `/api/v1/robot/*` and `/api/v1/ops/*`.
