"""Run real commands in the recorded terminal; forward only loopback ports."""
import os
from pathlib import Path
import shlex
import subprocess
import time
from urllib.request import urlopen

state = Path(os.environ['RECORDING_STATE_DIR'])
profile = os.environ.get('PROFILE', 'tbank-sre-hw02')
k = 'kubectl --context ' + shlex.quote(profile)
vm = 'http://127.0.0.1:18428'
processes = []

def section(title):
    print('\033[2J\033[H\033[1;36m' + title + '\033[0m\n', flush=True)
    time.sleep(3)

def command(text, pause=4):
    print('\033[1;32m$ \033[0m', end='', flush=True)
    for character in text:
        print(character, end='', flush=True)
        time.sleep(0.012)
    print(flush=True)
    subprocess.run(['bash', '-o', 'pipefail', '-c', text], check=True)
    time.sleep(pause)

def forward(text, log_name, url):
    print('$ ' + text, flush=True)
    with (state / log_name).open('w') as log:
        process = subprocess.Popen(shlex.split(text), stdout=log, stderr=subprocess.STDOUT)
    processes.append(process)
    for _ in range(40):
        if process.poll() is not None:
            raise RuntimeError((state / log_name).read_text())
        try:
            with urlopen(url, timeout=2):
                print((state / log_name).read_text(), flush=True)
                time.sleep(3)
                return
        except OSError:
            time.sleep(1)
    raise RuntimeError('Port-forward did not become ready')

def query(expression, pause=6):
    command('curl --fail --silent --get --data-urlencode ' + shlex.quote('query=' + expression) +
            ' ' + vm + '/api/v1/query | python3 scripts/format_vm_query.py', pause)

try:
    section('SRE / Домашняя работа 04 — VictoriaMetrics и метрики Taskboard')
    command('helm --kube-context ' + shlex.quote(profile) + ' list -n monitoring')
    command(k + ' -n monitoring get pods,svc,pvc', 7)
    command(k + ' -n taskboard-lab get pods', 5)
    section('1. Доступ к VictoriaMetrics и внутреннему порту метрик приложения')
    forward(k + ' -n monitoring port-forward svc/vm-single 18428:8428 --address=127.0.0.1',
            'vm.log', vm + '/health')
    forward(k + ' -n taskboard-lab port-forward deployment/taskboard 18082:8080 19092:9090 --address=127.0.0.1',
            'app.log', 'http://127.0.0.1:18082/healthz')
    command('curl --fail --silent -H ' + shlex.quote('Accept: application/openmetrics-text; version=1.0.0') +
            ' http://127.0.0.1:19092/metrics | grep -E ' + shlex.quote('^(go_goroutines |go_memstats_alloc_bytes |process_cpu_seconds_total |# EOF)'), 6)
    section('2. Бизнес-операции: CRUD и точная проверка успешных счётчиков')
    command('TASKBOARD_URL=http://127.0.0.1:18082 TASKBOARD_METRICS_URL=http://127.0.0.1:19092 make integration', 5)
    command('VM_URL=' + vm + ' python3 scripts/check_monitoring.py --replicas 3', 5)
    section('3. Данные уже в TSDB: таргеты, Go runtime и PostgreSQL')
    query('up')
    query('go_goroutines{job="taskboard"}')
    query('pg_up{job="postgres"}')
    query('pg_stat_database_xact_commit{job="postgres",datname="taskboard"}')
    section('4. Пять бизнес-метрик, сохранённых в VictoriaMetrics')
    query('sum by (__name__) ({job="taskboard",__name__=~"taskboard_(tasks_.*|task_lists_viewed)_total"})', 8)
    section('5. Service discovery: новая реплика обнаруживается автоматически')
    command(k + ' -n taskboard-lab scale deployment/taskboard --replicas=4')
    command(k + ' -n taskboard-lab rollout status deployment/taskboard --timeout=120s')
    command('VM_URL=' + vm + ' python3 scripts/check_monitoring.py --replicas 4', 5)
    query('count(up{job="taskboard"})', 7)
    section('6. Статус scraping и возврат к трём репликам')
    command('curl --fail --silent ' + vm + '/targets', 8)
    command(k + ' -n taskboard-lab scale deployment/taskboard --replicas=3')
    command('VM_URL=' + vm + ' python3 scripts/check_monitoring.py --replicas 3', 5)
    print('\nГотово: runtime + PostgreSQL + 5 бизнес-метрик, динамический discovery.', flush=True)
    time.sleep(5)
finally:
    for process in processes:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=15)
