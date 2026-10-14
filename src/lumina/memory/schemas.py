"""Validated shapes for what the LLM extracts or writes before it is stored.

LLM output is untrusted: every field is trimmed, capped and type-checked here, and anything
that does not validate is dropped (the caller stores nothing rather than something malformed).
"""

from __future__ import annotations

from typing import Literal

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

# The inner-weather check-in at the start of a conversation, and how each reads in a prompt.
Weather = Literal["clear", "part", "fog", "rain", "storm"]
WEATHER_WORDS = {"clear": "clear", "part": "partly cloudy", "fog": "foggy", "rain": "rainy", "storm": "stormy"}

_ITEM_CHARS = 120
_MAX_ITEMS = 3
JAR_CHARS = 80                   # one "thing that helped"
_TITLE_CHARS = 60


def _clean_items(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    out: list[str] = []
    seen: set[str] = set()
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, str):
            continue
        text = " ".join(item.split())[:_ITEM_CHARS].strip(" .")
        if text and text.lower() not in seen:
            seen.add(text.lower())
            out.append(text)
    return out[:_MAX_ITEMS]


class CbtElements(BaseModel):
    """The CBT triangle for one message: what happened, what they thought, felt and did."""
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    situation : str | None = None
    thoughts  : list[str] = Field(default_factory=list)
    feelings  : list[str] = Field(default_factory=list)
    behaviours: list[str] = Field(default_factory=list,
                                  validation_alias=AliasChoices("behaviours", "behaviors", "actions"))
    # What the person says helped them feel better or cope; offered for their "things that helped" jar.
    helped    : list[str] = Field(default_factory=list)

    @field_validator("situation", mode="before")
    @classmethod
    def _situation(cls, v):
        if isinstance(v, list):
            v = v[0] if v else None
        if not isinstance(v, str):
            return None
        v = " ".join(v.split())[:_ITEM_CHARS].strip(" .")
        return v or None

    @field_validator("thoughts", "feelings", "behaviours", mode="before")
    @classmethod
    def _items(cls, v):
        return _clean_items(v)

    @field_validator("helped", mode="before")
    @classmethod
    def _helped(cls, v):
        return [h for h in _clean_items(v) if len(h) <= JAR_CHARS][:2]

    @field_validator("feelings", mode="after")
    @classmethod
    def _lower(cls, v):
        return [f.lower() for f in v]

    def is_empty(self) -> bool:
        return not (self.situation or self.thoughts or self.feelings or self.behaviours or self.helped)


class EpisodeDraft(BaseModel):
    """LLM-written summary of one finished session."""
    model_config = ConfigDict(extra="ignore")

    summary: str = Field(min_length=10, max_length=700)
    themes : list[str] = Field(default_factory=list)
    title  : str | None = None          # a short title for the journal page

    @field_validator("title", mode="before")
    @classmethod
    def _title(cls, v):
        if not isinstance(v, str):
            return None
        v = " ".join(v.split()).strip(" .\"'")
        return v if v and len(v) <= _TITLE_CHARS and len(v.split()) <= 8 else None

    @field_validator("summary", mode="before")
    @classmethod
    def _summary(cls, v):
        return " ".join(v.split()) if isinstance(v, str) else v

    @field_validator("themes", mode="before")
    @classmethod
    def _themes(cls, v):
        return [t.lower() for t in _clean_items(v)][:4]
