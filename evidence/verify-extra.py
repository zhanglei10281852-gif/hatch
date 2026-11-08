import hashlib,json,os,pathlib,subprocess,sys,threading,http.server,zipfile,tarfile,time
import tempfile
ROOT=pathlib.Path(__file__).resolve().parent.parent
WORK=pathlib.Path(os.environ.get('HATCH_REVIEW_WORK',tempfile.mkdtemp(prefix='hatch-review-')))
WORK.mkdir(parents=True,exist_ok=True)
PY=pathlib.Path(sys.executable)
UV=pathlib.Path(sys.executable).parent/'uv.exe'
FIX=WORK/'fixtures-v5'
FIX.mkdir(exist_ok=True)
GUARD=WORK/'network-guard';GUARD.mkdir(exist_ok=True)
(GUARD/'sitecustomize.py').write_text('''import socket,os,json
_connect=socket.socket.connect
def guarded(self,address):
 if isinstance(address,tuple) and str(address[0]) not in ('127.0.0.1','::1','localhost'):
  with open(os.environ['HATCH_REVIEW_NETWORK_LOG'],'a') as f:f.write(json.dumps({'denied':str(address)})+'\\n')
  raise OSError('HATCH_REVIEW_PUBLIC_NETWORK_DENIED '+str(address))
 return _connect(self,address)
socket.socket.connect=guarded
''',encoding='utf8')
denied=[]
class Deny(http.server.BaseHTTPRequestHandler):
 def do_GET(self):
  denied.append({'method':'GET','url':self.path});self.send_response(403);self.end_headers();self.wfile.write(b'HATCH_REVIEW_PUBLIC_NETWORK_DENIED')
 def do_CONNECT(self):
  denied.append({'method':'CONNECT','url':self.path});self.send_response(403);self.end_headers()
 def log_message(self,*a):pass
proxy=http.server.ThreadingHTTPServer(('127.0.0.1',0),Deny)
threading.Thread(target=proxy.serve_forever,daemon=True).start()
base_env={**os.environ,'PYTHONPATH':str(GUARD)+os.pathsep+str(ROOT/'src'),'PYTHONNOUSERSITE':'1','PYTEST_DISABLE_PLUGIN_AUTOLOAD':'1',
 'PIP_NO_INDEX':'1','PIP_FIND_LINKS':str(ROOT/'evidence/offline'),'PIP_DISABLE_PIP_VERSION_CHECK':'1','UV_NO_INDEX':'1','UV_FIND_LINKS':str(ROOT/'evidence/offline'),
 'UV_OFFLINE':'1','UV_PYTHON_DOWNLOADS':'never','UV_NO_CACHE':'1','HATCH_ENV_TYPE_VIRTUAL_UV_PATH':str(UV),'PATH':str(PY.parent)+os.pathsep+os.environ['PATH'],
 'HTTP_PROXY':f'http://127.0.0.1:{proxy.server_port}','HTTPS_PROXY':f'http://127.0.0.1:{proxy.server_port}','ALL_PROXY':f'http://127.0.0.1:{proxy.server_port}',
 'NO_PROXY':'127.0.0.1,localhost','HATCH_REVIEW_NETWORK_LOG':str(WORK/'network-denied.jsonl'),'NO_COLOR':'1','COLUMNS':'160'}
for k in ['HATCH_ENV','HATCH_PROJECT','VIRTUAL_ENV','HATCH_ENV_ACTIVE','PYAPP','PYAPP_COMMAND_NAME'] :base_env.pop(k,None)
results=[]
def write(root,path,text):
 p=root/path;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(text,encoding='utf8');return p
def git(root,*args):
 p=subprocess.run(['git','-C',str(root),*args],capture_output=True,text=True,encoding='utf8',errors='replace')
 if p.returncode:raise RuntimeError(p.stderr)
 return p.stdout.strip()
def project(root,directory,name,deps=(),extras=None,dynamic=False):
 module=name.lower().replace('-','_').replace('.','_')
 t=f'[build-system]\nrequires=["hatchling==1.33.0"]\nbuild-backend="hatchling.build"\n[project]\nname={json.dumps(name)}\nversion="1.0.0"\n'
 if dynamic:t+='dynamic=["dependencies","optional-dependencies"]\n'
 else:
  t+='dependencies='+json.dumps(list(deps))+'\n'
  if extras:
   t+='[project.optional-dependencies]\n'+''.join(k+'='+json.dumps(v)+'\n' for k,v in extras.items())
 t+=f'[tool.hatch.build.targets.wheel]\npackages=["src/{module}"]\n[tool.hatch.build.hooks.custom]\n'
 if dynamic:t+='[tool.hatch.metadata.hooks.custom]\n'
 write(root,directory+'/pyproject.toml',t)
 write(root,directory+f'/src/{module}/__init__.py','VALUE=1\n')
 hook='''import os,json
from pathlib import Path
from hatchling.builders.hooks.plugin.interface import BuildHookInterface
from hatchling.metadata.plugin.interface import MetadataHookInterface
def record(root,phase):
 with open(os.environ['HATCH_REVIEW_EVENT_LOG'],'a',encoding='utf8') as f:f.write(json.dumps({'project':str(root),'phase':phase})+'\\n')
class BuildHook(BuildHookInterface):
 def initialize(self,version,build_data):record(self.root,'build-'+self.target_name)
 def clean(self,versions):record(self.root,'clean-'+self.target_name)
class MetadataHook(MetadataHookInterface):
 def update(self,metadata):
  record(self.root,'metadata')
  if (Path(self.root)/'fail-metadata').exists():raise RuntimeError('CONTROLLED_METADATA_FAILURE '+str(self.root))
  metadata['dependencies']=['Core.Lib>=999; python_version < "0"']
  metadata['optional-dependencies']={'unused':['client-app; sys_platform == "absent"']}
'''
 write(root,directory+'/hatch_build.py',hook)
 return root/directory
def workspace(name,items,*,root_project=False,members=None,exclude=None):
 root=FIX/name;root.mkdir()
 if root_project:project(root,'.','root-app')
 text='[tool.hatch.envs.default]\nworkspace.members='+json.dumps(members or [i[0] for i in items])+'\n'
 if exclude:text+='workspace.exclude='+json.dumps(exclude)+'\n'
 if root_project:
  with (root/'pyproject.toml').open('a',encoding='utf8') as f:f.write(text)
 else:write(root,'pyproject.toml',text)
 for item in items:project(root,*item)
 write(root,'shared.txt','shared-v1\n');write(root,'.gitignore','dist/\noutput/\n__pycache__/\n*.pyc\nfail-metadata\n')
 git(root,'init');git(root,'config','user.name','Delivery Reviewer');git(root,'config','user.email','review@example.invalid');git(root,'add','-A');git(root,'commit','-m','immutable fixture baseline')
 return root
def change(root,rel):
 with (root/rel).open('a',encoding='utf8') as f:f.write('\n# changed\n')
def snapshots(root):
 return {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file() and '.git' not in p.parts and ('dist' in p.parts or 'output' in p.parts)}
def run(name,root,args,*,env_name=None):
 state=WORK/'states-v5'/(env_name or name);state.mkdir(parents=True,exist_ok=True)
 config=state/'config.toml';config.write_text('mode="local"\n',encoding='utf8')
 log=state/'events.jsonl'
 env={**base_env,'HATCH_REVIEW_EVENT_LOG':str(log),'UV_CACHE_DIR':str(state/'uv-cache'),'PIP_CACHE_DIR':str(state/'pip-cache'),
 'APPDATA':str(state/'appdata'),'LOCALAPPDATA':str(state/'localappdata'),'XDG_CONFIG_HOME':str(state/'config'),'XDG_CACHE_HOME':str(state/'cache'),'XDG_DATA_HOME':str(state/'user-data')}
 cmd=[str(PY),'-m','hatch','--no-color','--config',str(config),'--data-dir',str(state/'data'),'--cache-dir',str(state/'hatch-cache'),*args]
 before=snapshots(root);old_events=len(log.read_text().splitlines()) if log.exists() else 0
 p=subprocess.run(cmd,cwd=root,env=env,capture_output=True,text=True,encoding='utf8',errors='replace',timeout=120)
 events=[json.loads(l) for l in log.read_text().splitlines()[old_events:]] if log.exists() else []
 artifacts=snapshots(root);entry={'name':name,'root':str(root),'args':args,'command':cmd,'code':p.returncode,'stdout':p.stdout,'stderr':p.stderr,'events':events,'artifactsBefore':before,'artifactsAfter':artifacts,'checks':{},'environmentPaths':[str(p) for p in (state/'data').rglob('pyvenv.cfg')] if (state/'data').exists() else []}
 results.append(entry);print(name,'exit',p.returncode,'builds',[pathlib.Path(x['project']).name for x in events if x['phase'].startswith('build')],flush=True)
 return entry
def check(r,k,v):
 r['checks'][k]=bool(v)
 if not v:print('CHECK FAILED',r['name'],k,flush=True)
def built(r):return [str(pathlib.Path(x['project']).relative_to(pathlib.Path(r['root']))).replace('\\','/') for x in r['events'] if x['phase']=='build-wheel']
def expect_build(r,names):
 check(r,'successfulActualBuild',r['code']==0);check(r,'selectedOrder',built(r)==names)
 check(r,'wheelCount',sum(p.endswith('.whl') for p in r['artifactsAfter'])==len(names))
 for f in r['artifactsAfter']:
  if f.endswith('.whl'):
   with zipfile.ZipFile(pathlib.Path(r['root'])/f) as z:check(r,'validWheel-'+f,any(n.endswith('METADATA') for n in z.namelist()))
def changed_args(ref='HEAD',*extra):return ['build','--all','--changed-since',ref,'-t','wheel',*extra]
try:
 r=workspace('selected-environment',[('a','a'),('b','b')])
 with (r/'pyproject.toml').open('a') as f:f.write('[tool.hatch.envs.selected]\nworkspace.members=["b"]\n')
 with (r/'b/pyproject.toml').open('a') as f:f.write('[tool.hatch.envs.selected]\nbuilder=true\ndetached=true\nskip-install=true\n')
 git(r,'add','-A');git(r,'commit','-m','selected env config');change(r,'shared.txt');x=run('selected-environment',r,['-e','selected',*changed_args()]);expect_build(x,['b'])
 r=workspace('direct-diverged-ref',[('a','a'),('b','b')]);original=git(r,'branch','--show-current');git(r,'checkout','-b','reference');change(r,'a/src/a/__init__.py');git(r,'add','a');git(r,'commit','-m','ref-only change');git(r,'checkout',original);change(r,'b/src/b/__init__.py');git(r,'add','b');git(r,'commit','-m','current-only change');x=run('direct-diverged-ref',r,changed_args('reference'));expect_build(x,['a','b'])
 r=workspace('dynamic-optional',[('core','Core.Lib'),('client','client-app'),('dynamic','dynamic-app',[],None,True),('unused','unused')]);change(r,'client/src/client_app/__init__.py');x=run('dynamic-optional',r,changed_args());expect_build(x,['client','dynamic'])
 r=workspace('explicit-selected-output',[('a','a'),('b','b')],root_project=True);change(r,'a/src/a/__init__.py');x=run('explicit-selected-output',r,['build','output','--all','--changed-since','HEAD','-t','sdist','-t','wheel']);check(x,'selectedTargetsOrderAndOutput',x['code']==0 and built(x)==['a'] and len(x['artifactsAfter'])==2 and all(f.startswith('output/') for f in x['artifactsAfter']) and sorted(e['phase'] for e in x['events'])==['build-sdist','build-wheel'])
finally:
 proxy.shutdown();proxy.server_close()
 summary={'cases':len(results),'checks':sum(len(r['checks']) for r in results),'failed':[(r['name'],k) for r in results for k,v in r['checks'].items() if not v]}
 (WORK/'verification-extra.json').write_text(json.dumps({'results':results,'summary':summary},ensure_ascii=False,indent=2),encoding='utf8');print(summary)
