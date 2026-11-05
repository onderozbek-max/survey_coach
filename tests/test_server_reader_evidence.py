"""Reader jobs: outcome classification, capture counts and evidence bundles (synthetic, in-memory, no network)."""
import pytest
from fastapi.testclient import TestClient

from surveycoach.reader.definition import adapt_definition, apply_definition
from surveycoach.reader.models import Capture, Coverage, ReadResult
from surveycoach.server import create_app
from surveycoach.snapshot import Page, SurveySnapshot
from tests.builders import intro, page, question, survey, thank_you

URL = "https://app.redjade.net/synthetic-audit"


@pytest.fixture
def app():
    return create_app(":memory:")


@pytest.fixture
def client(app):
    with TestClient(app, base_url="http://localhost") as client:
        yield client


def snapshot(*pages, title="Synthetic survey"):
    snap = survey(*(pages or (intro(), page(1, question()), thank_you())), title=title)
    snap.source_url = URL
    return snap


def read_result(tmp_path, snap=None, *, captures=0, stop="final_control", tag="a", claimed=None, warnings=()):
    snap = snap or snapshot()
    files = []
    for index in range(captures):
        png = tmp_path / f"{tag}-{index}.png"
        png.write_bytes(f"png-{tag}-{index}".encode())
        files.append(Capture(page_id=snap.pages[min(index, len(snap.pages) - 1)].id, viewport_png=png,
                             observation_json=tmp_path / "unused.json"))
    coverage = Coverage(pages_captured=captures if claimed is None else claimed, stop_reason=stop)
    coverage.warnings.extend(warnings)
    return ReadResult(snapshot=snap, coverage=coverage, capture_dir=tmp_path, captures=files)


def run(client, app, result):
    app.state.reader = lambda *args, **kwargs: result
    started = client.post("/api/reader/jobs", json={"url": URL, "approval": True, "ai": False}).json()
    return client.get(f"/api/jobs/{started['job_id']}").json()


def bundle_status(client, job, count):
    base = f"/api/surveys/{job['survey_id']}/versions/{job['version']}/captures/"
    return [client.get(base + str(index)).status_code for index in range(count + 1)]


# ---- Audit 11: error-only reads are not completed reviews -------------------------------------
def error_page(text="Service unavailable. Please retry later."):
    return Page(id="err", position=0, kind="info", text=text)


@pytest.mark.parametrize("stop", ["reader_error", "unsupported", "final_control"])
def test_titled_error_screen_is_a_failed_read_with_a_safe_message(client, app, tmp_path, stop):
    snap = snapshot(error_page(), title="Synthetic error")
    job = run(client, app, read_result(tmp_path, snap, stop=stop))
    assert job["status"] == "failed"
    assert "error" in job["error"].lower() and "No review was created" in job["error"]
    assert "Service unavailable" not in job["error"]          # vendor text is never echoed
    assert client.get("/api/surveys").json()["surveys"] == []


def test_error_screen_after_a_valid_welcome_is_still_a_failed_read(client, app, tmp_path):
    snap = snapshot(intro(), error_page("Something went wrong. Please try again."))
    assert run(client, app, read_result(tmp_path, snap, stop="reader_error"))["status"] == "failed"


def test_unrecognised_questionless_page_after_reader_error_is_a_failed_read(client, app, tmp_path):
    snap = snapshot(Page(id="x", position=0, kind="info", text="Quesadilla tray recipes and tips."))
    assert run(client, app, read_result(tmp_path, snap, stop="reader_error"))["status"] == "failed"


@pytest.mark.parametrize("pages,stop", [
    ((intro(),), "reader_error"),                      # welcome captured, then the browser failed
    ((thank_you(position=0),), "path_end"),            # only the closing screen
    ((intro(), thank_you()), "path_end"),
])
def test_welcome_and_terminal_screens_are_a_limited_but_completed_read(client, app, tmp_path, pages, stop):
    job = run(client, app, read_result(tmp_path, snapshot(*pages), stop=stop))
    assert job["status"] == "completed"
    assert job["outcome"] == "limited"
    assert client.get(f"/api/surveys/{job['survey_id']}").json()["coverage"]["read_outcome"] == "limited"


def test_unrecognised_questionless_page_without_a_reader_error_is_limited(client, app, tmp_path):
    snap = snapshot(Page(id="x", position=0, kind="info", text="Quesadilla tray recipes and tips."))
    job = run(client, app, read_result(tmp_path, snap, stop="unsupported"))
    assert job["status"] == "completed" and job["outcome"] == "limited"


def test_questions_make_a_reviewable_read_even_when_the_reader_later_failed(client, app, tmp_path):
    job = run(client, app, read_result(tmp_path, stop="reader_error"))
    assert job["status"] == "completed" and job["outcome"] == "reviewable"
    assert client.get(f"/api/surveys/{job['survey_id']}").json()["coverage"]["read_outcome"] == "reviewable"


# ---- Audit 12: pages_captured counts renders, never definition wording --------------------------
def test_definition_pages_without_captures_are_zero_captured_screens(client, app, tmp_path):
    parsed = adapt_definition({"title": "Synthetic", "data": {"pages": [
        {"id": "p1", "questions": [{"cid": "q1", "text": {"en_US": "Why?"}, "question_type": "textarea"}]},
        {"id": "p2", "questions": [{"cid": "q2", "text": {"en_US": "Where?"}, "question_type": "textarea"}]}]}},
        source_url=URL)
    result = ReadResult(snapshot=SurveySnapshot(title="", source_url=URL, pages=[]), coverage=Coverage(),
                        capture_dir=tmp_path)
    apply_definition(result, parsed)
    job = run(client, app, result)
    detail = client.get(f"/api/surveys/{job['survey_id']}").json()
    assert job["pages_captured"] == 0
    assert detail["coverage"]["pages_captured"] == 0 and detail["coverage"]["pages_defined"] == 2
    assert client.get(f"/api/reader/jobs/{job['id']}/preview/0").status_code == 404


def test_definition_only_review_reaches_the_api_as_unverified_images(client, app, tmp_path):
    parsed = adapt_definition({"title": "Synthetic", "data": {"pages": [{"id": "p1", "questions": [{
        "cid": "q1", "text": {"en_US": 'Choose one <img src="synthetic.png" alt="Important stimulus">'},
        "question_type": "radio", "answers": [{"id": "a", "text": {"en_US": "Yes"}},
                                              {"id": "b", "text": {"en_US": "No"}}]}]}]}}, source_url=URL)
    result = ReadResult(snapshot=SurveySnapshot(title="", source_url=URL, pages=[]), coverage=Coverage(),
                        capture_dir=tmp_path)
    apply_definition(result, parsed)
    job = run(client, app, result)
    detail = client.get(f"/api/surveys/{job['survey_id']}").json()
    results = detail["review"]["results"]
    assert all(results[cid]["assessed"] is False for cid in ("B7", "7.2", "7.3", "7.5", "7.6"))
    assert detail["coverage"]["visual_media_verified"] is False
    assert detail["snapshot"]["pages"][0]["visual_evidence"] == "definition_only"


def test_job_and_coverage_count_the_rendered_captures_and_every_index_resolves(client, app, tmp_path):
    snap = snapshot(intro(), page(1, question()), thank_you())      # three definition-like pages
    job = run(client, app, read_result(tmp_path, snap, captures=2, claimed=5))
    detail = client.get(f"/api/surveys/{job['survey_id']}").json()
    assert job["pages_captured"] == 2 and detail["coverage"]["pages_captured"] == 2
    assert [client.get(f"/api/reader/jobs/{job['id']}/preview/{i}").status_code for i in range(3)] == [200, 200, 404]
    assert bundle_status(client, job, 2) == [200, 200, 404]


# ---- Audit 6: one consistent evidence bundle per version ---------------------------------------
def test_first_read_creates_a_new_evidence_bundle(client, app, tmp_path):
    assert run(client, app, read_result(tmp_path, captures=1))["evidence"] == "new"


def test_failed_reread_retains_the_prior_bundle_atomically(client, app, tmp_path):
    first = run(client, app, read_result(tmp_path, captures=1, tag="first"))
    second = run(client, app, read_result(tmp_path, captures=0, stop="reader_error", tag="second"))
    assert second["deduplicated"] == 1 and second["version"] == first["version"]
    assert second["evidence"] == "retained"
    detail = client.get(f"/api/surveys/{first['survey_id']}").json()
    assert detail["coverage"]["stop_reason"] == "final_control" and detail["coverage"]["pages_captured"] == 1
    assert client.get(f"/api/surveys/{first['survey_id']}/versions/1/captures/0").content == b"png-first-0"
    assert bundle_status(client, second, 1) == [200, 404]


def test_richer_reread_replaces_the_whole_bundle(client, app, tmp_path):
    first = run(client, app, read_result(tmp_path, captures=1, tag="first"))
    second = run(client, app, read_result(tmp_path, captures=2, stop="path_end", tag="second"))
    assert second["evidence"] == "replaced" and second["deduplicated"] == 1
    detail = client.get(f"/api/surveys/{first['survey_id']}").json()
    assert detail["coverage"]["stop_reason"] == "path_end" and detail["coverage"]["pages_captured"] == 2
    base = f"/api/surveys/{first['survey_id']}/versions/1/captures/"
    assert [client.get(base + str(i)).content for i in range(2)] == [b"png-second-0", b"png-second-1"]


def test_shorter_reread_never_leaves_a_stale_tail_or_mixed_bundle(client, app, tmp_path):
    first = run(client, app, read_result(tmp_path, captures=2, tag="first"))
    second = run(client, app, read_result(tmp_path, captures=1, tag="second"))
    assert second["evidence"] == "retained"
    base = f"/api/surveys/{first['survey_id']}/versions/1/captures/"
    assert [client.get(base + str(i)).content for i in range(2)] == [b"png-first-0", b"png-first-1"]
    assert client.get(f"/api/surveys/{first['survey_id']}").json()["coverage"]["pages_captured"] == 2


def test_equal_reread_replaces_bundle_as_a_unit(client, app, tmp_path):
    first = run(client, app, read_result(tmp_path, captures=2, tag="first"))
    second = run(client, app, read_result(tmp_path, captures=2, tag="second"))
    assert second["evidence"] == "replaced"
    base = f"/api/surveys/{first['survey_id']}/versions/1/captures/"
    assert [client.get(base + str(i)).content for i in range(2)] == [b"png-second-0", b"png-second-1"]


def test_failed_manifest_write_leaves_the_prior_bundle_and_creates_nothing_new(client, app, tmp_path):
    first = run(client, app, read_result(tmp_path, captures=1, tag="first"))
    outside = tmp_path.parent / "outside.png"
    outside.write_bytes(b"outside")
    bad = read_result(tmp_path, captures=1, tag="second")
    bad.captures[0].viewport_png = outside
    job = run(client, app, bad)
    assert job["status"] == "failed"
    detail = client.get(f"/api/surveys/{first['survey_id']}").json()
    assert detail["coverage"]["pages_captured"] == 1 and len(detail["versions"]) == 1
    assert client.get(f"/api/surveys/{first['survey_id']}/versions/1/captures/0").content == b"png-first-0"
    db = app.state.repository.db
    assert db.execute("SELECT COUNT(*) FROM jobs WHERE status IN ('queued','running')").fetchone()[0] == 0
    assert db.execute("SELECT COUNT(*) FROM jobs").fetchone()[0] == 1   # the failed read queued no review


def test_evidence_replacement_never_touches_user_decisions(client, app, tmp_path):
    first = run(client, app, read_result(tmp_path, captures=1, tag="first"))
    db = app.state.repository.db
    with app.state.repository.transaction() as conn:
        conn.execute("INSERT INTO decisions(survey_id,version,fingerprint,data) VALUES (?,?,?,?)",
                     (first["survey_id"], 1, "abc123", '{"action":"keep","reason":"mine"}'))
    before = [tuple(row) for row in db.execute("SELECT * FROM decisions")]
    run(client, app, read_result(tmp_path, captures=2, tag="second"))      # replaced
    run(client, app, read_result(tmp_path, captures=0, stop="reader_error", tag="third"))  # retained
    assert [tuple(row) for row in db.execute("SELECT * FROM decisions")] == before


# ---- The UI never has to guess capture indices -------------------------------------------------
def test_detail_lists_the_capture_manifest_even_when_the_reader_claimed_more(client, app, tmp_path):
    snap = snapshot(intro(), page(1, question()), thank_you())
    job = run(client, app, read_result(tmp_path, snap, captures=2, claimed=5))
    manifest = client.get(f"/api/surveys/{job['survey_id']}").json()["captures"]
    assert [item["position"] for item in manifest] == [0, 1]
    assert [item["page_id"] for item in manifest] == [snap.pages[0].id, snap.pages[1].id]


def test_detail_manifest_is_empty_without_captures_and_follows_retention(client, app, tmp_path):
    job = run(client, app, read_result(tmp_path, captures=0, stop="reader_error"))
    assert client.get(f"/api/surveys/{job['survey_id']}").json()["captures"] == []
    run(client, app, read_result(tmp_path, captures=2, tag="more"))
    assert len(client.get(f"/api/surveys/{job['survey_id']}").json()["captures"]) == 2
    run(client, app, read_result(tmp_path, captures=1, tag="less"))
    assert len(client.get(f"/api/surveys/{job['survey_id']}").json()["captures"]) == 2   # retained
