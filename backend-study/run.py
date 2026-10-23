#!/usr/bin/env python3
"""Fail-closed local setup/collection; operates ONLY on compose project unibackend."""
from pathlib import Path
from datetime import datetime,timezone
import subprocess,sys,time,os,json,signal,hashlib,platform,uuid
B=Path(__file__).resolve().parent;R=B.parent;RAW=B/'results/raw';RAW.mkdir(parents=True,exist_ok=True)
C=['docker','compose','-p','unibackend','-f',str(B/'docker-compose.yml')]
now=lambda:datetime.now(timezone.utc).isoformat()
def append(name,obj):
 with (RAW/name).open('a') as f:f.write(json.dumps({'at':now(),**obj})+'\n')
def guard():
 p=subprocess.run(['pgrep','-f','[h]arness[.]mjs'],capture_output=True,text=True)
 if p.returncode not in (0,1):raise RuntimeError('Process enumeration unavailable; refusing load')
 return p.returncode==1,p.stdout.strip().splitlines()
def stop_ours():subprocess.run(C+['stop','-t','0','api','db','redis'],cwd=R,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
def stage(name,cmd,collection):
 clear,pids=guard();append('batches.jsonl',{'event':'start','stage':name,'collection':collection,'guard_clear':clear,'pids':pids,'command':cmd})
 if not clear:raise RuntimeError('Main research driver active; no load started')
 with (RAW/(name+'-'+collection+'.txt')).open('w') as out:
  p=subprocess.Popen(cmd,cwd=R,stdout=out,stderr=subprocess.STDOUT,start_new_session=True)
  while p.poll() is None:
   clear,pids=guard()
   if not clear:
    append('batches.jsonl',{'event':'abort','stage':name,'collection':collection,'guard_clear':False,'pids':pids})
    os.killpg(p.pid,signal.SIGTERM);stop_ours();p.wait();raise RuntimeError('Guard abort; attempt preserved, all its measurements excluded')
   time.sleep(.25)
  clear,pids=guard();append('batches.jsonl',{'event':'end','stage':name,'collection':collection,'guard_clear':clear,'pids':pids,'exit':p.returncode})
  if not clear:stop_ours();raise RuntimeError('Guard not clear after batch')
  if p.returncode:raise RuntimeError('Stage failed; inspect '+str(RAW/(name+'-'+collection+'.txt')))
  return RAW/(name+'-'+collection+'.txt')
def output(cmd):return subprocess.check_output(cmd,text=True).strip()
if __name__=='__main__':
 collection='backend-'+uuid.uuid4().hex[:12]
 clear,_=guard()
 if not clear:raise SystemExit('Main research driver active: no load started. Coding/writing may continue.')
 awake=subprocess.Popen(['caffeinate','-i','-s','-w',str(os.getpid())])
 try:
  sources={str(p.relative_to(B)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(B.rglob('*')) if p.is_file() and ('src' in p.parts or 'sql' in p.parts or p.name in ['manifest.json','PROTOCOL.md','run.py','Dockerfile','docker-compose.yml'])}
  env={'collection':collection,'at':now(),'platform':platform.platform(),'macos':output(['sw_vers','-productVersion']),'cpu':output(['sysctl','-n','machdep.cpu.brand_string']),'memory_bytes':int(output(['sysctl','-n','hw.memsize'])),'logical_cpus':int(output(['sysctl','-n','hw.logicalcpu'])),'node':output(['node','--version']),'docker':output(['docker','version','--format','{{json .}}']),'vm':output(['docker','info','--format','{{json .NCPU}} {{json .MemTotal}}']),'source_sha256':sources,'dump_sha256':hashlib.sha256((R/'app/generated_test_data_dump.sql').read_bytes()).hexdigest(),'git_head':output(['git','rev-parse','HEAD'])}
  (RAW/('environment-'+collection+'.json')).write_text(json.dumps(env,indent=2)+'\n')
  stage('build',C+['build','api'],collection)
  stage('startup',C+['up','-d'],collection)
  # The final TCP healthcheck excludes the temporary import server.
  prep=stage('correctness',C+['exec','-T','api','node','prepare.cjs'],collection)
  if not any('"type":"complete"' in x and '"PASS"' in x for x in prep.read_text().splitlines()):raise RuntimeError('Missing correctness completion marker')
  stage('plans',C+['exec','-T','api','node','plans.cjs'],collection)
  stage('measurement',['node',str(B/'src/runner.mjs'),collection],collection)
  append('collections.jsonl',{'collection':collection,'status':'accepted','manifest_sha256':sources['manifest.json']})
  print('Accepted collection:',collection,flush=True)
 finally:
  stop_ours();awake.terminate()
