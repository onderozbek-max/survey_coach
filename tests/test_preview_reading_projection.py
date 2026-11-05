"""Offline JS regressions: preview improvements use timing's canonical evidence."""
import json
from pathlib import Path
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]


def delta(pages, plan, method="previewReadingDelta"):
    script = """
const fs = require('node:fs');
global.window = {SC: {h: () => {}}};
for (const name of ['model.js', 'energy.js']) {
  eval(fs.readFileSync('site/' + name, 'utf8'));
}
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const before = JSON.stringify(input);
const result = input.pages.map(page => window.SC[input.method](page, input.plan));
if (JSON.stringify(input) !== before) throw new Error('Preview mutated the capture or plan');
console.log(JSON.stringify(result));
"""
    result = subprocess.run(
        ["node", "-e", script], cwd=ROOT,
        input=json.dumps({"pages": pages, "plan": plan, "method": method}),
        text=True, capture_output=True, check=True,
    )
    return json.loads(result.stdout)


def page(*fields, raw="", intro="", page_id="p", rate=.3):
    return {
        "id": page_id, "text": raw, "intro_text": intro,
        "questions": [{"id": "q1", "text": "Which household meal do you prefer today?",
                       "help_text": "", "kind": "single_choice", "options": []}],
        "reading_basis": {"seconds_per_word": rate, "fields": list(fields)},
    }


def field(text, question_id=None):
    return {"text": text, **({"question_id": question_id} if question_id else {})}


def fix(before, after, question_id=None, page_id="p"):
    return {"from": before, "to": after, "page_id": page_id,
            **({"question_id": question_id} if question_id else {})}


def test_raw_intro_and_structured_copies_do_not_multiply_improvement():
    original = "Which household meal do you prefer today?"
    structured = page(field(original, "q1"))
    captured = page(field(original, "q1"), raw=original, intro=original)
    plan = [fix(original, "Preferred meal?")]
    assert delta([structured, captured], plan) == [2, 2]


def test_unique_concept_prose_and_two_pages_stay_independent():
    concept = "Imagine a convenient meal prepared for your entire household"
    first = page(field(concept), field("Which meal?", "q1"), raw=concept, intro=concept)
    second = page(field(concept), field("Which meal?", "q1"), raw=concept, page_id="p2")
    assert delta([first, second], [fix(concept, "Imagine a meal")]) == [2, 0]


def test_question_scope_preserves_other_questions_and_their_options():
    long = "A freshly prepared meal for the entire family"
    p = page(field(long, "q1"), field(long, "q2"), field("Another long option unchanged", "q1"))
    p["questions"] = [
        {"id": qid, "text": long, "kind": "single_choice", "options": [{"label": long}]}
        for qid in ("q1", "q2")
    ]
    assert delta([p], [fix(long, "Family meal", "q1")]) == [2]


@pytest.mark.parametrize("kind", ["single_choice", "dropdown", "grid_single", "grid_multi"])
def test_counted_options_have_same_reading_projection_for_all_controls(kind):
    long = "A freshly prepared meal for the entire family"
    p = page(field("Choose one", "q1"), field(long, "q1"))
    p["questions"][0].update(kind=kind, options=[{"label": long}])
    assert delta([p], [fix(long, "Family meal", "q1")]) == [2]


def test_backend_rate_not_a_second_javascript_timing_constant():
    p = page(field("one two three four five six", "q1"), rate=1)
    assert delta([p], [fix("one two three four five six", "one", "q1")]) == [5]


def test_longer_copy_reports_negative_improvement_and_inputs_do_not_mutate():
    p = page(field("Meal?", "q1"))
    plan = [fix("Meal?", "Which meal would your household prefer?", "q1")]
    assert delta([p], plan) == [-1]


@pytest.mark.parametrize("basis", [None, {}, {"fields": []},
                                  {"seconds_per_word": -.3, "fields": []},
                                  {"seconds_per_word": .3, "fields": [None]},
                                  {"seconds_per_word": .3, "fields": [{"text": 3}]}])
def test_missing_or_invalid_canonical_evidence_is_not_a_claimed_zero_change(basis):
    p = page(field("Which meal?", "q1"))
    p["reading_basis"] = basis
    assert delta([p], [fix("Which meal?", "Meal?", "q1")]) == [None]


def test_evidence_copy_distinguishes_unavailable_from_numeric_improvement():
    p = page(field("one two three four five six", "q1"))
    legacy = {**p, "reading_basis": None}
    messages = delta([p, legacy], [fix("one two three four five six", "one", "q1")],
                     method="previewReadingEvidence")
    assert "2 seconds shorter" in messages[0]
    assert "not reassessed" in messages[0]
    assert "unavailable" in messages[1]
    assert "0 seconds" not in messages[1]


def test_repeated_legitimate_words_in_separate_fields_are_not_deduplicated_again():
    original = "Imagine a freshly prepared family meal"
    p = page(field(original), field(original, "q1"))
    assert delta([p], [fix(original, "Meal")]) == [3]
