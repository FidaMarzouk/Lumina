"""The HTML report renders from the shipped pipeline outputs and stays self-contained."""
import re

import pytest

pytest.importorskip("pandas")
pytest.importorskip("yaml")

from lumina import config
from lumina.reporting import build


@pytest.fixture(scope="module")
def page():
    return build.build()


def test_report_has_every_section_and_marks_settings_in_use(page):
    for sid in ("overview", "safety", "intent", "retrieval", "personal", "market"):
        assert f'id="{sid}"' in page
    assert f"In use: p ≥ {config.RISK_THRESHOLD:.2f}" in page
    assert f"In use: {config.MIN_SIMILARITY:.2f}" in page
    assert f"In use: {config.MEMORY_MIN_SIMILARITY:.2f}" in page
    assert page.count('<li class="finding">') == 7


def test_report_makes_no_external_requests(page):
    assert not re.search(r'(src|href)="https?://', page)
    assert "<link" not in page


def test_every_chart_has_a_table_view(page):
    assert page.count('<svg class="chart"') == page.count("<summary>Show as table</summary>")


def test_human_labels_keep_acronyms():
    assert build._human("ai_support_chat") == "AI support chat"
    assert build._human("self_guided_cbt_mood") == "Self guided CBT mood"
