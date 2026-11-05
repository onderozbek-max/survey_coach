"""Since last version (brief 4.6, D16): the four existing buckets, compact, never dropping 'couldn't compare'."""
import pytest

from concept_fixture import concept_survey
from surveycoach.review import run_review
from surveycoach.server.repository import Repository
from surveycoach.server.version_delta import SNIPPET_MAX, build_version_delta


def entry(headline="Reading level is high", where="Q1 · Screen 2", resolution="No longer flagged",
          old="Which of these apply?", new="Pick all that apply.", cid="3.1", fingerprint="fp1"):
    finding = {"headline": headline, "criterion_id": cid, "fingerprint": fingerprint}
    return {"prior_finding": finding, "current_finding": None, "screen_label": where,
            "old_wording": old, "new_wording": new, "resolution": resolution}


def changes(**buckets):
    base = {key: [] for key in ("fixed", "still", "new", "uncertain")}
    return {**base, **buckets, "compared_to_round": 1, "unchecked_paths": []}


def test_version_one_has_no_delta_so_the_ui_can_hide_the_comparison():
    assert build_version_delta(changes(), 1) is None
    assert build_version_delta({"fixed": [], "still": [], "new": [], "uncertain": []}, 2) is None


def test_counts_match_the_buckets_and_the_summary_uses_the_briefs_words():
    delta = build_version_delta(changes(
        fixed=[entry(fingerprint=f"f{i}") for i in range(4)], still=[entry()], uncertain=[entry(resolution="Not verified")]), 2)
    assert delta["counts"] == {"fixed": 4, "still": 1, "new": 0, "uncertain": 1}
    assert delta["summary"] == "4 fixed · 1 still open · 0 new · 1 couldn't compare"
    assert delta["from_version"] == 1 and delta["to_version"] == 2
    assert all(len(delta[key]) == delta["counts"][key] for key in delta["counts"])
    assert "no longer flagged" in delta["caveat"].lower()


def test_each_fixed_item_shows_before_and_after_from_stored_wording():
    delta = build_version_delta(changes(fixed=[entry(), entry(resolution="Fixed with your rewrite", fingerprint="f2")]), 2)
    first, second = delta["fixed"]
    assert (first["before"], first["after"]) == ("Which of these apply?", "Pick all that apply.")
    assert first["headline"] == "Reading level is high" and first["location"] == "Q1 · Screen 2"
    assert (first["by_rewrite"], second["by_rewrite"]) == (False, True)
    assert first["fingerprint"] == "fp1"


def test_snippets_are_bounded_and_missing_wording_stays_missing():
    long = entry(old="word " * 200, new=None)
    item = build_version_delta(changes(fixed=[long]), 2)["fixed"][0]
    assert len(item["before"]) <= SNIPPET_MAX and item["before"].endswith("…")
    assert item["after"] is None


def test_still_new_and_uncertain_items_are_listed_with_headline_and_location():
    new = {"prior_finding": None, "current_finding": {"headline": "Brand new", "criterion_id": "9.1", "fingerprint": "n"},
           "screen_label": "Q9 · Screen 9", "old_wording": None, "new_wording": "x", "resolution": "Newly flagged"}
    delta = build_version_delta(changes(new=[new], still=[entry()],
                                        uncertain=[entry(resolution="Not verified: changed context")]), 3)
    assert delta["new"][0]["headline"] == "Brand new" and delta["new"][0]["location"] == "Q9 · Screen 9"
    assert delta["uncertain"][0]["resolution"].startswith("Not verified")
    assert "before" not in delta["still"][0]      # only a fixed item has something to show before and after


@pytest.fixture
def repo(tmp_path):
    repository = Repository(tmp_path / "delta.db")
    yield repository
    repository.close()


def save(repo, snapshot, survey_id=None):
    created = repo.submit(snapshot, ai=False, survey_id=survey_id)
    result = run_review(snapshot)
    review = result.model_dump(mode="json", exclude={"timing"})
    review["findings"] = [f.model_dump(mode="json") | {"fingerprint": f.fingerprint} for f in result.findings]
    repo.finish(created["job_id"], {"review": review})
    return created["id"]


def test_detail_has_null_delta_on_v1_and_a_matching_delta_on_v2(repo):
    survey_id = save(repo, concept_survey())
    assert repo.detail(survey_id)["version_delta"] is None
    changed = concept_survey().model_copy(deep=True)
    changed.pages[1].questions[0].text = "How often do you make breakfast at home?"
    save(repo, changed, survey_id)
    detail = repo.detail(survey_id, 2)
    delta, buckets = detail["version_delta"], detail["round_changes"]
    assert delta["counts"] == {key: len(buckets[key]) for key in ("fixed", "still", "new", "uncertain")}
    assert sum(delta["counts"].values()) > 0
    assert repo.detail(survey_id, 1)["version_delta"] is None
