"""Turn traces — what happened in each conversational turn, for debugging and evaluation.  Never any text.

One row per turn in its own SQLite file (config.TRACE_DB_PATH, next to the accounts database but separate
from it): stage timings, the safety outcome, the reply path and the guard's reasons.  There is no user id,
session id or message text, so a trace cannot be linked back to a person or a conversation; deleting an
account has nothing to remove here.  Rows older than TRACE_RETENTION_DAYS are purged.

    sw = Stopwatch()
    with sw.stage("safety"): ...
    record({...fields}, sw)                    # never raises: tracing must not break a reply

    python -m lumina.observability [--days 7]  # summary of recent turns → eval/reports/turn_traces.json
    python eval/runners/latency.py             # scripted messages through the real stack → the same file
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import statistics
import threading
import time
from collections import Counter
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .config import PROJECT_ROOT, TRACE_DB_PATH, TRACE_RETENTION_DAYS, TRACES_ENABLED

log = logging.getLogger(__name__)

STAGES = ("safety", "analysis", "memory", "prompt", "llm", "output_guard", "total")

# Every column is a label, a number or a list of labels.  Adding a free-text column would break the
# promise above: `test_traces_hold_no_text` checks the schema.
_SCHEMA = """
CREATE TABLE IF NOT EXISTS turn_traces (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    ts              TEXT NOT NULL,
    signed_in       INTEGER NOT NULL,
    path            TEXT NOT NULL,
    risk_level      TEXT NOT NULL,
    crisis_subtype  TEXT NOT NULL,
    injection       INTEGER NOT NULL,
    language        TEXT,
    reader          TEXT,
    intent          TEXT,
    intent_category TEXT,
    rag_hits        INTEGER,
    replaced        INTEGER NOT NULL DEFAULT 0,
    guard_reasons   TEXT NOT NULL DEFAULT '[]',
    degraded        TEXT NOT NULL DEFAULT '[]',
    tokens_in       INTEGER,
    tokens_out      INTEGER,
    ms              TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS turn_traces_ts ON turn_traces(ts);
"""
_COLUMNS = ("signed_in", "path", "risk_level", "crisis_subtype", "injection", "language", "reader", "intent",
            "intent_category", "rag_hits", "replaced", "guard_reasons", "degraded", "tokens_in", "tokens_out")
_JSON = {"guard_reasons", "degraded", "ms"}


class Stopwatch:
    """Milliseconds per named stage; a stage entered twice adds up."""

    def __init__(self):
        self.ms: dict[str, float] = {}
        self._start = time.perf_counter()

    @contextmanager
    def stage(self, name: str):
        t = time.perf_counter()
        try:
            yield
        finally:
            self.ms[name] = self.ms.get(name, 0.0) + (time.perf_counter() - t) * 1000

    def finish(self) -> dict[str, float]:
        self.ms["total"] = (time.perf_counter() - self._start) * 1000
        return {k: round(v, 1) for k, v in self.ms.items()}


class TraceStore:
    def __init__(self, path: Path | str):
        self.path = Path(path)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as c:
            c.executescript(_SCHEMA)

    @contextmanager
    def _conn(self):
        conn = sqlite3.connect(self.path, timeout=5)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def add(self, fields: dict, ms: dict, now: datetime | None = None) -> None:
        row = {k: fields.get(k) for k in _COLUMNS}
        for k in ("signed_in", "injection", "replaced"):
            row[k] = int(bool(row[k]))
        for k in ("guard_reasons", "degraded"):
            row[k] = json.dumps(sorted(row[k] or []))
        ts = (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")
        with self._conn() as c:
            c.execute(f"INSERT INTO turn_traces (ts, {', '.join(_COLUMNS)}, ms) VALUES (?, {', '.join('?' * len(_COLUMNS))}, ?)",
                      (ts, *row.values(), json.dumps(ms)))

    def rows(self, since: datetime | None = None) -> list[dict]:
        q, args = "SELECT * FROM turn_traces", []
        if since is not None:
            q, args = q + " WHERE ts >= ?", [since.isoformat(timespec="seconds")]
        with self._conn() as c:
            out = [dict(r) for r in c.execute(q + " ORDER BY id", args)]
        for r in out:
            for k in _JSON:
                r[k] = json.loads(r[k])
        return out

    def purge(self, older_than_days: int = TRACE_RETENTION_DAYS, now: datetime | None = None) -> int:
        cutoff = (now or datetime.now(timezone.utc)) - timedelta(days=older_than_days)
        with self._conn() as c:
            return c.execute("DELETE FROM turn_traces WHERE ts < ?", (cutoff.isoformat(timespec="seconds"),)).rowcount


_DEFAULT: TraceStore | None = None
_LOCK = threading.Lock()


def default_traces() -> TraceStore | None:
    global _DEFAULT
    if not TRACES_ENABLED:
        return None
    if _DEFAULT is None:
        with _LOCK:
            if _DEFAULT is None:
                _DEFAULT = TraceStore(TRACE_DB_PATH)
    return _DEFAULT


def set_default_traces(store: TraceStore | None) -> None:
    """Point tracing at another database (tests, the latency runner)."""
    global _DEFAULT
    _DEFAULT = store


def record(fields: dict, ms: dict) -> None:
    """Store one turn's trace.  Never raises."""
    try:
        store = default_traces()
        if store is not None:
            store.add(fields, ms)
    except Exception as exc:
        log.warning("Turn trace not stored: %s", type(exc).__name__)


# ── summary ───────────────────────────────────────────────────────────────────
def _pctl(values: list[float], q: float) -> float:
    s = sorted(values)
    return round(s[min(len(s) - 1, int(round(q * (len(s) - 1))))], 1)


def summarise(rows: list[dict]) -> dict:
    """Aggregates only: counts, shares and latency percentiles per stage."""
    n = len(rows)
    if not n:
        return {"n_turns": 0}
    latency = {}
    for stage in STAGES:
        vals = [r["ms"][stage] for r in rows if stage in r["ms"]]
        if vals:
            latency[stage] = {"n": len(vals), "p50": _pctl(vals, 0.5), "p90": _pctl(vals, 0.9), "max": round(max(vals), 1)}
    llm_rows = [r for r in rows if r["path"] == "llm"]
    tokens = [r for r in llm_rows if r["tokens_in"] is not None]
    count = lambda key: dict(Counter(r[key] for r in rows).most_common())     # noqa: E731
    return {
        "n_turns": n,
        "first": rows[0]["ts"], "last": rows[-1]["ts"],
        "latency_ms": latency,
        "path": count("path"),
        "risk_level": count("risk_level"),
        "crisis_subtype": dict(Counter(r["crisis_subtype"] for r in rows if r["crisis_subtype"] != "none")),
        "language": count("language"),
        "intent": dict(Counter(r["intent"] for r in rows if r["intent"]).most_common()),
        "replaced_by_output_guard": round(sum(r["replaced"] for r in llm_rows) / len(llm_rows), 3) if llm_rows else None,
        "guard_reasons": dict(Counter(g for r in rows for g in r["guard_reasons"]).most_common()),
        "turns_with_a_degraded_layer": round(sum(bool(r["degraded"]) for r in rows) / n, 3),
        "degraded_layers": dict(Counter(d for r in rows for d in r["degraded"]).most_common()),
        "tokens_per_reply": ({"in_p50": statistics.median(r["tokens_in"] for r in tokens),
                              "out_p50": statistics.median(r["tokens_out"] for r in tokens)} if tokens else None),
        "signed_in_share": round(sum(r["signed_in"] for r in rows) / n, 3),
    }


def write_summary(rows: list[dict], source: str, out: Path | None = None, extra: dict | None = None) -> dict:
    from .config import LLM_MODEL, LLM_PROVIDER
    report = {"source": source, "llm": f"{LLM_PROVIDER}:{LLM_MODEL}", **(extra or {}), **summarise(rows)}
    out = out or PROJECT_ROOT / "eval" / "reports" / "turn_traces.json"
    out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarise recent turn traces into eval/reports/turn_traces.json")
    parser.add_argument("--days", type=int, default=7)
    args = parser.parse_args()
    store = default_traces()
    if store is None:
        raise SystemExit("Tracing is off (TRACES_ENABLED=0).")
    rows = store.rows(since=datetime.now(timezone.utc) - timedelta(days=args.days))
    report = write_summary(rows, f"live traces, last {args.days} days")
    print(json.dumps({k: report[k] for k in ("n_turns", "latency_ms") if k in report}, indent=2))


if __name__ == "__main__":
    main()
