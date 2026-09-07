# University assignment data contract

This is the canonical intermediate representation used by `university-ops`.

## Raw portal record

Capture as much as the portal exposes:

```json
{
  "source_id": "immutable portal assignment id if available",
  "course": "Course code/name",
  "title": "Assignment title",
  "due_raw": "Portal deadline exactly as shown",
  "url": "Canonical assignment URL",
  "description": "Plain-text assignment brief",
  "kind": "assignment|exam|quiz|project|presentation|reading|other",
  "portal_status": "open|submitted|graded|missing|late|unknown",
  "attachments": [
    {"name": "brief.pdf", "url": "https://..."}
  ]
}
```

Minimum record for safe creation:
- `course`
- `title`
- one of `source_id` or `url`
- deadline if the portal provides one

If both source ID and URL are absent, creation is allowed only in an interactive dry-run first because deduplication is weaker.

## Normalized record

`normalize_assignment.py` returns:

```json
{
  "course": "...",
  "title": "...",
  "due_at": "2026-10-03T23:59:00+02:00",
  "due_epoch_ms": 1791064740000,
  "url": "...",
  "description": "...",
  "kind": "assignment",
  "portal_status": "open",
  "attachments": [],
  "source_key": "portal:<id-or-hash>",
  "source_hash": "<sha256>",
  "identity_basis": "source_id|url|composite"
}
```

## Ownership

Portal-owned normalized fields:
- course
- title
- due_at / due_epoch_ms
- url
- description
- kind
- portal_status
- attachments
- source_hash

Stable identity:
- source_key

ClickUp-owned fields never included in source_hash:
- ClickUp status
- priority
- start date
- estimates
- assignee
- comments
- subtasks
- dependencies
- manual notes

Drive-owned:
- drive_file_id
- drive_url
- drive_modified_time
