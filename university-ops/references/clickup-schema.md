# Recommended ClickUp University schema

The skill works without custom fields by storing identity inside the managed description block, but custom fields improve searchability.

## Required operational structure

- Space: **University**
- One List per course is preferred, but not mandatory.
- Configure `university.clickup_default_list_id` as a safe fallback.

## Recommended custom fields

| Field | Type | Owner | Purpose |
|---|---|---|---|
| Portal Source Key | Text | Hermes | Stable dedupe key |
| Portal URL | URL | Hermes | Open assignment |
| Course | Dropdown/Text | Hermes | Course identity |
| Assignment Type | Dropdown | Hermes | assignment/exam/project/etc. |
| Portal Status | Dropdown/Text | Hermes | submitted/graded/late/etc. |
| Drive Artifact URL | URL | Hermes | Completed-work link |
| Last Portal Sync | Date/Text | Hermes | Auditability |

Do not require these fields for correctness. If they do not exist, use the managed description block.

## Task field ownership

Portal/Hermes may update:
- name;
- due date (official deadline);
- managed description block;
- portal-related custom fields.

User owns:
- workflow status by default;
- priority;
- start date;
- time estimate;
- assignee;
- subtasks/dependencies;
- comments;
- all description text outside the managed block.

## Status recommendation

Keep the existing ClickUp workflow. A simple university workflow works well:

`TO DO → IN PROGRESS → READY TO SUBMIT → DONE`

Portal submission state should be metadata, not the workflow status, unless `auto_complete_on_portal_submission` is explicitly enabled.
