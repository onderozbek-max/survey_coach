"""Read-only round comparison. Identity needs source position AND observed context."""
from copy import deepcopy
from urllib.parse import urlsplit, urlunsplit

from surveycoach.labels import finding_label, screen_labels
from surveycoach.reader.policy import UnsafeSurveyURL, validate_url
from surveycoach.snapshot import SurveySnapshot


def canonical_source_url(url):
    """Do not strip tokens or normalize distinct paths into the same survey."""
    try:
        validate_url(url, approval=True)
    except (UnsafeSurveyURL, ValueError, TypeError):
        return None
    parts = urlsplit(url)
    return urlunsplit(("https", parts.hostname, parts.path or "/", "", ""))


def normalized(value):
    return " ".join((value or "").split())


def _scale_context(scale):
    if scale is None:
        return None
    return (scale.get("points"), scale.get("low_label"), scale.get("high_label"),
            tuple(scale.get("labels", [])))


def locations(snapshot):
    result = []
    labels = screen_labels(SurveySnapshot.model_validate(snapshot))
    for index, page in enumerate(snapshot.get("pages", [])):
        base = {"position": page["position"], "page_id": page["id"],
                "screen_label": f'{labels[index]["name"]} · Screen {index + 1}', "page": page}
        result.append(dict(base, question_id=None, slot=None,
                           wording=page.get("intro_text") or page.get("text", ""),
                           context=("page", page.get("kind"), bool(page.get("questions")))))
        for slot, question in enumerate(page.get("questions", [])):
            label = (base["screen_label"] if question["kind"] == "info" else
                     finding_label({"question_id": question["id"]}, labels))
            result.append(dict(base, question_id=question["id"], slot=slot, question=question,
                               screen_label=label,
                               wording=question["text"],
                               context=(question["kind"],
                                        tuple(sorted((o["label"], repr(o.get("is_exclusive")),
                                                      repr(o.get("is_other_with_text")))
                                                     for o in question.get("options", []))),
                                        tuple(question.get("rows", [])),
                                        question.get("required", True), question.get("conditional", False),
                                        question.get("help_text", ""),
                                        _scale_context(question.get("scale")))))
    return result


def locate(finding, places):
    candidates = [p for p in places if (p["question_id"] == finding.get("question_id")
                  if finding.get("question_id") else p["page_id"] == finding.get("page_id") and p["slot"] is None)]
    return candidates[0] if len(candidates) == 1 else None


def actual_wording(place, finding):
    """Only return text observed in the snapshot, never explanatory finding evidence."""
    if place is None:
        return None
    question = place.get("question", {})
    current = finding.get("current_text")
    values = [place["wording"], question.get("help_text", "")]
    values += [o["label"] for o in question.get("options", [])]
    scale = question.get("scale") or {}
    values += [scale.get("low_label"), scale.get("high_label"), *scale.get("labels", [])]
    return next((v for v in values if v and normalized(v) == normalized(current)), place["wording"])


def same_location(old, new, decision):
    if old["position"] != new["position"] or old["slot"] != new["slot"] or old["context"] != new["context"]:
        return False
    # A changed prompt at the same raw ID/position is NOT sufficient identity.
    return (bool(normalized(old["wording"])) and normalized(old["wording"]) == normalized(new["wording"])) or (
        decision.get("action") == "pick" and normalized(decision.get("picked_text")) == normalized(new["wording"])
        and bool(normalized(new["wording"])))


def allowed_texts(finding):
    return {o["text"] for o in finding.get("options", [])} | ({finding["suggested_text"]} if finding.get("suggested_text") else set())


def valid_decisions(detail):
    findings = {f["fingerprint"]: f for f in (detail.get("review") or {}).get("findings", [])}
    output = {}
    for key, decision in detail.get("decisions", {}).items():
        finding = findings.get(key)
        if not finding:
            continue
        if decision.get("action") == "pick" and decision.get("picked_text") not in allowed_texts(finding):
            output[key] = dict(decision, action="open", picked_text=None, manual_done=False,
                               stale_pick=True, previous_text=decision.get("picked_text"))
        else:
            output[key] = decision
    return output


def scope(detail):
    review = detail.get("review") or {}
    coverage = detail.get("coverage")
    results = review.get("results")
    applicable = {cid: result for cid, result in (results or {}).items()
                  if result.get("applies", True)}
    checked = {cid for cid, result in applicable.items()
               if result.get("assessed", True)
               and (result.get("fraction") is not None or cid.startswith("B"))}
    from surveycoach.rubric import load_rubric
    rubric = load_rubric()
    # Missing active checks are unknown evidence, including AI-only blockers.
    # An explicit non-applicable result is not missing and stays out of coverage.
    active = [*(c for c in rubric.criteria if c.active), *rubric.blockers]
    missing = {c.id for c in active if c.id not in (results or {})}
    titles = {c.id: c.title for c in active}
    unchecked = list(dict.fromkeys([*review.get("unchecked", []),
                                   *(titles.get(cid, cid) for cid in sorted(
                                       (applicable.keys() - checked) | missing))]))
    # Counts describe assessed evidence, never points, findings or passing credit.
    # Older payloads without criterion results cannot establish a denominator.
    return {"checked_count": len(checked) if results is not None else None,
            "total_count": len(applicable) + len(missing) if results is not None else None,
            "summary": (f"{coverage['pages_captured']} captured screens; only observed paths checked."
                        if coverage else "Imported screens; capture completeness not independently verified."),
            "unchecked_paths": ([] if coverage and coverage.get("full_branching_coverage") else
                                ["Unvisited branches and uncaptured screens were not checked."]),
            "unchecked_checks": unchecked,
            "review_available": bool(detail.get("review"))}


def presentation(detail):
    findings = (detail.get("review") or {}).get("findings", [])
    decisions = detail.get("decisions", {})
    blockers = [f for f in findings if f["severity"] == "must_fix"]
    acknowledged = [f for f in blockers if decisions.get(f["fingerprint"], {}).get("action") == "keep"
                    and decisions[f["fingerprint"]].get("reason", "").strip()]
    count = len(blockers) - len(acknowledged)
    return {"verdict": ("Review not available" if not detail.get("review") else
                        f"{count} issues to fix before launch" if count else
                        "No blockers found in what we checked"),
            "open_blockers": count, "acknowledged_risks": len(acknowledged),
            "scope": scope(detail), "launch_approval": False}


def compare_rounds(prior, current):
    changes = {key: [] for key in ("fixed", "still", "new", "uncertain")}
    carried = {}
    old_findings = (prior.get("review") or {}).get("findings", [])
    new_findings = (current.get("review") or {}).get("findings", [])
    old_places, new_places = locations(prior["snapshot"]), locations(current["snapshot"])
    old_decisions = valid_decisions(prior)
    used = set()
    checked = set((current.get("review") or {}).get("checked_criteria", []))
    matches = {}
    for old in old_findings:
        decision = old_decisions.get(old["fingerprint"], {})
        place = locate(old, old_places)
        candidates = [p for p in new_places if place and same_location(place, p, decision)]
        matches[old["fingerprint"]] = candidates
    for old in old_findings:
        decision = old_decisions.get(old["fingerprint"], {})
        old_place = locate(old, old_places)
        candidates = matches[old["fingerprint"]]
        new_place = candidates[0] if len(candidates) == 1 else None
        related = [f for f in new_findings if f["criterion_id"] == old["criterion_id"]
                   and new_place and locate(f, new_places) == new_place]
        # Several same-criterion findings on one screen require evidence, not list order.
        if len(related) > 1:
            related = [f for f in related if normalized(f.get("evidence")) == normalized(old.get("evidence"))]
        # Global findings need unchanged survey evidence, not a reused fingerprint.
        if old_place is None:
            same_content = [(p["position"], p["slot"], p["wording"], p["context"]) for p in old_places] == [
                (p["position"], p["slot"], p["wording"], p["context"]) for p in new_places]
            related = [f for f in new_findings if same_content and not locate(f, new_places)
                       and f["criterion_id"] == old["criterion_id"] and f["evidence"] == old["evidence"]]
        now = related[0] if len(related) == 1 else None
        # Reverse uniqueness prevents two old issues from carrying into one new issue.
        competing = [f for f in old_findings if f["criterion_id"] == old["criterion_id"]
                     and f["fingerprint"] != old["fingerprint"] and new_place in matches[f["fingerprint"]]] if new_place else []
        unique = now is not None and not competing and now["fingerprint"] not in used
        # Show the observed text at a changed source position without treating it as identity.
        positional = [p for p in new_places if old_place and p["position"] == old_place["position"]
                      and p["slot"] == old_place["slot"]]
        display_place = new_place or (positional[0] if len(positional) == 1 else None)
        entry = {"prior_finding": old, "current_finding": now if unique else None,
                 "screen_label": (new_place or old_place or {}).get("screen_label", "Survey overall"),
                 "old_wording": actual_wording(old_place, old),
                 "new_wording": actual_wording(display_place, now or old), "resolution": None}
        if unique:
            used.add(now["fingerprint"])
            entry["resolution"] = "Still flagged"
            changes["still"].append(entry)
            action = decision.get("action")
            if (action in {"keep", "original", "pick"}
                    and (action != "keep" or decision.get("reason", "").strip())
                    and (action != "pick" or decision.get("picked_text") in allowed_texts(now))):
                carried[now["fingerprint"]] = dict(decision, fingerprint=now["fingerprint"],
                    original=now.get("current_text") or now["evidence"], manual_done=False,
                    client_id=None, revision=0,
                    carried_from_round=prior["version"], carried_from_fingerprint=old["fingerprint"],
                    acknowledged_risk=action == "keep")
        elif new_place and not related and old["criterion_id"] in checked and current.get("review"):
            observed = decision.get("action") == "pick" and normalized(decision.get("picked_text")) == normalized(entry["new_wording"])
            entry["resolution"] = "Fixed with your rewrite" if observed else "No longer flagged"
            changes["fixed"].append(entry)
        else:
            entry["resolution"] = "Not verified: changed context, missing screen, ambiguous match or unchecked criterion"
            changes["uncertain"].append(entry)
    for now in new_findings:
        if now["fingerprint"] not in used:
            place = locate(now, new_places)
            changes["new"].append({"prior_finding": None, "current_finding": now,
                "screen_label": (place or {}).get("screen_label", "Survey overall"),
                "old_wording": None, "new_wording": actual_wording(place, now), "resolution": "Newly flagged"})
    for entries in changes.values():
        for entry in entries:
            # Backward-compatible presentation aliases for lightweight clients.
            entry.update(previous=entry["prior_finding"], current=entry["current_finding"],
                         before_text=entry["old_wording"], after_text=entry["new_wording"],
                         reason=entry["resolution"])
    return changes, carried


def change_sheet(detail):
    places = locations(detail["snapshot"])
    lines = []
    for finding in (detail.get("review") or {}).get("findings", []):
        if finding.get("absorbed_by"):
            continue  # The parent owns this change; retain the child as evidence only.
        decision = detail.get("decisions", {}).get(finding["fingerprint"], {})
        if decision.get("action") not in {"pick", "keep"}:
            continue
        place = locate(finding, places)
        wording = actual_wording(place, finding)
        question = (place or {}).get("question", {})
        target = "Question" if question else "Screen text"
        for index, option in enumerate(question.get("options", []), 1):
            if wording == option["label"]:
                target = f"Answer {index}"
        if wording in [v for v in (question.get("scale") or {}).values() if isinstance(v, str)]:
            target = "Scale label"
        if finding.get('edit_kind') == 'add_answer':
            target = 'New answer option'
        lines.append({"fingerprint": finding["fingerprint"], 'edit_kind':finding.get('edit_kind','rewrite'),
                      'instructions':finding.get('explanation',''),
                      "screen_label": (place or {}).get("screen_label", "Survey overall"),
                      "position": (place or {}).get("position", 0), "target": target,
                      "find": wording, "replace": decision.get("picked_text"),
                      "action": decision["action"], "reason": decision.get("reason", ""),
                      "acknowledged_risk": decision["action"] == "keep",
                      "manual_edit_required": bool(finding.get("structural") or not wording)})
    return sorted(lines, key=lambda line: line["position"])


def project_review(snapshot, review):
    """Refresh code evidence on read, never stored history or historical AI judgements.

    New reviews retain assessed results, including AI passes with no findings. Merge
    that evidence with refreshed code checks; only legacy reviews without results
    need a conservative, no-inferred-AI-credit fallback.
    """
    if not review:
        return review
    from surveycoach.findings import CheckResult, Finding
    from surveycoach.review import _merge, _with_ai, run_review
    from surveycoach.judge.batches import BATCHES
    from surveycoach.rubric import load_rubric
    from surveycoach.scoring import score
    from surveycoach.snapshot import SurveySnapshot

    projected = deepcopy(review)
    rubric = load_rubric()
    current = run_review(SurveySnapshot.model_validate(snapshot), rubric=rubric)
    results = current.results
    affected = set(results)
    retained = [f for f in projected.get("findings", [])
                if f.get("source") == "ai" or f["criterion_id"] not in affected]
    stored = review.get("results")
    ai_ids = {cid for batch in BATCHES for cid in (*batch.criteria, *batch.blockers)}
    evidence = {}
    if stored is not None:
        # Stored results are code+AI merged. Never replay their old auto findings;
        # current code remains authoritative for deterministic evidence.
        for cid, encoded in stored.items():
            if cid not in ai_ids:
                continue
            result = CheckResult.model_validate(encoded)
            result.findings = [f for f in result.findings if f.source == "ai"]
            evidence[cid] = result
        results = _with_ai(results, evidence)

    # Legacy concerns remain visible but cannot imply an assessed pass. A missing
    # per-criterion result is also legacy evidence, even in a partial results map.
    for encoded in retained:
        finding = Finding.model_validate(encoded)
        cid = finding.criterion_id
        result = results.setdefault(cid, CheckResult(criterion_id=cid, assessed=False))
        if not any(f.root_identity == finding.root_identity for f in result.findings):
            result.findings.append(finding)
        if cid not in evidence:
            result.fraction = None
            result.assessed = False
            result.applies = True

    # Finding validation drops serialized fingerprints. Restore persisted API keys
    # only for an unambiguous surviving retained issue, never a fresh auto winner
    # replacing an AI duplicate (or a different criterion at the same root).
    fingerprints = {}
    for encoded in retained:
        finding = Finding.model_validate(encoded)
        if encoded.get("fingerprint"):
            key = (finding.source, finding.criterion_id, finding.root_identity)
            fingerprints.setdefault(key, set()).add(encoded["fingerprint"])

    # Display the same merged evidence we score, including legacy unknown criteria.
    projected["findings"] = []
    for finding in _merge(results, rubric):
        key = (finding.source, finding.criterion_id, finding.root_identity)
        saved = fingerprints.get(key, set())
        fingerprint = next(iter(saved)) if len(saved) == 1 else finding.fingerprint
        projected["findings"].append(finding.model_dump(mode="json") | {"fingerprint": fingerprint})
    kept = frozenset(review.get("scorecard", {}).get("kept_blockers", []))
    projected["scorecard"] = score(rubric, results, kept).model_dump(mode="json")
    projected["results"] = {cid: result.model_dump(mode="json") for cid, result in results.items()}
    projected["unchecked"] = [c.title for c in rubric.criteria if c.active
                              and ((r := results.get(c.id)) is None
                                   or (r.applies and (not r.assessed or r.fraction is None)))]
    projected["checked_criteria"] = sorted(
        cid for cid, result in results.items()
        if result.applies and result.assessed and (result.fraction is not None or cid.startswith("B")))
    for field in ("rubric_version", "est_minutes", "promised_minutes"):
        projected[field] = getattr(current, field)
    has_ai = bool(review.get("ai")) or any(f.get("source") == "ai" for f in retained)
    projected["projection"] = {
        "deterministic_criteria": sorted(affected), "stored_history_unchanged": True,
        "historical_checked_criteria": deepcopy(review.get("checked_criteria", [])),
        "ai_score_reconstructed": not has_ai or stored is not None,
        "score_basis": ("current_code_and_retained_assessed_results" if stored is not None else
                        "current_code_and_retained_historical_concerns"),
        "score_limitations": ([
            "Historical AI criterion fractions were not stored separately. AI findings and run status "
            "are preserved, but no historical AI passing credit is inferred. The score is a conservative "
            "current-code evidence score, not a reconstruction of the original combined review."
        ] if has_ai and stored is None else []),
    }
    return projected
