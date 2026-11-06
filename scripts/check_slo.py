"""Check real scraped SLIs; optional phase assertions for the recorded incident."""
import argparse
import json
import math
import os
from pathlib import Path
import time
from urllib.parse import urlencode
from urllib.request import urlopen

from slo_queries import INDICATORS, ROOT, compliance, expressions, monthly_window_ready, write_queries

BASE = os.environ.get('VM_URL', 'http://127.0.0.1:8428')


def query(expression, at=None, allow_empty=False):
    params = {'query': expression}
    if at is not None:
        params['time'] = at
    with urlopen(BASE + '/api/v1/query?' + urlencode(params), timeout=30) as response:
        result = json.load(response)
    if result.get('status') != 'success':
        raise RuntimeError(result)
    rows = result['data']['result']
    if allow_empty and not rows:
        return None
    if len(rows) != 1:
        raise RuntimeError(f'Expected one value, got {len(rows)}: {expression}')
    value = float(rows[0]['value'][1])
    if not math.isfinite(value):
        raise RuntimeError('Invalid SLI sample')
    return value


def check_monthly():
    values = {key: query(expr, allow_empty=True) for key, expr in expressions('30d').items()}
    ready = query(monthly_window_ready())
    formal = query(compliance('30d'), allow_empty=True)
    if ready == 0 and formal is not None:
        raise RuntimeError('A partial month must not produce a formal SLA result')
    evidence = {'raw_partial_30d': values, 'monthly_window_ready': ready, 'formal_monthly_sla': formal}
    target = ROOT / 'artifacts/hw05'
    target.mkdir(parents=True, exist_ok=True)
    (target / 'monthly-validation.json').write_text(json.dumps(evidence, indent=2) + '\n')
    print('PASS: all 30d formulas execute; monthly SLA is gated on complete history')


def snapshot(phase=None):
    values = {key: query(expr) for key, expr in expressions().items()}
    if any(value < 0 or value > 100.001 for value in values.values()):
        raise RuntimeError(f'Invalid SLI percentage: {values}')
    if query('min(up{job="taskboard-prober"})') != 1:
        raise RuntimeError('Prober is not being scraped')
    if time.time() - query('max(taskboard_probe_last_run_timestamp_seconds{job="taskboard-prober"})') > 12:
        raise RuntimeError('Prober is stale')
    if phase in ('healthy', 'recovery'):
        for item in INDICATORS:
            if values[item['id']] < item['slo']:
                raise RuntimeError(f'{phase} has not recovered: {values}')
    if phase == 'slow' and (values['latency'] >= 90 or values['availability'] < 99 or values['creation'] < 99):
        raise RuntimeError(f'Expected slow successful responses: {values}')
    if phase == 'errors' and (values['availability'] >= 99 or values['creation'] >= 98 or values['probe'] >= 98):
        raise RuntimeError(f'Expected visible request and business failures: {values}')
    values['sla_compliance_demo'] = query(compliance())
    if phase in ('healthy', 'recovery') and values['sla_compliance_demo'] != 100:
        raise RuntimeError('Expected all demo SLA thresholds to pass')
    if phase in ('slow', 'errors') and values['sla_compliance_demo'] != 0:
        raise RuntimeError('Expected a visible demo SLA breach')
    return {'phase': phase or 'check', 'timestamp': time.time(), 'window': '1m', 'values': values}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=['healthy', 'slow', 'errors', 'recovery'])
    parser.add_argument('--timeout', type=int, default=120)
    parser.add_argument('--monthly', action='store_true')
    args = parser.parse_args()
    write_queries()
    if args.monthly:
        check_monthly()
        return
    deadline = time.monotonic() + args.timeout
    while True:
        try:
            evidence = snapshot(args.phase)
            break
        except Exception as error:
            if time.monotonic() >= deadline:
                raise SystemExit(str(error))
            time.sleep(3)
    target = ROOT / 'artifacts/hw05'
    target.mkdir(parents=True, exist_ok=True)
    (target / (evidence['phase'] + '.json')).write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(evidence, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
