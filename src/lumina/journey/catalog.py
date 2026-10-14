"""Journey catalogue — structured, evidence-based programmes loaded from configs/journeys/*.yaml."""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

import yaml

from ..config import JOURNEYS_DIR


@dataclass(frozen=True)
class Step:
    id: str
    title: str
    goal: str
    guidance: str
    opener: str


@dataclass(frozen=True)
class Journey:
    id: str
    order: int
    title: str
    summary: str
    approach: str
    themes: tuple[str, ...]
    steps: tuple[Step, ...]

    def step_index(self, step_id: str) -> int | None:
        return next((i for i, s in enumerate(self.steps) if s.id == step_id), None)

    def public(self) -> dict:
        return {"id": self.id, "title": self.title, "summary": self.summary, "approach": self.approach,
                "steps": [{"id": s.id, "title": s.title} for s in self.steps]}


def _load(path: Path) -> Journey:
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    steps = tuple(Step(**{k: str(s[k]).strip() for k in ("id", "title", "goal", "guidance", "opener")})
                  for s in data["steps"])
    if not steps:
        raise ValueError(f"{path.name}: a journey needs at least one step")
    return Journey(id=data["id"], order=int(data.get("order", 99)), title=data["title"], summary=data["summary"],
                   approach=data["approach"], themes=tuple(data.get("themes", [])), steps=steps)


@lru_cache(maxsize=4)
def load_catalog(directory: Path = JOURNEYS_DIR) -> dict[str, Journey]:
    journeys = sorted((_load(p) for p in sorted(Path(directory).glob("*.yaml"))), key=lambda j: (j.order, j.id))
    return {j.id: j for j in journeys}


def get(journey_id: str) -> Journey | None:
    return load_catalog().get(journey_id)
