"""Validated record schemas for market-intelligence data.

Every record carries provenance: where it came from (source_url), when (collected_at), and
which collection run produced it (run_id, see data/raw/<source>/<run_id>/manifest.json).
No usernames or profile data are stored: reviewer names are replaced by a salted hash.
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Provenance(BaseModel):
    source: str
    source_url: str
    collected_at: str
    run_id: str


class InAppPurchase(BaseModel):
    name: str
    price: str


class PrivacyLabel(BaseModel):
    type: str                       # e.g. DATA_LINKED_TO_YOU, DATA_NOT_LINKED_TO_YOU, DATA_NOT_COLLECTED
    categories: list[str] = Field(default_factory=list)


class FeaturedReview(BaseModel):
    """One of the ~8 reviews Apple shows on the product page. NOT a random or recent sample."""
    review_id: str
    app_id: str
    country: str
    rating: int = Field(ge=1, le=5)
    title: str
    text: str
    date: str | None
    author_hash: str
    provenance: Provenance


class SimilarApp(BaseModel):
    app_id: str
    title: str


class AppProfile(BaseModel):
    app_id: str
    country: str
    name: str
    developer: str | None
    seller: str | None
    category: str | None
    genres: list[str] = Field(default_factory=list)
    description: str
    price: float | None
    currency: str | None
    in_app_purchases: list[InAppPurchase] = Field(default_factory=list)
    rating_average: float | None
    rating_count: int | None
    rating_histogram_5_to_1: list[int] | None
    age_rating: str | None
    languages: list[str] = Field(default_factory=list)
    size: str | None
    compatibility: str | None
    current_version: str | None
    current_version_date: str | None
    release_notes: str | None
    privacy_labels: list[PrivacyLabel] = Field(default_factory=list)
    accessibility_statement: str | None
    developer_website: str | None
    privacy_policy_url: str | None
    similar_apps: list[SimilarApp] = Field(default_factory=list)
    featured_review_count: int = 0
    provenance: Provenance
