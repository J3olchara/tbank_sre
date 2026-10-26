// Actual headed Chromium interaction, captured by ffmpeg from the X display.
const { chromium } = require('playwright');
const { execFileSync } = require('node:child_process');
const path = require('node:path');
const state = process.env.RECORDING_STATE_DIR;
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
async function click(locator) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  const x = Math.round(box.x + box.width / 2), y = Math.round(box.y + box.height / 2);
  // Move the visible system pointer, so the screencast shows each action.
  execFileSync('xdotool', ['mousemove', String(x), String(y)]);
  await pause(700); await locator.click(); await pause(1300);
}
(async () => {
  const browser = await chromium.launch({headless:false, args:['--window-position=0,0','--window-size=1440,900']});
  try {
    const page = await browser.newPage({viewport:null, locale:'ru-RU'});
    page.on('dialog', dialog => dialog.accept());
    await page.goto(process.env.TASKBOARD_URL || 'http://127.0.0.1:18080', {waitUntil:'networkidle'});
    await pause(3500);
    await click(page.getByLabel('Название'));
    await page.getByLabel('Название').pressSequentially('Проверить minikube', {delay:100});
    await click(page.getByLabel('Описание'));
    await page.getByLabel('Описание').pressSequentially('Приложение работает в Kubernetes. Три реплики Go, общая БД PostgreSQL.', {delay:55});
    await click(page.getByLabel('Статус'));
    await page.getByLabel('Статус').selectOption('doing'); await pause(1500);
    await click(page.getByRole('button', {name:'Сохранить', exact:true}));
    const card = page.locator('article').filter({has:page.getByRole('heading', {name:'Проверить minikube', exact:true})});
    await card.waitFor(); await pause(3500);
    await click(card.getByRole('button', {name:'Изменить'}));
    await page.getByLabel('Статус').selectOption('done'); await pause(2500);
    await click(page.getByRole('button', {name:'Сохранить', exact:true}));
    await pause(3000); await page.reload({waitUntil:'networkidle'}); await pause(3000);
    if (!(await card.innerText()).includes('Готово')) throw new Error('Updated task did not persist');
    await page.screenshot({path:path.join(state, 'ui-complete.png')});
    await click(card.getByRole('button', {name:'Удалить'}));
    await card.waitFor({state:'detached'}); await pause(4500);
    console.log('UI CRUD verified in headed Chromium');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
