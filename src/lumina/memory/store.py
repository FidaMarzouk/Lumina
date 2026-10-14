"""Personal data store — accounts, sessions and the derived memory behind insights and journeys.

SQLite (stdlib), one file at config.USER_DB_PATH (data/user/, not in git).  A connection is opened
per operation, so the store is safe to use from the API threads and the background extraction pool.

What is stored (derived data only — never the messages themselves):
    users            account, password hash (scrypt), memory switch, consent time
    auth_tokens      SHA-256 of each login token (the token itself is never stored)
    sessions         one row per conversation: mode (open | guided) and journey step
    turn_signals     per user turn: intent, emotion, sentiment, pain points, risk level and the
                     paraphrased CBT elements (situation / thoughts / feelings / behaviours)
    episodes         per finished session: LLM-written summary, themes, embedding
    insights         session reflections and weekly insights, with their evidence and feedback
    journey_progress the user's position in each journey
    next_steps       the step waiting for the user's next visit
    jar_items        "things that helped": noticed by Lumina (suggested) or kept by the person (kept)

Deleting a user removes every row that belongs to them (foreign keys with ON DELETE CASCADE).
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id             TEXT PRIMARY KEY,
    email          TEXT NOT NULL UNIQUE,
    display_name   TEXT NOT NULL DEFAULT '',
    password_hash  TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    memory_enabled INTEGER NOT NULL DEFAULT 0,
    consent_at     TEXT
);
CREATE TABLE IF NOT EXISTS auth_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    mode       TEXT NOT NULL,
    journey_id TEXT,
    step_id    TEXT,
    started_at TEXT NOT NULL,
    ended_at   TEXT
);
CREATE TABLE IF NOT EXISTS turn_signals (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id      TEXT NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    user_id         TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ts              TEXT NOT NULL,
    intent          TEXT,
    emotion         TEXT,
    sentiment       TEXT,
    pain_points     TEXT NOT NULL DEFAULT '[]',
    macro           TEXT,
    risk_level      TEXT NOT NULL DEFAULT 'none',
    elements        TEXT,
    insight_offered INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS turn_signals_user_ts ON turn_signals(user_id, ts);
CREATE TABLE IF NOT EXISTS episodes (
    session_id TEXT PRIMARY KEY REFERENCES sessions(id) ON DELETE CASCADE,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    summary    TEXT NOT NULL,
    themes     TEXT NOT NULL DEFAULT '[]',
    elements   TEXT NOT NULL DEFAULT '{}',
    emotions   TEXT NOT NULL DEFAULT '[]',
    had_crisis INTEGER NOT NULL DEFAULT 0,
    embedding  BLOB
);
CREATE INDEX IF NOT EXISTS episodes_user_created ON episodes(user_id, created_at);
CREATE TABLE IF NOT EXISTS insights (
    id           TEXT PRIMARY KEY,
    user_id      TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind         TEXT NOT NULL,
    session_id   TEXT,
    period_start TEXT,
    period_end   TEXT,
    created_at   TEXT NOT NULL,
    text         TEXT NOT NULL,
    evidence     TEXT NOT NULL DEFAULT '{}',
    feedback     TEXT
);
CREATE INDEX IF NOT EXISTS insights_user_created ON insights(user_id, created_at);
CREATE TABLE IF NOT EXISTS journey_progress (
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    journey_id TEXT NOT NULL,
    step_index INTEGER NOT NULL DEFAULT 0,
    status     TEXT NOT NULL,
    started_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (user_id, journey_id)
);
CREATE TABLE IF NOT EXISTS next_steps (
    user_id    TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    step       TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS jar_items (
    id         TEXT PRIMARY KEY,
    user_id    TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    session_id TEXT,
    text       TEXT NOT NULL,
    status     TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS jar_user_created ON jar_items(user_id, created_at);
"""


_JSON_COLUMNS = {"pain_points", "elements", "themes", "emotions", "evidence", "step"}


class EmailTaken(ValueError):
    """An account with this email already exists."""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    """One timestamp format everywhere, so ISO strings compare in time order."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds")


def parse_iso(text: str) -> datetime:
    return datetime.fromisoformat(text)


def _row(row: sqlite3.Row | None) -> dict | None:
    if row is None:
        return None
    out = dict(row)
    for key in _JSON_COLUMNS & out.keys():
        if out[key] is not None:
            out[key] = json.loads(out[key])
    if out.get("embedding") is not None:
        out["embedding"] = np.frombuffer(out["embedding"], dtype=np.float32)
    return out


def _dump(value) -> str:
    return json.dumps(value, ensure_ascii=False)


class Store:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.execute("PRAGMA journal_mode=WAL")
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=10)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    # ── users ──────────────────────────────────────────────────────────────
    def create_user(self, email: str, password_hash: str, display_name: str = "", consent: bool = False,
                    now: datetime | None = None) -> dict:
        now = iso(now or utcnow())
        uid = uuid.uuid4().hex
        try:
            with self._conn() as c:
                c.execute("INSERT INTO users (id, email, display_name, password_hash, created_at, memory_enabled, "
                          "consent_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                          (uid, email, display_name, password_hash, now, int(consent), now if consent else None))
        except sqlite3.IntegrityError as exc:
            raise EmailTaken(email) from exc
        return self.get_user(uid)

    def get_user(self, user_id: str) -> dict | None:
        with self._conn() as c:
            return _row(c.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone())

    def get_user_by_email(self, email: str) -> dict | None:
        with self._conn() as c:
            return _row(c.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone())

    def update_user(self, user_id: str, *, display_name: str | None = None, memory_enabled: bool | None = None,
                    now: datetime | None = None) -> dict | None:
        with self._conn() as c:
            if display_name is not None:
                c.execute("UPDATE users SET display_name = ? WHERE id = ?", (display_name, user_id))
            if memory_enabled is not None:
                # Turning memory on is consent; the first consent time is kept.
                c.execute("UPDATE users SET memory_enabled = ?, consent_at = COALESCE(consent_at, ?) WHERE id = ?",
                          (int(memory_enabled), iso(now or utcnow()) if memory_enabled else None, user_id))
        return self.get_user(user_id)

    def delete_user(self, user_id: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM users WHERE id = ?", (user_id,))

    # ── login tokens ───────────────────────────────────────────────────────
    def add_token(self, token_hash: str, user_id: str, expires_at: datetime, now: datetime | None = None) -> None:
        with self._conn() as c:
            c.execute("INSERT INTO auth_tokens VALUES (?, ?, ?, ?)",
                      (token_hash, user_id, iso(now or utcnow()), iso(expires_at)))

    def get_token(self, token_hash: str) -> dict | None:
        with self._conn() as c:
            return _row(c.execute("SELECT * FROM auth_tokens WHERE token_hash = ?", (token_hash,)).fetchone())

    def delete_token(self, token_hash: str) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM auth_tokens WHERE token_hash = ?", (token_hash,))

    def purge_expired_tokens(self, now: datetime | None = None) -> None:
        with self._conn() as c:
            c.execute("DELETE FROM auth_tokens WHERE expires_at < ?", (iso(now or utcnow()),))

    # ── sessions ───────────────────────────────────────────────────────────
    def create_session(self, user_id: str, mode: str, journey_id: str | None = None, step_id: str | None = None,
                       now: datetime | None = None) -> dict:
        sid = uuid.uuid4().hex
        with self._conn() as c:
            c.execute("INSERT INTO sessions (id, user_id, mode, journey_id, step_id, started_at) VALUES (?, ?, ?, ?, ?, ?)",
                      (sid, user_id, mode, journey_id, step_id, iso(now or utcnow())))
        return self.get_session(sid, user_id)

    def get_session(self, session_id: str, user_id: str) -> dict | None:
        """The session, only if it belongs to `user_id`."""
        with self._conn() as c:
            return _row(c.execute("SELECT * FROM sessions WHERE id = ? AND user_id = ?",
                                  (session_id, user_id)).fetchone())

    def end_session(self, session_id: str, now: datetime | None = None) -> None:
        with self._conn() as c:
            c.execute("UPDATE sessions SET ended_at = COALESCE(ended_at, ?) WHERE id = ?",
                      (iso(now or utcnow()), session_id))

    def user_sessions(self, user_id: str) -> list[dict]:
        with self._conn() as c:
            return [_row(r) for r in c.execute("SELECT * FROM sessions WHERE user_id = ? ORDER BY started_at",
                                               (user_id,))]

    # ── turn signals ───────────────────────────────────────────────────────
    def add_turn(self, session_id: str, user_id: str, *, intent: str | None, emotion: str | None,
                 sentiment: str | None, pain_points: list[str], macro: str | None, risk_level: str,
                 elements: dict | None = None, now: datetime | None = None) -> int:
        with self._conn() as c:
            cur = c.execute(
                "INSERT INTO turn_signals (session_id, user_id, ts, intent, emotion, sentiment, pain_points, macro, "
                "risk_level, elements) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (session_id, user_id, iso(now or utcnow()), intent, emotion, sentiment, _dump(pain_points), macro,
                 risk_level, None if elements is None else _dump(elements)))
            return int(cur.lastrowid)

    def set_turn_elements(self, turn_id: int, elements: dict) -> None:
        with self._conn() as c:
            c.execute("UPDATE turn_signals SET elements = ? WHERE id = ?", (_dump(elements), turn_id))

    def mark_insight_offered(self, turn_id: int) -> None:
        with self._conn() as c:
            c.execute("UPDATE turn_signals SET insight_offered = 1 WHERE id = ?", (turn_id,))

    def session_turns(self, session_id: str) -> list[dict]:
        with self._conn() as c:
            return [_row(r) for r in c.execute("SELECT * FROM turn_signals WHERE session_id = ? ORDER BY id",
                                               (session_id,))]

    def user_turns(self, user_id: str, since: datetime | None = None, until: datetime | None = None) -> list[dict]:
        q, args = "SELECT * FROM turn_signals WHERE user_id = ?", [user_id]
        if since is not None:
            q, args = q + " AND ts >= ?", args + [iso(since)]
        if until is not None:
            q, args = q + " AND ts < ?", args + [iso(until)]
        with self._conn() as c:
            return [_row(r) for r in c.execute(q + " ORDER BY ts, id", args)]

    # ── episodes ───────────────────────────────────────────────────────────
    def save_episode(self, session_id: str, user_id: str, *, summary: str, themes: list[str], elements: dict,
                     emotions: list[str], had_crisis: bool, embedding: np.ndarray | None,
                     now: datetime | None = None) -> None:
        blob = None if embedding is None else np.asarray(embedding, dtype=np.float32).tobytes()
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO episodes VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (session_id, user_id, iso(now or utcnow()), summary, _dump(themes), _dump(elements),
                       _dump(emotions), int(had_crisis), blob))

    def user_episodes(self, user_id: str, since: datetime | None = None, until: datetime | None = None) -> list[dict]:
        q, args = "SELECT * FROM episodes WHERE user_id = ?", [user_id]
        if since is not None:
            q, args = q + " AND created_at >= ?", args + [iso(since)]
        if until is not None:
            q, args = q + " AND created_at < ?", args + [iso(until)]
        with self._conn() as c:
            return [_row(r) for r in c.execute(q + " ORDER BY created_at", args)]

    # ── insights ───────────────────────────────────────────────────────────
    def add_insight(self, user_id: str, kind: str, text: str, evidence: dict, *, session_id: str | None = None,
                    period_start: datetime | None = None, period_end: datetime | None = None,
                    now: datetime | None = None) -> dict:
        iid = uuid.uuid4().hex
        with self._conn() as c:
            c.execute("INSERT INTO insights (id, user_id, kind, session_id, period_start, period_end, created_at, "
                      "text, evidence) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                      (iid, user_id, kind, session_id, period_start and iso(period_start),
                       period_end and iso(period_end), iso(now or utcnow()), text, _dump(evidence)))
            return _row(c.execute("SELECT * FROM insights WHERE id = ?", (iid,)).fetchone())

    def list_insights(self, user_id: str, kind: str | None = None, limit: int = 20) -> list[dict]:
        q, args = "SELECT * FROM insights WHERE user_id = ?", [user_id]
        if kind:
            q, args = q + " AND kind = ?", args + [kind]
        with self._conn() as c:
            return [_row(r) for r in c.execute(q + " ORDER BY created_at DESC LIMIT ?", args + [limit])]

    def set_feedback(self, insight_id: str, user_id: str, value: str) -> bool:
        with self._conn() as c:
            cur = c.execute("UPDATE insights SET feedback = ? WHERE id = ? AND user_id = ?", (value, insight_id, user_id))
            return cur.rowcount == 1

    # ── things that helped ─────────────────────────────────────────────────
    def add_jar_item(self, user_id: str, text: str, status: str, session_id: str | None = None,
                     now: datetime | None = None) -> dict:
        """Adds `text` unless the jar already holds it (case-insensitive); keeping a suggestion promotes it."""
        with self._conn() as c:
            existing = _row(c.execute("SELECT * FROM jar_items WHERE user_id = ? AND lower(text) = lower(?)",
                                      (user_id, text)).fetchone())
            if existing:
                if status == "kept" and existing["status"] != "kept":
                    c.execute("UPDATE jar_items SET status = 'kept' WHERE id = ?", (existing["id"],))
                    existing["status"] = "kept"
                return existing
            iid = uuid.uuid4().hex
            c.execute("INSERT INTO jar_items VALUES (?, ?, ?, ?, ?, ?)",
                      (iid, user_id, session_id, text, status, iso(now or utcnow())))
            return _row(c.execute("SELECT * FROM jar_items WHERE id = ?", (iid,)).fetchone())

    def jar_items(self, user_id: str) -> list[dict]:
        with self._conn() as c:
            return [_row(r) for r in c.execute("SELECT * FROM jar_items WHERE user_id = ? ORDER BY created_at",
                                               (user_id,))]

    def keep_jar_item(self, item_id: str, user_id: str) -> bool:
        with self._conn() as c:
            cur = c.execute("UPDATE jar_items SET status = 'kept' WHERE id = ? AND user_id = ?", (item_id, user_id))
            return cur.rowcount == 1

    def delete_jar_item(self, item_id: str, user_id: str) -> bool:
        with self._conn() as c:
            cur = c.execute("DELETE FROM jar_items WHERE id = ? AND user_id = ?", (item_id, user_id))
            return cur.rowcount == 1

    # ── journeys ───────────────────────────────────────────────────────────
    def journey_progress(self, user_id: str) -> dict[str, dict]:
        with self._conn() as c:
            return {r["journey_id"]: _row(r) for r in
                    c.execute("SELECT * FROM journey_progress WHERE user_id = ?", (user_id,))}

    def set_progress(self, user_id: str, journey_id: str, step_index: int, status: str,
                     now: datetime | None = None) -> None:
        now = iso(now or utcnow())
        with self._conn() as c:
            c.execute("INSERT INTO journey_progress VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(user_id, journey_id) "
                      "DO UPDATE SET step_index = excluded.step_index, status = excluded.status, "
                      "updated_at = excluded.updated_at",
                      (user_id, journey_id, step_index, status, now, now))

    def set_next_step(self, user_id: str, step: dict, now: datetime | None = None) -> None:
        with self._conn() as c:
            c.execute("INSERT OR REPLACE INTO next_steps VALUES (?, ?, ?)", (user_id, iso(now or utcnow()), _dump(step)))

    def get_next_step(self, user_id: str) -> dict | None:
        with self._conn() as c:
            row = _row(c.execute("SELECT * FROM next_steps WHERE user_id = ?", (user_id,)).fetchone())
        return row["step"] if row else None

    # ── export ─────────────────────────────────────────────────────────────
    def export_user(self, user_id: str) -> dict:
        """Everything stored about the user (minus the password hash and login tokens)."""
        user = self.get_user(user_id)
        if user is None:
            return {}
        user.pop("password_hash", None)
        episodes = self.user_episodes(user_id)
        for e in episodes:
            e.pop("embedding", None)
        with self._conn() as c:
            progress = [_row(r) for r in c.execute("SELECT * FROM journey_progress WHERE user_id = ?", (user_id,))]
        return {"account": user, "sessions": self.user_sessions(user_id), "turn_signals": self.user_turns(user_id),
                "episodes": episodes, "insights": self.list_insights(user_id, limit=10_000),
                "journey_progress": progress, "next_step": self.get_next_step(user_id),
                "jar": self.jar_items(user_id)}


# ── default instance ─────────────────────────────────────────────────────────
_DEFAULT: Store | None = None
_LOCK = threading.Lock()


def default_store() -> Store:
    global _DEFAULT
    if _DEFAULT is None:
        with _LOCK:
            if _DEFAULT is None:
                from ..config import USER_DB_PATH
                _DEFAULT = Store(USER_DB_PATH)
    return _DEFAULT


def set_default_store(store: Store | None) -> None:
    """Point the app at another database (tests, the demo seeder)."""
    global _DEFAULT
    _DEFAULT = store
