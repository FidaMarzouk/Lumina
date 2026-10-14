"""Day-one insight: connect the thoughts, feelings and behaviours of the current conversation.

Works on the CBT elements already extracted from earlier turns of this session (the current
turn's elements are extracted after its reply).  A reflection is offered only when the evidence
holds up, and not too often:

    ready  =  ≥ INSIGHT_MIN_TURNS turns with elements
          and a feeling plus a thought or a behaviour to link it to
          and no reflection and no crisis turn in the last INSIGHT_COOLDOWN_TURNS turns
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

from ..config import INSIGHT_COOLDOWN_TURNS, INSIGHT_MIN_TURNS


@dataclass
class Connections:
    situations: list[str] = field(default_factory=list)
    thoughts  : list[str] = field(default_factory=list)
    feelings  : list[str] = field(default_factory=list)
    behaviours: list[str] = field(default_factory=list)
    turns_with_elements: int = 0
    chain: dict | None = None          # {situation?, thought?, feeling, behaviour?} — the link to reflect
    ready: bool = False

    def as_prompt_dict(self) -> dict:
        return {"situations": self.situations[-3:], "thoughts": self.thoughts[-3:], "feelings": self.feelings[:3],
                "behaviours": self.behaviours[-3:], "offer": self.ready}


def _unique(items: list[str]) -> list[str]:
    seen, out = set(), []
    for item in items:
        if item.lower() not in seen:
            seen.add(item.lower())
            out.append(item)
    return out


def build(turns: list[dict]) -> Connections:
    """`turns` = store.session_turns(session_id), oldest first."""
    situations, thoughts, behaviours = [], [], []
    feeling_counts: Counter = Counter()
    last_seen: dict[str, int] = {}
    n = 0
    for i, turn in enumerate(turns):
        e = turn.get("elements") or {}
        if not any(e.get(k) for k in ("situation", "thoughts", "feelings", "behaviours")):
            continue
        n += 1
        if e.get("situation"):
            situations.append(e["situation"])
        thoughts += e.get("thoughts", [])
        behaviours += e.get("behaviours", [])
        for f in e.get("feelings", []):
            feeling_counts[f] += 1
            last_seen[f] = i

    # Most frequent feeling first; ties go to the most recent.
    feelings = sorted(feeling_counts, key=lambda f: (-feeling_counts[f], -last_seen[f]))
    conn = Connections(_unique(situations), _unique(thoughts), feelings, _unique(behaviours), n)

    if feelings and (conn.thoughts or conn.behaviours):
        chain = {"situation": conn.situations[-1] if conn.situations else None,
                 "thought": conn.thoughts[-1] if conn.thoughts else None,
                 "feeling": feelings[0],
                 "behaviour": conn.behaviours[-1] if conn.behaviours else None}
        conn.chain = {k: v for k, v in chain.items() if v}

    recent = turns[-INSIGHT_COOLDOWN_TURNS:]
    quiet = not any(t.get("insight_offered") or t.get("risk_level") == "crisis" for t in recent)
    conn.ready = conn.chain is not None and n >= INSIGHT_MIN_TURNS and quiet
    return conn
