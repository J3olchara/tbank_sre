// Screenshots of the running services; no mocked responses or page rewriting.
const { chromium } = require('playwright');
const fs = require('node:fs/promises');
const path = require('node:path');

(async () => {
  const phase = process.argv[2];
  if (!['healthy', 'slow', 'errors', 'runtime', 'recovery'].includes(phase)) throw Error('Unknown phase');
  const root = path.resolve(__dirname, '..');
  const output = path.join(root, 'homework/06/screenshots');
  await fs.mkdir(output, { recursive: true });
  const browser = await chromium.launch({ headless: true, args: ['--no-sandbox'] });
  try {
    const page = await browser.newPage({ viewport: { width: 1600, height: 1000 }, timezoneId: 'Europe/Moscow' });
    const pages = [
      ['rules', (process.env.VMALERT_URL || 'http://127.0.0.1:18880') + '/vmalert/groups'],
      ['alertmanager', (process.env.ALERTMANAGER_URL || 'http://127.0.0.1:19093') + '/#/alerts'],
      ['notifications', (process.env.ALERT_INBOX_URL || 'http://127.0.0.1:18085') + '/'],
    ];
    const evidence = [];
    for (const [name, url] of pages) {
      if (phase === 'healthy' && name !== 'rules') continue;
      const response = await page.goto(url, { waitUntil: 'networkidle' });
      if (response.status() !== 200) throw Error(`Page failed: ${url}`);
      if (name === 'rules') await page.getByText('Expand All', { exact: true }).click();
      if (name === 'alertmanager') {
        const expand = page.getByText('Expand all groups', { exact: true });
        if (await expand.isVisible()) await expand.click();
      }
      const text = await page.locator('body').innerText();
      if (name !== 'alertmanager' && !text.includes('Taskboard')) throw Error('Expected taskboard UI');
      const file = `${phase}-${name}.png`;
      await page.screenshot({ path: path.join(output, file), fullPage: true });
      evidence.push({ url: page.url(), status: response.status(), file, captured_at: new Date().toISOString(), text });
    }
    await fs.writeFile(path.join(root, `artifacts/hw06/${phase}-screenshots.json`), JSON.stringify(evidence, null, 2) + '\n');
    console.log(`Captured ${phase}: ${evidence.length} real UI screenshots`);
  } finally {
    await browser.close();
  }
})().catch(error => { console.error(error); process.exitCode = 1; });
