// Actual headed vmui, real kubectl commands in xterm and real TSDB responses.
const fs = require('node:fs');
const path = require('node:path');
const { execFileSync } = require('node:child_process');
const { chromium } = require('playwright');
const root = path.resolve(__dirname, '..');
const state = process.env.RECORDING_STATE_DIR;
const base = process.env.VM_URL || 'http://127.0.0.1:8428';
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const data = JSON.parse(fs.readFileSync(path.join(root, 'homework/05/queries.json')));
let sequence = 0;
const events = [], responses = [];
function saveProof() {
  fs.writeFileSync(path.join(root,'artifacts/hw05/vmui-recording.json'),JSON.stringify({events,responses},null,2));
}
function mark(event) { events.push({ event, timestamp: Date.now()/1000 }); saveProof(); console.log(event); }
function raise(pattern) {
  const ids = execFileSync('xdotool', ['search', '--onlyvisible', '--name', pattern], {encoding:'utf8'}).trim().split('\n');
  execFileSync('xdotool', ['windowraise', ids[ids.length-1]]);
  execFileSync('xdotool', ['windowfocus', ids[ids.length-1]]);
}
async function command(action) {
  mark('command: ' + action);
  raise('HW05 Control');
  const request = {sequence: ++sequence, action};
  const tmp = path.join(state, 'command.tmp');
  fs.writeFileSync(tmp, JSON.stringify(request));
  fs.renameSync(tmp, path.join(state, 'command.json'));
  const deadline = Date.now() + 180000;
  while (true) {
    const file = path.join(state, 'done.json');
    if (fs.existsSync(file)) {
      const result = JSON.parse(fs.readFileSync(file));
      if (result.sequence === sequence) {
        if (result.code) throw new Error('Terminal command failed: ' + action);
        break;
      }
    }
    if (Date.now() > deadline) throw new Error('Terminal timed out');
    await pause(250);
  }
  await pause(2500);
}
function url(id) {
  if (id === 'compliance') {
    const expr = 'label_set((' + data.demo_sla_compliance + '), "series", "ALL 4 SLA checks (demo 1m): 100=pass, 0=breach")';
    return base + '/vmui/?' + new URLSearchParams({'g0.expr':expr,'g0.range_input':'5m','g0.step_input':'5s'});
  }
  return data.indicators.find(x => x.id === id).demo_vmui_url.replace('http://127.0.0.1:8428', base);
}
function checkPhase(phase) {
  const output = execFileSync('python3', ['scripts/check_slo.py','--phase',phase,'--timeout','20'], {cwd:root, encoding:'utf8', timeout:30000});
  mark('verified: ' + phase);
  console.log(output);
}
(async () => {
  const browser = await chromium.launch({headless:false, args:['--window-position=0,0','--window-size=1920,1200']});
  const page = await browser.newPage({viewport:null, locale:'en-US'});
  const pending = new Set();
  page.on('response', response => {
    if (!new URL(response.url()).pathname.endsWith('/api/v1/query_range')) return;
    const task = (async () => {
      const body = await response.json();
      if (!response.ok() || body.status !== 'success' || !body.data.result.length) throw new Error('vmui query failed');
      responses.push({timestamp:Date.now()/1000,status:response.status(),query:response.request().postData(),result:body.data.result});
      saveProof();
    })();
    pending.add(task); task.finally(() => pending.delete(task)).catch(() => {});
  });
  const screenshots = path.join(root, 'homework/05/screenshots');
  fs.mkdirSync(screenshots, {recursive:true});
  const intermediate = path.join(root, 'artifacts/hw05/screenshots');
  fs.mkdirSync(intermediate, {recursive:true});
  async function show(id, phase, seconds) {
    mark(phase + ': ' + id);
    const count = responses.length;
    const response = page.waitForResponse(r => new URL(r.url()).pathname.endsWith('/api/v1/query_range'));
    await page.goto(url(id), {waitUntil:'networkidle'});
    await response;
    await page.getByRole('button',{name:'Settings',exact:true}).click();
    await page.getByPlaceholder('{{label_name}}',{exact:true}).fill('{{series}}');
    await page.getByPlaceholder('Ungrouped',{exact:true}).click();
    await page.getByText('Ungrouped',{exact:true}).click();
    await page.getByRole('button',{name:'close',exact:true}).click();
    // Set a relative range and enable the native five-second auto-refresh.
    await page.getByRole('button',{name:'time range controls'}).click();
    await page.getByText('Last 5 minutes',{exact:true}).click();
    const auto = page.getByRole('button',{name:/Auto-refresh control/});
    if ((await auto.getAttribute('aria-label')).includes('Off')) {
      await auto.click();
      await page.getByText('5s',{exact:true}).last().click();
    }
    await page.bringToFront(); raise('VMUI');
    await page.mouse.wheel(0,1800);
    await pause(seconds * 1000);
    await Promise.all([...pending]);
    const latest = responses[responses.length-1];
    if (responses.length === count || !latest.result.length) throw new Error('No real chart samples');
    if (id !== 'compliance' && latest.result.length !== 3) throw new Error('SLI, SLO and SLA must all be visible');
    await page.screenshot({path:path.join(phase === 'final' ? screenshots : intermediate, phase + '-' + id + '.png')});
  }
  try {
    await command('status');
    for (const id of ['availability','probe','compliance']) await show(id,'healthy',3);
    checkPhase('healthy');
    await command('slow');
    await show('latency','slow',45);
    checkPhase('slow');
    await show('compliance','slow',5);
    await command('errors');
    await show('availability','errors',18);
    await show('creation','errors',18);
    await show('probe','errors',25);
    checkPhase('errors');
    await show('compliance','errors',5);
    await command('healthy');
    await show('availability','recovery',20);
    await show('creation','recovery',15);
    await show('probe','recovery',90);
    checkPhase('recovery');
    await page.screenshot({path:path.join(screenshots,'final-probe.png')});
    await show('compliance','final',5);
    await show('availability','final',4);
    await show('latency','final',4);
    await show('creation','final',4);
    await command('summary');
    await Promise.all([...pending]);
    saveProof();
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
