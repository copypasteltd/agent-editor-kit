/** Actual offline N002 gallery: stable selections, keyboard, screenshots, cleanup. */
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const {pathToFileURL, fileURLToPath} = require('node:url');
const root = path.resolve(__dirname, '../..');
const sha = b => crypto.createHash('sha256').update(b).digest('hex');

async function main() {
  const html = path.join(root, 'docs/assets/optical-n002-20261029-r1/index.html');
  const publication = JSON.parse(await fs.readFile(path.join(root, 'docs/validation/evidence/optical-n002-publication-20261029-r1/verification.json')));
  assert.equal(publication.status, 'published-and-documented');
  assert.equal(sha(await fs.readFile(html)), publication.actual_gallery_html_sha256);
  const proof = path.join(root, 'docs/validation/evidence/optical-n002-gallery-20261029-r1');
  const assets = path.join(root, 'docs/assets/optical-n002-gallery-20261029-r1');
  const work = path.join(root, 'local/agent-ffmpeg/optical-n002-browser-r1');
  for (const folder of [proof, assets, work]) await fs.mkdir(folder);
  process.env.TEMP = work;
  process.env.TMP = work;
  const {chromium} = require('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
  const catalog = JSON.parse(await fs.readFile(path.join(root, 'docs/content/effect-packs/optical-v1/catalog.json')));
  const errors = [], external = [], selections = [];
  let browser, context, result, closedPages = 0;
  try {
    browser = await chromium.launch({executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe', headless: true,
      downloadsPath: path.join(work, 'downloads'), args: ['--disable-gpu', '--disable-background-networking',
        '--disable-component-update', '--disable-sync', '--no-first-run', '--disk-cache-dir=' + path.join(work, 'cache')]});
    context = await browser.newContext({viewport: {width: 1440, height: 1080}, offline: true, serviceWorkers: 'block'});
    await context.route('**/*', route => {
      const url = route.request().url();
      if (url.startsWith('file:') || url.startsWith('data:')) return route.continue();
      external.push(url);
      return route.abort();
    });
    const page = await context.newPage();
    page.on('pageerror', e => errors.push(String(e)));
    await page.goto(pathToFileURL(html).href, {waitUntil: 'load'});
    assert.equal(await page.locator('article').count(), 8);
    const links = await page.locator('a[href],img[src]').evaluateAll(elements => elements.map(el =>
      new URL(el.getAttribute(el.tagName === 'A' ? 'href' : 'src'), document.baseURI).href));
    for (const url of links) {
      assert.ok(url.startsWith('file:'));
      assert.ok((await fs.stat(fileURLToPath(url))).isFile());
    }
    for (const item of catalog.items) {
      await page.locator(`button[data-id="${item.id}"]`).click();
      const selection = JSON.parse(await page.locator('#selection').inputValue());
      assert.equal(selection.id, item.id);
      assert.equal(selection.template_id, item.template_id);
      assert.equal(selection.template_sha256, item.sha256);
      assert.equal(selection.preview_source, 'N002-user-supplied');
      assert.equal(selection.preview_frame, 24);
      assert.equal(await page.locator('button[aria-pressed="true"]').count(), 1);
      selections.push(selection);
    }
    await page.waitForFunction(() => [...document.querySelectorAll('article img')].every(i => i.complete && i.naturalWidth === 480));
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({path: path.join(assets, 'desktop.png'), fullPage: true, animations: 'disabled'});
    await page.setViewportSize({width: 420, height: 900});
    const first = page.locator('button[data-id="OP01"]');
    await first.focus();
    await first.press('Enter');
    assert.equal(JSON.parse(await page.locator('#selection').inputValue()).id, 'OP01');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({path: path.join(assets, 'mobile.png'), fullPage: true, animations: 'disabled'});
    assert.deepEqual(errors, []);
    assert.deepEqual(external, []);
    result = {status: 'passed', actual_native_browser: 'Chrome ' + browser.version(), choices: selections,
      html_sha256: sha(await fs.readFile(html)), local_targets_checked: links.length,
      actual_images_loaded: 8, mobile_keyboard_Enter_selection: true, mobile_horizontal_overflow: false,
      page_errors: errors, external_requests: external, native_E_drive_temporary_directory: true,
      screenshots: await Promise.all(['desktop.png', 'mobile.png'].map(async n => ({
        path: 'docs/assets/optical-n002-gallery-20261029-r1/' + n, sha256: sha(await fs.readFile(path.join(assets, n)))}))),
      human_quality_accepted: false};
  } catch (error) {
    result = {status: 'failed', error: String(error.stack || error), choices: selections};
    process.exitCode = 1;
  } finally {
    if (context) {
      for (const page of context.pages()) {await page.close(); closedPages++;}
      await context.close();
    }
    if (browser) await browser.close();
    result.cleanup = {owned_pages_closed: closedPages, context_closed: !!context, browser_closed: !!browser && !browser.isConnected()};
    await fs.copyFile(__filename, path.join(proof, 'executed-runner.cjs'));
    await fs.writeFile(path.join(proof, 'verification.json'), JSON.stringify(result, null, 2) + '\n');
    console.log(JSON.stringify(result));
  }
}
main().catch(error => {console.error(error.stack || error); process.exitCode = 1;});
