# Calibrated profile assumptions — v2

This file captures only facts explicitly supplied by the user plus derived planner rules.
It is not an analytics log.

## Work
- Work hours are flexible.
- Earliest usual work call: 13:00 Europe/Moscow.
- Latest usual work call ends around 19:00-20:00 Europe/Moscow.
- These are a fragmentation prior, not a blocked work interval. Real Google Calendar
  events are authoritative.
- Prefer high-cognitive focus before the first call when feasible; between calls use a
  deep-work block only when the actual free gap is at least 90 minutes.

## ClickUp
- Current useful task metadata: time estimate, native priority, tags.
- Planner-specific metadata belongs in local SQLite, not Custom Fields.
- Any mutation of ClickUp requires an explicit confirmation for the exact proposed diff.
- Personal-project target dates are soft targets and remain local by default.
- Master's deadlines are hard commitments. Prefer storing confirmed hard deadlines as
  native ClickUp due dates; if not yet written there, mirror them locally with provenance
  and keep surfacing the missing source-of-truth until confirmed.

## Sleep
- Typical bedtime window: 00:00-02:00 local.
- Typical wake window: 07:00-10:00 local.
- Without an explicit wake commitment, capacity before 10:00 is contingent and MUST NOT
  be required to make a hard deadline feasible.

## Sport
- Trainer session: Thursday 11:00 local; represent it as a user-owned recurring Calendar
  event so the planning agent cannot move it.
- Football: Saturday evening; likewise user-owned recurring Calendar event.
- Additional self-directed training is flexible. Schedule existing sport tasks, but do
  not create new training commitments without confirmation.
