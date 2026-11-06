"""Exercise the real stdout -> Vector -> VictoriaLogs pipeline and four LogsQL queries."""
import argparse
import json
import os
from pathlib import Path
import time
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
VL_URL = os.environ.get('VL_URL', 'http://127.0.0.1:9428')
APP_URL = os.environ.get('APP_URL', 'http://127.0.0.1:18080')


def query(expression):
    body = urlencode({'query': expression, 'limit': '100'}).encode()
    with urlopen(Request(VL_URL + '/select/logsql/query', data=body), timeout=12) as response:
        return [json.loads(line) for line in response if line.strip()]


def generate_traffic():
    requests = []
    def call(method, path, body=None, status=200):
        req = Request(APP_URL + path, method=method,
                      data=json.dumps(body).encode() if body is not None else None,
                      headers={'Content-Type': 'application/json'})
        try:
            response = urlopen(req, timeout=10)
        except HTTPError as error:
            response = error
        with response:
            data = response.read()
            if response.status != status:
                raise RuntimeError(f'{method} {path}: expected {status}, got {response.status}')
            request_id = response.headers.get('X-Request-ID')
            if not request_id:
                raise RuntimeError('Application does not provide request correlation; deploy the JSON logging build')
            requests.append({'method': method, 'path': path, 'status': status, 'request.id': request_id})
            return json.loads(data) if data else None
    call('GET', '/api/tasks')
    task = call('POST', '/api/tasks', {'title':'Проверка доставки логов', 'status':'todo'}, 201)
    path = '/api/tasks/' + str(task['id'])
    try:
        call('GET', path)
        call('PUT', path, {'title':'Логи доставлены', 'status':'done'})
        call('PUT', path, {'title':'', 'status':'done'}, 400)
    finally:
        call('DELETE', path, status=204)
    call('GET', path, status=404)
    call('GET', '/api/tasks/not-a-number', status=400)
    return requests


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--generate', action='store_true')
    parser.add_argument('--timeout', type=int, default=120)
    args = parser.parse_args()
    requests = generate_traffic() if args.generate else []
    queries = json.loads((ROOT / 'homework/03/queries.json').read_text())
    deadline = time.monotonic() + args.timeout
    while True:
        try:
            results = {item['id']: query(item['query']) for item in queries}
            if any(not rows for rows in results.values()):
                raise RuntimeError('Some LogsQL queries still return no rows')
            raw = results['01-raw']
            for event in raw:
                for key in ['_time', '_msg', 'level', 'service.name', 'kubernetes.namespace', 'kubernetes.pod']:
                    if not event.get(key):
                        raise RuntimeError(f'Missing structured field: {key}')
                if event['kubernetes.namespace'] != 'taskboard-lab' or event['service.name'] != 'taskboard':
                    raise RuntimeError('Unexpected log source')
            if any(row['level'] != 'warn' for row in results['02-field-filter']):
                raise RuntimeError('Field filter returned an unexpected level')
            if not any(row['level'] == 'info' for row in results['03-grouped-count']):
                raise RuntimeError('No info group')
            aggregate = results['04-aggregates'][0]
            if float(aggregate['p95_ms']) < 0 or int(aggregate['unique_paths']) < 1:
                raise RuntimeError('Invalid aggregate values')
            # A unique request ID proves end-to-end delivery of this run, not old data.
            if requests:
                probe = requests[-1]
                event = query('_time:5m service.name:taskboard request.id:' + json.dumps(probe['request.id']))
                if not event or int(event[0]['status']) != 400 or event[0]['level'] != 'warn':
                    raise RuntimeError('Fresh correlated request has not arrived yet')
            break
        except Exception as error:
            if time.monotonic() >= deadline:
                raise SystemExit(f'Logging check failed: {error}')
            time.sleep(3)
    target = ROOT / 'artifacts/hw03'
    target.mkdir(parents=True, exist_ok=True)
    evidence = {'queries': queries, 'results': results, 'generated_requests': requests}
    (target / 'verification.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
    print('PASS: JSON stdout -> Vector -> VictoriaLogs; 4 non-empty LogsQL queries; grouped count, p95 and unique paths verified')


if __name__ == '__main__':
    main()
