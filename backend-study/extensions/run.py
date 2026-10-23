#!/usr/bin/env python3
"""Guarded collection for the extension experiments; operates ONLY on compose project unibackendx."""
from pathlib import Path
import sys,subprocess,os,uuid,json,hashlib,platform
X=Path(__file__).resolve().parent;B=X.parent;R=B.parent
sys.path.insert(0,str(B))
import run as base
RAW=X/'results/raw';RAW.mkdir(parents=True,exist_ok=True)
C=['docker','compose','-p','unibackendx','-f',str(X/'docker-compose.yml')]
base.RAW=RAW;base.C=C   # reuse the primary guard/stage logic against this project
if __name__=='__main__':
 collection='ext-'+uuid.uuid4().hex[:12]
 clear,_=base.guard()
 if not clear:raise SystemExit('Main research driver active: no load started.')
 awake=subprocess.Popen(['caffeinate','-i','-s','-w',str(os.getpid())])
 try:
  sources={str(p.relative_to(X)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(X.rglob('*')) if p.is_file() and 'results' not in p.parts and p.suffix in ('.cjs','.mjs','.py','.yml','.json') or p.name=='Dockerfile'}
  sources.update({'sql/'+p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted((B/'sql').glob('*.sql'))})
  env={'collection':collection,'at':base.now(),'platform':platform.platform(),'macos':base.output(['sw_vers','-productVersion']),'cpu':base.output(['sysctl','-n','machdep.cpu.brand_string']),'docker':base.output(['docker','version','--format','{{.Server.Version}}']),'sources':sources,'git_commit':base.output(['git','-C',str(R),'rev-parse','HEAD'])}
  (RAW/('environment-'+collection+'.json')).write_text(json.dumps(env,indent=2)+'\n')
  base.stage('build',C+['build','api','api_default'],collection)
  base.stage('startup',C+['up','-d'],collection)
  prep=base.stage('correctness',C+['exec','-T','api','node','prepare.cjs'],collection)
  if not any('"type":"complete"' in x and '"PASS"' in x for x in prep.read_text().splitlines()):raise RuntimeError('Missing correctness completion marker')
  for api,svc in [('tuned','api'),('default','api_default')]:
   plans=base.stage('plans-'+api,C+['exec','-T',svc,'node','plans.cjs',api],collection)
  base.stage('settings',['sh','-c','curl -s http://127.0.0.1:24002/settings; echo; curl -s http://127.0.0.1:24003/settings'],collection)
  base.stage('measurement',['node',str(X/'runner.mjs'),collection],collection)
  base.append('collections.jsonl',{'collection':collection,'status':'accepted','manifest_sha256':sources['manifest.json']})
  print('Accepted collection:',collection,flush=True)
 finally:
  base.stop_ours();awake.terminate()
