# Planning Agent v2 — полный план интеграции

Все времена в этом документе и во всей системе по умолчанию указаны в IANA timezone
`Europe/Moscow`. Внешнее событие Google Calendar с явно заданной другой timezone
сохраняет собственную timezone; planner не должен переписывать её ради нормализации.

## 0. Целевое состояние

```text
Telegram
   |
   v
Hermes Gateway
timezone = Europe/Moscow
   |
   +-- planning-agent Skill
   |
   +-- existing ClickUp MCP -----------------> ClickUp
   |
   +-- planning_core MCP
          |
          +-- Google Calendar API
          |      |
          |      +-- user calendars: READ ONLY
          |      +-- Planning Agent calendar: READ/WRITE
          |
          +-- SQLite planner.db
                 +-- task annotations
                 +-- ClickUp snapshots
                 +-- observations
                 +-- audit
                 +-- future plan/model tables

Hermes cron:
  22:15 Europe/Moscow  evening planning
  10:05 Europe/Moscow  morning reconcile
  16:30 Europe/Moscow  risk scan
  Sun 19:30             weekly review
  day 1 19:00           monthly review

systemd:
  deterministic local health checks
```

Autonomy boundary:

```text
planner.db                 autonomous
Planning Agent calendar    autonomous
existing ClickUp           ask for exact mutation
user/external calendars    read-only
external invitations       never
```

## 1. Preconditions

Assumptions:

- Hermes Agent is already installed and Telegram gateway works.
- Existing ClickUp MCP already works in Hermes.
- Linux server, root access.
- Python 3.11+.
- `uv` installed.
- Google account contains the calendars that must constrain planning.
- All planner-facing times are `Europe/Moscow`.

Before changing anything:

```bash
cp ~/.hermes/config.yaml ~/.hermes/config.yaml.backup-$(date +%F-%H%M)
hermes status --deep
```

Keep the backup until the entire acceptance suite passes.

## 2. Configure Hermes timezone

Edit:

```text
~/.hermes/config.yaml
```

Set the top-level timezone:

```yaml
timezone: "Europe/Moscow"
```

Do not use a permanent fixed UTC offset. Use the IANA name `Europe/Moscow`.

Restart/reload Hermes using the same service mechanism you already use, then verify:

```bash
hermes status --deep
```

## 3. Deploy the local planning-core runtime

From the unpacked bundle:

```bash
sudo mkdir -p /opt/planning-agent
sudo chown "$USER":"$USER" /opt/planning-agent

cp -a planner_mcp /opt/planning-agent/
cp -a scripts /opt/planning-agent/
cp pyproject.toml /opt/planning-agent/

cd /opt/planning-agent
uv sync
```

Verify the environment:

```bash
python3 --version
uv --version

/opt/planning-agent/.venv/bin/python -c \
'from mcp.server import MCPServer; print("MCP import OK")'
```

Expected: Python >= 3.11 and `MCP import OK`.

## 4. Create planner config and state directories

```bash
mkdir -p ~/.config/planning-agent
mkdir -p ~/.local/share/planning-agent
```

Copy configuration:

```bash
cp /path/to/bundle/planning-agent.env.example \
  ~/.config/planning-agent/env

cp /path/to/bundle/policy.yaml \
  ~/.config/planning-agent/policy.yaml

chmod 600 ~/.config/planning-agent/env
```

Verify that:

```bash
grep PLANNER_TIMEZONE ~/.config/planning-agent/env
```

returns:

```text
PLANNER_TIMEZONE=Europe/Moscow
```

Important limitation of v2: `policy.yaml` is the canonical machine-readable policy,
but the current MCP server does not yet load and enforce every policy field. The
Hermes Skill is currently the reasoning-side enforcement layer, while Calendar write
guards are enforced in code.

## 5. Create Google Cloud OAuth credentials

In Google Cloud Console:

1. Create a dedicated project, for example `personal-planning-agent`.
2. Enable Google Calendar API.
3. Configure OAuth consent.
4. Create OAuth Client with application type `Desktop app`.
5. Download the client JSON.
6. Put it on the server as:

```text
~/.config/planning-agent/google_oauth_client.json
```

Protect it:

```bash
chmod 600 ~/.config/planning-agent/google_oauth_client.json
```

The bundle requests only:

```text
calendar.events.readonly
calendar.calendarlist.readonly
calendar.app.created
```

The intended model is:
- read user calendars;
- create and mutate only the app-created `Planning Agent` secondary calendar.

## 6. Perform one-time Google OAuth authorization

From your laptop, open an SSH tunnel:

```bash
ssh -L 8765:127.0.0.1:8765 USER@SERVER
```

Keep the SSH session open.

On the server:

```bash
cd /opt/planning-agent

set -a
source ~/.config/planning-agent/env
set +a

uv run python scripts/oauth_bootstrap.py
```

Open the authorization URL printed by the script in your laptop browser and approve
the account that owns/reads your real calendars.

After successful authorization:

```bash
ls -lah ~/.config/planning-agent/google_token.json
chmod 600 ~/.config/planning-agent/google_token.json
```

## 7. Initialize SQLite

From the bundle directory:

```bash
sqlite3 ~/.local/share/planning-agent/planner.db < schema.sql
```

Verify:

```bash
sqlite3 ~/.local/share/planning-agent/planner.db ".tables"
```

Expected tables include:

```text
audit_log
calendar_event_cache
clickup_task_snapshot
duration_model
kv_state
plan
plan_block
preference
productivity_window
sync_state
task_annotation
task_observation
```

SQLite is the planner operational memory. It is not a replacement for ClickUp task
status and it is not a replacement for Google Calendar commitments.

## 8. Register planning_core MCP in Hermes

Merge `hermes-config-snippet.yaml` into the existing:

```text
~/.hermes/config.yaml
```

Use real absolute paths, for example:

```yaml
timezone: "Europe/Moscow"

mcp_servers:
  # Keep the existing ClickUp MCP entry unchanged.

  planning_core:
    command: "/opt/planning-agent/.venv/bin/python"
    args:
      - "/opt/planning-agent/planner_mcp/server.py"
    env:
      PLANNER_HOME: "/home/YOUR_USER/.local/share/planning-agent"
      PLANNER_DB: "/home/YOUR_USER/.local/share/planning-agent/planner.db"
      PLANNER_POLICY: "/home/YOUR_USER/.config/planning-agent/policy.yaml"
      GOOGLE_OAUTH_CLIENT: "/home/YOUR_USER/.config/planning-agent/google_oauth_client.json"
      GOOGLE_TOKEN: "/home/YOUR_USER/.config/planning-agent/google_token.json"
      PLANNING_CALENDAR_ID_FILE: "/home/YOUR_USER/.config/planning-agent/planning_calendar_id"
      PLANNING_CALENDAR_NAME: "Planning Agent"
      PLANNER_TIMEZONE: "Europe/Moscow"
      READ_CALENDAR_IDS: "primary"
    timeout: 30
    connect_timeout: 10
    enabled: true
    supports_parallel_tool_calls: false
```

Replace `YOUR_USER`.

Restart Hermes gateway through your existing service manager.

Verify:

```bash
hermes status --deep
```

## 9. MCP health acceptance test

Start an interactive Hermes session or use Telegram and ask:

```text
Покажи инструменты planning_core и вызови planner_health.
```

Expected health result should contain:

```json
{
  "db": true,
  "google_token": true,
  "planning_calendar": true,
  "ok": true
}
```

The first successful call may create the app-owned secondary calendar:

```text
Planning Agent
```

Do not continue to cron until this test passes.

## 10. Calendar write-isolation acceptance test

Ask Hermes:

```text
Создай через planning_core тестовый planning block завтра с 15:00 до 15:30
Europe/Moscow.
```

Verify in Google Calendar:

- event exists;
- event belongs to `Planning Agent` calendar;
- primary/user calendar was not modified.

Then ask:

```text
Удали этот тестовый planning block.
```

It must disappear.

Negative safety test:

```text
Попробуй удалить мою обычную встречу из primary calendar через planning_core.
```

Expected behavior: impossible/refused. `planning_core` does not expose a mutation tool
for arbitrary user calendar events.

This test is mandatory before autonomous cron.

## 11. Configure all readable Google calendars

The default is:

```text
READ_CALENDAR_IDS=primary
```

If work, university or personal commitments live in separate calendars, ask Hermes to
call:

```text
calendar_list_calendars
```

Record the real calendar IDs.

Then update both:

```text
~/.config/planning-agent/env
~/.hermes/config.yaml
```

Example:

```text
READ_CALENDAR_IDS=primary,WORK_ID,UNIVERSITY_ID
```

Restart Hermes after changing MCP environment.

Do not add the app-owned `Planning Agent` calendar here merely to make writes work;
its write target is resolved separately. Add it to reads only if your reconciliation
logic explicitly needs it in the same read set.

## 12. Put fixed sport commitments in the user Calendar

Create user-owned events rather than agent-owned planning blocks.

Thursday:

```text
Тренировка с тренером
11:00 Europe/Moscow
recurring each Thursday
```

Saturday football:

- if start time is stable: recurring user event;
- if start time changes weekly: add the actual game each week.

The planner must read these as hard time constraints and must never move them.

## 13. Install the Hermes Planning Agent Skill

```bash
mkdir -p ~/.hermes/skills/productivity/planning-agent

cp hermes-skill/planning-agent/SKILL.md \
  ~/.hermes/skills/productivity/planning-agent/SKILL.md
```

Start a new Hermes session or restart the gateway if needed for skill discovery.

Behavioral test:

```text
Используя planning-agent, кратко перечисли свои границы автономии.
```

Expected:
- planner Calendar may be changed autonomously;
- ClickUp mutation requires confirmation;
- user Calendar events are not changed;
- soft project dates may live locally;
- master's deadlines are hard.

## 14. Verify the existing ClickUp MCP contract

Do not rename or invent ClickUp tools.

Ask Hermes:

```text
Используя мой существующий ClickUp MCP, прочитай до 10 активных задач и покажи:
ID, title, status, priority, time estimate, tags, due date. Ничего не меняй.
```

Determine which real tools provide those capabilities.

The planner requires semantic access to:
- task ID;
- title;
- status;
- priority;
- time estimate;
- tags;
- due date.

Dependencies are useful if available, but are not required for the first MVP.

## 15. Verify ClickUp -> local snapshot caching

Ask Hermes:

```text
Прочитай актуальный ClickUp backlog минимальным числом пакетных вызовов и сохрани
нормализованный snapshot в planning_core. ClickUp не меняй.
```

Then:

```text
Теперь прочитай тот же набор задач только из локального planner cache, без нового
ClickUp запроса.
```

This validates:

```text
ClickUp MCP
   ->
Hermes
   ->
planner_cache_clickup_tasks
   ->
SQLite
```

The system deliberately treats ClickUp MCP calls as a limited resource and should not
poll ClickUp every few minutes.

## 16. Adopt the hard-deadline convention

Recommended durable rule:

```text
ClickUp Due Date = real hard deadline only.
```

Examples:

```text
Сдать отчёт по магистратуре 18 сентября
-> native ClickUp Due Date

Хочу закончить pet-project к концу месяца
-> local planner soft_target_at
-> no ClickUp Due Date
```

Because all ClickUp mutations require confirmation, the agent must first propose:

```text
Task: Distributed Systems report
Due Date: none -> 2026-09-18 23:59 Europe/Moscow
Применить?
```

Only an explicit confirmation authorizes that exact change.

## 17. Acceptance test for ClickUp confirmation

Ask:

```text
Повысь priority задачи X до urgent.
```

Expected behavior before any mutation:

```text
Предлагаю:
task X
priority: high -> urgent
Подтвердить?
```

Reply:

```text
да
```

Only then should the agent mutate ClickUp.

Next, request a different mutation. The agent must ask again. One approval must not be
treated as continuing permission.

## 18. First manual end-to-end evening plan

Before creating recurring cron jobs, run at least one manual evening plan:

```text
Используй planning-agent.
Прочитай fresh Calendar и свежий ClickUp backlog минимальным числом batch reads,
сохрани snapshot и спланируй завтра целиком.
Все времена Europe/Moscow.
Если моего решения не требуется — сразу запиши movable blocks в Planning Agent
Calendar. ClickUp без подтверждения не меняй.
```

Inspect the resulting calendar.

Acceptance criteria:

- no user event moved or deleted;
- agent events exist only in `Planning Agent`;
- no double booking;
- 20%ish buffer is visible in capacity, even if not every buffer minute is a named event;
- schedule is not packed to 100%;
- master's hard deadlines are backward-planned;
- personal projects use local soft targets;
- morning before 10:00 is not required for deadline feasibility when wake time is unknown;
- high-cognitive work is preferentially placed before the first work call when feasible;
- context switching is reasonable.

Inspect local state:

```bash
sqlite3 ~/.local/share/planning-agent/planner.db
```

Useful queries:

```sql
SELECT task_id, life_area, task_type, cognitive_load, soft_target_at
FROM task_annotation;

SELECT *
FROM audit_log
ORDER BY at DESC
LIMIT 20;
```

## 19. Broken-day replan acceptance test

After a valid plan exists, simulate a disruption:

```text
Я проснулся только в 10:30, а в 15:00 появился новый созвон.
Перестрой остаток дня. Все времена Europe/Moscow.
```

Acceptance criteria:

- past time is frozen;
- the new user Calendar event is fixed;
- only future agent-owned blocks are moved;
- minimum necessary number of blocks changes;
- low-value flexible work is dropped/deferred before sleep or hard commitments;
- hard-deadline feasibility is recalculated;
- Telegram message summarizes the material changes without narrating bookkeeping.

## 20. Install deterministic systemd health check

```bash
mkdir -p ~/.config/systemd/user

cp systemd/planning-agent-health.service \
  ~/.config/systemd/user/

cp systemd/planning-agent-health.timer \
  ~/.config/systemd/user/

systemctl --user daemon-reload
systemctl --user enable --now planning-agent-health.timer
```

Test:

```bash
systemctl --user start planning-agent-health.service
journalctl --user -u planning-agent-health.service -n 50
systemctl --user status planning-agent-health.timer
```

If user services must survive logout:

```bash
sudo loginctl enable-linger "$USER"
```

Note: v2 systemd health is a local filesystem/SQLite/token presence check. The deeper
Google API health check is exposed through MCP as `planner_health()`.

## 21. Do not enable autonomous cron before three tests pass

Required tests:

```text
A. Manual plan tomorrow
B. Broken-day replan
C. Confirmed ClickUp mutation
```

Also verify the negative Calendar-mutation safety test.

Only after all four behaviors are correct should recurring jobs be enabled.

## 22. Configure Telegram delivery for Hermes cron

The bundle's cron prompts are the canonical ritual prompts, but during installation
verify the exact delivery flags supported by your installed Hermes version.

The desired behavior is explicit delivery to the Telegram conversation/gateway rather
than relying accidentally on an unrelated session origin.

Create jobs interactively if that makes the delivery target clearer than executing the
script blindly.

## 23. Create ritual cron jobs

All schedules are Europe/Moscow because Hermes top-level timezone must be
`Europe/Moscow`.

Desired schedule:

```text
22:15 daily       evening planning
10:05 daily       morning reconcile
16:30 daily       risk scan
19:30 Sunday      weekly review
19:00 day 1       monthly review
```

Equivalent cron expressions:

```text
15 22 * * *
5 10 * * *
30 16 * * *
30 19 * * 0
0 19 1 * *
```

Use the `planning-agent` skill for every ritual.

## 24. Pin the cron model/provider

For autonomous planning, avoid silently changing the reasoning model just because the
interactive-chat model changed.

If your installed Hermes version supports cron-level model/provider pinning, pin the
planning jobs to the model/provider you intend to use for planning.

After configuration, inspect:

```bash
hermes cron list
```

## 25. Run each cron job manually before leaving it enabled

For every created job:

```bash
hermes cron run <job_id>
hermes cron runs <job_id>
```

Verify:

- execution completed;
- Telegram delivery works;
- no duplicate Calendar blocks;
- no unauthorized ClickUp mutation;
- correct `Europe/Moscow` times;
- repeated run is idempotent enough not to duplicate the plan.

## 26. Normal operating model after installation

Evening:

```text
fresh/batched ClickUp read
+ fresh Calendar
+ local annotations/model
-> tomorrow plan
-> Planning Agent Calendar
-> compact Telegram summary
```

Morning:

```text
fresh Calendar
+ cached ClickUp unless task freshness matters
-> reconcile only
-> minimal change
-> compact final plan
```

During day:

```text
user reports disruption
or material fixed event appears
-> fresh Calendar
-> ClickUp refresh only if needed
-> freeze past/current/external
-> replan future
```

Risk scan:

```text
no material risk
-> silence

new hard-deadline risk / fixed conflict / >90 min replan
-> Telegram
```

## 27. What v2 intentionally does not yet implement deterministically

Do not mistake the current Skill policy for a full mathematical scheduling daemon.

Still to be implemented in a later phase:

```text
planner_get_policy()
planner_build_day()
planner_prepare_plan()
planner_commit_plan()
planner_rollback_plan()
incremental Google syncToken worker
manual Calendar override fingerprint detector
automatic robust duration-model updater
```

Current split:

```text
Calendar write isolation / idempotent block writes / SQLite primitives
-> code-enforced

planning algorithm / scoring / confirmation dialogue / ClickUp batching policy
-> Hermes Skill reasoning
```

This is suitable for MVP/shadow operation. Full autonomy should follow after observing
real behavior and moving stable rules into deterministic code.

## 28. Recommended Phase 2 after 2-3 weeks

Priority order:

1. Load `policy.yaml` inside planning-core and expose `planner_get_policy()`.
2. Implement deterministic free-interval and capacity calculation.
3. Implement hard-deadline backward feasibility.
4. Implement deterministic candidate scoring.
5. Add `plan_id` transaction/commit semantics.
6. Add inverse rollback.
7. Add manual Calendar override detection.
8. Only then consider incremental Calendar sync or webhooks.

Do not add Redis, Postgres, Kafka, n8n, Kubernetes, vector DB or webhooks unless real
operational evidence shows SQLite + MCP + cron is insufficient.

## 29. Final go-live checklist

The system is ready for unattended daily rituals only if every item below is true:

- [ ] Hermes timezone is `Europe/Moscow`.
- [ ] `PLANNER_TIMEZONE=Europe/Moscow`.
- [ ] planning_core MCP appears in Hermes.
- [ ] `planner_health()` returns `ok=true`.
- [ ] `Planning Agent` secondary calendar exists.
- [ ] planner can create/delete its own test event.
- [ ] planner cannot mutate a user Calendar event.
- [ ] every relevant user calendar is readable.
- [ ] fixed trainer/football commitments live as user-owned Calendar events.
- [ ] Planning Agent Skill is discovered.
- [ ] ClickUp task read contract works.
- [ ] ClickUp snapshot caching works.
- [ ] ClickUp mutation asks for exact confirmation.
- [ ] one full manual day plan passed review.
- [ ] one broken-day replan passed review.
- [ ] audit rows are written.
- [ ] systemd health timer is running.
- [ ] cron Telegram delivery was manually tested.
- [ ] every cron job was run manually once.
- [ ] repeated planning run does not duplicate Calendar blocks.

After these checks, the v2 system is appropriate for MVP autonomous operation with
Calendar autonomy and confirmation-gated ClickUp writes.
