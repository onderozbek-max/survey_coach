"""D1: question screens expose their stimulus copy via timing's own subtraction, never a second one."""
import pytest

from surveycoach import timing
from surveycoach.rubric import load_rubric
from surveycoach.server.present import enrich
from surveycoach.snapshot import Media, Option, Page, Question, SurveySnapshot
from surveycoach.timing import estimate, reading_basis

# Invented copy only.
BODY = ("Here is a new idea from Acme.\nAcme Widget Tray\nImagine a tray of widgets that snap together "
        "in seconds, ready for any weeknight dinner without any mess at all.")
QUESTION = "How likely are you to buy the Acme Widget Tray?"
OPTIONS = ["Definitely would buy", "Probably would buy", "Would not buy"]


def stimulus_page(body=BODY, nav="\nNext", **extra):
    q = Question(id="q1", text=QUESTION, kind="single_choice",
                 options=[Option(id=f"o{i}", label=label) for i, label in enumerate(OPTIONS)])
    raw = body + "\n" + QUESTION + "\n" + "\n".join(OPTIONS) + nav
    return Page(id="p1", position=1, kind="question", questions=[q], text=raw, **extra)


def words(text):
    return len(text.split())


def test_question_page_stimulus_is_the_body_without_question_options_or_navigation():
    assert stimulus_page().stimulus_text == BODY


def test_stimulus_is_derived_not_stored():
    page = stimulus_page()
    assert "stimulus_text" not in page.model_dump()
    assert Page.model_validate(page.model_dump()).stimulus_text == BODY


def test_info_pages_and_bare_question_pages_have_no_stimulus():
    assert Page(id="i", position=0, kind="info", text="Welcome to our study.").stimulus_text == ""
    assert stimulus_page(body="").stimulus_text == ""


def test_stimulus_reuses_the_timing_subtraction_instead_of_a_second_routine(monkeypatch):
    original = timing._unrepresented_text
    calls = []

    def marked(text, represented, *, whole_lines=False):
        calls.append(text)
        remaining, unmatched = original(text, represented, whole_lines=whole_lines)
        return remaining.replace("Imagine", "REUSED"), unmatched
    monkeypatch.setattr(timing, "_unrepresented_text", marked)
    assert "REUSED a tray of widgets" in stimulus_page().stimulus_text
    assert calls


def test_vendor_optional_label_is_not_stimulus():
    page = stimulus_page(nav="\nOptional\nNext")
    assert page.stimulus_text == BODY


def test_timing_is_identical_to_before_the_split():
    info = Page(id="p0", position=0, kind="info", text="Welcome to our study. Thanks for helping.")
    result = estimate(SurveySnapshot(title="Acme Widget Tray", pages=[info, stimulus_page()]))
    # Golden values captured from the pre-split implementation.
    assert result.total_seconds == 24.3
    assert [p.seconds for p in result.pages] == [3.6, 20.7]


def test_stimulus_words_plus_structured_words_equal_the_counted_reading_words():
    page = stimulus_page()
    counted = sum(words(f["text"]) for f in reading_basis(page)["fields"])
    structured = words(QUESTION) + sum(words(o) for o in OPTIONS)
    navigation = 1  # timing counts the "Next" label; the preview never shows it
    assert counted == words(page.stimulus_text) + structured + navigation


def test_enriched_payload_serves_recomputed_stimulus_with_the_pages_own_media():
    page = stimulus_page(media=[Media(element_id="hero", alt="Acme Widget Tray")])
    snapshot = SurveySnapshot(title="Acme", pages=[page])
    stored = snapshot.model_dump(mode="json")
    stored["pages"][0]["stimulus_text"] = "stale injected value"
    payload = enrich({"snapshot": stored, "review": None}, load_rubric())["snapshot"]["pages"][0]
    assert payload["stimulus_text"] == BODY
    assert payload["media"][0]["element_id"] == "hero"


@pytest.mark.parametrize("page", [Page(id="i", position=0, kind="info", text="Welcome."), stimulus_page(body="")])
def test_enriched_payload_has_empty_stimulus_when_there_is_none(page):
    payload = enrich({"snapshot": SurveySnapshot(title="t", pages=[page]).model_dump(mode="json"),
                      "review": None}, load_rubric())["snapshot"]["pages"][0]
    assert payload["stimulus_text"] == ""
