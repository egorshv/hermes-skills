# ClickUp contract — calibrated for Free Forever

The names below are **abstract capabilities**, not claims about your current MCP tool
names. Bind them to the actual tools exposed by your already-working ClickUp MCP.

## Operating constraint

The official ClickUp MCP documentation currently lists a 100-call rolling-24-hour limit
for Free Forever workspaces. Treat ClickUp as a rate-limited remote source, not something
we poll every few minutes.

Target budget:
- normal autonomous planning: <= 40 calls/day;
- keep ~40 calls/day unspent for user-driven work and exceptional replans;
- prefer one broad search/list call over N per-task calls when your real MCP supports it;
- cache the normalized result in planner SQLite;
- the midday risk scan uses the cache unless a fresh task read is materially necessary.

## Current task metadata

Use what the user already maintains:
- `id`
- `name`
- `status`
- `priority`
- `time_estimate`
- `tags`
- native `due_date` when the user explicitly adopts it for a hard deadline

Do not consume ClickUp Custom Field uses for planner bookkeeping. Planner annotations
(life area, task type, cognitive load, soft target, confidence) live in `planner.db`.

## Deadline semantics

Two different concepts MUST NOT be collapsed into one field:

1. **hard deadline** — external/real commitment, especially master's coursework;
2. **soft target** — desired date for a personal project.

Recommended source:
- hard deadline: confirmed native ClickUp due date;
- soft target: planner SQLite only.

If the user states a master's deadline in Telegram but it is absent in ClickUp, store a
local mirrored hard deadline with provenance `user_message`, use it for risk calculations,
and propose the exact ClickUp due-date write for confirmation.

## Planner tags

Tags are useful for user-visible classification and are available on Free Forever, but
because the user requested confirmation for ClickUp mutations, the planner must not add
or remove tags autonomously. Local annotations are the default.

Possible tag taxonomy if the user later approves it:
- `area/work`
- `area/masters`
- `area/project`
- `area/learning`
- `area/sport`
- `area/social`

Do not create this taxonomy automatically.

## Mutation policy

Every ClickUp mutation requires explicit confirmation for the exact proposed diff.
Confirmation does not grant an open-ended permission.

Examples:
- `priority: normal -> high` -> ask;
- add `area/masters` tag -> ask;
- set due date -> ask;
- status -> complete -> ask;
- create subtask -> ask.

Reading, ranking, local annotations, Calendar planning blocks and planner soft-targets do
not require confirmation.
