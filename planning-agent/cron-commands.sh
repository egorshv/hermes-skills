#!/usr/bin/env bash
set -euo pipefail

# Europe/Moscow cron schedule. All planner policy times use Europe/Moscow.
# The evening run does the expensive ClickUp refresh. Morning and risk scans prefer the
# cached snapshot to preserve the Free Forever MCP call budget.

hermes cron create "15 22 * * *" --skill planning-agent \
  "Evening planning ritual. Refresh ClickUp with the smallest practical number of batched calls and cache the normalized snapshot. Read Google Calendar for tomorrow and the next 7 days. Treat work as flexible; actual meetings are fixed, while 13:00-20:00 Europe/Moscow is only a fragmentation prior. If tomorrow's wake time is unknown, do not require any pre-10:00 Europe/Moscow capacity for deadline feasibility. Build and commit agent-owned blocks when no material ambiguity remains. For master's work, distinguish hard deadlines from personal-project soft targets. Ask at most one question, only if its answer materially changes tomorrow. Never mutate ClickUp without an exact explicit confirmation."

hermes cron create "5 10 * * *" --skill planning-agent \
  "Morning ritual. Read fresh Calendar state. Reuse the cached ClickUp snapshot unless it is stale or there is evidence task state changed materially; preserve ClickUp MCP budget. Reconcile overnight Calendar changes, repair only agent-owned future blocks, and send the compact final plan. Do not infer that the user woke before 10:00 unless they explicitly said so."

hermes cron create "30 16 * * *" --skill planning-agent \
  "Risk scan. Use current Calendar plus cached ClickUp state by default. Refresh ClickUp only when stale state could change a deadline-risk decision. Message only for a newly at-risk hard deadline, a fixed-event conflict, or a replan moving more than 90 minutes. Otherwise stay silent."

hermes cron create "30 19 * * 0" --skill planning-agent \
  "Weekly review. Use cached/task history, Calendar and planner observations for the last 7 days. Report estimate error, deadline feasibility, plan churn, focus completion, six-area balance, training placement, and the single biggest recurring disruption. Propose only one process experiment. Never mutate ClickUp without confirmation."

hermes cron create "0 19 1 * *" --skill planning-agent \
  "Monthly review. Compare the last 4-6 weeks. Rebuild duration calibration and productive-window hypotheses using robust statistics and decay, review false alerts and manual overrides, then propose at most three policy changes. Ask before changing autonomy boundaries, hard-deadline semantics, or protected recovery floors."
