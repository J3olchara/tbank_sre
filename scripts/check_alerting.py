"""Verify real vmalert -> Alertmanager -> webhook delivery and recovery."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import urlencode
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / 'artifacts/hw06'
VMALERT = os.environ.get('VMALERT_URL', 'http://127.0.0.1:18880')
MANAGER = os.environ.get('ALERTMANAGER_URL', 'http://127.0.0.1:19093')
INBOX = os.environ.get('ALERT_INBOX_URL', 'http://127.0.0.1:18085')
VM = os.environ.get('VM_URL', 'http://127.0.0.1:8428')
EXPECTED = {
    'slow': {'TaskboardHighLatency'},
    'errors': {'TaskboardHighErrorRate', 'TaskboardProbeFailed'},
    'runtime': {'TaskboardGoroutinesHigh', 'TaskboardGoHeapHigh'},
}
NAMES = set.union(*EXPECTED.values())


def get(base, path):
    with urlopen(base + path, timeout=15) as response:
        return json.load(response)


def scalar(expr):
    result = get(VM, '/api/v1/query?' + urlencode({'query': expr}))
    rows = result['data']['result']
    if result.get('status') != 'success' or len(rows) != 1:
        raise RuntimeError('Missing scraped sample: ' + expr)
    return float(rows[0]['value'][1])


def snapshot(phase, since):
    result = get(VMALERT, '/api/v1/rules')
    groups = result['data']['groups']
    rules = {r['name']: r for g in groups for r in g['rules'] if r['name'] in NAMES}
    if set(rules) != NAMES or any(r['health'] != 'ok' or r.get('lastError') for r in rules.values()):
        raise RuntimeError('Rules missing or evaluation failed')
    active = get(MANAGER, '/api/v2/alerts')
    deliveries = get(INBOX, '/api/notifications')
    # Go emits nanoseconds; Python 3.10 accepts at most microsecond precision.
    def received_at(delivery):
        stamp = re.sub(r'(\.\d{6})\d+', r'\1', delivery['received_at'])
        return datetime.fromisoformat(stamp.replace('Z', '+00:00')).timestamp()
    recent = [d for d in deliveries if received_at(d) >= since]
    notifications = {
        status: {a['labels']['alertname'] for d in recent for a in d['payload']['alerts'] if a['status'] == status}
        for status in ('firing', 'resolved')
    }
    states = {name: rule['state'] for name, rule in rules.items()}
    if phase in ('healthy', 'recovery'):
        if any(value != 'inactive' for value in states.values()):
            raise RuntimeError('Waiting for all rules to become inactive: ' + str(states))
        if phase == 'recovery' and not NAMES <= notifications['resolved']:
            raise RuntimeError('Waiting for resolved webhooks: ' + str(NAMES - notifications['resolved']))
    else:
        required = EXPECTED[phase]
        manager_names = {a['labels']['alertname'] for a in active if a['status']['state'] == 'active'}
        if not all(states[name] == 'firing' for name in required):
            raise RuntimeError('Waiting for firing rules: ' + str(states))
        if not required <= manager_names or not required <= notifications['firing']:
            raise RuntimeError('Waiting for Alertmanager delivery: ' + str(required - notifications['firing']))
    metrics = {
        'goroutines_max': scalar('max(go_goroutines{job="taskboard",namespace="taskboard-lab"})'),
        'heap_bytes_max': scalar('max(go_memstats_heap_alloc_bytes{job="taskboard",namespace="taskboard-lab"})'),
        'probe_success': scalar('min(taskboard_probe_success{job="taskboard-prober",namespace="taskboard-lab"})'),
    }
    return {'phase': phase, 'timestamp': time.time(), 'since': since, 'states': states,
            'metrics': metrics, 'rules': result, 'alertmanager': active, 'notifications': deliveries}


def wait_phase(phase, since, timeout):
    deadline = time.monotonic() + timeout
    next_update = 0
    while True:
        try:
            proof = snapshot(phase, since)
            OUTPUT.mkdir(parents=True, exist_ok=True)
            (OUTPUT / (phase + '.json')).write_text(json.dumps(proof, indent=2) + '\n')
            print(json.dumps({'phase': phase, 'states': proof['states'], 'metrics': proof['metrics']}), flush=True)
            return proof
        except Exception as error:
            if time.monotonic() >= deadline:
                raise RuntimeError(f'{phase}: {error}') from error
            if time.monotonic() >= next_update:
                print(f'{phase}: {error}', flush=True)
                next_update = time.monotonic() + 15
            time.sleep(3)


def command(*args):
    subprocess.run(args, cwd=ROOT, check=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['healthy', 'slow', 'errors', 'runtime', 'recovery'])
    parser.add_argument('--since', type=float, default=0)
    parser.add_argument('--timeout', type=int, default=180)
    parser.add_argument('--screenshots', action='store_true')
    args = parser.parse_args()
    if args.phase:
        wait_phase(args.phase, args.since, args.timeout)
        return
    started = time.time()
    completed = []
    try:
        command('bash', 'scripts/alerting.sh', 'mode', 'healthy')
        command('bash', 'scripts/slo.sh', 'load-start')
        for phase in ['healthy', 'slow', 'errors', 'runtime', 'recovery']:
            since = time.time()
            if phase != 'healthy':
                command('bash', 'scripts/alerting.sh', 'mode', 'healthy' if phase == 'recovery' else phase)
            wait_phase(phase, started if phase == 'recovery' else since, args.timeout)
            if args.screenshots:
                command('node', 'scripts/capture_hw06.cjs', phase)
            completed.append(phase)
    finally:
        # Cleanup also runs after a failed query or interrupted screenshot.
        try:
            command('bash', 'scripts/alerting.sh', 'mode', 'healthy')
        finally:
            command('bash', 'scripts/slo.sh', 'load-stop')
    evidence = {'started': started, 'finished': time.time(), 'phases': completed,
                'verified_alerts': sorted(NAMES), 'screenshots': args.screenshots,
                'healthy_restored': True, 'load_job_deleted': True}
    (OUTPUT / 'verification.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print('PASS: five real firing alerts and five resolved webhooks; healthy restored', flush=True)


if __name__ == '__main__':
    main()
