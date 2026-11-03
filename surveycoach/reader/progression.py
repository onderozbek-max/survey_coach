"""Observe-answer-validate-repair loop with strict local budgets."""
from pathlib import Path

from .actions import answer_groups, upload_from_button
from .observe import OBSERVE
from .requirements import UnmetRequirement
from .rules import LIMITS


async def advance(page, observation: dict, *, controls, participate: bool, slow: int, upload_dir: Path) -> str:
    """Return advanced, same_page_change or blocked; never count retries as pages."""
    current = observation
    if not participate and (current.get('uploads') or any(
        item['type'] == 'file' for group in current['groups'] for item in group['items']
    )):
        raise UnmetRequirement('Synthetic uploads require approved participant mode.')
    feedback = ''
    uploaded = False
    for attempt in range(LIMITS['repair_attempts']):
        if not uploaded:
            uploaded = await upload_from_button(page, current, upload_dir)
        current = await page.evaluate(OBSERVE)
        committed = await answer_groups(page, current, upload_dir=upload_dir, feedback=feedback, skip_upload=uploaded)
        uploaded = uploaded or any(item['type']=='file' for group in current['groups'] for item in group['items'])
        revealed = await page.evaluate(OBSERVE)
        if revealed['state_key'] != current['state_key'] and not committed:
            return 'same_page_change'
        nav = controls(revealed, participate=participate)
        if len(nav) != 1:
            if attempt == LIMITS['repair_attempts'] - 1:
                return 'blocked'
            current = revealed
            feedback = ' '.join(revealed.get('errors', []))
            await page.wait_for_timeout(500)
            continue
        await page.locator(f'[data-surveycoach-id="{nav[0]["id"]}"]').click()
        try:
            await page.wait_for_function(
                'old => { const current=(' + OBSERVE + ')(); return current.text.trim() && '
                '!/^(loading[. …]*|please wait[. …]*)$/i.test(current.text.trim()) && '
                '!current.errors.length && '
                'current.state_key !== old; }',
                arg=revealed['state_key'], timeout=2000 * slow)
            await page.wait_for_timeout(100)
            # Validation can arrive after a state-key change (including prompt text).
            settled = await page.evaluate(OBSERVE)
            if settled.get('errors'):
                current = settled
                feedback = ' '.join(settled.get('errors', []))
                continue
            return 'advanced'
        except Exception:
            current = await page.evaluate(OBSERVE)
            errors = current.get('errors', [])
            invalid = [item.get('validation', '') for group in current['groups'] for item in group['items']]
            feedback = ' '.join(errors + invalid)
            # No new actionable evidence: do not submit the same invalid answers again.
            if not feedback or attempt == LIMITS['repair_attempts'] - 1:
                return 'blocked'
    raise UnmetRequirement('Recovery attempt limit reached.')
