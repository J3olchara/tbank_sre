"""Import, verify through Grafana's datasource proxy, and export actual dashboards."""
import argparse
import base64
import hashlib
import json
import math
import os
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from grafana_dashboards import OUT, ROOT, application, postgres


class Grafana:
    def __init__(self):
        self.base=os.environ.get('GRAFANA_URL','http://127.0.0.1:3000').rstrip('/')
        url=urlparse(self.base)
        if url.scheme not in ('http','https') or url.hostname not in ('127.0.0.1','localhost','::1') or url.username:
            raise RuntimeError('Use a loopback GRAFANA_URL with kubectl port-forward')
        result=subprocess.check_output(['kubectl','--context',os.environ.get('PROFILE','tbank-sre-hw02'),'-n','monitoring','get','secret','grafana-admin','-o','json'],text=True)
        data=json.loads(result)['data']
        login=base64.b64decode(data['admin-user'])+b':'+base64.b64decode(data['admin-password'])
        self.authorization='Basic '+base64.b64encode(login).decode()

    def request(self,path,data=None,method=None):
        body=None if data is None else json.dumps(data).encode()
        request=Request(self.base+path,data=body,method=method,
                        headers={'Authorization':self.authorization,'Content-Type':'application/json'})
        try:
            with urlopen(request,timeout=60) as response:
                return json.load(response)
        except HTTPError as error:
            raise RuntimeError(f'Grafana {path}: HTTP {error.code}: '+error.read().decode()[:400]) from error

    def query(self,expression,instant=False):
        now=int(time.time()*1000)
        result=self.request('/api/ds/query',{'from':str(now-180000),'to':str(now),'queries':[
            {'refId':'A','datasource':{'type':'prometheus','uid':'victoriametrics'},
             'expr':expression,'instant':instant,'range':not instant,'format':'time_series',
             'intervalMs':5000,'maxDataPoints':200}]})['results']['A']
        if result.get('error') or result.get('status',200)>=400:
            raise RuntimeError(result)
        values=[]
        for frame in result.get('frames',[]):
            for field,column in zip(frame['schema']['fields'],frame['data']['values']):
                if field['type']=='number':
                    values.extend(float(v) for v in column if v is not None and math.isfinite(float(v)))
        return values


def validate():
    for name,expected in [('taskboard.json',application()),('postgres.json',postgres())]:
        actual=json.loads((OUT/name).read_text())
        if actual!=expected:
            raise RuntimeError(f'{name} is stale; run python3 scripts/grafana_dashboards.py')
        ids=[]
        rectangles=[]
        for panel in actual['panels']:
            ids.append(panel['id'])
            pos=panel['gridPos']
            if not (0<=pos['x']<24 and 0<pos['w']<=24-pos['x'] and pos['h']>0):
                raise RuntimeError('Invalid panel grid')
            for previous in rectangles:
                if pos['x']<previous['x']+previous['w'] and previous['x']<pos['x']+pos['w'] and pos['y']<previous['y']+previous['h'] and previous['y']<pos['y']+pos['h']:
                    raise RuntimeError(f'Overlapping panels: {name} {panel["id"]}')
            rectangles.append(pos)
            for target in panel.get('targets',[]):
                if target['datasource']['uid']!='victoriametrics':
                    raise RuntimeError('Unexpected data source')
                expr=target['expr']
                if '$release' in expr or '$namespace' in expr:
                    raise RuntimeError('Legacy exporter labels remain')
                if 'rate(' in expr and 'resident_memory' in expr:
                    raise RuntimeError('Memory is a gauge, not a counter')
        if len(ids)!=len(set(ids)):
            raise RuntimeError('Duplicate panel IDs')
    source=json.loads((OUT.parent/'postgres-source.json').read_text())
    if hashlib.sha256((OUT.parent/'postgres-9628.original.json').read_bytes()).hexdigest()!=source['upstream_sha256']:
        raise RuntimeError('Upstream dashboard checksum mismatch')
    print('PASS: generated dashboard JSON, grid, datasource, upstream checksum')


def import_postgres(client):
    dashboard=json.loads((OUT/'postgres.json').read_text())
    response=client.request('/api/dashboards/db',{'dashboard':dashboard,'folderUid':'sre','overwrite':True,'message':'Import adapted Grafana.com PostgreSQL Exporter dashboard 9628'})
    if response.get('status')!='success':
        raise RuntimeError(response)
    print('Imported PostgreSQL dashboard 9628: '+response['url'])


def check(client):
    datasource=client.request('/api/datasources/uid/victoriametrics')
    if datasource['type']!='prometheus' or datasource['url']!='http://vm-single.monitoring.svc.cluster.local:8428':
        raise RuntimeError('Unexpected VictoriaMetrics datasource')
    health=client.request('/api/datasources/uid/victoriametrics/health')
    if health['status']!='OK':
        raise RuntimeError(health)
    evidence={'timestamp':time.time(),'datasource':{'uid':datasource['uid'],'url':datasource['url'],'health':health},'panels':[]}
    for uid in ('taskboard-overview','taskboard-postgres'):
        dashboard=client.request('/api/dashboards/uid/'+uid)['dashboard']
        for panel in dashboard['panels']:
            for query in panel.get('targets',[]):
                expr=query['expr'].replace('$__rate_interval','1m').replace('$instance','.*').replace('$datname','taskboard').replace('$mode','.*')
                values=client.query(expr,query.get('instant',False))
                # The formal monthly panel must remain empty before 30d history.
                if not values and not (uid=='taskboard-overview' and panel['id']==33):
                    raise RuntimeError(f'Empty Grafana panel {uid}/{panel["id"]}: {expr}')
                evidence['panels'].append({'dashboard':uid,'panel_id':panel['id'],'title':panel['title'],'refId':query['refId'],'expression':expr,'samples':len(values),'last':values[-1] if values else None})
    if client.query('((time() - max(timestamp(up{job="taskboard"}))) < bool 20)',True)!=[1.0]:
        raise RuntimeError('Application samples are stale')
    output=ROOT/'artifacts/hw06/grafana-check.json'
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print(f'PASS: datasource health, fresh samples, {len(evidence["panels"])} real Grafana queries')


def export(client):
    directory=ROOT/'homework/06/dashboards'
    directory.mkdir(parents=True,exist_ok=True)
    for uid,name in [('taskboard-overview','taskboard.json'),('taskboard-postgres','postgres.json')]:
        dashboard=client.request('/api/dashboards/uid/'+uid)['dashboard']
        dashboard['id']=None
        (directory/name).write_text(json.dumps(dashboard,ensure_ascii=False,indent=2)+'\n')
        print('Exported '+str(directory/name))


if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=['validate','import-postgres','check','export'])
    action=parser.parse_args().action
    if action=='validate':
        validate()
    else:
        client=Grafana()
        {'import-postgres':import_postgres,'check':check,'export':export}[action](client)
