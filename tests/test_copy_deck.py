"""Copy-deck regression contracts, separate from the active outcome-claims guard."""
import json
import re
from pathlib import Path

import pytest

from surveycoach.demo_export import SITE_DATA, SAMPLES
from surveycoach.rubric import load_rubric
from surveycoach.server.present import enrich
from surveycoach.server.report import summary_packet

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("phrase", [
    r"fix before launch", r"worth a look", r"['\"](?-i:Polish)['\"]|\} polish", r"keep mine",
    r"check again", r"share for sign-off", r"ready to launch", r"almost ready",
    r"\bRound [{$]", r"\b(?:first|previous) round\b",
    r"min on the captured path", r"scope-limited review · not launch approval",
])
def test_authored_copy_has_no_retired_deck_phrases(phrase):
    sources = [*(ROOT / "site").glob("*.html"),
               *(p for p in (ROOT / "site").glob("*.js") if p.name != "data.js"),
               ROOT / "surveycoach/server/report.py"]
    matches = [str(p.relative_to(ROOT)) for p in sources
               if re.search(phrase, p.read_text(), re.I)]
    assert not matches, matches


@pytest.mark.parametrize("download", [False, True])
def test_summaries_use_version_and_stakeholder_language(download):
    detail = {"title": "Synthetic", "version": 2, "review": None,
              "snapshot": {"title": "Synthetic", "pages": []}, "decisions": {},
              "round_changes": {"compared_to_round": 1, "fixed": [], "still": [],
                                "new": [], "uncertain": []}}
    html = summary_packet(detail, download=download)
    assert "Version 2" in html and "Share with stakeholders" in html
    assert "not launch approval" in html
    assert "No readiness judgement has been made" in html
    assert "Round " not in html
    if not download:
        assert "Compared with Version 1" in html
        assert "Keep as is acknowledges a risk" in html


def test_demo_entry_description_uses_member_perspective_copy():
    html = (ROOT / "site/index.html").read_text()
    assert "See your survey through your members' eyes." in html


def test_every_committed_demo_entry_has_current_canonical_projection():
    data = json.loads(SITE_DATA.read_text().removeprefix("window.SURVEYCOACH_DEMO = ").rstrip(";\n"))
    assert [entry["id"] for entry in data["surveys"]] == [sample_id for sample_id, _ in SAMPLES]
    for entry in data["surveys"]:
        assert entry["snapshot"]["source_url"].startswith("fixture://")
        canonical = enrich(entry, load_rubric())
        for key in ("screens", "plan", "overview"):
            assert entry[key] == canonical[key]
        assert len(entry["screens"]) == len(entry["snapshot"]["pages"])
        assert len(entry["overview"]["signals"]) == 6
        assert entry["plan"]["counts"]
        assert "AI step has not run" not in entry["blurb"]
        assert "Ready to launch" not in entry["blurb"]
