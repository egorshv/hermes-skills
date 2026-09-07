# university-ops — Hermes skill

A Hermes-native orchestration skill for:

**authenticated student portal → ClickUp University space → Google Drive artifact reconciliation**

## Install

Copy this directory to:

```text
~/.hermes/skills/productivity/university-ops/
```

Then start a new Hermes session (or reset the current one) and verify:

```bash
hermes skills list
```

Configure the skill:

```bash
hermes skills config university-ops
```

At minimum set:
- student portal assignments URL;
- ClickUp University Space ID;
- fallback ClickUp List ID.

For Drive reconciliation, configure the bundled `google-workspace` skill and set the Drive root folder ID.

## Browser authentication

Recommended for a student portal that uses your normal browser login:

```yaml
browser:
  use_real_profile: true
```

This allows Hermes to use a managed snapshot of your existing Chromium-family browser profile rather than storing portal credentials inside the skill.

If the Hermes host is not already using your university timezone, also set the top-level timezone because Hermes cron uses the configured/server-local timezone:

```yaml
timezone: "Europe/Oslo"
```

## ClickUp MCP

Recommended server name:

```yaml
mcp_servers:
  clickup:
    # your existing ClickUp MCP transport/config
```

Hermes derives MCP tool names/toolsets from the server name. If your server is named differently, set `university.clickup_server_name` accordingly.

For scheduled runs, use `hermes tools` and make sure the **cron** platform exposes `browser`, `terminal`, and your ClickUp MCP toolset (for a server named `clickup`, normally `mcp-clickup`).

## First run

Use dry-run before writes:

```text
/university-ops dry-run
```

Then:

```text
/university-ops sync
```

Run the acceptance tests in `references/acceptance-tests.md` before enabling the scheduled blueprint.

## Automation

The skill includes a blueprint suggestion for twice-daily sync at 07:00 and 18:00. Installing a blueprint does not silently schedule it; accept the suggestion in Hermes before it becomes a cron job.

For a quieter schedule, edit the `metadata.hermes.blueprint.schedule` field before enabling it.
