"""No learned success from modals and no unrelated adaptive button actions."""
import asyncio
import pytest
from surveycoach.reader.strategy_executor import progressed, execute
from surveycoach.reader.observe import OBSERVE
from surveycoach.reader.strategies import Strategy, Action
from surveycoach.reader.requirements import UnmetRequirement


def test_new_id_on_upload_dialog_is_not_progression():
    before = {'state_key': 'old', 'source_page_id': 'survey', 'groups': [], 'nav': [], 'text': 'Question'}
    after = {'state_key': 'new', 'source_page_id': 'dialog', 'groups': [], 'nav': [],
             'text': 'Upload Successful', 'dialog': True, 'unsupported': True}
    assert not progressed(before, after)


@pytest.mark.parametrize('label', ['Reset survey', 'Withdraw response', 'Buy now'])
def test_executor_rejects_unrelated_observed_buttons(tmp_path, label):
    from playwright.async_api import async_playwright
    async def scenario():
        async with async_playwright() as driver:
            local = await driver.chromium.launch()
            page = await local.new_page()
            await page.set_content('<button>' + label + '</button>')
            observation = await page.evaluate(OBSERVE)
            with pytest.raises(UnmetRequirement):
                await execute(page, Strategy(actions=[Action(op='click', target=0)]), observation, tmp_path)
            await local.close()
    asyncio.run(scenario())
