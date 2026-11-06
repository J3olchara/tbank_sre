// Capture actual vmui query execution and real result bodies; requires Playwright.
const fs = require('node:fs');
const path = require('node:path');
const { chromium } = require('playwright');
(async () => {
  const root = path.resolve(__dirname, '..');
  const queries = JSON.parse(fs.readFileSync(path.join(root, 'homework/03/queries.json'), 'utf8'));
  const base = process.env.VL_URL || 'http://127.0.0.1:9428';
  const target = path.join(root, 'homework/03/screenshots');
  fs.mkdirSync(target, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const evidence = [];
  try {
    for (const item of queries) {
      const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, locale: 'en-US' });
      await page.goto(base + '/select/vmui/', { waitUntil: 'networkidle' });
      const hide = page.getByRole('button', { name: 'Hide filters', exact: true });
      if (await hide.count()) await hide.click();
      await page.locator('textarea').fill(item.query);
      const pending = page.waitForResponse(response =>
        new URL(response.url()).pathname === '/select/logsql/query' &&
        new URLSearchParams(response.request().postData() || '').get('query') === item.query);
      await page.getByRole('button', { name: 'Execute', exact: true }).click();
      const response = await pending;
      const body = await response.text();
      if (!response.ok()) throw new Error(body);
      const rows = body.trim().split('\n').filter(Boolean).map(line => JSON.parse(line));
      if (!rows.length) throw new Error('No data in ' + item.id);
      await page.getByText('JSON', { exact: true }).click();
      await page.waitForTimeout(700);
      await page.screenshot({ path: path.join(target, item.id + '.png') });
      evidence.push({ id: item.id, query: item.query, url: page.url(), status: response.status(), rows });
      console.log(item.id + ': executed in vmui, ' + rows.length + ' rows');
      await page.close();
    }
  } finally { await browser.close(); }
  const proof = path.join(root, 'artifacts/hw03');
  fs.mkdirSync(proof, { recursive: true });
  fs.writeFileSync(path.join(proof, 'vmui-queries.json'), JSON.stringify(evidence, null, 2));
})().catch(error => { console.error(error); process.exitCode = 1; });
