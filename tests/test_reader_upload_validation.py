"""Upload validation is interaction feedback, never a successful next screen."""
import asyncio
from pathlib import Path

from surveycoach.reader.actions import answer_groups
from surveycoach.reader.observe import OBSERVE
from surveycoach.reader.progression import advance
from surveycoach.reader.session import progression_controls


def test_validation_that_changes_prompt_does_not_advance(tmp_path):
    from playwright.async_api import async_playwright

    async def scenario():
        async with async_playwright() as driver:
            browser = await driver.chromium.launch()
            page = await browser.new_page()
            await page.set_content('''<fieldset><legend>Upload a photo</legend>
                <label>Photo<input type="file" accept="image/png"></label></fieldset>
                <div id="feedback"></div><button onclick="
                document.querySelector('legend').textContent='Please correct the following errors: Upload a photo Media is required';
                document.querySelector('#feedback').innerHTML='<p role=alert>Media is required</p>'">Next</button>''')
            observed = await page.evaluate(OBSERVE)
            outcome = await advance(page, observed, controls=progression_controls,
                                    participate=True, slow=1, upload_dir=tmp_path)
            assert outcome == 'blocked'
            await browser.close()
    asyncio.run(scenario())


def test_saved_inline_media_never_clicks_add_media_after_native_input_disappears(tmp_path):
    from playwright.async_api import async_playwright

    async def scenario():
        async with async_playwright() as driver:
            browser = await driver.chromium.launch()
            page = await browser.new_page()
            await page.set_content('''<fieldset><legend>Photo</legend>
                <div data-testid="media-uploader"><p>Upload successful</p>
                <button onclick="window.extra=true">Add Media</button></div></fieldset>''')
            observed = await page.evaluate(OBSERVE)
            # Some uploader states expose an upload affordance after resetting the file input.
            observed['uploads'] = [{'id': 'saved-upload', 'label': 'Upload photo'}]
            await answer_groups(page, observed, upload_dir=tmp_path)
            assert await page.evaluate('window.extra === true') is False
            await browser.close()
    asyncio.run(scenario())
