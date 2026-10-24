import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from secrets import token_urlsafe


@contextmanager
def connect(path: str) -> Iterator[sqlite3.Connection]:
    db = sqlite3.connect(path, timeout=30)
    db.row_factory = sqlite3.Row
    db.execute("PRAGMA foreign_keys = ON")
    try:
        with db:
            yield db
    finally:
        db.close()


def initialize(path: str) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with connect(path) as db:
        db.execute("PRAGMA journal_mode = WAL")
        db.executescript("""
            CREATE TABLE IF NOT EXISTS recommendations (
                id TEXT PRIMARY KEY, created_at TEXT NOT NULL, payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS bot_sessions (
                session_key TEXT PRIMARY KEY, updated_at TEXT NOT NULL, payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS inbox (
                message_id TEXT PRIMARY KEY, reply TEXT NOT NULL, sent INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS subscriptions (
                session_key TEXT PRIMARY KEY, phone TEXT NOT NULL,
                latitude REAL NOT NULL, longitude REAL NOT NULL,
                consent_at TEXT NOT NULL, last_alert_date TEXT
            );
            CREATE TABLE IF NOT EXISTS village_soil (
                village_key TEXT PRIMARY KEY,
                block_name TEXT NOT NULL,
                village_name TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                payload TEXT NOT NULL
            );
        """)


def save_report(db: sqlite3.Connection, report: dict) -> dict:
    report["id"] = token_urlsafe(24)
    report["created_at"] = datetime.now(timezone.utc).isoformat()
    db.execute(
        "INSERT INTO recommendations VALUES (?, ?, ?)",
        (report["id"], report["created_at"], json.dumps(report, ensure_ascii=False)),
    )
    return report


def get_report(db: sqlite3.Connection, report_id: str) -> dict | None:
    row = db.execute("SELECT payload FROM recommendations WHERE id = ?", (report_id,)).fetchone()
    return json.loads(row["payload"]) if row else None


def normalize_village_key(block: str, village: str) -> str:
    return f"{block.strip().lower()}::{village.strip().lower()}"


def save_village_soil(db: sqlite3.Connection, record: dict) -> dict:
    now = datetime.now(timezone.utc).isoformat()
    record["updated_at"] = now
    key = normalize_village_key(record["block"], record["village"])
    db.execute(
        "INSERT INTO village_soil VALUES (?, ?, ?, ?, ?) "
        "ON CONFLICT(village_key) DO UPDATE SET block_name=excluded.block_name, "
        "village_name=excluded.village_name, updated_at=excluded.updated_at, payload=excluded.payload",
        (key, record["block"], record["village"], now, json.dumps(record, ensure_ascii=False)),
    )
    return record


def list_village_soil(db: sqlite3.Connection) -> list[dict]:
    rows = db.execute("SELECT payload FROM village_soil ORDER BY updated_at DESC").fetchall()
    return [json.loads(r["payload"]) for r in rows]


def find_village_soil(db: sqlite3.Connection, block: str, village: str) -> dict | None:
    key = normalize_village_key(block, village)
    row = db.execute("SELECT payload FROM village_soil WHERE village_key = ?", (key,)).fetchone()
    if row:
        return json.loads(row["payload"])
    row = db.execute(
        "SELECT payload FROM village_soil WHERE lower(village_name) = ?",
        (village.strip().lower(),),
    ).fetchone()
    return json.loads(row["payload"]) if row else None
