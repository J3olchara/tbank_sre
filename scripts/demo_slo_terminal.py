"""Visible terminal controller; every displayed command is actually executed."""
import json
import os
from pathlib import Path
import subprocess
import time

state = Path(os.environ['RECORDING_STATE_DIR'])
profile = os.environ.get('PROFILE', 'tbank-sre-hw02')
last = -1
print('Домашняя работа 05: SLI / SLO / SLA\nОжидание демонстрации…', flush=True)
while True:
    request = state / 'command.json'
    if not request.is_file():
        time.sleep(.2)
        continue
    data = json.loads(request.read_text())
    if data['sequence'] == last:
        time.sleep(.2)
        continue
    last = data['sequence']
    action = data['action']
    commands = {
        'status': [
            ['kubectl', '--context', profile, '-n', 'taskboard-lab', 'get', 'pods'],
            ['python3', 'scripts/check_slo.py', '--phase', 'healthy', '--timeout', '15'],
        ],
        'slow': [['make', 'slo-mode', 'MODE=slow']],
        'errors': [['make', 'slo-mode', 'MODE=errors']],
        'healthy': [['make', 'slo-mode', 'MODE=healthy']],
        'summary': [['python3', 'scripts/check_slo.py', '--phase', 'recovery', '--timeout', '15']],
    }
    titles = {
        'status': 'НОРМА: реальные SLI на окне 1 минута. SLA/SLO: окно 30 дней.',
        'slow': 'ЗАДЕРЖКИ: 750 мс на API. Снижается доля ответов <= 250 мс.',
        'errors': 'ОТКАЗ: API отвечает 503. Pods и /healthz продолжают работать.',
        'healthy': 'ВОССТАНОВЛЕНИЕ: задержки и ошибки отключены.',
        'summary': 'ПРОВЕРКА ВОССТАНОВЛЕНИЯ: все четыре SLI и общий статус SLA.',
    }
    print('\033[2J\033[H' + titles[action] + '\n' + time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime()), flush=True)
    code = 0
    for command in commands[action]:
        print('\n$ ' + ' '.join(command), flush=True)
        code = subprocess.run(command).returncode
        if code:
            break
    if action in ('slow', 'errors', 'healthy'):
        print('\nДалее: настоящая vmui. SLI меняются, целевые SLO/SLA остаются постоянными.', flush=True)
        print('На экране демонстрационное окно 1 минута; это не месячный SLA-отчёт.', flush=True)
    temporary = state / 'done.tmp'
    temporary.write_text(json.dumps({'sequence': last, 'code': code}))
    temporary.replace(state / 'done.json')
