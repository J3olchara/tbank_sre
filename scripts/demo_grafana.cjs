// Real headed Grafana, real datasource responses and real kubectl commands.
const fs = require('node:fs');
const path = require('node:path');
const {execFileSync} = require('node:child_process');
const {chromium} = require('playwright');
const root = path.resolve(__dirname, '..');
const base = process.env.GRAFANA_URL || 'http://127.0.0.1:3000';
const state = process.env.RECORDING_STATE_DIR;
const evidence = {events:[], responses:[]};
const screenshots = path.join(root,'homework/07/screenshots');
const pause = ms => new Promise(resolve => setTimeout(resolve,ms));
let sequence = 0;
function save() {
  fs.writeFileSync(path.join(root,'artifacts/hw07/grafana-recording.json'),JSON.stringify(evidence,null,2));
}
function mark(event, details={}) {
  evidence.events.push({event,timestamp:Date.now()/1000,...details}); save(); console.log(event);
}
function raise(pattern) {
  const ids=execFileSync('xdotool',['search','--onlyvisible','--name',pattern],{encoding:'utf8'}).trim().split('\n');
  execFileSync('xdotool',['windowraise',ids[ids.length-1]]);
  execFileSync('xdotool',['windowfocus',ids[ids.length-1]]);
}
async function command(action) {
  mark('command: '+action); raise('HW07 Control');
  fs.writeFileSync(path.join(state,'command.tmp'),JSON.stringify({sequence:++sequence,action}));
  fs.renameSync(path.join(state,'command.tmp'),path.join(state,'command.json'));
  const deadline=Date.now()+180000;
  while (true) {
    const done=path.join(state,'done.json');
    if (fs.existsSync(done)) {
      const result=JSON.parse(fs.readFileSync(done));
      if (result.sequence===sequence) {
        if (result.code) throw new Error('Terminal command failed: '+action);
        break;
      }
    }
    if (Date.now()>deadline) throw new Error('Terminal command timed out');
    await pause(250);
  }
  await pause(2500);
}
function phase(name) {
  execFileSync('python3',['scripts/check_slo.py','--phase',name,'--timeout','30'],{cwd:root,stdio:'pipe',timeout:40000});
  const sample=JSON.parse(fs.readFileSync(path.join(root,'artifacts/hw05',name+'.json')));
  fs.writeFileSync(path.join(root,'artifacts/hw07','phase-'+name+'.json'),JSON.stringify(sample,null,2));
  mark('verified: '+name,{values:sample.values});
}
(async()=>{
  fs.mkdirSync(screenshots,{recursive:true});
  const browser=await chromium.launch({headless:false,args:['--window-position=0,0','--window-size=1920,1200']});
  const context=await browser.newContext({viewport:null,locale:'en-US'});
  const page=await context.newPage();
  const failures=[],pending=new Set();
  page.on('response', response=>{
    if (new URL(response.url()).pathname!=='/api/ds/query') return;
    const task=(async()=>{
      const body=await response.json();
      const query=response.request().postDataJSON();
      const results=Object.values(body.results || {});
      if (!response.ok() || !results.length || results.some(r=>r.error || (r.status || 200)>=400)) {
        throw new Error('Grafana datasource query failed: '+JSON.stringify(body).slice(0,400));
      }
      evidence.responses.push({timestamp:Date.now()/1000,status:response.status(),
        queries:query.queries.map(q=>({refId:q.refId,expr:q.expr})),
        frames:results.reduce((n,r)=>n+(r.frames || []).length,0)});
      save();
    })().catch(error=>{
      // Navigating away can cancel an in-flight auto-refresh request.
      if (!/No resource|No data found|No resource with given identifier|body is unavailable|Protocol error|Target.*closed/i.test(error.message)) failures.push(error.message);
    });
    pending.add(task); task.finally(()=>pending.delete(task));
  });
  async function open(uid) {
    await page.goto(base+'/d/'+uid+'?from=now-10m&to=now&refresh=5s',{waitUntil:'domcontentloaded'});
    await page.getByText(uid==='taskboard-overview'?'Taskboard · текущее состояние':'General Counters, CPU, Memory and File Descriptor Stats',{exact:true}).waitFor();
    await pause(5000);
    await page.bringToFront(); raise('Grafana');
  }
  async function show(event,title,seconds=5,file=null) {
    await page.getByText(title,{exact:true}).first().evaluate(el=>el.scrollIntoView({block:'start'}));
    await page.bringToFront(); raise('Grafana');
    mark(event);
    await pause(seconds*1000);
    if (file) await page.screenshot({path:path.join(screenshots,file)});
  }
  try {
    const secret=JSON.parse(execFileSync('kubectl',['--context',process.env.PROFILE || 'tbank-sre-hw02','-n','monitoring','get','secret','grafana-admin','-o','json'],{encoding:'utf8'})).data;
    const login=await context.request.post(base+'/login',{data:{user:Buffer.from(secret['admin-user'],'base64').toString(),password:Buffer.from(secret['admin-password'],'base64').toString()}});
    if (!login.ok()) throw new Error('Grafana login failed');
    await command('status');
    await open('taskboard-overview');
    await show('app-overview','Taskboard · текущее состояние',8,'overview.png');
    await show('app-runtime','Go runtime / ресурсы · детализация по репликам',8,'runtime.png');
    await show('app-sla','SLA пробера · UI + чтение задач через Service',8,'sla.png');
    phase('healthy');
    // Upload the saved upstream adaptation through Grafana's native Import UI.
    await page.goto(base+'/dashboard/import');
    await pause(1000);
    await page.locator('input[type=file]').setInputFiles(path.join(root,'deploy/grafana/dashboards/postgres.json'));
    await page.getByRole('button',{name:/^Import/}).waitFor();
    const rootFolder=page.getByRole('button',{name:'Dashboards',exact:true});
    if (await rootFolder.isVisible()) {
      await rootFolder.click();
      await page.getByText('SRE',{exact:true}).click();
    }
    await page.bringToFront(); raise('Grafana');
    await pause(4000);
    await page.screenshot({path:path.join(screenshots,'postgres-import.png')});
    await page.getByRole('button',{name:/^Import/}).click();
    await page.waitForURL(/\/d\/taskboard-postgres/);
    mark('pg-import');
    await pause(6000);
    await show('pg-overview','General Counters, CPU, Memory and File Descriptor Stats',6,'postgres.png');
    await show('pg-database','Database Stats',8,'postgres-database.png');
    await command('slow');
    await open('taskboard-overview');
    await show('slow','Taskboard · текущее состояние',42,'slow.png');
    phase('slow');
    await command('errors');
    await open('taskboard-overview');
    await show('errors-red','Taskboard · текущее состояние',25);
    await show('errors-sla','SLA пробера · UI + чтение задач через Service',40,'errors.png');
    phase('errors');
    await command('healthy');
    await open('taskboard-overview');
    await show('recovery-red','Taskboard · текущее состояние',30);
    await show('recovery-runtime','Go runtime / ресурсы · детализация по репликам',15);
    await show('recovery-sla','SLA пробера · UI + чтение задач через Service',80,'recovery.png');
    phase('recovery');
    await command('summary');
    await open('taskboard-postgres');
    await show('pg-final','Database Stats',5);
    await Promise.all([...pending]);
    if (failures.length) throw new Error(failures.join('\n'));
    if (!evidence.responses.length) throw new Error('No real Grafana responses');
    mark('complete');
  } catch (error) {
    await page.screenshot({path:path.join(root,'artifacts/hw07/browser-error.png')}).catch(()=>{});
    fs.writeFileSync(path.join(root,'artifacts/hw07/browser-error.txt'),await page.locator('body').innerText().catch(()=>''));
    throw error;
  } finally {
    await browser.close();
  }
})().catch(error=>{console.error(error);process.exitCode=1;});
