"""Property over every fixture: tiles, signals, screen markers and counts agree, and every finding
honours the action contract. Fixtures: the two sample surveys, the offline demo data, and a
synthetic concept test shaped like a real one."""
import pytest

from concept_fixture import concept_survey
from surveycoach.demo_export import build_demo_data
from surveycoach.recommendations import validate_finding
from surveycoach.review import run_review
from surveycoach.server.repository import Repository
from surveycoach.status import FIX_BEFORE_LAUNCH, IMPROVE, STATES, YOU_CHECK, worst_state

OPEN_STATES = (FIX_BEFORE_LAUNCH, IMPROVE, YOU_CHECK)

# Visible copy that the CHECKS still write themselves (headline / member_impact), so only the checks'
# owners can fix it. The legacy fallback already scrubs explanations. The list may only shrink.
KNOWN_COPY_DEBT = {
    "B7": {"banned:reader"},                 # headline "Reader could not verify image loading"
    "8.5": {"member_impact_long"}, "B1": {"member_impact_long"}, "B2": {"member_impact_long"},
}


def encoded(snapshot):
    result = run_review(snapshot)
    review = result.model_dump(mode="json", exclude={"timing"})
    review["findings"] = [f.model_dump(mode="json") | {"fingerprint": f.fingerprint} for f in result.findings]
    return {"review": review}


@pytest.fixture(scope="module")
def details(tmp_path_factory):
    repo = Repository(tmp_path_factory.mktemp("consistency") / "c.db")
    found = {}
    concept = concept_survey()
    created = repo.submit(concept, ai=False)
    repo.finish(created["job_id"], encoded(concept))
    found["concept"] = repo.detail(created["id"])
    # decided variants of the same survey exercise open vs. closed counting
    first = next(i for i in found["concept"]["overview"]["items"])
    for fingerprint in first["fingerprints"]:
        repo.save_decision(created["id"], 1, fingerprint, {"action": "original"})
    found["concept-decided"] = repo.detail(created["id"])
    for index, survey in enumerate(build_demo_data()["surveys"]):
        found[f"demo-{index}"] = survey
    repo.close()
    return found


def assert_consistent(detail):
    overview = detail["overview"]
    items, verdict = overview["items"], overview["verdict"]
    assert len({i["id"] for i in items}) == len(items), "an item is counted twice"
    assert all(i["state"] in OPEN_STATES for i in items)
    open_items = [i for i in items if i["open"]]
    # tiles: the same items, counted once
    for key, state in (("fix", FIX_BEFORE_LAUNCH), ("improve", IMPROVE), ("you_check", YOU_CHECK)):
        assert verdict["tiles"][key] == sum(i["state"] == state for i in open_items), key
    assert verdict["progress"] == {"done": len(items) - len(open_items), "total": len(items)}
    expected = ("fix_before_launch" if verdict["tiles"]["fix"] else
                "almost_ready" if verdict["tiles"]["improve"] or verdict["tiles"]["you_check"] else
                "ready_for_signoff")
    assert verdict["kind"] == expected
    # the fix tile agrees with the plan's open must-fix count
    assert verdict["tiles"]["fix"] == detail["plan"]["counts"]["open_must_fix"]
    # signals: every item with a signal lives in exactly one, and the card never contradicts it
    seen = {}
    for signal in overview["signals"]:
        assert signal["state"] is None or signal["state"] in STATES
        for entry in signal["items"]:
            assert entry["id"] not in seen, "an item sits in two categories"
            seen[entry["id"]] = signal["id"]
        opened = [e["state"] for e in signal["items"] if e["open"]]
        if opened:
            assert signal["state"] == worst_state(opened), signal["id"]      # Time included
        else:
            assert signal["state"] in (None, "looks_good"), (signal["id"], "a state with nothing open")
        if signal["state"] == "looks_good" and signal["id"] != "time":
            assert signal["summary"] == "Nothing to fix here."
        if signal["id"] != "time" and signal["state"] == "looks_good":
            checks = signal["methodology"]["coverage"]
            assert checks["checked"] >= 2 and checks["checked"] * 2 >= checks["total"] - len(checks["not_applicable"])
    assert set(seen) == {i["id"] for i in items if i["signal"]}
    # per-screen markers: the worst open state on that screen
    for screen in overview["energy"]["screens"]:
        on_screen = [i["state"] for i in open_items if screen["page_id"] in i["pages"]]
        assert screen["state"] == worst_state(on_screen)
    # never a score in the primary payload
    assert "score" not in verdict and "provisional" not in verdict


@pytest.mark.parametrize("name", ["concept", "concept-decided", "demo-0", "demo-1"])
def test_tiles_signals_markers_and_counts_agree(details, name):
    assert_consistent(details[name])


def test_decided_items_move_from_open_to_done_in_every_view(details):
    before, after = details["concept"]["overview"], details["concept-decided"]["overview"]
    assert after["verdict"]["progress"]["done"] > before["verdict"]["progress"]["done"]
    assert sum(after["verdict"]["tiles"].values()) < sum(before["verdict"]["tiles"].values())


def all_findings(details):
    for name, detail in details.items():
        for finding in (detail.get("review") or {}).get("findings", []):
            yield name, finding


def test_every_fixture_finding_has_exactly_one_action_kind_and_is_valid(details):
    problems = {}
    for name, finding in all_findings(details):
        for code in validate_finding(finding):
            problems.setdefault((finding["criterion_id"], code), set()).add(name)
    hard = {key: where for key, where in problems.items() if not key[1].startswith(("banned:", "member_impact_long"))}
    assert hard == {}, hard


def test_visible_copy_has_no_banned_words_or_long_impact_beyond_the_known_debt(details):
    soft = {}
    for _, finding in all_findings(details):
        for code in validate_finding(finding):
            if code.startswith(("banned:", "member_impact_long")):
                soft.setdefault(finding["criterion_id"], set()).add(code)
    unexpected = {cid: codes for cid, codes in soft.items() if codes - KNOWN_COPY_DEBT.get(cid, set())}
    assert unexpected == {}, unexpected
    stale = {cid: known - soft.get(cid, set()) for cid, known in KNOWN_COPY_DEBT.items()
             if known - soft.get(cid, set())}
    assert stale == {}, f"fixed: remove from KNOWN_COPY_DEBT {stale}"


def test_checks_still_on_the_legacy_fallback_are_all_of_them_for_now(details):
    """No check sets action fields yet; the full list is reported in impl-1a-status.md."""
    explicit = {f["criterion_id"] for _, f in all_findings(details) if not f.get("action_fallback")}
    assert explicit == set()
