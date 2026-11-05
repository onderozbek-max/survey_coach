"""Round-loop contracts, entirely synthetic; no reader, AI or user's saved DB."""
from copy import deepcopy
import json

from fastapi.testclient import TestClient

from surveycoach.server import create_app
from surveycoach.server.rounds import canonical_source_url, compare_rounds
from surveycoach.snapshot import SurveySnapshot


def snapshot(text="How did you like it?", question_id="old", title="Survey"):
    return {"title": title, "pages": [{"id": "intro", "position": 1, "kind": "intro",
        "intro_text": "Welcome! About 2 minutes. Earn points."},
        {"id": "page", "position": 2, "kind": "question", "questions": [
            {"id": question_id, "text": text, "kind": "single_choice",
             "options": [{"id": "a", "label": "Yes"}, {"id": "b", "label": "No"}]}]}]}


def finding(key="old", question_id="old", text="How did you like it?", suggestion="What do you think?"):
    return {"fingerprint": key, "criterion_id": "9.1", "severity": "worth_improving",
            "headline": "Wording", "evidence": text, "explanation": "Make it neutral",
            "member_impact": "Clearer", "question_id": question_id, "page_id": None,
            "current_text": text, "suggested_text": suggestion, "options": [], "source": "ai"}


def detail(snap=None, findings=None, decisions=None, version=1):
    return {"snapshot": snap or snapshot(), "version": version,
            "review": {"findings": [finding()] if findings is None else findings,
                       "checked_criteria": ["9.1"], "unchecked": []},
            "decisions": decisions or {}, "coverage": None}


def test_still_uses_context_not_capture_ids_and_carries_reason():
    old = detail(decisions={"old": {"action": "keep", "reason": "Tracker wording", "manual_done": True}})
    now = detail(snapshot(question_id="changed-id"), [finding("new", "changed-id")], version=2)
    changes, carried = compare_rounds(old, now)
    assert len(changes["still"]) == 1
    assert carried["new"]["reason"] == "Tracker wording"
    assert carried["new"]["acknowledged_risk"] is True
    assert carried["new"]["manual_done"] is False
    assert carried["new"]["carried_from_round"] == 1


def test_same_raw_id_and_position_never_matches_changed_prompt():
    old = detail(decisions={"old": {"action": "keep", "reason": "Approved"}})
    now = detail(snapshot("What is your age?"), [finding(text="What is your age?")])
    changes, carried = compare_rounds(old, now)
    assert changes["uncertain"] and changes["new"]
    assert not changes["still"] and not changes["fixed"] and not carried


def test_observed_pick_is_the_only_fixed_with_rewrite_proof():
    old = detail(decisions={"old": {"action": "pick", "picked_text": "What do you think?"}})
    now = detail(snapshot("What do you think?", question_id="other"), [], version=2)
    changes, carried = compare_rounds(old, now)
    item = changes["fixed"][0]
    assert item["resolution"] == "Fixed with your rewrite"
    assert item["old_wording"] == "How did you like it?"
    assert item["new_wording"] == "What do you think?"
    assert item["current_finding"] is None and item["prior_finding"]["fingerprint"] == "old"
    assert not carried
    changes, _ = compare_rounds(detail(), detail(findings=[]))
    assert changes["fixed"][0]["resolution"] == "No longer flagged"


def test_missing_or_unchecked_is_not_fixed():
    old = detail()
    now = detail(findings=[])
    now["review"]["checked_criteria"] = []
    changes, _ = compare_rounds(old, now)
    assert changes["uncertain"] and not changes["fixed"]
    now = detail({"title": "Missing", "pages": []}, [])
    changes, _ = compare_rounds(old, now)
    assert changes["uncertain"] and not changes["fixed"]


def test_invalid_or_removed_picks_never_carry_or_certify():
    old = detail(decisions={"old": {"action": "pick", "picked_text": "Not recommended"}})
    now = detail(snapshot("Not recommended"), [])
    changes, carried = compare_rounds(old, now)
    assert not changes["fixed"] and not carried
    old = detail(decisions={"old": {"action": "pick", "picked_text": "What do you think?"}})
    now = detail(findings=[finding(suggestion="A different rewrite")])
    changes, carried = compare_rounds(old, now)
    assert changes["still"] and not carried


def test_ambiguous_same_criterion_does_not_carry():
    old = detail(decisions={"old": {"action": "keep", "reason": "Approved"}})
    now = detail(findings=[finding("one"), finding("two")])
    changes, carried = compare_rounds(old, now)
    assert changes["uncertain"] and not changes["still"] and not carried


def test_canonical_source_is_fail_closed():
    assert canonical_source_url("https://APP.redjade.net:443/surveys/a") == "https://app.redjade.net/surveys/a"
    for url in ("https://app.redjade.net/surveys/a?token=x", "https://app.redjade.net/surveys/a#secret",
                "https://app.redjade.net.evil.test/a", "https://user:pass@app.redjade.net/a", "http://app.redjade.net/a"):
        assert canonical_source_url(url) is None
    assert canonical_source_url("https://app.redjade.net/A") != canonical_source_url("https://app.redjade.net/a")


def test_api_title_known_url_and_immutable_rounds(tmp_path):
    app = create_app(tmp_path / "test.db")
    with TestClient(app, base_url="http://localhost") as client:
        snap = snapshot()
        snap["source_url"] = "https://APP.redjade.net:443/surveys/approved"
        first = client.post("/api/surveys", json={"snapshot": snap}).json()
        url = f"/api/surveys/{first['id']}"
        original = client.get(url).json()
        assert client.patch(url, json={"title": "  Researcher title  "}).json()["title"] == "Researcher title"
        for title in (" ", "a" * 201, "bad\nname", 17):
            assert client.patch(url, json={"title": title}).status_code == 422
        changed = deepcopy(snap)
        changed["source_url"] = "https://app.redjade.net/surveys/approved"
        changed["pages"][1]["questions"][0]["required"] = False
        second = client.post("/api/surveys", json={"snapshot": changed}).json()
        assert second["id"] == first["id"] and second["version"] == 2
        assert len(client.get("/api/surveys").json()["surveys"]) == 1
        current = client.get(url).json()
        historic = client.get(url + "/versions/1").json()
        assert historic["snapshot"] == original["snapshot"]
        assert current["title"] == historic["title"] == "Researcher title"
        assert current["snapshot"]["title"] == "Survey"
        assert set(current["round_changes"]) >= {"fixed", "still", "new", "uncertain", "unchecked_paths"}
        assert current["round_changes"]["compared_to_round"] == 1
        assert "carried" in current and "carried_decisions" in current
        sheet = client.get(url + "/versions/2/change-sheet").json()
        assert sheet["round"] == 2 and "changes" in sheet


def test_recheck_after_reading_history_compares_latest_saved_version(tmp_path):
    app = create_app(tmp_path / "history.db")
    with TestClient(app, base_url="http://localhost") as client:
        first = client.post("/api/surveys", json={"snapshot": snapshot()}).json()
        url = f"/api/surveys/{first['id']}"
        for version in (2, 3):
            saved = client.post(url + "/recheck", json={
                "snapshot": snapshot(title=f"Saved version {version}")}).json()
            assert saved['version'] == version
        historical = client.get(url + "/versions/1").json()
        result = client.post(url + "/recheck", json={
            "snapshot": snapshot(title="Updated from historical view")}).json()
        assert result['version'] == 4
        current = client.get(url).json()
        assert current['round_changes']['compared_to_round'] == 3
        after = client.get(url + "/versions/1").json()
        # The timeline gains version 4; the historical review itself is immutable.
        assert {k: v for k, v in after.items() if k != 'versions'} == {
            k: v for k, v in historical.items() if k != 'versions'}


def test_report_plain_words_escaped_and_csp(tmp_path):
    app = create_app(tmp_path / "test.db")
    with TestClient(app, base_url="http://localhost") as client:
        snap = snapshot(title="<script>unsafe()</script>")
        created = client.post("/api/surveys", json={"snapshot": snap}).json()
        url = f"/api/surveys/{created['id']}/versions/1"
        response = client.get(url + "/summary")
        assert "default-src 'none'" in response.headers["content-security-policy"]
        assert "&lt;script&gt;" in response.text and "<script>unsafe()" not in response.text
        for text in ("Version 1", "What we checked", "Chosen changes", "Kept risks", "Technical appendix"):
            assert text in response.text
        for raw in ("must_fix", "almost_ready", "pending_blockers", "content_hash"):
            assert raw not in response.text
        assert "not launch approval" in response.text


def test_carried_decision_is_overridable_and_prior_round_stays_unchanged(tmp_path):
    app = create_app(tmp_path / "test.db")
    with TestClient(app, base_url="http://localhost") as client:
        snap = snapshot()
        first = client.post("/api/surveys", json={"snapshot": snap}).json()
        url = f"/api/surveys/{first['id']}"
        initial = client.get(url).json()
        issue = initial["review"]["findings"][0]
        decision_url = url + f"/versions/1/decisions/{issue['fingerprint']}"
        saved = client.put(decision_url, json={"action": "keep", "reason": "Tracker",
                           "client_id": "same-browser", "revision": 90}).json()
        second = deepcopy(snap)
        second["title"] = "Round two source title"
        client.post(url + "/recheck", json={"snapshot": second})
        current = client.get(url).json()
        carried = current["decisions"][issue["fingerprint"]]
        assert carried["reason"] == "Tracker" and carried["revision"] == 0
        assert carried["client_id"] is None
        override = client.put(url + f"/versions/2/decisions/{issue['fingerprint']}",
                              json={"action": "open", "client_id": "same-browser", "revision": 1})
        assert override.json()["action"] == "open"
        assert client.get(url).json()["decisions"][issue["fingerprint"]]["action"] == "open"
        assert client.get(url + "/versions/1").json()["decisions"][issue["fingerprint"]] == saved


def test_saved_info_welcome_is_corrected_without_snapshot_rewrite(tmp_path):
    app = create_app(tmp_path / "test.db")
    with TestClient(app, base_url="http://localhost") as client:
        snap = snapshot()
        snap["pages"][0]["kind"] = "info"
        snap["pages"][0]["text"] = snap["pages"][0].pop("intro_text")
        created = client.post("/api/surveys", json={"snapshot": snap}).json()
        result = client.get(f"/api/surveys/{created['id']}").json()
        assert result["snapshot"]["pages"][0]["kind"] == "info"
        assert not any(f["criterion_id"] == "B4" for f in result["review"]["findings"])


def test_read_projection_does_not_write_history(tmp_path):
    app = create_app(tmp_path / "test.db")
    with TestClient(app, base_url="http://localhost") as client:
        created = client.post("/api/surveys", json={"snapshot": snapshot()}).json()
        repo = app.state.repository
        with repo.transaction() as db:
            row = db.execute("SELECT id,data FROM reviews").fetchone()
            stored = json.loads(row["data"])
            stored["review"]["findings"].append({**finding(), "criterion_id": "B4", "source": "auto"})
            encoded = json.dumps(stored)
            db.execute("UPDATE reviews SET data=? WHERE id=?", (encoded, row["id"]))
        result = client.get(f"/api/surveys/{created['id']}").json()
        assert not any(f["criterion_id"] == "B4" for f in result["review"]["findings"])
        assert result["review"]["projection"]["stored_history_unchanged"]
        with repo.transaction() as db:
            assert db.execute("SELECT data FROM reviews WHERE id=?", (row["id"],)).fetchone()[0] == encoded


def test_no_blockers_presentation_is_reachable_without_claiming_full_coverage(tmp_path):
    app = create_app(tmp_path / "test.db")
    with TestClient(app, base_url="http://localhost") as client:
        created = client.post("/api/surveys", json={"snapshot": snapshot()}).json()
        result = client.get(f"/api/surveys/{created['id']}").json()
        verdict = result["presentation"]["verdict"]
        assert verdict["tiles"]["fix"] == 0 and verdict["kind"] != "fix_before_launch"   # no blockers found...
        assert result["methodology"]["not_checked_automatically"]                         # ...without claiming it all ran
        assert result["presentation"]["scope"]["unchecked_paths"]
        assert result["review"]["scorecard"]["readiness"] != "ready"
