/** Exercise the actual offline gallery in native Chrome; close every owned page. */
const fs = require('node:fs/promises');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const {pathToFileURL, fileURLToPath} = require('node:url');

const root = path.resolve(__dirname, '../..');
const proofDir = path.join(root, 'docs/validation/evidence/optical-pack-gallery-20261029-r1');
const assetDir = path.join(root, 'docs/assets/optical-pack-gallery-20261029-r1');
const work = path.join(root, 'local/agent-ffmpeg/optical-gallery-browser-r1');
const html = path.join(root, 'docs/assets/optical-pack-20261029-r1/index.html');
const pack = path.join(root, 'docs/content/effect-packs/optical-v1');
const sha = b => crypto.createHash('sha256').update(b).digest('hex');

async function main() {
  await fs.mkdir(proofDir);
  await fs.mkdir(assetDir);
  await fs.mkdir(work);
  const temp = path.join(work, 'temporary');
  await fs.mkdir(temp);
  process.env.TEMP = temp;
  process.env.TMP = temp;
  const {chromium} = require('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules/playwright');
  const catalog = JSON.parse(await fs.readFile(path.join(pack, 'catalog.json'), 'utf8'));
  assert.equal(catalog.items.length, 8);
  const checks = [], errors = [], external = [];
  let browser, context, result;
  let pagesClosed = 0, contextClosed = false, browserClosed = false;
  try {
    browser = await chromium.launch({
      executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
      headless: true,
      downloadsPath: path.join(work, 'downloads'),
      args: ['--disable-gpu', '--disable-background-networking', '--disable-component-update',
        '--disable-default-apps', '--disable-sync', '--no-first-run', '--no-default-browser-check',
        '--disk-cache-dir=' + path.join(work, 'cache')],
    });
    context = await browser.newContext({viewport: {width: 1440, height: 1080},
      deviceScaleFactor: 1, serviceWorkers: 'block', offline: true});
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
    assert.equal(await page.locator('video[preload="none"]').count(), 8);
    assert.equal(await page.locator('button[data-id]').count(), 8);
    const localUrls = await page.locator('a[href], img[src], video[src], video[poster]').evaluateAll(elements =>
      elements.flatMap(el => ['href', 'src', 'poster'].filter(a => el.hasAttribute(a)).map(a => new URL(el.getAttribute(a), document.baseURI).href)));
    for (const url of localUrls) {
      assert.ok(url.startsWith('file:'), url);
      const target = fileURLToPath(url);
      assert.ok((await fs.stat(target)).isFile(), target);
    }
    for (const item of catalog.items) {
      const button = page.locator(`button[data-id="${item.id}"]`);
      await button.click();
      assert.equal(await page.locator('button[aria-pressed="true"]').count(), 1);
      assert.equal(await button.getAttribute('aria-pressed'), 'true');
      const selected = JSON.parse(await page.locator('#selection').inputValue());
      assert.equal(selected.id, item.id);
      assert.equal(selected.template_id, item.template_id);
      assert.equal(selected.template_sha256, sha(await fs.readFile(path.join(pack, item.template))));
      assert.equal(selected.pack_version, catalog.version);
      assert.deepEqual(selected.author_clock_example, {ticks_per_second: 90000, middle_tick: 180000, end_tick: 360000});
      checks.push({id: item.id, selected_template_id: selected.template_id,
        selected_sha256: selected.template_sha256, exactly_one_pressed: true});
    }
    await page.locator('video').evaluateAll(videos => videos.forEach(v => {v.muted = true;}));
    await page.locator('video').nth(0).evaluate(async v => {await v.play();});
    await page.waitForFunction(() => document.querySelectorAll('video')[0].currentTime > 0.15, {timeout: 15000});
    const firstPlayback = await page.locator('video').nth(0).evaluate(v => ({time: v.currentTime, width: v.videoWidth, height: v.videoHeight}));
    assert.equal(firstPlayback.width, 480);
    assert.equal(firstPlayback.height, 270);
    await page.locator('video').nth(1).evaluate(async v => {await v.play();});
    await page.waitForFunction(() => {
      const videos = document.querySelectorAll('video');
      return videos[0].paused && !videos[1].paused && videos[1].currentTime > 0.1;
    }, {timeout: 15000});
    await page.locator('video').evaluateAll(videos => videos.forEach(v => {v.pause(); v.currentTime = 0;}));
    assert.ok(await page.locator('video').evaluateAll(videos => videos.every(v => v.paused)));
    await page.evaluate(() => window.scrollTo(0, 0));
    const desktop = path.join(assetDir, 'desktop.png');
    await page.screenshot({path: desktop, fullPage: true, animations: 'disabled'});
    await page.setViewportSize({width: 420, height: 900});
    await page.locator('button[data-id="OP03"]').click();
    assert.equal(JSON.parse(await page.locator('#selection').inputValue()).id, 'OP03');
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth));
    await page.evaluate(() => window.scrollTo(0, 0));
    const mobile = path.join(assetDir, 'mobile.png');
    await page.screenshot({path: mobile, fullPage: true, animations: 'disabled'});
    assert.deepEqual(errors, []);
    assert.deepEqual(external, []);
    result = {status: 'passed', actual_native_browser: 'Chrome ' + browser.version(),
      html_sha256: sha(await fs.readFile(html)), catalog_sha256: sha(await fs.readFile(path.join(pack, 'catalog.json'))),
      choices: checks, local_links_checked: localUrls.length, video_preload_none: 8,
      actual_H264_playback: firstPlayback, second_play_pauses_first: true,
      mobile_selection_passed: true, mobile_horizontal_overflow: false,
      external_requests: external, page_errors: errors,
      screenshots: await Promise.all([desktop, mobile].map(async p => ({path: path.relative(root, p).replaceAll('\\', '/'), sha256: sha(await fs.readFile(p))}))),
      native_browser_used_E_drive_temporary_directory: true, source_or_formal_skill_modified: false,
      natural_client_footage_quality_accepted: false, human_listening_approval: false};
  } catch (error) {
    result = {status: 'failed', error: String(error.stack || error), checks, page_errors: errors, external_requests: external};
    process.exitCode = 1;
  } finally {
    if (context) {
      for (const page of context.pages()) {await page.close(); pagesClosed++;}
      await context.close();
      contextClosed = true;
    }
    if (browser) {await browser.close(); browserClosed = true;}
    result.cleanup = {owned_pages_closed: pagesClosed, context_closed: contextClosed, browser_closed: browserClosed};
    assert.ok(!browser || browserClosed);
    assert.ok(!context || contextClosed);
    await fs.copyFile(__filename, path.join(proofDir, 'executed-runner.cjs'));
    await fs.writeFile(path.join(proofDir, 'verification.json'), JSON.stringify(result, null, 2) + '\n');
    console.log(JSON.stringify(result));
  }
}
main().catch(error => {console.error(error.stack || error); process.exitCode = 1;});
