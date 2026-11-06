"""One source of truth for report formulas, vmui links and executable checks."""
import json
import os
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
INDICATORS = [
    {'id': 'availability', 'title': 'API availability / RBSLO', 'slo': 99.5, 'sla': 99.0},
    {'id': 'latency', 'title': 'API responses <= 250 ms / RBSLO', 'slo': 95.0, 'sla': 90.0},
    {'id': 'creation', 'title': 'Committed task creation / RBSLO', 'slo': 99.0, 'sla': 98.0},
    {'id': 'probe', 'title': 'UI + task list: good minutes / TBSLO', 'slo': 99.0, 'sla': 98.0},
]


def expressions(window='1m'):
    route = 'route=~"(GET|POST|PUT|DELETE) /api/tasks.*"'
    def inc(metric, labels=''):
        selector = 'job="taskboard"' + (',' + labels if labels else '')
        return f'sum(increase({metric}{{{selector}}}[{window}]))'
    def ratio(good, total):
        # No events is an undefined request SLI, never an invented 100%.
        return f'(100 * clamp_max(({good}) / ({total}), 1)) and on() (({total}) > 0)'
    requests = 'taskboard_http_requests_total'
    total = inc(requests, route + ',code=~"2..|5.."')
    good = '(' + inc(requests, route + ',code=~"2.."') + ' or vector(0))'
    available = ratio(good, total)
    latency = ratio(inc('taskboard_http_request_duration_seconds_bucket', route + ',le="0.25"'),
                    inc('taskboard_http_request_duration_seconds_count', route))
    creation = ratio(inc('taskboard_tasks_created_total'),
                     inc(requests, 'route="POST /api/tasks",code=~"2..|5.."'))
    # A missing exporter, failed scrape or stale check is bad, not silently good.
    fresh = '((time() - (max(taskboard_probe_last_run_timestamp_seconds{job="taskboard-prober"}) or vector(0))) < bool 12)'
    probe_now = ('(min(taskboard_probe_success{job="taskboard-prober"}) or vector(0))'
                 ' * (min(up{job="taskboard-prober"}) or vector(0)) * ' + fresh)
    good_minute = f'min_over_time(({probe_now})[1m:5s])'
    probe = f'100 * avg_over_time(({good_minute})[{window}:1m])'
    return dict(availability=available, latency=latency, creation=creation, probe=probe)


def labelled(expression, label):
    return f'label_set(({expression}), "series", "{label}")'


def chart_queries(indicator, window='1m'):
    prefix = indicator['id'] + ': '
    return [labelled(expressions(window)[indicator['id']], prefix + f'SLI ({window}) %'),
            labelled(f'vector({indicator["slo"]})', prefix + 'SLO target %'),
            labelled(f'vector({indicator["sla"]})', prefix + 'SLA target %')]


def compliance(window='1m'):
    indicators = expressions(window)
    aliases = [f'sli_{key}=({value})' for key, value in indicators.items()]
    parts = [labelled(f'sli_{item["id"]} >= bool {item["sla"]}', item['id']) for item in INDICATORS]
    aliases.append('checks=(' + ' or '.join(parts) + ')')
    # All four SLIs must have data; missing request traffic makes this undefined.
    result = 'WITH (' + ', '.join(aliases) + ') (100 * min(checks)) and on() (count(checks) == 4)'
    if window == '30d':
        result += ' and on() ((' + monthly_window_ready() + ') == 1)'
    return result


def monthly_window_ready():
    first = 'min(tfirst_over_time(taskboard_probe_success{job="taskboard-prober"}[35d]))'
    return f'(((time() - {first}) >= bool 2592000) or vector(0))'


def vmui_url(queries, base=None, start=None, end=None):
    base = base or os.environ.get('VM_URL', 'http://127.0.0.1:8428')
    params = {'g0.range_input': '10m', 'g0.tab': '0', 'g0.step_input': '5s'}
    if end is not None:
        from datetime import datetime, timezone
        params['g0.end_input'] = datetime.fromtimestamp(end, timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
    if start is not None and end is not None:
        params['g0.range_input'] = f'{int(end-start)}s'
    params['g0.expr'] = ' or '.join('(' + query + ')' for query in queries)
    return base.rstrip('/') + '/vmui/?' + urlencode(params)


def write_queries():
    output = ROOT / 'homework/05/queries.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({
        'demo_window': '1m', 'objective_window': '30d',
        'indicators': [{**item, 'demo_query': expressions()[item['id']],
                        'monthly_query': expressions('30d')[item['id']],
                        'demo_vmui_url': vmui_url(chart_queries(item), base='http://127.0.0.1:8428')} for item in INDICATORS],
        'demo_sla_compliance': compliance(),
        'monthly_sla_compliance': compliance('30d'),
        'monthly_window_ready': monthly_window_ready(),
    }, ensure_ascii=False, indent=2) + '\n')
    return output


if __name__ == '__main__':
    print(write_queries())
