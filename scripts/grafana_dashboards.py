"""Build portable Grafana JSON; reuse the HW05 SLI formulas without copying them."""
import hashlib
import json

from slo_queries import INDICATORS, ROOT, expressions, monthly_window_ready

DS = {'type': 'prometheus', 'uid': 'victoriametrics'}
OUT = ROOT / 'deploy/grafana/dashboards'
ROUTE = 'route=~"(GET|POST|PUT|DELETE) /api/tasks.*"'
APP = 'job="taskboard",namespace="taskboard-lab"'


def target(expr, legend='', ref='A', instant=False):
    return dict(refId=ref, expr=expr, legendFormat=legend, datasource=DS,
                editorMode='code', range=not instant, instant=instant)


def panel(ident, title, kind, pos, queries=(), unit='short', description=''):
    defaults = dict(unit=unit, decimals=2, noValue='Нет данных',
                    color={'mode': 'palette-classic'},
                    thresholds={'mode': 'absolute', 'steps': [{'color': 'green', 'value': None}]})
    p = dict(id=ident, title=title, type=kind, datasource=DS, description=description,
             gridPos=dict(zip(('x','y','w','h'), pos)),
             fieldConfig={'defaults': defaults, 'overrides': []}, targets=list(queries))
    if kind == 'stat':
        defaults['color'] = {'mode': 'thresholds'}
        p['options'] = dict(reduceOptions={'calcs': ['lastNotNull'], 'fields': '', 'values': False},
                            orientation='auto', colorMode='value', graphMode='none', textMode='auto')
    elif kind == 'timeseries':
        defaults['custom'] = dict(drawStyle='line', lineInterpolation='linear', lineWidth=2,
                                  fillOpacity=7, showPoints='never', spanNulls=False,
                                  axisCenteredZero=False, hideFrom={'legend':False,'tooltip':False,'viz':False})
        p['options'] = dict(legend={'displayMode':'list','placement':'bottom','calcs':['lastNotNull']},
                            tooltip={'mode':'multi','sort':'none'})
    return p


def percent(p, thresholds=None):
    p['fieldConfig']['defaults'].update(min=0, max=100)
    if thresholds:
        p['fieldConfig']['defaults']['thresholds']['steps'] = thresholds
    return p


def row(ident, title, y):
    return dict(id=ident, title=title, type='row', collapsed=False, panels=[],
                gridPos={'x':0,'y':y,'w':24,'h':1})


def dashboard(uid, title, panels):
    return dict(id=None, uid=uid, title=title, version=1, schemaVersion=39,
                tags=['tbank-sre','hw06'], timezone='browser', editable=True,
                refresh='5s', time={'from':'now-15m','to':'now'},
                timepicker={'refresh_intervals':['5s','10s','30s','1m']},
                templating={'list':[]}, annotations={'list':[]}, panels=panels,
                links=[])


def application():
    requests = f'taskboard_http_requests_total{{{APP},{ROUTE}}}'
    all_rate = f'sum(rate({requests}[$__rate_interval]))'
    fail_rate = f'(sum(rate(taskboard_http_requests_total{{{APP},{ROUTE},code=~"5.."}}[$__rate_interval])) or (0 * {all_rate}))'
    error_ratio = f'(100 * {fail_rate} / {all_rate}) and on() ({all_rate} > 0)'
    bucket = f'sum by (le) (rate(taskboard_http_request_duration_seconds_bucket{{{APP},{ROUTE}}}[$__rate_interval]))'
    probe = expressions()['probe']
    panels = [row(1,'Taskboard · текущее состояние',0)]
    top = [
        ('API · scrape UP',f'sum(up{{{APP}}})','short'),
        ('API · запросы/с',all_rate,'reqps'),
        ('API · ошибки 5xx',error_ratio,'percent'),
        ('API · p95',f'histogram_quantile(0.95, {bucket})','s'),
        ('PostgreSQL', 'min(pg_up{job="postgres",namespace="taskboard-lab"})','short'),
        ('Пробер · последний результат', '(min(taskboard_probe_success{job="taskboard-prober"}) or vector(0)) * (min(up{job="taskboard-prober"}) or vector(0)) * ((time() - (max(taskboard_probe_last_run_timestamp_seconds{job="taskboard-prober"}) or vector(0))) < bool 12)','short'),
    ]
    for n,(title,expr,unit) in enumerate(top):
        p=panel(2+n,title,'stat',(n*4,1,4,4),[target(expr,instant=True)],unit)
        if n==2:
            percent(p,[{'color':'green','value':None},{'color':'red','value':1}])
        if n in (4,5):
            p['fieldConfig']['defaults'].update(mappings=[{'type':'value','options':{'0':{'text':'DOWN','color':'red'},'1':{'text':'UP','color':'green'}}}])
        panels.append(p)
    panels.append(row(10,'RED / Golden Signals · трафик, ошибки, задержки',5))
    panels.extend([
        panel(11,'RPS по HTTP-методу','timeseries',(0,6,8,7),[target(f'sum by (method) (rate({requests}[$__rate_interval]))','{{method}}')],'reqps','Только task API; health/readiness и выдача UI исключены.'),
        panel(12,'Ошибки сервера · 5xx/с','timeseries',(8,6,8,7),[target(fail_rate,'HTTP 5xx')],'reqps','Ноль при работающем API без 5xx; при отсутствии метрик нет данных.'),
        panel(13,'Задержка API · p50 / p95 / p99','timeseries',(16,6,8,7),[target(f'histogram_quantile({q}, {bucket})',name,chr(65+i)) for i,(q,name) in enumerate([(0.5,'p50'),(0.95,'p95'),(0.99,'p99')])],'s','Перцентили из общей гистограммы реплик. Это приближение по bucket, не среднее перцентилей.'),
    ])
    panels.append(row(20,'SLI / SLO / SLA · демонстрационное окно 1m',13))
    for i,item in enumerate(INDICATORS[:3]):
        title={'availability':'Успешность API','latency':'Ответы API ≤250 мс','creation':'Создание задач'}[item['id']]
        p=panel(21+i,title+' · 1m','timeseries',(8*i,14,8,7),[
            target(expressions()[item['id']],'SLI, %'),
            target(f'vector({item["slo"]})',f'SLO {item["slo"]}%', 'B'),
            target(f'vector({item["sla"]})',f'SLA {item["sla"]}%', 'C')], 'percent',
            'Формула из ДЗ №5. Пустой request denominator означает отсутствие оценки. Целевое окно 30d; здесь только demo 1m.')
        panels.append(percent(p))
    panels.append(row(30,'SLA пробера · UI + чтение задач через Service',21))
    panels.append(percent(panel(31,'Пробер · хорошие минуты, SLO 99%, SLA 98% · demo 1m','timeseries',(0,22,12,8),[
        target(probe,'Хорошие минуты, %'),target('vector(99)','SLO 99%', 'B'),target('vector(98)','SLA 98%', 'C')],
        'percent','TBSLO: все проверки минуты должны быть успешны. Сбой scrape, устаревшая проверка >12s и отсутствие exporter считаются плохими. Окно демонстрации 1m.')))
    status=percent(panel(32,'SLA пробера · demo 1m','stat',(12,22,6,4),[target(f'100 * (({probe}) >= bool 98)',instant=True)],'percent','100 = порог 98% выполнен, 0 = нарушен. Это не месячный SLA.'))
    status['fieldConfig']['defaults']['mappings']=[{'type':'value','options':{'0':{'text':'НАРУШЕН','color':'red'},'100':{'text':'ВЫПОЛНЕН','color':'green'}}}]
    panels.append(status)
    monthly=f'({expressions("30d")["probe"]}) and on() (({monthly_window_ready()}) == 1)'
    month=percent(panel(33,'Пробер · SLA за 30d (цель ≥98%)','stat',(18,22,6,8),[target(monthly,instant=True)],'percent','Формальный результат только после накопления 30 суток. До этого «Нет 30d истории», а не 100%.'))
    month['fieldConfig']['defaults']['noValue']='Нет 30d истории'
    month['fieldConfig']['defaults']['mappings']=[{'type':'special','options':{'match':'null','result':{'text':'Нет 30d истории','color':'gray'}}}]
    panels.append(month)
    panels.append(panel(34,'Пробер · время последней проверки','timeseries',(12,26,6,4),[target('max(taskboard_probe_duration_seconds{job="taskboard-prober"})','UI + API')],'s','Время синтетического запроса по сети Service; deadline 2s.'))
    panels.append(row(40,'Go runtime / ресурсы · детализация по репликам',30))
    panels.extend([
        panel(41,'CPU процесса · ядра','timeseries',(0,31,6,7),[target(f'rate(process_cpu_seconds_total{{{APP}}}[$__rate_interval])','{{pod}}')],'short','Utilization процесса. 1 = одно полностью занятое ядро, лимит контейнера 0.5 CPU.'),
        panel(42,'Память · RSS и Go heap','timeseries',(6,31,6,7),[target(f'process_resident_memory_bytes{{{APP}}}','{{pod}} · RSS'),target(f'go_memstats_heap_alloc_bytes{{{APP}}}','{{pod}} · heap','B')],'bytes'),
        panel(43,'Go goroutines','timeseries',(12,31,6,7),[target(f'go_goroutines{{{APP}}}','{{pod}}')],'short','Рост может указывать на очередь работ или утечку; это не точное измерение saturation.'),
        percent(panel(44,'Занятые файловые дескрипторы','timeseries',(18,31,6,7),[target(f'100 * process_open_fds{{{APP}}} / process_max_fds{{{APP}}}','{{pod}}')],'percent','Доля process_open_fds / process_max_fds — доступный сигнал насыщения ресурса.')),
    ])
    panels.append(row(50,'Бизнес-операции · только успешные действия',38))
    panels.append(panel(51,'CRUD · успешные операции/с','timeseries',(0,39,12,7),[
        target(f'sum(rate({metric}{{{APP}}}[$__rate_interval]))',name,chr(65+i)) for i,(metric,name) in enumerate([
            ('taskboard_tasks_created_total','create'),('taskboard_tasks_updated_total','update'),('taskboard_tasks_deleted_total','delete'),('taskboard_task_lists_viewed_total','list')])],'ops'))
    panels.append(panel(52,'CPU / память · подсказка','text',(12,39,12,7),description=''))
    panels[-1]['options']={'mode':'markdown','content':'**Источник: VictoriaMetrics** → встроенный Prometheus data source.\n\nRED: RPS, 5xx, длительность. Golden Signals: traffic, errors, latency и признаки saturation.\n\nCPU, RSS, heap и FD относятся к процессу Go, не ко всей ноде. Node exporter и kube-state-metrics в стенд не добавлялись.\n\n**SLA:** целевой период 30d; графики 1m служат для демонстрации. При отсутствии запросов request SLI не определён.'}
    d=dashboard('taskboard-overview','Taskboard · приложение и SLA',panels)
    d['description']='ДЗ №6: RED, Go runtime, бизнес-метрики и отдельный SLA пробера. Demo 1m отделён от целевого окна 30d.'
    d['links']=[{'type':'link','title':'PostgreSQL Exporter · 9628','url':'/d/taskboard-postgres','targetBlank':False}]
    return d


def postgres():
    source=ROOT/'deploy/grafana/postgres-9628.original.json'
    upstream=json.loads(source.read_text())
    panels=[]
    for old in upstream['panels']:
        ident=old['id']
        if old['type']=='row':
            panels.append(row(ident,old['title'],old['gridPos']['y']))
            continue
        # PG17 moved checkpoint statistics out of pg_stat_bgwriter; upstream
        # panels 64/70 target removed metrics. Leave them out, never invent data.
        if ident in (64,70):
            continue
        queries=[]
        for i,t in enumerate(old.get('targets',[])):
            expr=t['expr'].replace('release="$release", ', '').replace('release="$release",','')
            expr=expr.replace('[$interval]','[$__rate_interval]').replace('[5m]','[$__rate_interval]')
            expr=expr.replace('instance="$instance"','job="postgres",namespace="taskboard-lab",instance=~"$instance"')
            if 'job="postgres"' not in expr:
                expr=expr.replace('instance=~"$instance"','job="postgres",namespace="taskboard-lab",instance=~"$instance"')
            # Zero events are real zeros, not missing series on an idle lab.
            expr=expr.replace(' !=0','').replace(' != 0','')
            queries.append(target(expr,t.get('legendFormat',''),chr(65+i),old['type']=='singlestat'))
        title=old['title']
        unit=old.get('format','short')
        kind='stat' if old['type']=='singlestat' else 'timeseries'
        if kind=='timeseries':
            unit=old.get('yaxes',[{}])[0].get('format','short')
        if ident in (1,3,4,5,6,7,8,10,11,12,14,26,36,38,50,52,54,56):
            # Upstream incorrectly formats tuple counts as bytes.
            unit='short'
        if ident in (60,66):
            unit='ops'
        if ident in (1,4):
            queries=[target('sum by (datname,state) ('+q['expr']+')','{{datname}} · {{state}}',q['refId']) for q in queries]
        if ident==22:
            title='Exporter CPU · cores'
            unit='short'
            queries=[target('rate(process_cpu_seconds_total{job="postgres",namespace="taskboard-lab",instance=~"$instance"}[$__rate_interval])','exporter')]
        if ident==24:
            title='Exporter memory · RSS / virtual'
            unit='bytes'
            queries=[target(f'{m}{{job="postgres",namespace="taskboard-lab",instance=~"$instance"}}',label,chr(65+i)) for i,(m,label) in enumerate([('process_resident_memory_bytes','RSS'),('process_virtual_memory_bytes','virtual')])]
        if ident==26:
            title='Exporter · open file descriptors'
        if ident==36:
            title='PostgreSQL · exporter connection'
            queries=[target('pg_up{job="postgres",namespace="taskboard-lab",instance=~"$instance"}',instant=True)]
        if ident==28:
            title='Database size'
            unit='bytes'
            queries=[target('sum(pg_database_size_bytes{job="postgres",namespace="taskboard-lab",instance=~"$instance",datname=~"$datname"})',instant=True)]
        if ident==62:
            # New/unused DBs can have no block reads; keep undefined denominators.
            unit='percentunit'
        p=panel(ident,title,kind,tuple(old['gridPos'][k] for k in ('x','y','w','h')),queries,unit)
        if kind=='stat':
            p['gridPos']['h']=4
        panels.append(p)
    # Lay out the imported groups again after modernising singlestat panels.
    y=0; x=0; height=0
    for p in panels:
        if p['type']=='row':
            if x: y+=height; x=0; height=0
            p['gridPos'].update(x=0,y=y); y+=1
            continue
        w=p['gridPos']['w']; h=p['gridPos']['h']
        if x+w>24: y+=height; x=0; height=0
        p['gridPos'].update(x=x,y=y); x+=w; height=max(height,h)
    d=dashboard('taskboard-postgres','PostgreSQL Database · 9628',panels)
    d['gnetId']=9628
    d['description']='Imported Grafana.com dashboard 9628; adapted for current exporter/PG17 and stat/timeseries panels. Original JSON and SHA256 are included.'
    d['links']=[{'type':'link','title':'Upstream · 9628','url':'https://grafana.com/grafana/dashboards/9628-postgresql-database/','targetBlank':True},
                {'type':'link','title':'Taskboard','url':'/d/taskboard-overview','targetBlank':False}]
    def variable(name,label,query,all_value=None):
        return dict(name=name,label=label,type='query',datasource=DS,refresh=2,
                    query={'query':query,'refId':'variable-'+name},definition=query,
                    options=[],current={},multi=all_value is not None,
                    includeAll=all_value is not None,allValue=all_value,sort=1)
    d['templating']['list']=[
        variable('instance','Instance','label_values(pg_up{job="postgres",namespace="taskboard-lab"}, instance)'),
        variable('datname','Database','label_values(pg_stat_database_xact_commit{job="postgres",namespace="taskboard-lab"}, datname)'),
        variable('mode','Lock mode','label_values(pg_locks_count{job="postgres",namespace="taskboard-lab"}, mode)', '.*'),
    ]
    d['templating']['list'][1]['current']={'text':'taskboard','value':'taskboard'}
    d['templating']['list'][2]['current']={'text':'All','value':'$__all'}
    return d


def postgres_source():
    source=OUT.parent/'postgres-9628.original.json'
    upstream=json.loads(source.read_text())
    return {'dashboard_id':9628,'download_url':'https://grafana.com/api/dashboards/9628/revisions/latest/download',
              'upstream_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
              'upstream_version':upstream['version'],
              'changes':['fixed VictoriaMetrics datasource UID and exporter labels',
                         'singlestat/graph converted to stat/timeseries',
                         'process metrics labelled as exporter, memory kept as gauges',
                         'tuple/session counters use counts, not bytes; sessions grouped by database/state',
                         'PG17 obsolete bgwriter/checkpoint panels 64/70 removed',
                         'pg_static version panel replaced by pg_up',
                         'unavailable postmaster start-time panel replaced by database size',
                         'database and instance variables use available metric labels']}


def write():
    OUT.mkdir(parents=True,exist_ok=True)
    for filename,value in [('taskboard.json',application()),('postgres.json',postgres())]:
        (OUT/filename).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')
    (OUT.parent/'postgres-source.json').write_text(json.dumps(postgres_source(),indent=2)+'\n')


if __name__=='__main__':
    write()
    print('Generated application and imported PostgreSQL dashboard JSON')
