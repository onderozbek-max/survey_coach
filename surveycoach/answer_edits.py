"""Turn verified additive answer bundles into small, explicit authoring actions."""
import re


def _normalized(text):
    return ' '.join(text.replace('’', "'").split()).casefold()


def answer_addition(finding, snapshot):
    if not snapshot or finding.get('edit_kind') == 'add_answer':
        return dict(finding)
    questions = [q for p in snapshot.get('pages', [])
                 if not finding.get('page_id') or p['id'] == finding['page_id']
                 for q in p.get('questions', []) if q['id'] == finding.get('question_id')]
    if len(questions) != 1 or questions[0].get('kind') not in {'single_choice', 'multi_choice', 'dropdown'}:
        return dict(finding)
    question = questions[0]
    existing = [_normalized(o['label']) for o in question.get('options', [])]
    if not existing:
        return dict(finding)
    candidates = [finding.get('suggested_text'), *[o['text'] for o in finding.get('options', [])]]
    additions = []
    for text in candidates:
        if not text:
            continue
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        # Only recognize a bundle retaining every existing answer, unchanged and
        # in order, followed by one new answer. Never infer a fix from its headline.
        if len(lines) != len(existing) + 2:
            continue
        if [_normalized(line) for line in lines[1:-1]] != existing:
            continue
        if _normalized(lines[-1]) in existing:
            continue
        if _normalized(lines[-1]) not in {_normalized(value) for value in additions}:
            additions.append(lines[-1])
    if not additions:
        return dict(finding)
    options = [{'label':'Add answer option', 'text':text} for text in additions]
    explanation = finding.get('explanation', '')
    instruction = 'Keep the question and existing answers unchanged. Add the answer option below in RedJade.'
    # A nonparticipation/none answer contradicts positive selections in a select-all.
    negative = all(re.search(r"\b(?:did not|didn't|haven't|have not|none|no purchase|not applicable)\b",
                             _normalized(text)) for text in additions)
    if question['kind'] == 'multi_choice' and negative:
        instruction += ' Make this answer exclusive so it cannot be selected with the other answers. Verify that behavior in RedJade.'
    return dict(finding, edit_kind='add_answer', current_text=question['text'], structural=True,
                suggested_text=additions[0], options=options,
                explanation=f'{explanation}\n\n{instruction}'.strip())
