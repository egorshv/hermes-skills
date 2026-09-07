#!/usr/bin/env bash
set -euo pipefail

# Europe/Moscow cron schedule. All planner policy times use Europe/Moscow.
# The evening run does the expensive ClickUp refresh. Morning and risk scans prefer the
# cached snapshot to preserve the Free Forever MCP call budget.
# User-facing communication must be in Russian.
# Fixed commitments are always read from: primary, Work, Study, Sport, Routine, Personal.

hermes cron create "15 22 * * *" --skill planning-agent \
  "Вечерний ритуал планирования. Общайся с пользователем только на русском. Обнови ClickUp минимальным практичным числом батчевых вызовов и закэшируй нормализованный snapshot. Прочитай внешние обязательства на завтра и следующие 7 дней через google-workspace по календарям primary, Work, Study, Sport, Routine, Personal; собственные план-блоки читай через planning_core calendar_list_planning_blocks. Treat work as flexible; actual meetings are fixed, while 13:00-20:00 Europe/Moscow is only a fragmentation prior. If tomorrow's wake time is unknown, do not require any pre-10:00 Europe/Moscow capacity for deadline feasibility. Build and commit agent-owned blocks when no material ambiguity remains. For master's work, distinguish hard deadlines from personal-project soft targets. Ask at most one question, only if its answer materially changes tomorrow. Never mutate ClickUp without an exact explicit confirmation."

hermes cron create "5 10 * * *" --skill planning-agent \
  "Утренний ритуал. Общайся с пользователем только на русском. Прочитай свежий Calendar state через google-workspace по календарям primary, Work, Study, Sport, Routine, Personal; собственные блоки — через planning_core. Reuse the cached ClickUp snapshot unless it is stale or there is evidence task state changed materially; preserve ClickUp MCP budget. Reconcile overnight Calendar changes, repair only agent-owned future blocks, and send the compact final plan. Treat any planner block whose time no longer matches what you committed as a user override and keep the user's time. Never write a Calendar event through google-workspace. Do not infer that the user woke before 10:00 unless they explicitly said so."

hermes cron create "30 16 * * *" --skill planning-agent \
  "Risk scan. Общайся с пользователем только на русском. Use current Calendar: google-workspace для external commitments по календарям primary, Work, Study, Sport, Routine, Personal; planning_core для собственных блоков. Use cached ClickUp state by default. Refresh ClickUp only when stale state could change a deadline-risk decision. Message only for a newly at-risk hard deadline, a fixed-event conflict, or a replan moving more than 90 minutes. Otherwise respond exactly [SILENT]."

hermes cron create "30 19 * * 0" --skill planning-agent \
  "Weekly review. Общайся с пользователем только на русском. Use cached/task history, google-workspace Calendar reads по календарям primary, Work, Study, Sport, Routine, Personal and planner observations for the last 7 days. Report estimate error, deadline feasibility, plan churn, focus completion, six-area balance, training placement, and the single biggest recurring disruption. Propose only one process experiment. Never mutate ClickUp without confirmation."

hermes cron create "0 19 1 * *" --skill planning-agent \
  "Monthly review. Общайся с пользователем только на русском. Compare the last 4-6 weeks. Rebuild duration calibration and productive-window hypotheses using robust statistics and decay, review false alerts and manual overrides, then propose at most three policy changes. Ask before changing autonomy boundaries, hard-deadline semantics, or protected recovery floors."
