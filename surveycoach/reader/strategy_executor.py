"""Execute a tiny action language against previously observed controls only."""
import asyncio
import re
from pathlib import Path

from .observe import OBSERVE
from .requirements import UnmetRequirement, synthetic_text
from .actions import _synthetic_png_payload
from .strategies import Strategy, catalog, descriptor


async def execute(page, plan: Strategy, initial: dict, upload_dir: Path) -> bool:
    baseline = catalog(initial)
    initial_state = initial['state_key']
    for action in plan.actions:
        if action.op == 'wait':
            await page.wait_for_timeout(action.milliseconds)
            continue
        if action.target >= len(baseline):
            raise UnmetRequirement('Strategy referenced an unobserved control.')
        intended = baseline[action.target]
        current = await page.evaluate(OBSERVE)
        matches = [entry for entry in catalog(current) if descriptor(entry) == descriptor(intended)]
        if len(matches) != 1:
            raise UnmetRequirement('Strategy control changed or is ambiguous.')
        entry = matches[0]
        locator = page.locator(f'[data-surveycoach-id="{entry["id"]}"]')
        if action.op == 'click':
            if entry['category'] not in {'nav', 'uploads', 'auxiliary'}:
                raise UnmetRequirement('Strategy cannot click an arbitrary answer control.')
            label = entry.get('label', '').lower()
            if not re.fullmatch(r'(?:next|continue|begin|start|submit\b.*|finish\b.*|complete\b.*|done\b.*|add media)', label):
                raise UnmetRequirement('Strategy requested an unsupported action; new capabilities require a reviewed executor change.')
            # No links: browser navigation remains controlled by the survey's buttons.
            if not await locator.evaluate("e => e.tagName === 'BUTTON' || (e.tagName === 'INPUT' && ['button','submit'].includes(e.type))"):
                raise UnmetRequirement('Strategy navigation must use observed buttons, not links.')
            await locator.click(timeout=3000)
        elif action.op == 'fill':
            if entry.get('kind') not in {'text_short', 'text_long', 'numeric'}:
                raise UnmetRequirement('Strategy can only fill supported synthetic answer fields.')
            if entry['kind'] == 'numeric':
                value = entry.get('min') or '1'
            else:
                minimum = max(1, entry.get('minlength', -1))
                maximum = entry.get('maxlength', -1)
                if action.length < minimum or (maximum >= 0 and action.length > maximum):
                    raise UnmetRequirement('Strategy text length violates observed constraints.')
                constraints = {**entry, 'minlength': action.length, 'maxlength': action.length}
                value = synthetic_text(constraints)
            await locator.fill('')
            await locator.press_sequentially(value)
            await page.wait_for_timeout(300)
        elif action.op == 'check':
            if entry.get('kind') not in {'single_choice', 'multi_choice', 'grid_single', 'grid_multi'}:
                raise UnmetRequirement('Strategy check target is not a choice.')
            if not entry.get('checked'):
                if await locator.evaluate("e => e.tagName === 'INPUT'"):
                    await locator.check()
                else:
                    await locator.click()
        elif action.op == 'select':
            options = entry.get('options', [])
            if action.option >= len(options) or options[action.option]['disabled']:
                raise UnmetRequirement('Strategy referenced an unavailable option.')
            await locator.select_option(value=options[action.option]['value'])
        elif action.op == 'upload_png':
            if entry.get('type') != 'file':
                raise UnmetRequirement('Strategy upload target is not a file input.')
            accept = entry.get('accept', '').lower()
            if accept and not any(token.strip() in {'image/png', 'image/*', '.png', '*/*'} for token in accept.split(',')):
                raise UnmetRequirement('Strategy upload does not accept the synthetic PNG.')
            await locator.set_input_files(_synthetic_png_payload(upload_dir))
        # Freshly observed IDs never carry over to the next action.
        await page.wait_for_timeout(100)
    for _ in range(20):
        current = await page.evaluate(OBSERVE)
        if progressed(initial, current):
            return True
        await asyncio.sleep(0.1)
    return False


def progressed(before: dict, after: dict) -> bool:
    """Do not teach from an error, modal or answer-dependent wording change."""
    if before['state_key'] == after['state_key'] or after.get('errors') or after.get('unsupported'):
        return False
    if not after.get('text', '').strip() or after['text'].strip().lower().rstrip('. …') in {'loading', 'please wait'}:
        return False
    if after.get('dialog'):
        return False
    if after.get('source_page_id') and after['source_page_id'] != before.get('source_page_id') and after['groups'] and after['nav']:
        return True
    if not after['groups'] and not after['nav']:
        return any(phrase in after['text'].lower() for phrase in ('thank you', 'response received', 'survey complete'))
    old = {(group.get('source_id'), group['prompt'], group['kind']) for group in before['groups']}
    new = {(group.get('source_id'), group['prompt'], group['kind']) for group in after['groups']}
    return bool(old and new and old.isdisjoint(new) and not after.get('unsupported'))
