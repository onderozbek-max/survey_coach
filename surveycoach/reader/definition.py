"""Passive RedJade definition adapter. Never requests, answers, or advances anything."""
from copy import deepcopy
from dataclasses import dataclass, field
from html import unescape
import re

from surveycoach.snapshot import Option, Page, Question, SurveySnapshot

KINDS = {
    "radio": "single_choice", "checkbox": "multi_choice", "dropdown": "dropdown",
    "text": "text_short", "textarea": "text_long", "number": "numeric",
    "date": "date", "info": "info",
}


@dataclass(frozen=True)
class DefinitionAnswer:
    id: str
    text: str


@dataclass(frozen=True)
class DefinitionQuestion:
    id: str
    text: str
    answers: tuple[DefinitionAnswer, ...]


@dataclass(frozen=True)
class DefinitionPage:
    id: str
    questions: tuple[DefinitionQuestion, ...]
    # None means unsupported semantics, NOT an unconditional page.
    triggers: tuple[tuple[str, tuple[str, ...]], ...] | None


def _normalized(text: str) -> str:
    return " ".join(text.casefold().split())


@dataclass(frozen=True)
class Definition:
    """Immutable routing evidence; never permission for a network write.

    Only page-level any/all/equal answer gates are understood. Unknown gates,
    group routing and question routing must stop progression. The caller still
    owns transport policy and must verify selections against the rendered DOM.
    """
    pages: tuple[DefinitionPage, ...]
    routing_supported: bool = True

    def page_for(self, visible_text: str) -> DefinitionPage | None:
        """Require every full prompt and one unique candidate; no prefix guesses."""
        visible = " " + _normalized(visible_text) + " "
        matches = [p for p in self.pages if p.questions and all(
            q.text and " " + _normalized(q.text) + " " in visible for q in p.questions)]
        return matches[0] if len(matches) == 1 else None

    def ids_for(self, page_id: str, question_id: str,
                labels: list[str]) -> frozenset[str] | None:
        """Resolve only unique labels in the specified page AND question."""
        questions = [q for p in self.pages if p.id == page_id
                     for q in p.questions if q.id == question_id]
        if len(questions) != 1:
            return None
        selected = set()
        for label in labels:
            matches = [a.id for a in questions[0].answers
                       if _normalized(a.text) == _normalized(label)]
            if len(matches) != 1:
                return None
            selected.add(matches[0])
        return frozenset(selected)

    def progression(self, page_id: str, selected_ids: set[str]) -> str:
        """advance/final/unknown; unknown MUST stop, never click Next.

        This is not an attestation of safe live progression. Supply verified
        current selections after answering, not proposed or historical picks.
        """
        positions = [i for i, p in enumerate(self.pages) if p.id == page_id]
        if not self.routing_supported or len(positions) != 1:
            return "unknown"
        position = positions[0]
        known = {a.id for p in self.pages[:position + 1]
                 for q in p.questions for a in q.answers}
        if not selected_ids <= known:
            return "unknown"
        states = []
        for page in self.pages[position + 1:]:
            if page.triggers is None:
                return "unknown"
            satisfied = not page.triggers
            for condition, wanted in page.triggers:
                if not set(wanted) <= known:
                    return "unknown"
                satisfied |= (bool(set(wanted) & selected_ids) if condition == "any"
                              else set(wanted) <= selected_ids)
            states.append(satisfied)
        return "advance" if any(states) else "final"


def parse_definition(payload: object, *, locale: str = "en_US") -> Definition | None:
    """Parse bounded known envelopes, without retaining participant/API fields.

    No recursive searching, filesystem, network or expression evaluation.
    Malformed input returns None; unsupported routing remains explicit.
    """
    if not isinstance(payload, dict):
        return None
    payload = payload.get("response", payload)
    if not isinstance(payload, dict) or not isinstance(payload.get("questionnaire"), dict):
        return None
    data = payload["questionnaire"].get("data")
    if not isinstance(data, dict) or ("pages" in data) == ("page_groups" in data):
        return None
    routing_keys = ("conditions", "triggers", "routing")
    supported = not any(data.get(k) for k in routing_keys)
    pages = data.get("pages")
    if "page_groups" in data:
        groups = data["page_groups"]
        if not isinstance(groups, list) or len(groups) > 300:
            return None
        pages = []
        for group in groups:
            if not isinstance(group, dict) or not isinstance(group.get("pages"), list):
                return None
            supported &= not any(group.get(k) for k in routing_keys)
            if len(pages) + len(group["pages"]) > 300:
                return None
            pages.extend(group["pages"])
    if not isinstance(pages, list) or not 1 <= len(pages) <= 300:
        return None

    def identifier(value):
        if not isinstance(value, (str, int)) or isinstance(value, bool):
            raise ValueError
        value = str(value)
        if not value or len(value) > 256:
            raise ValueError
        return value

    def wording(value):
        if isinstance(value, dict):
            value = value.get(locale)
        if not isinstance(value, str) or len(value) > 100_000:
            raise ValueError
        return " ".join(unescape(re.sub(r"<[^>]+>", " ", value)).split())

    def sequence(value, limit):
        if not isinstance(value, list) or len(value) > limit:
            raise ValueError
        return value

    def gates(raw):
        if not isinstance(raw, list) or len(raw) > 300:
            return None
        result = []
        for gate in raw:
            if (not isinstance(gate, dict) or set(gate) - {"condition", "answers"}
                    or gate.get("condition") not in {"any", "all", "equal"}):
                return None
            answers = gate.get("answers")
            if not isinstance(answers, list) or not 1 <= len(answers) <= 1000:
                return None
            result.append((gate["condition"], tuple(identifier(a) for a in answers)))
        return tuple(result)

    normalized = []
    seen_pages, seen_questions, seen_answers = set(), set(), set()

    def unique(value, seen):
        value = identifier(value)
        if value in seen:
            raise ValueError
        seen.add(value)
        return value

    try:
        for page in pages:
            if not isinstance(page, dict):
                return None
            pid = unique(page.get("id"), seen_pages)
            supported &= not any(page.get(k) for k in ("conditions", "routing"))
            questions = []
            for question in sequence(page.get("questions"), 300):
                if not isinstance(question, dict):
                    return None
                qid = unique(question.get("cid", question.get("id")), seen_questions)
                supported &= not any(question.get(k) for k in routing_keys)
                answers = []
                for answer in sequence(question.get("answers", []), 1000):
                    if not isinstance(answer, dict):
                        return None
                    aid = unique(answer.get("id"), seen_answers)
                    answers.append(DefinitionAnswer(aid, wording(answer.get("text"))))
                questions.append(DefinitionQuestion(qid, wording(question.get("text")), tuple(answers)))
            normalized.append(DefinitionPage(pid, tuple(questions), gates(page.get("triggers", []))))
    except (ValueError, TypeError):
        return None
    return Definition(tuple(normalized), bool(supported))


def find_definition(payload: object) -> dict | None:
    """Only the known root or response.questionnaire.data.pages envelope is accepted."""
    if not isinstance(payload, dict):
        return None
    payload = payload.get("response", payload)
    if not isinstance(payload, dict):
        return None
    questionnaire = payload.get("questionnaire")
    if (isinstance(questionnaire, dict) and isinstance(questionnaire.get("data"), dict)
            and isinstance(questionnaire["data"].get("pages"), list)):
        return questionnaire
    return None


@dataclass
class DefinitionRead:
    snapshot: SurveySnapshot
    raw: dict
    conditions: dict = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    wording_complete: bool = True
    # Only real, unique source IDs may establish rendered/definition identity.
    known_page_ids: set[str] = field(default_factory=set)
    known_question_ids: set[str] = field(default_factory=set)


def adapt_definition(questionnaire: dict, *, source_url: str = "", locale: str = "en_US") -> DefinitionRead:
    """Preserve source order, wording, answer IDs and raw conditions, without evaluating paths.

    Unsupported types retain wording/options as unknown. Missing translations fall back
    explicitly, never silently to empty English. Malformed shapes reject the definition.
    """
    if (not isinstance(questionnaire, dict) or not isinstance(questionnaire.get("data"), dict)
            or not isinstance(questionnaire["data"].get("pages"), list)
            or len(questionnaire["data"]["pages"]) > 300):
        raise ValueError("Malformed or oversized definition")
    result = DefinitionRead(SurveySnapshot(title="", source_url=source_url, pages=[]), deepcopy(questionnaire))

    def warn(message):
        if message not in result.warnings:
            result.warnings.append(message)

    def wording(value, location):
        if isinstance(value, dict):
            if not isinstance(value.get(locale), str):
                alternatives = sorted(k for k, v in value.items() if isinstance(v, str) and v.strip())
                chosen = alternatives[0] if alternatives else None
                warn(f"Missing {locale} translation at {location}; " +
                     (f"using {chosen}." if chosen else "no wording available."))
                result.wording_complete = False
                value = value.get(chosen, "")
            else:
                value = value[locale]
        if not isinstance(value, str):
            value = ""
            result.wording_complete = False
            warn(f"No supported wording at {location}.")
        if len(value) > 100_000:
            raise ValueError("Oversized definition wording")
        # Strip markup before decoding so literal &lt;words&gt; are not removed.
        value = re.sub(r"<\s*(?:br\s*/?|/p|/div)\s*>", "\n", value, flags=re.I)
        return unescape(re.sub(r"<[^>]+>", "", value)).strip()

    pages = questionnaire["data"]["pages"]
    seen_pages, seen_questions = set(), set()
    result.snapshot.title = wording(questionnaire.get("title", questionnaire.get("questionnaire_type", "")), "title")
    for position, page in enumerate(pages):
        if (not isinstance(page, dict) or not isinstance(page.get("questions"), list)
                or len(page["questions"]) > 1000):
            raise ValueError("Malformed definition page")
        source_pid = page.get("id", page.get("cid"))
        pid = str(source_pid) if source_pid is not None else f"definition-page-{position}"
        if pid in seen_pages:
            raise ValueError("Duplicate definition page ID")
        seen_pages.add(pid)
        if source_pid is not None:
            result.known_page_ids.add(pid)
        page_conditions = {k: deepcopy(page[k]) for k in ("triggers", "conditions") if k in page}
        result.conditions[pid] = {"page": page_conditions, "questions": {}}
        questions = []
        for index, question in enumerate(page["questions"]):
            if not isinstance(question, dict):
                raise ValueError("Malformed definition question")
            source_qid = question.get("cid", question.get("id"))
            qid = str(source_qid) if source_qid is not None else f"{pid}-question-{index}"
            if qid in seen_questions:
                raise ValueError("Duplicate definition question ID")
            seen_questions.add(qid)
            if source_qid is not None:
                result.known_question_ids.add(qid)
            conditions = {k: deepcopy(question[k]) for k in ("triggers", "conditions") if k in question}
            result.conditions[pid]["questions"][qid] = conditions
            kind = KINDS.get(question.get("question_type"), "unknown")
            if kind == "unknown":
                warn(f"Unsupported question type at {qid}; wording and answers retained, behavior unverified.")
            answers = question.get("answers", [])
            if (not isinstance(answers, list) or len(answers) > 1000
                    or any(not isinstance(a, dict) for a in answers)):
                raise ValueError("Malformed definition answers")
            options = [Option(id=str(answer.get("id", f"{qid}-answer-{n}")),
                              label=wording(answer.get("text"), f"{qid} answer {n}"))
                       for n, answer in enumerate(answers)]
            if len({o.id for o in options}) != len(options):
                raise ValueError("Duplicate definition answer ID")
            prompt = wording(question.get("text"), qid)
            if not prompt or any(not option.label for option in options):
                result.wording_complete = False
                warn(f"Missing question or answer wording at {qid}.")
            if not isinstance(question.get("required"), bool):
                warn(f"Requiredness is unknown at {qid}; definition did not specify it.")
            questions.append(Question(
                id=qid, text=prompt, kind=kind,
                help_text=wording(question.get("help_text", ""), f"{qid} help"),
                required=question["required"] if isinstance(question.get("required"), bool) else None,
                options=options,
                conditional=any(bool(value) for value in [*page_conditions.values(), *conditions.values()]),
            ))
        result.snapshot.pages.append(Page(id=pid, position=position,
            kind="question" if questions else "info", questions=questions,
            text=wording(page.get("text", ""), pid)))
    if not pages:
        result.wording_complete = False
        warn("Definition contains no pages; no complete wording claim is possible.")
    warn("Definition wording is not visual verification: media, layout, and all paths remain unverified.")
    return result


def apply_definition(result, definition: DefinitionRead) -> None:
    """Prefer complete definition wording; merge visual fields only with explicit IDs."""
    coverage = result.coverage
    rendered = result.snapshot
    snapshot = definition.snapshot.model_copy(deep=True)
    merged = set()
    for observed in rendered.pages:
        targets = [p for p in snapshot.pages if p.id == observed.id and p.id in definition.known_page_ids]
        if len(targets) != 1 or not observed.questions:
            continue
        target = targets[0]
        known = {q.id: q for q in target.questions if q.id in definition.known_question_ids}
        ids = [q.id for q in observed.questions]
        if len(set(ids)) != len(ids) or not all(qid in known for qid in ids):
            continue
        target.media = observed.media
        for question in observed.questions:
            destination = known[question.id]
            # Definition remains authoritative for wording, answers and conditions.
            # Definition wording and answers stay authoritative; a visible Optional label
            # (rendered evidence) may only fill a requiredness the definition left unknown.
            if destination.required is None:
                destination.required = question.required
            for key in ("media", "fits_one_screen", "options_below_fold"):
                setattr(destination, key, getattr(question, key))
        merged.add(target.id)
    result.snapshot = snapshot
    result.definition = definition.raw
    coverage.definition_available = True
    coverage.definition_wording_complete = definition.wording_complete
    coverage.pages_defined = len(snapshot.pages)
    coverage.questions_defined = len(snapshot.all_questions())
    coverage.definition_conditions = definition.conditions
    coverage.rendered_definition_pages = sorted(merged)
    coverage.warnings = [w for w in coverage.warnings if not w.startswith("No definition/API")]
    coverage.warnings.extend(definition.warnings)
    if not merged:
        coverage.warnings.append("Definition-only snapshot: no rendered page and question IDs were verified; captures are separate evidence.")
