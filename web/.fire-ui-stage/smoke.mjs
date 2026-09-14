import { chromium } from 'playwright';
import assert from 'node:assert/strict';

const browser = await chromium.launch({channel: 'chrome', headless: true});
const errors = [];
try {
  for (const width of [390, 320, 1440]) {
    const page = await browser.newPage({viewport: {width, height: 900}});
    page.on('pageerror', e => errors.push(e.message));
    await page.goto('http://127.0.0.1:43187/#calc');
    await page.locator('#fire-age').waitFor();
    assert.equal(await page.locator('.fire__input-panel:visible').count(), 1);
    assert.equal(await page.locator('.fire__result-details').evaluate(e => e.open), width >= 992);
    assert.equal(await page.locator('.fire__products-more').evaluate(e => e.open), false);
    await page.locator('#fire-monthlySaving').fill('333');
    await page.locator('#fire-input-tab-1').click();
    await page.locator('#fire-children').fill('2');
    assert.equal(await page.locator('#fire-childCost').isVisible(), true);
    await page.locator('#fire-children').fill('0');
    assert.equal(await page.locator('#fire-childCost').isVisible(), false);
    await page.locator('#fire-input-tab-1').press('End');
    assert.equal(await page.locator('#fire-input-tab-2').getAttribute('aria-selected'), 'true');
    await page.locator('#fire-input-tab-2').press('Home');
    assert.equal(await page.locator('#fire-monthlySaving').inputValue(), '333');
    await page.locator('.fire__result-details').evaluate(e => {e.open = true;});
    await page.locator('.chart details').evaluate(e => {e.open = true;});
    await page.locator('#fire-monthlySaving').fill('334');
    assert.equal(await page.locator('.fire__result-details').evaluate(e => e.open), true);
    assert.equal(await page.locator('.chart details').evaluate(e => e.open), true);
    await page.reload();
    await page.locator('#fire-age').waitFor();
    assert.equal(await page.locator('#fire-monthlySaving').inputValue(), '334');
    const size = await page.evaluate(() => ({width: innerWidth, contentWidth: document.documentElement.scrollWidth, height: document.documentElement.scrollHeight}));
    assert.ok(size.contentWidth <= size.width, JSON.stringify(size));
    await page.screenshot({path: `.fire-ui-stage/fire-${width}.png`, fullPage: true});
    console.log(JSON.stringify({viewport: width, ...size, checks: 'passed'}));
    await page.close();
  }
  assert.deepEqual(errors, []);
} finally {
  await browser.close();
}
