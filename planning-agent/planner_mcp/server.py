from __future__ import annotations

import base64
import hashlib
import json
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("planning-core")

# Reading user/external calendars is the google-workspace skill's job. planning-core
# holds only app.created, so this credential structurally cannot see or touch any
# calendar it did not create itself.
SCOPES = ["https://www.googleapis.com/auth/calendar.app.created"]

def expand_env_path(name: str, default: str) -> Path:
    raw = os.environ.get(name, default)
    return Path(os.path.expandvars(raw)).expanduser()

DB_PATH = expand_env_path("PLANNER_DB", "~/.local/share/planning-agent/planner.db")
TOKEN_PATH = expand_env_path("GOOGLE_TOKEN", "~/.config/planning-agent/google_token.json")
CAL_ID_FILE = expand_env_path(
    "PLANNING_CALENDAR_ID_FILE",
    "~/.config/planning-agent/planning_calendar_id",
)
CAL_NAME = os.environ.get("PLANNING_CALENDAR_NAME", "Planning Agent")
TZ = os.environ.get("PLANNER_TIMEZONE", "Europe/Moscow")
SCHEMA_PATH = expand_env_path(
    "PLANNER_SCHEMA", str(Path(__file__).resolve().parent.parent / "schema.sql")
)

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

_schema_applied = False

def db() -> sqlite3.Connection:
    global _schema_applied
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    if not _schema_applied:
        if not SCHEMA_PATH.exists():
            raise RuntimeError(
                f"schema.sql not found at {SCHEMA_PATH}. Deploy it next to planner_mcp/ "
                "or point PLANNER_SCHEMA at it."
            )
        # schema.sql is CREATE ... IF NOT EXISTS throughout, so replaying it is a no-op.
        con.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        con.commit()
        _schema_applied = True
    return con

def service():
    if not TOKEN_PATH.exists():
        raise RuntimeError(
            f"OAuth token not found: {TOKEN_PATH}. Run scripts/oauth_bootstrap.py first."
        )
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")
        os.chmod(TOKEN_PATH, 0o600)
    if not creds.valid:
        raise RuntimeError("Google credentials are invalid; re-run OAuth bootstrap.")
    return build("calendar", "v3", credentials=creds, cache_discovery=False)

def audit(
    action: str,
    target_type: str,
    target_id: str | None,
    before: Any,
    after: Any,
    reason: str,
    actor: str = "hermes",
    plan_id: str | None = None,
    reversible: bool = True,
) -> str:
    aid = str(uuid.uuid4())
    with db() as con:
        con.execute(
            """
            INSERT INTO audit_log(
              audit_id, at, actor, action, target_type, target_id,
              before_json, after_json, reason, plan_id, reversible
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                aid, now_iso(), actor, action, target_type, target_id,
                json.dumps(before, ensure_ascii=False) if before is not None else None,
                json.dumps(after, ensure_ascii=False) if after is not None else None,
                reason, plan_id, 1 if reversible else 0,
            ),
        )
    return aid

def planning_calendar_id() -> str:
    if CAL_ID_FILE.exists():
        return CAL_ID_FILE.read_text(encoding="utf-8").strip()

    s = service()
    created = s.calendars().insert(
        body={"summary": CAL_NAME, "timeZone": TZ}
    ).execute()
    cid = created["id"]
    CAL_ID_FILE.parent.mkdir(parents=True, exist_ok=True)
    CAL_ID_FILE.write_text(cid, encoding="utf-8")
    os.chmod(CAL_ID_FILE, 0o600)
    audit(
        "create",
        "calendar",
        cid,
        None,
        {"summary": CAL_NAME, "timeZone": TZ},
        "initial planning calendar creation",
        actor="system",
        reversible=False,
    )
    return cid

def deterministic_event_id(planner_key: str) -> str:
    digest = hashlib.sha256(planner_key.encode("utf-8")).digest()
    # Google Calendar event IDs allow base32hex chars (0-9, a-v).
    encoded = base64.b32hexencode(digest).decode("ascii").lower().rstrip("=")
    return "p" + encoded[:39]

def _get_event(event_id: str) -> dict[str, Any] | None:
    s = service()
    try:
        return s.events().get(
            calendarId=planning_calendar_id(), eventId=event_id
        ).execute()
    except HttpError as e:
        if e.resp.status == 404:
            return None
        raise

@mcp.tool()
def calendar_ensure_planning_calendar() -> dict[str, str]:
    """Create the dedicated Planning Agent calendar once and return its id."""
    return {"calendar_id": planning_calendar_id(), "summary": CAL_NAME}

@mcp.tool()
def calendar_list_planning_blocks(
    time_min: str,
    time_max: str,
) -> list[dict[str, Any]]:
    """
    Read blocks on the dedicated planning calendar only, with their planner_key.
    User and external calendars are read through the google-workspace skill, not here.
    Call this before an upsert so a manually moved block is not silently overwritten.
    """
    s = service()
    cid = planning_calendar_id()
    out: list[dict[str, Any]] = []
    page = None
    while True:
        res = s.events().list(
            calendarId=cid,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
            pageToken=page,
        ).execute()
        for e in res.get("items", []):
            private = e.get("extendedProperties", {}).get("private", {})
            out.append(
                {
                    "event_id": e.get("id"),
                    "status": e.get("status"),
                    "summary": e.get("summary", ""),
                    "start": e.get("start"),
                    "end": e.get("end"),
                    "planner_owned": private.get("planner_owned") == "1",
                    "planner_key": private.get("planner_key"),
                    "planner_revision": private.get("planner_revision"),
                    "clickup_task_id": private.get("clickup_task_id"),
                    "plan_id": private.get("plan_id"),
                }
            )
        page = res.get("nextPageToken")
        if not page:
            return out

@mcp.tool()
def calendar_upsert_planning_block(
    planner_key: str,
    title: str,
    start_at: str,
    end_at: str,
    reason: str,
    clickup_task_id: str | None = None,
    plan_id: str | None = None,
    revision: int = 1,
    description: str | None = None,
) -> dict[str, Any]:
    """
    Idempotently create/update an event ONLY on the dedicated planning calendar.
    planner_key must be stable for the logical block across retries.
    """
    s = service()
    cid = planning_calendar_id()
    eid = deterministic_event_id(planner_key)
    current = _get_event(eid)

    private = {
        "planner_owned": "1",
        "planner_key": planner_key[:1024],
        "planner_revision": str(revision),
    }
    if clickup_task_id:
        private["clickup_task_id"] = clickup_task_id[:1024]
    if plan_id:
        private["plan_id"] = plan_id[:1024]

    body = {
        "id": eid,
        "summary": title,
        "description": description or "",
        "start": {"dateTime": start_at, "timeZone": TZ},
        "end": {"dateTime": end_at, "timeZone": TZ},
        "extendedProperties": {"private": private},
    }

    if current is None:
        created = s.events().insert(calendarId=cid, body=body).execute()
        audit("create", "calendar_event", eid, None, body, reason, plan_id=plan_id)
        return {"action": "created", "event_id": eid, "htmlLink": created.get("htmlLink")}

    props = current.get("extendedProperties", {}).get("private", {})
    if props.get("planner_owned") != "1":
        raise RuntimeError("Refusing to overwrite an event not owned by Planning Agent.")

    # Preserve fields we do not own by reading the event first, then updating the full event.
    updated_body = dict(current)
    updated_body.update({
        "summary": title,
        "description": description or current.get("description", ""),
        "start": {"dateTime": start_at, "timeZone": TZ},
        "end": {"dateTime": end_at, "timeZone": TZ},
        "extendedProperties": {"private": private},
    })
    updated_body.pop("etag", None)
    updated = s.events().update(
        calendarId=cid,
        eventId=eid,
        body=updated_body,
    ).execute()
    audit("update", "calendar_event", eid, current, updated_body, reason, plan_id=plan_id)
    return {"action": "updated", "event_id": eid, "htmlLink": updated.get("htmlLink")}

@mcp.tool()
def calendar_delete_planning_block(
    planner_key: str,
    reason: str,
    plan_id: str | None = None,
) -> dict[str, Any]:
    """Delete only a Planning-Agent-owned block. External events are unreachable here."""
    s = service()
    cid = planning_calendar_id()
    eid = deterministic_event_id(planner_key)
    current = _get_event(eid)
    if current is None:
        return {"action": "noop", "event_id": eid}
    props = current.get("extendedProperties", {}).get("private", {})
    if props.get("planner_owned") != "1":
        raise RuntimeError("Refusing to delete an event not owned by Planning Agent.")
    s.events().delete(calendarId=cid, eventId=eid).execute()
    audit("delete", "calendar_event", eid, current, None, reason, plan_id=plan_id)
    return {"action": "deleted", "event_id": eid}

@mcp.tool()
def planner_record_task_observation(
    task_id: str,
    observed_at: str,
    area: str | None = None,
    task_type: str | None = None,
    estimate_min: int | None = None,
    actual_min: int | None = None,
    interruption_min: int = 0,
    completed: bool = False,
    energy_before: int | None = None,
    energy_after: int | None = None,
    cognitive_load: int | None = None,
    start_local: str | None = None,
    end_local: str | None = None,
    notes: str | None = None,
) -> dict[str, Any]:
    """Append a raw observation. Raw observations are never overwritten."""
    weekday = None
    if start_local:
        try:
            weekday = datetime.fromisoformat(start_local).weekday()
        except ValueError:
            pass
    with db() as con:
        cur = con.execute(
            """
            INSERT INTO task_observation(
              task_id, observed_at, area, task_type, estimate_min, actual_min,
              interruption_min, completed, energy_before, energy_after,
              cognitive_load, start_local, end_local, weekday, notes
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                task_id, observed_at, area, task_type, estimate_min, actual_min,
                interruption_min, 1 if completed else 0, energy_before, energy_after,
                cognitive_load, start_local, end_local, weekday, notes,
            ),
        )
        oid = cur.lastrowid
    audit(
        "append", "task_observation", str(oid), None,
        {"task_id": task_id, "actual_min": actual_min, "estimate_min": estimate_min},
        "task execution observation",
        reversible=False,
    )
    return {"observation_id": oid}

@mcp.tool()
def planner_get_duration_stats(
    area: str | None = None,
    task_type: str | None = None,
    limit: int = 200,
) -> dict[str, Any]:
    """Return raw duration ratios for planner-side robust estimation."""
    query = """
      SELECT task_id, area, task_type, estimate_min, actual_min, observed_at
      FROM task_observation
      WHERE estimate_min IS NOT NULL AND actual_min IS NOT NULL
        AND estimate_min > 0 AND actual_min > 0
    """
    params: list[Any] = []
    if area:
        query += " AND area = ?"
        params.append(area)
    if task_type:
        query += " AND task_type = ?"
        params.append(task_type)
    query += " ORDER BY observed_at DESC LIMIT ?"
    params.append(max(1, min(limit, 1000)))
    with db() as con:
        rows = [dict(r) for r in con.execute(query, params).fetchall()]
    for r in rows:
        r["ratio"] = r["actual_min"] / r["estimate_min"]
    return {"samples": rows}

@mcp.tool()
def planner_upsert_task_annotation(
    task_id: str,
    life_area: str | None = None,
    task_type: str | None = None,
    cognitive_load: int | None = None,
    energy_requirement: str | None = None,
    splittable: bool | None = None,
    minimum_block_min: int | None = None,
    hard_deadline_at: str | None = None,
    hard_deadline_source: str | None = None,
    soft_target_at: str | None = None,
    soft_target_reason: str | None = None,
    confidence: float = 0.5,
    annotation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Store planner-only task semantics without mutating ClickUp."""
    if cognitive_load is not None and cognitive_load not in (1, 2, 3):
        raise ValueError("cognitive_load must be 1, 2, or 3")
    confidence = max(0.0, min(float(confidence), 1.0))
    current = planner_get_task_annotations([task_id])
    before = current[0] if current else None
    with db() as con:
        con.execute(
            """
            INSERT INTO task_annotation(
              task_id, life_area, task_type, cognitive_load, energy_requirement,
              splittable, minimum_block_min, hard_deadline_at, hard_deadline_source,
              soft_target_at, soft_target_reason, annotation_json, confidence, updated_at
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(task_id) DO UPDATE SET
              life_area=COALESCE(excluded.life_area, task_annotation.life_area),
              task_type=COALESCE(excluded.task_type, task_annotation.task_type),
              cognitive_load=COALESCE(excluded.cognitive_load, task_annotation.cognitive_load),
              energy_requirement=COALESCE(excluded.energy_requirement, task_annotation.energy_requirement),
              splittable=COALESCE(excluded.splittable, task_annotation.splittable),
              minimum_block_min=COALESCE(excluded.minimum_block_min, task_annotation.minimum_block_min),
              hard_deadline_at=COALESCE(excluded.hard_deadline_at, task_annotation.hard_deadline_at),
              hard_deadline_source=COALESCE(excluded.hard_deadline_source, task_annotation.hard_deadline_source),
              soft_target_at=COALESCE(excluded.soft_target_at, task_annotation.soft_target_at),
              soft_target_reason=COALESCE(excluded.soft_target_reason, task_annotation.soft_target_reason),
              annotation_json=COALESCE(excluded.annotation_json, task_annotation.annotation_json),
              confidence=excluded.confidence,
              updated_at=excluded.updated_at
            """,
            (
                task_id, life_area, task_type, cognitive_load, energy_requirement,
                None if splittable is None else (1 if splittable else 0),
                minimum_block_min, hard_deadline_at, hard_deadline_source,
                soft_target_at, soft_target_reason,
                json.dumps(annotation, ensure_ascii=False) if annotation is not None else None,
                confidence, now_iso(),
            ),
        )
    after_rows = planner_get_task_annotations([task_id])
    after = after_rows[0] if after_rows else None
    audit("upsert", "task_annotation", task_id, before, after,
          "planner-local task semantics; ClickUp unchanged")
    return after or {"task_id": task_id}

@mcp.tool()
def planner_get_task_annotations(task_ids: list[str]) -> list[dict[str, Any]]:
    """Read planner-local task annotations for ClickUp task ids."""
    if not task_ids:
        return []
    unique = list(dict.fromkeys(task_ids))[:500]
    placeholders = ",".join("?" for _ in unique)
    with db() as con:
        rows = con.execute(
            f"SELECT * FROM task_annotation WHERE task_id IN ({placeholders})",
            unique,
        ).fetchall()
    result = []
    for row in rows:
        item = dict(row)
        if item.get("annotation_json"):
            try:
                item["annotation"] = json.loads(item["annotation_json"])
            except json.JSONDecodeError:
                item["annotation"] = None
        item.pop("annotation_json", None)
        if item.get("splittable") is not None:
            item["splittable"] = bool(item["splittable"])
        result.append(item)
    return result

@mcp.tool()
def planner_cache_clickup_tasks(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    """Cache a batched ClickUp read locally. Does not call or mutate ClickUp."""
    fetched = now_iso()
    cached = 0
    with db() as con:
        for task in tasks[:5000]:
            task_id = str(task.get("id") or "").strip()
            if not task_id:
                continue
            cached += 1
            con.execute(
                """
                INSERT INTO clickup_task_snapshot(task_id, payload_json, fetched_at)
                VALUES(?,?,?)
                ON CONFLICT(task_id) DO UPDATE SET
                  payload_json=excluded.payload_json,
                  fetched_at=excluded.fetched_at
                """,
                (task_id, json.dumps(task, ensure_ascii=False), fetched),
            )
    return {"cached": cached, "received": len(tasks), "fetched_at": fetched}

@mcp.tool()
def planner_get_cached_clickup_tasks(task_ids: list[str] | None = None) -> dict[str, Any]:
    """Read the local ClickUp snapshot and its age. No remote ClickUp call is made."""
    with db() as con:
        if task_ids:
            unique = list(dict.fromkeys(task_ids))[:500]
            placeholders = ",".join("?" for _ in unique)
            rows = con.execute(
                f"SELECT * FROM clickup_task_snapshot WHERE task_id IN ({placeholders})",
                unique,
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM clickup_task_snapshot ORDER BY fetched_at DESC LIMIT 5000"
            ).fetchall()
    tasks = []
    newest = None
    for row in rows:
        try:
            tasks.append(json.loads(row["payload_json"]))
        except json.JSONDecodeError:
            continue
        if newest is None or row["fetched_at"] > newest:
            newest = row["fetched_at"]
    return {"tasks": tasks, "newest_fetched_at": newest, "count": len(tasks)}

@mcp.tool()
def planner_audit_recent(limit: int = 50) -> list[dict[str, Any]]:
    """Read the recent audit trail."""
    with db() as con:
        rows = con.execute(
            "SELECT * FROM audit_log ORDER BY at DESC LIMIT ?",
            (max(1, min(limit, 500)),),
        ).fetchall()
    return [dict(r) for r in rows]

@mcp.tool()
def planner_health() -> dict[str, Any]:
    """Read-only health check for token, DB and planning calendar."""
    status: dict[str, Any] = {
        "db": False,
        "google_token": TOKEN_PATH.exists(),
        "planning_calendar": False,
        "timezone": TZ,
    }
    try:
        with db() as con:
            con.execute("SELECT 1").fetchone()
        status["db"] = True
    except Exception as e:
        status["db_error"] = str(e)

    try:
        if not CAL_ID_FILE.exists():
            raise RuntimeError(
                "planning calendar not created yet; "
                "call calendar_ensure_planning_calendar once"
            )
        cid = CAL_ID_FILE.read_text(encoding="utf-8").strip()
        service().calendars().get(calendarId=cid).execute()
        status["planning_calendar"] = True
        status["planning_calendar_id"] = cid
    except Exception as e:
        status["calendar_error"] = str(e)

    status["ok"] = all([
        status["db"],
        status["google_token"],
        status["planning_calendar"],
    ])
    return status

if __name__ == "__main__":
    mcp.run(transport="stdio")
