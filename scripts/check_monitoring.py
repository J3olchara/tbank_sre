"""Verify discovery and stored runtime, database and business metrics via VM API."""
import argparse
import json
import os
import time
from urllib.parse import urlencode
from urllib.request import urlopen

parser = argparse.ArgumentParser()
parser.add_argument('--replicas', type=int, default=3)
parser.add_argument('--timeout', type=int, default=90)
args = parser.parse_args()
base = os.environ.get('VM_URL', 'http://127.0.0.1:8428')

def query(expression):
    with urlopen(base + '/api/v1/query?' + urlencode({'query': expression}), timeout=8) as response:
        data = json.load(response)
    if data.get('status') != 'success':
        raise RuntimeError(data)
    return data['data']['result']

def check():
    app = query('up{job="taskboard"}')
    database = query('up{job="postgres"}')
    if len(app) != args.replicas or len({item['metric']['pod'] for item in app}) != args.replicas:
        raise RuntimeError(f'Expected {args.replicas} distinct app pods, found {len(app)}')
    if len(database) != 1 or any(float(item['value'][1]) != 1 for item in app + database):
        raise RuntimeError('Some discovered targets are down, absent or duplicated')
    for name in ['go_goroutines', 'process_cpu_seconds_total']:
        if len(query(name + '{job="taskboard"}')) != args.replicas:
            raise RuntimeError(f'{name} missing for some app replicas')
    database_up = query('pg_up{job="postgres"}')
    if len(database_up) != 1 or float(database_up[0]['value'][1]) != 1:
        raise RuntimeError('Exporter cannot reach PostgreSQL')
    if not query('pg_stat_database_xact_commit{job="postgres",datname="taskboard"}'):
        raise RuntimeError('PostgreSQL transaction metrics are missing')
    for name in ['taskboard_tasks_created_total', 'taskboard_tasks_updated_total',
                 'taskboard_tasks_deleted_total', 'taskboard_tasks_read_total',
                 'taskboard_task_lists_viewed_total']:
        result = query(f'sum({name}{{job="taskboard"}})')
        if not result or float(result[0]['value'][1]) < 1:
            raise RuntimeError(f'{name}: no successful business operation collected yet')
    freshness = query('time() - max(timestamp(go_goroutines{job="taskboard"}))')
    if not freshness or float(freshness[0]['value'][1]) > 30:
        raise RuntimeError('Runtime samples are stale')

deadline = time.monotonic() + args.timeout
while True:
    try:
        check()
        print(f'PASS: {args.replicas} app targets + 1 PostgreSQL target; runtime, database and all 5 business counters stored in VictoriaMetrics')
        break
    except Exception as error:
        if time.monotonic() >= deadline:
            raise SystemExit(f'Monitoring check failed: {error}')
        time.sleep(3)
