# Planning Agent bundle for Hermes — calibrated v2

This bundle is intentionally split into:
1. Hermes = reasoning/orchestration + Telegram + existing ClickUp MCP.
2. `planning-core` MCP = Google Calendar write guard + structured planning memory + audit primitives.
3. Hermes cron = agentic rituals.
4. systemd timers = deterministic maintenance/health jobs.


## Calibrated profile in this version

- Flexible work; meeting-heavy/fragmented window roughly 13:00-20:00 Europe/Moscow.
- Canonical planner timezone is Europe/Moscow for all planning, rituals and policy anchors.
- Typical wake varies 07:00-10:00, so unconfirmed early-morning time is contingent.
- Thursday 11:00 trainer and Saturday-evening football should be user-owned recurring
  Calendar events.
- ClickUp mutations require confirmation; planner-specific semantics stay in SQLite.
- Personal-project target dates are local soft targets; master's deadlines are hard.
- Free Forever ClickUp MCP calls are treated as scarce; the planner caches batched reads.

## Assumptions
- Hermes Agent by Nous Research.
- Linux server, one user.
- Hermes gateway is already connected to Telegram.
- Existing ClickUp MCP is already registered in Hermes.
- Timezone: `Europe/Moscow`.
- Python 3.11+ and `uv` available (or install it separately).

## Install

```bash
sudo mkdir -p /opt/planning-agent
sudo chown "$USER":"$USER" /opt/planning-agent
cp -a planner_mcp scripts pyproject.toml schema.sql /opt/planning-agent/
cd /opt/planning-agent
uv sync
mkdir -p ~/.config/planning-agent ~/.local/share/planning-agent
cp /path/to/planning-agent-bundle-v2-moscow/planning-agent.env.example \
  ~/.config/planning-agent/env
cp /path/to/planning-agent-bundle-v2-moscow/policy.yaml \
  ~/.config/planning-agent/policy.yaml
chmod 600 ~/.config/planning-agent/env
```

`planning-core` requests exactly one Google scope, `calendar.app.created`, so the
credential cannot see or touch any calendar it did not create itself. Reading the user's
real calendars is the `google-workspace` skill's job.

Create a Google Cloud project, enable Google Calendar API, create an OAuth client of type
"Desktop app", download the JSON credentials, and save it to:

```text
~/.config/planning-agent/google_oauth_client.json
```

For first authorization on a headless server, use an SSH tunnel from your laptop:

```bash
ssh -L 8765:127.0.0.1:8765 your-server
```

Then on the server:

```bash
cd /opt/planning-agent
set -a
source ~/.config/planning-agent/env
set +a
uv run python scripts/oauth_bootstrap.py
```

Open the printed authorization URL on your laptop. The callback to
`http://localhost:8765/` will traverse the SSH tunnel.

## Register MCP in Hermes

Merge the snippet from `hermes-config-snippet.yaml` into `~/.hermes/config.yaml`,
then restart the Hermes gateway.

Important: the exact existing ClickUp MCP tool names are deployment-specific.
Map them to the abstract contracts in `docs/clickup-contract.md`; do not rename or
invent upstream ClickUp tools.

## Initialize database

```bash
sqlite3 ~/.local/share/planning-agent/planner.db < schema.sql
```

The server also applies `schema.sql` itself on its first database connection (every
statement is `CREATE ... IF NOT EXISTS`, so replaying it is a no-op). Running it by hand
just makes the state inspectable from day one. The server looks for `schema.sql` one
directory above `planner_mcp/`; override with `PLANNER_SCHEMA` if you deploy a different
layout.

## Install deterministic maintenance

Copy the systemd files, replacing `%h` is not necessary for user units:

```bash
mkdir -p ~/.config/systemd/user
cp systemd/planning-agent-health.service ~/.config/systemd/user/
cp systemd/planning-agent-health.timer ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now planning-agent-health.timer
```

For a server where user services must survive logout:

```bash
sudo loginctl enable-linger "$USER"
```

## Configure the planning skill

The skill depends on the bundled `google-workspace` skill for all reads of the user's real
calendars, and on the `planning_core` MCP for every planning-block read and write. Set at
least `planning.calendar_read_ids` (the calendars holding fixed commitments) and
`planning.planning_calendar_name`, which must match `PLANNING_CALENDAR_NAME` in the MCP
environment.

## Install the Hermes planning skill

```bash
mkdir -p ~/.hermes/skills/productivity/planning-agent
cp hermes-skill/planning-agent/SKILL.md \
  ~/.hermes/skills/productivity/planning-agent/SKILL.md
```

Start a new Hermes session after installing the skill.

## Create Hermes rituals

Run `bash cron-commands.sh` after replacing `<TELEGRAM_TARGET>` if your Hermes version
requires an explicit delivery target. If `deliver: origin` already points to your
Telegram conversation, you can create the jobs interactively instead.

## Files

- `SYSTEM_PROMPT.md` — canonical planning policy source.
- `hermes-skill/planning-agent/SKILL.md` — Hermes-loadable version of that policy.
- `policy.yaml` — default scheduling/autonomy policy.
- `schema.sql` — operational memory, task annotations, ClickUp snapshot + audit schema.
- `docs/clickup-contract.md` — rate-aware ClickUp semantic contract.
- `docs/tool-contracts.json` — side effects, write guards and idempotency keys per tool.
- `docs/profile-overrides.md` — calibrated profile assumptions from the user.
- `INTEGRATION_PLAN.md` — complete manual integration and acceptance-test runbook.
- `planner_mcp/server.py` — Google Calendar + planner memory MCP.
- `scripts/oauth_bootstrap.py` — one-time OAuth bootstrap.
- `hermes-config-snippet.yaml` — MCP registration.
- `cron-commands.sh` — ritual schedule.
- `systemd/*` — deterministic health check.
