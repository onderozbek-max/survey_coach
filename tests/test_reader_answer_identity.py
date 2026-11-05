"""Every observed answer control keeps its own identity; only proven-same grid columns merge."""
from surveycoach.reader.extract import extract_page


def item(label, row="", name="", column=None, row_index=None):
    data = {"label": label, "row": row, "name": name}
    if column is not None:
        data["column"] = column
    if row_index is not None:
        data["row_index"] = row_index
    return data


def observation(kind, items, prompt="Choose one"):
    return {"title": "Synthetic", "text": prompt, "source_page_id": "p",
            "groups": [{"prompt": prompt, "kind": kind, "source_id": "q", "required": True, "items": items}],
            "media": [], "screenout": False}


def test_equal_label_choices_are_three_controls_with_three_ids():
    page = extract_page(observation("single_choice", [item("Same"), item("Same"), item("Other")]), 0)
    options = page.questions[0].options
    assert [o.label for o in options] == ["Same", "Same", "Other"]
    assert len({o.id for o in options}) == 3


def test_equal_label_multi_choice_keeps_every_control():
    page = extract_page(observation("multi_choice", [item("None"), item("None")]), 0)
    assert [o.label for o in page.questions[0].options] == ["None", "None"]


def test_option_ids_are_stable_across_identical_reads():
    items = [item("Same"), item("Same")]
    first = extract_page(observation("single_choice", items), 0).questions[0].options
    again = extract_page(observation("single_choice", items), 1).questions[0].options
    assert [o.id for o in first] == [o.id for o in again]


def test_grid_columns_repeat_per_row_but_merge_by_column_identity():
    items = [item("Bad", "Texture", "t", 1, 1), item("Good", "Texture", "t", 2, 1),
             item("Bad", "Flavor", "f", 1, 2), item("Good", "Flavor", "f", 2, 2)]
    question = extract_page(observation("grid_single", items), 0).questions[0]
    assert [o.label for o in question.options] == ["Bad", "Good"]
    assert question.rows == ["Texture", "Flavor"]


def test_grid_columns_with_equal_labels_are_distinct_columns():
    items = [item("Same", "Row", "r", 1, 1), item("Same", "Row", "r", 2, 1),
             item("Same", "Other", "o", 1, 2), item("Same", "Other", "o", 2, 2)]
    question = extract_page(observation("grid_single", items), 0).questions[0]
    assert [o.label for o in question.options] == ["Same", "Same"]


def test_grid_rows_with_equal_labels_are_distinct_rows():
    items = [item("Yes", "Item", "a", 1, 1), item("No", "Item", "a", 2, 1),
             item("Yes", "Item", "b", 1, 2), item("No", "Item", "b", 2, 2)]
    question = extract_page(observation("grid_single", items), 0).questions[0]
    assert question.rows == ["Item", "Item"]
    assert [o.label for o in question.options] == ["Yes", "No"]


def test_grid_without_column_identity_falls_back_to_position_within_row():
    items = [item("Same", "Row", "r"), item("Same", "Row", "r"),
             item("Same", "Other", "o"), item("Same", "Other", "o")]
    question = extract_page(observation("grid_single", items), 0).questions[0]
    assert [o.label for o in question.options] == ["Same", "Same"]
