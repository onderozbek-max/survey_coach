"""D6: a survey's name is the user's, then the definition's, then its URL slug, then its stimulus heading."""
import pytest

from surveycoach.reader.models import Coverage, ReadResult
from surveycoach.reader.naming import (SLUG_PREFIXES, first_stimulus_heading, humanize_slug,
                                       is_generic_title, presentable_title, resolve_title)
from surveycoach.snapshot import Option, Page, Question, SurveySnapshot

BASE = "https://app.redjade.net/take/"


@pytest.mark.parametrize("title", ["Surveys", "survey", " SURVEYS ", ""])
def test_generic_or_blank_titles_count_as_missing(title):
    assert is_generic_title(title)


def test_real_titles_are_not_generic():
    assert not is_generic_title("Quesadilla Tray")
    assert not is_generic_title("Customer Surveys Insights")


@pytest.mark.parametrize("url,expected", [
    (BASE + "InsightsHMSQuesadillaTray", "Quesadilla Tray"),
    (BASE + "HMSQuesadillaTray?token=abcDEF123", "Quesadilla Tray"),
    (BASE + "quesadilla-tray", "Quesadilla Tray"),
    (BASE + "quesadilla_tray#section", "Quesadilla Tray"),
    (BASE + "InsightsHMSQuesadillaTray/3f9a2c1e5b7d4a60", "Quesadilla Tray"),
    (BASE + "QuesadillaInsights", "Quesadilla Insights"),   # only leading prefixes are stripped
    (BASE + "BBQRibsTray", "BBQ Ribs Tray"),
])
def test_slug_is_humanized(url, expected):
    assert humanize_slug(url) == expected


@pytest.mark.parametrize("url", [
    "", "not a url", "https://app.redjade.net", "https://app.redjade.net/",
    BASE + "InsightsHMS",                     # nothing left after the prefixes
    BASE + "3f9a2c1e5b7d4a60e1c2d3f4a5b6c7d8",  # token
    BASE + "123456",
    BASE + "k3J9xQ2mP7",                      # mixed letters and digits: token-like
    BASE + "KjHgFdSaPoIuYtReWq",              # random letters: not words
    BASE + "survey", BASE + "preview",
])
def test_unusable_slugs_are_missing(url):
    assert humanize_slug(url) is None


def test_prefix_list_starts_with_insights_and_hms():
    assert SLUG_PREFIXES[:2] == ("Insights", "HMS")


def stimulus_snapshot(*bodies, title="Surveys", url=""):
    pages = []
    for index, body in enumerate(bodies):
        q = Question(id=f"q{index}", text="How likely are you to buy it?", kind="single_choice",
                     options=[Option(id=f"o{index}", label="Yes")])
        pages.append(Page(id=f"p{index}", position=index, kind="question", questions=[q],
                          text=body + "\nHow likely are you to buy it?\nYes\nNext"))
    return SurveySnapshot(title=title, source_url=url, pages=pages)


def test_first_short_unpunctuated_stimulus_line_is_the_heading():
    snapshot = stimulus_snapshot("Alright, here is our idea…\nAcme Widget Tray\nImagine a tray of widgets.")
    assert first_stimulus_heading(snapshot) == "Acme Widget Tray"


def test_no_heading_when_stimulus_is_only_sentences():
    assert first_stimulus_heading(stimulus_snapshot("Imagine a tray of widgets.\nIt snaps together.")) is None
    assert first_stimulus_heading(stimulus_snapshot("")) is None


def test_definition_title_beats_slug_and_heading():
    snapshot = stimulus_snapshot("Acme Widget Tray\nImagine it.", url=BASE + "InsightsHMSQuesadillaTray")
    assert resolve_title(snapshot, definition_title="Spring concept study") == "Spring concept study"


def test_generic_definition_title_falls_to_slug_then_heading_then_document_title():
    with_slug = stimulus_snapshot("Acme Widget Tray\nImagine it.", url=BASE + "InsightsHMSQuesadillaTray")
    assert resolve_title(with_slug, definition_title="Surveys") == "Quesadilla Tray"
    no_slug = stimulus_snapshot("Acme Widget Tray\nImagine it.", url=BASE + "preview")
    assert resolve_title(no_slug, definition_title="") == "Acme Widget Tray"
    bare = stimulus_snapshot("Imagine it.", url=BASE + "preview")
    assert resolve_title(bare, document_title="Synthetic study") == "Synthetic study"


def test_generic_document_title_is_only_a_last_resort():
    bare = stimulus_snapshot("Imagine it.", url=BASE + "preview")
    assert resolve_title(bare, document_title="Surveys") == "Surveys"
    assert resolve_title(bare) == ""


def test_presentable_title_projects_legacy_generic_titles_without_changing_them():
    legacy = stimulus_snapshot("Imagine it.", title="Surveys", url=BASE + "InsightsHMSQuesadillaTray")
    assert presentable_title(legacy) == "Quesadilla Tray"
    assert legacy.title == "Surveys"
    assert presentable_title(stimulus_snapshot("Imagine it.", title="My own study", url=BASE + "x-y")) == "My own study"
    assert presentable_title(stimulus_snapshot("Imagine it.", title="Surveys")) == "Surveys"


def test_definition_title_survives_apply_definition_and_generic_one_is_replaced(tmp_path):
    from surveycoach.reader.definition import adapt_definition, apply_definition

    def applied(title):
        parsed = adapt_definition({"title": title, "data": {"pages": [{"id": "p", "questions": [
            {"cid": "q", "text": {"en_US": "Why?"}, "question_type": "textarea"}]}]}},
            source_url=BASE + "InsightsHMSQuesadillaTray")
        result = ReadResult(snapshot=SurveySnapshot(title="", pages=[]), coverage=Coverage(), capture_dir=tmp_path)
        apply_definition(result, parsed)
        return resolve_title(result.snapshot, definition_title=result.snapshot.title)
    assert applied("Spring concept study") == "Spring concept study"
    assert applied("Surveys") == "Quesadilla Tray"


def test_flattened_answer_labels_are_never_a_heading():
    q = Question(id="q", text="Pick one", kind="single_choice",
                 options=[Option(id="a", label="Yes"), Option(id="b", label="No")])
    page = Page(id="p", position=0, kind="question", questions=[q], text="Pick one\nYesNo\nNext")
    assert first_stimulus_heading(SurveySnapshot(title="t", pages=[page])) is None
