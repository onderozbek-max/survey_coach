"""Synthetic definitions only: no RedJade access or captured participant data."""
import pytest

from surveycoach.reader.definition import Definition, parse_definition


def question(qid="q1", text="Choose a fruit", answers=None):
    return {"id": qid, "cid": qid, "question_type": "radio",
            "text": {"en_US": text}, "answers": answers or [
                {"id": f"{qid}-a", "text": {"en_US": "Apple"}},
                {"id": f"{qid}-b", "text": {"en_US": "Other"}},
            ]}


def page(pid="p1", prompt="Choose a fruit", **extra):
    return {"id": pid, "index": 17, "questions": [question(pid + "q", prompt)],
            "triggers": [], **extra}


def payload(*pages):
    return {"questionnaire": {"data": {"pages": list(pages)}}}


@pytest.mark.parametrize("grouped", [False, True])
def test_parses_both_known_shapes_without_retaining_extra_response_data(grouped):
    data = payload(page(), page("p2", "Tell us why"))
    if grouped:
        data["questionnaire"]["data"] = {"page_groups": [
            {"pages": [page()]}, {"pages": [page("p2", "Tell us why")]}]}
    data["participant"] = {"secret": "must-not-retain"}
    definition = parse_definition({"response": data})
    assert isinstance(definition, Definition)
    assert [p.id for p in definition.pages] == ["p1", "p2"]
    assert "must-not-retain" not in repr(definition)
    assert definition.pages[0].questions[0].text == "Choose a fruit"


def test_parser_owns_immutable_normalized_copy():
    raw = payload(page(prompt="<b>Choose</b> &amp; explain&nbsp;please"))
    definition = parse_definition(raw)
    raw["questionnaire"]["data"]["pages"][0]["questions"].clear()
    assert definition.pages[0].questions[0].text == "Choose & explain please"
    with pytest.raises((AttributeError, TypeError)):
        definition.pages[0].id = "changed"


@pytest.mark.parametrize("raw", [None, [], {}, {"questionnaire": []},
    {"questionnaire": {"data": {"pages": []}}},
    {"questionnaire": {"data": {"pages": "not pages"}}},
    payload(page(), page()),
    payload(page(questions=[question(answers=[{"id": "a", "text": {"en_US": "A"}},
                                               {"id": "a", "text": {"en_US": "B"}}])])),
])
def test_malformed_or_ambiguous_payload_does_not_make_a_definition(raw):
    assert parse_definition(raw) is None


def test_full_question_text_and_all_questions_required_for_unique_match():
    first = page(prompt="What do you think of this particular fruit and its texture?")
    second = page("p2", "What do you think of this particular fruit and its taste?")
    definition = parse_definition(payload(first, second))
    assert definition.page_for("What do you think of this particular fruit") is None
    assert definition.page_for("Header " + first["questions"][0]["text"]["en_US"]).id == "p1"
    assert definition.page_for(first["questions"][0]["text"]["en_US"] + " " +
                               second["questions"][0]["text"]["en_US"]) is None
    first["questions"].append(question("extra", "Explain your selection"))
    definition = parse_definition(payload(first))
    assert definition.page_for(first["questions"][0]["text"]["en_US"]) is None


def test_duplicate_visible_page_prompts_are_not_guessed():
    definition = parse_definition(payload(page(), page("p2")))
    assert definition.page_for("Choose a fruit Apple Other") is None


def test_progression_uses_array_position_not_vendor_index():
    definition = parse_definition(payload(page(), page("p2", "Explain")))
    assert definition.progression("p1", set()) == "advance"
    assert definition.progression("p2", set()) == "final"
    assert definition.progression("missing", set()) == "unknown"


@pytest.mark.parametrize("condition, selected, expected", [
    ("any", {"p1q-a"}, "advance"), ("any", set(), "final"),
    ("all", {"p1q-a"}, "final"),
    ("all", {"p1q-a", "p1q-b"}, "advance"),
    ("equal", {"p1q-a", "p1q-b"}, "advance"),
    ("invented", set(), "unknown"),
])
def test_supported_trigger_conditions_and_unknown_fail_closed(condition, selected, expected):
    later = page("p2", "Explain", triggers=[
        {"condition": condition, "answers": ["p1q-a", "p1q-b"]}])
    definition = parse_definition(payload(page(), later))
    assert definition.progression("p1", selected) == expected


@pytest.mark.parametrize("trigger", [
    {"condition": "any", "answers": ["missing"]},
    {"condition": "any", "answers": []},
    {"condition": "any", "answers": ["p1q-a"], "type": "screenout"},
    {"condition": "any", "answers": ["p1q-a"], "operator": "not"},
])
def test_unverified_trigger_semantics_never_authorize_progression(trigger):
    definition = parse_definition(payload(page(), page("p2", "Explain", triggers=[trigger])))
    assert definition.progression("p1", {"p1q-a"}) == "unknown"


def test_future_answer_dependency_is_unknown_not_false():
    definition = parse_definition(payload(page(), page("p2", "Explain", triggers=[
        {"condition": "any", "answers": ["p2q-a"]}])))
    assert definition.progression("p1", set()) == "unknown"


def test_question_level_routing_is_not_silently_ignored():
    first = page()
    first["questions"][0]["triggers"] = [{"condition": "any", "answers": ["p1q-a"]}]
    definition = parse_definition(payload(first, page("p2", "Explain")))
    assert definition.progression("p1", {"p1q-a"}) == "unknown"


def test_ids_for_labels_are_scoped_to_page_and_question_not_global_text():
    definition = parse_definition(payload(page(), page("p2", "Explain")))
    assert definition.ids_for("p1", "p1q", ["Apple"]) == frozenset({"p1q-a"})
    assert definition.ids_for("p2", "p1q", ["Apple"]) is None
    assert definition.ids_for("p1", "p1q", ["missing"]) is None
    assert definition.progression("p1", {"foreign-id"}) == "unknown"


def test_duplicate_answer_labels_are_not_guessed():
    first = page()
    first["questions"][0]["answers"][1]["text"] = {"en_US": "Apple"}
    definition = parse_definition(payload(first))
    assert definition.ids_for("p1", "p1q", ["Apple"]) is None


def test_bounded_parser_rejects_huge_or_too_deep_payloads():
    assert parse_definition(payload(*[page(str(i)) for i in range(301)])) is None
    raw = payload(page())
    raw["questionnaire"]["data"]["pages"][0]["questions"][0]["text"]["en_US"] = "x" * 100_001
    assert parse_definition(raw) is None


def test_page_group_routing_and_dual_shapes_are_not_treated_as_linear():
    raw = payload(page())
    raw["questionnaire"]["data"]["page_groups"] = [{"pages": [page("p2")]}]
    assert parse_definition(raw) is None
    raw["questionnaire"]["data"].pop("pages")
    raw["questionnaire"]["data"]["page_groups"][0]["triggers"] = [{"condition": "any"}]
    assert parse_definition(raw).progression("p2", set()) == "unknown"
