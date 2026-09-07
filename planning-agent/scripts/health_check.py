from __future__ import annotations
import json
import os
import sqlite3
from pathlib import Path

db_path = Path(os.path.expandvars(
    os.environ.get("PLANNER_DB", "~/.local/share/planning-agent/planner.db")
)).expanduser()
token_path = Path(os.path.expandvars(
    os.environ.get("GOOGLE_TOKEN", "~/.config/planning-agent/google_token.json")
)).expanduser()
cal_id_path = Path(os.path.expandvars(
    os.environ.get(
        "PLANNING_CALENDAR_ID_FILE",
        "~/.config/planning-agent/planning_calendar_id",
    )
)).expanduser()

result = {
    "db_exists": db_path.exists(),
    "token_exists": token_path.exists(),
    "calendar_id_exists": cal_id_path.exists(),
}

if db_path.exists():
    try:
        with sqlite3.connect(db_path) as con:
            con.execute("PRAGMA quick_check").fetchone()
        result["db_ok"] = True
    except Exception as e:
        result["db_ok"] = False
        result["db_error"] = str(e)

print(json.dumps(result, ensure_ascii=False))
if not all([
    result.get("db_exists"),
    result.get("token_exists"),
    result.get("calendar_id_exists"),
    result.get("db_ok", False),
]):
    raise SystemExit(1)
