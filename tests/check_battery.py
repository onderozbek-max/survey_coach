"""Synthetic surveys that, between them, make every deterministic check raise its findings.

One place for the trigger cases, so the copy contract tests (test_check_actions) can run over
the whole check set and fail loudly when a new finding never gets exercised.
"""
from dataclasses import replace

from builders import context, image, intro, page, question, scale, survey, thank_you

from surveycoach.checks import run_all
from surveycoach.snapshot import Media, Option, Question, Scale


def _wide(n: int, kind="single_choice", **extra):
    return question("w", "Which of these matter to you most?", kind, options=tuple(f"Reason {i}" for i in range(n)), **extra)


def _run(snapshot, calibrated=True):
    ctx = context(snapshot)
    ctx = replace(ctx, timing=ctx.timing.model_copy(update={"calibrated": calibrated}))
    return run_all(ctx)


def _many_text(count, intro_text, required=True):
    pages = [intro(intro_text)] + [
        page(i + 1, question(f"q{i}", "Tell us more", "text_long", options=(), required=required))
        for i in range(count)] + [thank_you()]
    return survey(*pages)


def _choice_images(sizes, shapes, labels=True):
    options = [Option(id=f"o{i}", label=f"Pic {i}" if labels else "",
                      media=image(natural=shapes[i], rendered=(sizes[i], sizes[i])))
               for i in range(len(sizes))]
    return Question(id="pic", text="Which picture do you like best?", kind="image_choice", required=True, options=options)


def surveys() -> dict:
    """name -> (snapshot, calibrated). Every one is deliberately flawed."""
    hard_text = ("To what extent do you consider that the aforementioned considerations regarding "
                 "organizational responsibilities substantially influence your overall satisfaction "
                 "with the comprehensive assortment of contemporary refrigerated alternatives?")
    q1 = ("How often do you purchase ready-to-heat or ready-to-cook meal solutions, such as prepared "
          "meals or meal kits, to enjoy at home?")
    content = survey(
        intro("Hello respondents \U0001F600\U0001F600 thanks for helping."),
        page(1, question("c1", "Why did you choose the item?", options=("Taste", "Price")),
             question("c2", "We want your PERSONAL view!!", options=("Yes", "No"))),
        page(2, question("c3", "Describe the viscosity of the sauce", "text_short", options=())),
        page(3, question("c4", hard_text, "text_short", options=())),
        page(4, question("c5", q1, "text_short", options=())),
        page(5, question("c6", "Which Of These Do You Like?", "multi_choice",
                         options=("Red \U0001F600", "blue", "Green"))),
        page(6, question("c7", "Do you click the button on the left?", options=("Yes", "No"))),
        page(7, question("c8", "Did you love it \U0001F600?", options=("Yes", "No"))),
        page(8, question("c9", "I always buy this. How about you?", options=("Yes", "No"))),
        thank_you("Thank you respondents!"),
        title="Help Pick Our Next Flavor")
    answers = survey(
        intro(), page(1, question("a1", "How long have you owned it?",
                                  options=("1 to 5 years", "5 to 10 years", "More than 10 years"))),
        page(2, question("a2", "How long did it take to arrive?", options=("1 to 2 hours", "2 to 3 hours", "4 to 5 hours"))),
        page(3, question("a3", "How good was it?", "rating", options=(), scale=scale(low=None, high=None))),
        page(4, question("a4", "How satisfied are you?", "rating", options=(),
                         scale=scale(low="Great", high=None, labels=("Great", "Good", "Fine", "Poor")))),
        page(5, question("a5", "How was the fit?", "rating", options=(),
                         scale=scale(labels=("Great", "Good", "Love it", "Fine", "Poor")))),
        page(6, question("a6", "How easy was it?", "rating", options=(), scale=scale(low="Extremely", high="Not at all"))),
        *[page(7 + i, question(f"ag{i}", f"The product is great, statement {i}.", "single_choice",
                               options=("Strongly agree", "Agree", "Disagree", "Strongly disagree")))
          for i in range(4)],
        thank_you())
    phone = survey(
        intro(),
        page(1, question("p1", " ".join(["word"] * 30) + "?", options=("Yes", "No"), options_below_fold=2)),
        page(2, question("p2", "Pick one", options=("A" * 80, "Short"))),
        page(3, _wide(10, "multi_choice")),
        page(4, question("p4", "Which one?", "dropdown", options=("One", "Two", "Three", "Four"))),
        page(5, question("p5", "Rate each", "grid_single", options=tuple(f"C{i}" for i in range(7)),
                         rows=[f"Row {i}" for i in range(7)], scale=Scale(points=7))),
        page(6, question("p6", "How likely are you to come back?", "rating", options=(), scale=Scale(points=11))),
        page(7, question("p7", "Tell us more...", "text_short", options=()), links_out=["https://example.com/x"]),
        page(8, question("p8", "Q8a", options=("Yes", "No")), question("p8b", "Q8b", options=("Yes", "No"))),
        thank_you())
    images = survey(
        intro(),
        page(1, question("i1", "Which looks best?", options=("A", "B")), ),
        page(2, question("i2", "Another one?", options=("A", "B"))),
        thank_you())
    images.pages[-1].media = [image(bytes=2_800_000), image(bytes=2_800_000)]
    images.pages[1].media = [image(natural=(1600, 600), rendered=(349, 131), bytes=650_000, alt="")]
    images.pages[2].media = [image(natural=(500, 500), rendered=(349, 349), alt="Small")]
    images.pages.insert(3, page(3, _choice_images([349] * 7, [(1000, 1000)] * 6 + [(1000, 500)])))
    images.pages.insert(4, page(4, _choice_images([80, 80], [(500, 500)] * 2)))
    images.pages.insert(5, page(5, _choice_images([349, 120], [(1000, 1000), (1000, 1000)], labels=False)))
    broken = Media(kind="image", element_id="hero", alt="Hero shot", loaded=False)
    images.pages[1].questions[0].media = [broken]
    grids = survey(intro(), *[page(i, question(f"g{i}", f"Rate set {i}", "grid_single", options=("Bad", "OK", "Good"),
                                                 rows=[f"Row {r}" for r in range(5)], scale=Scale(points=3)))
                              for i in range(1, 5)], thank_you())
    playful = survey(intro(), page(1, question("e1", "How was it?", options=("\U0001F600", "\U0001F610", "\U0001F61E"))),
                     thank_you(), survey_type="community_pulse")
    structure = {
        "no_intro": (survey(page(1, question()), thank_you()), True),
        "promise": (_many_text(12, "Thanks! This takes about 2 minutes."), True),
        "no_time_reward": (survey(intro("Welcome to our survey."), page(1, question()), thank_you()), True),
        "no_time_reward_uncalibrated": (survey(intro("Welcome to our survey."), page(1, question()), thank_you()), False),
        "reward_only": (survey(intro("This takes about 1 minute."), page(1, question()), thank_you()), True),
        "overrun": (_many_text(6, "Thanks! This takes about 3 minutes and you earn points."), False),
        "long": (_many_text(30, "This takes about 4 minutes and you earn points."), True),
        "screen_out": (survey(intro(), *[page(i, question(f"s{i}", "Tell us more", "text_long", options=(), required=True))
                                         for i in range(1, 13)], page(13, kind="screen_out", text="Sorry."), thank_you()), True),
        "placeholder": (survey(intro(), page(1, question("ph", "Insert question here")), thank_you()), True),
        "exclusive": (survey(intro(), page(1, Question(id="ex", text="What do you use?", kind="multi_choice", required=True,
                                                        options=[Option(id="x1", label="Soap"), Option(id="x2", label="None of these", is_exclusive=False)])),
                             thank_you()), True),
        "other_no_text": (survey(intro(), page(1, Question(id="ot", text="What do you use?", kind="single_choice", required=True,
                                                            options=[Option(id="y1", label="Soap"),
                                                                     Option(id="y2", label="Other (please specify)", is_other_with_text=False)])),
                                 thank_you()), True),
        "no_comment": (survey(intro(), page(1, question()), thank_you()), True),
        "optional_comment": (survey(intro(), page(1, question("cm", "Anything else?", "text_long", options=(), required=True)), thank_you()), True),
        "typing": (_many_text(5, "This takes about 5 minutes and you earn points."), True),
    }
    return {"grids": (grids, True), "playful": (playful, True), "content": (content, True), "answers": (answers, True), "phone": (phone, True),
            "images": (images, True), **structure}


def all_findings() -> list:
    """(survey name, Finding) for every finding any check raised on the battery."""
    return [(name, f) for name, (snapshot, calibrated) in surveys().items()
            for result in _run(snapshot, calibrated).values() for f in result.findings]
