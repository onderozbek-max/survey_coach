"""Synthetic participant actions, separate from capture and transport policy."""
from decimal import Decimal, ROUND_CEILING
from pathlib import Path

from .requirements import UnmetRequirement, placeholder_png, selection_minimum, synthetic_text


def _synthetic_png_payload(upload_dir: Path) -> dict:
    """Keep file bytes in memory: Chromium interception omits disk-backed parts."""
    image = placeholder_png(upload_dir)
    return {'name': image.name, 'mimeType': 'image/png', 'buffer': image.read_bytes()}


async def answer_groups(page, observation: dict, *, upload_dir: Path, feedback: str = '', skip_upload: bool = False) -> bool:
    text_count = sum(group['kind'] in {'text_short', 'text_long'} for group in observation['groups'])
    staged = False
    # The widget can remove/reset its file input after saving. Detect its container,
    # not just the input branch, or Add Media incorrectly creates an empty slot.
    redjade_media = await page.locator('[data-testid="media-uploader"]').count() > 0
    for group in observation['groups']:
        selected = {}
        for item in group['items']:
            if item['disabled']:
                continue
            locator = page.locator(f'[data-surveycoach-id="{item["id"]}"]')
            kind = group['kind']
            if item['type'] == 'file':
                if skip_upload or item.get('files'):
                    continue
                accept = item.get('accept', '').lower()
                if accept and not any(token.strip() in {'image/*', 'image/png', '.png', '*/*'} for token in accept.split(',')):
                    raise UnmetRequirement('Upload requires a format other than the synthetic PNG.')
                inline_media = await locator.evaluate("e => !!e.closest('[data-testid=media-uploader]')")
                payload = _synthetic_png_payload(upload_dir)
                if inline_media:
                    # This widget saves on upload. Its Add Media button creates a NEW
                    # empty answer; clicking it is not a commit and can require deletes.
                    try:
                        async with page.expect_response(
                            lambda response: response.request.method == 'POST' and
                            response.url.split('?', 1)[0].endswith('/file-proxy/attach-multipart'),
                            timeout=20000,
                        ) as pending:
                            await locator.set_input_files(payload)
                        response = await pending.value
                        if not response.ok:
                            raise UnmetRequirement('Media upload was rejected by the survey.')
                        await response.finished()
                    except UnmetRequirement:
                        raise
                    except Exception as error:
                        raise UnmetRequirement('Media upload did not finish within its bounded wait.') from error
                else:
                    await locator.set_input_files(payload)
                staged = True
                await page.wait_for_timeout(500)
            elif kind in {'single_choice', 'multi_choice', 'grid_single', 'grid_multi'}:
                key = item['row'] or item['name'] or 'group'
                target = selection_minimum(group, feedback) if kind in {'multi_choice', 'grid_multi'} else 1
                if selected.get(key, 0) >= target:
                    continue
                if not item['checked']:
                    if item['type'] in {'radio', 'checkbox'} and await locator.evaluate("e => e.tagName === 'INPUT'"):
                        await locator.check()
                    else:
                        await locator.click()
                selected[key] = selected.get(key, 0) + 1
            elif kind in {'text_short', 'text_long'}:
                scoped = item.get('feedback', '') or item.get('validation', '')
                value = synthetic_text(item, scoped or (feedback if text_count == 1 else ''))
                if item.get('value') != value:
                    await locator.fill('')
                    await locator.press_sequentially(value)
                    await page.wait_for_timeout(300)
            elif kind == 'numeric':
                low = Decimal(item['min'] or '1')
                high = Decimal(item['max'] or str(max(low, Decimal('10'))))
                step = Decimal(item.get('step') or '1') if item.get('step') != 'any' else Decimal('0.1')
                base = Decimal(item['min'] or '0')
                value = base + ((low - base) / step).to_integral_value(rounding=ROUND_CEILING) * step
                if step <= 0 or value > high:
                    raise UnmetRequirement('Numeric bounds have no supported valid value.')
                await locator.fill(str(value))
            elif kind == 'dropdown':
                usable = [option for option in item['options'] if option['value'] and not option['disabled']]
                if not usable:
                    raise UnmetRequirement('No usable dropdown option.')
                await locator.select_option(value=usable[0]['value'])
    # Some generic widgets stage a file and comment before an explicit commit.
    # RedJade's inline media-uploader is NOT one of those widgets.
    commit = page.get_by_role('button', name='Add Media', exact=True)
    if not redjade_media and not skip_upload and (staged or observation.get('uploads')) and await commit.count() == 1 and await commit.is_visible():
        try:
            await page.wait_for_function("() => [...document.querySelectorAll('button')].some(e => e.innerText.trim()==='Add Media' && !e.disabled)", timeout=10000)
        except Exception as error:
            raise UnmetRequirement('Media upload did not become ready within 10 seconds.') from error
        await commit.click()
        await page.wait_for_timeout(1000)
        return True
    return False


async def upload_from_button(page, observation: dict, upload_dir: Path) -> bool:
    """For apps which create the file input only when a labeled upload is clicked."""
    if any(item['type'] == 'file' for group in observation['groups'] for item in group['items']):
        return False
    buttons = observation.get('uploads', [])
    if len(buttons) != 1:
        return False
    button = buttons[0]
    # Camera capture requires actual media, not a file chooser; do not open device permissions.
    if button['label'].lower().startswith('take'):
        raise UnmetRequirement('Camera-only capture has no file-input alternative.')
    try:
        async with page.expect_file_chooser(timeout=2000) as pending:
            await page.locator(f'[data-surveycoach-id="{button["id"]}"]').click()
        chooser = await pending.value
        await chooser.set_files(_synthetic_png_payload(upload_dir))
        await page.wait_for_timeout(500)
        return True
    except Exception as error:
        raise UnmetRequirement('Upload control did not open a supported file chooser.') from error
