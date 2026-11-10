"""Run the commands shown in the recorded xterm."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import time

state=Path(os.environ['RECORDING_STATE_DIR'])
profile=os.environ.get('PROFILE','tbank-sre-hw02')
last=-1
print('Домашняя работа 07 · Grafana\nОжидание демонстрации…',flush=True)
commands={
    'status':[
        ['helm','list','--kube-context',profile,'-n','monitoring'],
        ['kubectl','--context',profile,'-n','monitoring','get','pods,svc'],
        ['kubectl','--context',profile,'-n','taskboard-lab','get','pods'],
    ],
    'slow':[['make','slo-mode','MODE=slow']],
    'errors':[['make','slo-mode','MODE=errors']],
    'healthy':[['make','slo-mode','MODE=healthy']],
    'summary':[['make','grafana-check','grafana-export']],
}
titles={
    'status':'Grafana + VictoriaMetrics · minikube tbank-sre-hw02',
    'slow':'Задержка API 750 мс · наблюдаем RED и SLI latency',
    'errors':'API возвращает 503 · наблюдаем ошибки и SLA пробера',
    'healthy':'Восстановление · DEMO-режимы выключены',
    'summary':'Проверка запросов через Grafana и экспорт JSON дашбордов',
}
while True:
    request=state/'command.json'
    if not request.is_file():
        time.sleep(.2)
        continue
    data=json.loads(request.read_text())
    if data['sequence']==last:
        time.sleep(.2)
        continue
    last=data['sequence']; action=data['action']
    print('\033[2J\033[H'+titles[action]+'\n',flush=True)
    code=0
    for command in commands[action]:
        print('$ '+shlex.join(command),flush=True)
        code=subprocess.run(command).returncode
        if code:
            break
    print('\nDemo: окно 1m. Месячный SLA: 30d, цель пробера ≥98%.',flush=True)
    temporary=state/'done.tmp'
    temporary.write_text(json.dumps({'sequence':last,'code':code}))
    temporary.replace(state/'done.json')
