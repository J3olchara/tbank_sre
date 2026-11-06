"""Readable rendering of the real VictoriaMetrics HTTP API response on stdin."""
import json
import sys

response = json.load(sys.stdin)
if response.get('status') != 'success':
    raise SystemExit(json.dumps(response, ensure_ascii=False))
for item in response['data']['result']:
    print(json.dumps(item['metric'], ensure_ascii=False, sort_keys=True), '=>', item['value'][1])
print('Series:', len(response['data']['result']))
