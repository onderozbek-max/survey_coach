from surveycoach.snapshot import Media, Option, Page, Question, SurveySnapshot
from surveycoach.timing import TimingConstants, estimate, parse_promised_minutes


def snapshot_of(*questions: Question, intro_words: int = 0) -> SurveySnapshot:
    pages = [Page(id="p0", position=0, kind="intro", intro_text=" ".join(["word"] * intro_words))]
    pages += [Page(id=f"p{i + 1}", position=i + 1, kind="question", questions=[q]) for i, q in enumerate(questions)]
    return SurveySnapshot(title="t", pages=pages)


def choice(qid="q", words=10, options=4, kind="single_choice") -> Question:
    return Question(id=qid, text=" ".join(["w"] * words), kind=kind,
                    options=[Option(id=str(i), label="x") for i in range(options)])


def test_reading_time_scales_with_words():
    constants = TimingConstants()
    short = estimate(snapshot_of(choice(words=10)), constants).total_seconds
    long = estimate(snapshot_of(choice(words=110)), constants).total_seconds
    assert round(long - short, 1) == round(100 * constants.seconds_per_word, 1)


def test_grid_costs_per_row():
    grid = lambda rows: Question(id="g", text="Rate", kind="grid_single", rows=[f"r{i}" for i in range(rows)])
    four = estimate(snapshot_of(grid(4))).total_seconds
    eight = estimate(snapshot_of(grid(8))).total_seconds
    constants = TimingConstants()
    # Each extra row needs both label reading and an answer interaction.
    assert round(eight - four, 1) == round(4 * (constants.grid_row_seconds + constants.seconds_per_word), 1)


def test_open_text_costs_more_than_a_choice():
    text = Question(id="t", text="Why?", kind="text_long")
    assert estimate(snapshot_of(text)).total_seconds > estimate(snapshot_of(choice(words=1, options=2))).total_seconds


def test_images_add_viewing_time():
    plain = choice()
    pictured = choice().model_copy(update={"media": [Media()]})
    assert estimate(snapshot_of(pictured)).total_seconds > estimate(snapshot_of(plain)).total_seconds


def test_fatigue_zone_follows_cumulative_time():
    questions = [Question(id=f"q{i}", text="Tell us more", kind="text_long") for i in range(12)]
    zones = [p.fatigue for p in estimate(snapshot_of(*questions)).pages if p.kind == "question"]
    assert zones[0] == "fresh"
    assert zones[-1] == "high"
    assert "fatigue_builds" in zones


def test_minutes_property():
    timing = estimate(snapshot_of(choice()))
    assert timing.minutes == round(timing.total_seconds / 60, 1)


def test_parse_promised_minutes():
    cases = {
        "This takes about 5 minutes.": 5,
        "It should take 10-12 minutes": 12,
        "Less than 3 min of your time": 3,
        "around 7.5 minutes": 7.5,
        "5 to 8 minutes": 8,
        "It takes a few minutes": None,
        "": None,
    }
    for text, expected in cases.items():
        assert parse_promised_minutes(text) == expected, text
