#!/usr/bin/env python3
"""
Normalize one or many university assignment records.

Stdlib-only by design.

Examples:
  python normalize_assignment.py --json '{"course":"ABC101","title":"Essay","due_raw":"2026-10-03 23:59","url":"https://portal/x/123"}' --timezone Europe/Oslo
  python normalize_assignment.py --input assignments.jsonl --timezone Europe/Oslo
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import unicodedata
from datetime import datetime, time
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo


SPACE_RE = re.compile(r"\s+")
DATE_PATTERNS = [
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%d.%m.%Y %H:%M",
    "%d.%m.%Y",
    "%d/%m/%Y %H:%M",
    "%d/%m/%Y",
]


def clean_text(value: Any) -> str:
    if value is None:
        return ""
    s = unicodedata.normalize("NFKC", str(value)).strip()
    return SPACE_RE.sub(" ", s)


def clean_multiline(value: Any) -> str:
    if value is None:
        return ""
    lines = [SPACE_RE.sub(" ", unicodedata.normalize("NFKC", x).strip()) for x in str(value).splitlines()]
    return "\n".join(x for x in lines if x)


def normalize_url(value: Any) -> str:
    s = clean_text(value)
    if not s:
        return ""
    try:
        p = urlsplit(s)
        # Fragment is usually UI-only and unstable for identity.
        return urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), p.query, ""))
    except Exception:
        return s


def slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).casefold()
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-")[:120]


def parse_due(raw: str, tz_name: str, default_due_time: str) -> datetime | None:
    raw = clean_text(raw)
    if not raw:
        return None

    # ISO-8601 first.
    iso = raw.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo(tz_name))
        return dt
    except ValueError:
        pass

    default_h, default_m = map(int, default_due_time.split(":"))
    for fmt in DATE_PATTERNS:
        try:
            dt = datetime.strptime(raw, fmt)
        except ValueError:
            continue
        if "%H" not in fmt:
            dt = datetime.combine(dt.date(), time(default_h, default_m))
        return dt.replace(tzinfo=ZoneInfo(tz_name))

    raise ValueError(f"Unrecognized deadline format: {raw!r}")


def identity(record: dict[str, Any], due_at: str) -> tuple[str, str]:
    source_id = clean_text(record.get("source_id"))
    url = normalize_url(record.get("url"))
    course = clean_text(record.get("course"))
    title = clean_text(record.get("title"))

    if source_id:
        return f"portal:{source_id}", "source_id"
    if url:
        digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:24]
        return f"portal-url:{digest}", "url"

    basis = "|".join([slug(course), slug(title), due_at[:10] if due_at else "no-date"])
    digest = hashlib.sha256(basis.encode("utf-8")).hexdigest()[:24]
    return f"portal-composite:{digest}", "composite"


def normalize(record: dict[str, Any], tz_name: str, default_due_time: str) -> dict[str, Any]:
    due = parse_due(record.get("due_raw", ""), tz_name, default_due_time)
    due_at = due.isoformat() if due else ""
    source_key, identity_basis = identity(record, due_at)

    attachments = []
    for item in record.get("attachments") or []:
        if not isinstance(item, dict):
            continue
        attachments.append({
            "name": clean_text(item.get("name")),
            "url": normalize_url(item.get("url")),
        })

    out = {
        "course": clean_text(record.get("course")),
        "title": clean_text(record.get("title")),
        "due_at": due_at,
        "due_epoch_ms": int(due.timestamp() * 1000) if due else None,
        "url": normalize_url(record.get("url")),
        "description": clean_multiline(record.get("description")),
        "kind": clean_text(record.get("kind")) or "other",
        "portal_status": clean_text(record.get("portal_status")) or "unknown",
        "attachments": attachments,
        "source_key": source_key,
        "identity_basis": identity_basis,
    }

    source_hash_payload = {
        k: out[k]
        for k in [
            "course", "title", "due_at", "url", "description",
            "kind", "portal_status", "attachments"
        ]
    }
    canonical = json.dumps(source_hash_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    out["source_hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return out


def iter_records(args: argparse.Namespace):
    if args.json:
        yield json.loads(args.json)
        return
    if args.input:
        path = Path(args.input)
        if path.suffix.lower() == ".json":
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                yield from data
            else:
                yield data
        else:
            for line in path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    yield json.loads(line)
        return
    for line in sys.stdin:
        if line.strip():
            yield json.loads(line)


def main() -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group()
    src.add_argument("--json", help="Single JSON object")
    src.add_argument("--input", help="JSON or JSONL file")
    ap.add_argument("--timezone", default="Europe/Oslo")
    ap.add_argument("--default-due-time", default="23:59")
    ap.add_argument("--pretty", action="store_true")
    args = ap.parse_args()

    # Validate timezone and default time up front.
    ZoneInfo(args.timezone)
    datetime.strptime(args.default_due_time, "%H:%M")

    records = [normalize(r, args.timezone, args.default_due_time) for r in iter_records(args)]
    if args.json or (args.input and Path(args.input).suffix.lower() == ".json" and len(records) == 1):
        payload: Any = records[0] if len(records) == 1 else records
        print(json.dumps(payload, ensure_ascii=False, indent=2 if args.pretty else None))
    else:
        for record in records:
            print(json.dumps(record, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
