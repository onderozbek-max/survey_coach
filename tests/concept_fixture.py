"""Synthetic concept test mirroring the structure of a real one, with invented product copy.

Welcome, one warm-up, a concept with its interest question, three repeated tray blocks (an
add-to-cart question, then a "Yes, please!" follow-up with ten select-all answers including
"Something else (please specify)"), a near pre/post interest question, a wrap-up and a thank-you
image. Requiredness is unknown and nothing records which answers the reader chose.
"""
from builders import image, intro, page, question, survey, thank_you
from surveycoach.snapshot import Option, Question, Scale

CONCEPT = ("Alright, here is our idea. The Sunrise Skillet Kit has everything for an easy breakfast "
           "at home: eggs, potatoes, peppers and a smoky seasoning packet. Imagine a warm skillet "
           "on the table in ten minutes, with almost no cleanup afterwards.")
TRAY = "Tray {n}: the Sunrise Skillet Kit with {flavor}. It serves four and costs $12.98."
FLAVORS = ("chorizo", "mushroom", "sweet potato")
YES_PLEASE = ("Cheesy goodness", "Easy to make", "Great price", "Looks tasty", "Right portion",
              "Fresh ingredients", "Fun to share", "Good for breakfast", "Different from what I eat",
              "Something else (please specify)")


def _page_text(body: str, q: Question) -> str:
    options = "\n".join(o.label for o in q.options)
    return f"{body}\n{q.text}\n{options}".strip()


def _block(position: int, n: int) -> list:
    q_cart = question(f"cart{n}", "Would you add this tray to your cart?", options=("Yes", "No"),
                      required=None)
    q_why = Question(id=f"why{n}", kind="multi_choice", required=None,
                     text="What about this tray has you saying 'Yes, please!'?",
                     options=[Option(id=f"why{n}-o{i}", label=label) for i, label in enumerate(YES_PLEASE)])
    body = TRAY.format(n=n, flavor=FLAVORS[n - 1])
    return [page(position, q_cart, text=_page_text(body, q_cart)), page(position + 1, q_why)]


def concept_survey(survey_type: str = "services_concept"):
    warm = question("warm", "How often do you cook breakfast at home?", required=None,
                    options=("Daily", "Weekly", "Rarely"))
    interest = question("interest", "How interested are you in this kit?", kind="rating", required=None,
                        options=(), scale=Scale(points=5, low_label="Not at all", high_label="Extremely"))
    after = question("after", "Now that you have seen a few ideas, how interested are you overall?",
                     kind="rating", required=None, options=(),
                     scale=Scale(points=5, low_label="Not at all", high_label="Extremely"))
    refer = question("refer", "Would you buy this skillet kit for your family?", options=("Yes", "No"),
                     required=None)
    comment = question("comment", "Anything else to tell us?", kind="text_long", options=(), required=None)
    pages = [intro("Welcome! Thanks for helping shape our breakfast ideas. This takes about 6 minutes."),
             page(1, warm),
             page(2, interest, text=_page_text(CONCEPT, interest))]
    for n in (1, 2, 3):
        pages.extend(_block(3 + 2 * (n - 1), n))
    pages += [page(9, after), page(10, refer), page(11, comment),
              thank_you("Thank you for sharing your thoughts with Member's Mark!", position=12)]
    pages[-1].media = [image()]
    return survey(*pages, survey_type=survey_type, title="Sunrise Skillet Concept Test")


def question_ids(snapshot) -> dict:
    """page id -> question ids, for asserting where items point."""
    return {p.id: [q.id for q in p.questions] for p in snapshot.pages}
