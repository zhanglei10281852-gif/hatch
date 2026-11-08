import hashlib,json,os,pathlib,subprocess,sys,threading,http.server,zipfile,tarfile,time
import tempfile
ROOT=pathlib.Path(__file__).resolve().parent.parent
WORK=pathlib.Path(os.environ.get('HATCH_REVIEW_WORK',tempfile.mkdtemp(prefix='hatch-review-')))
WORK.mkdir(parents=True,exist_ok=True)
PY=pathlib.Path(sys.executable)
UV=pathlib.Path(sys.executable).parent/('uv.exe' if os.name == 'nt' else 'uv')
FIX=WORK/'fixtures-v3'
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
 state=WORK/'states-v3'/(env_name or name);state.mkdir(parents=True,exist_ok=True)
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
 # Prove the spawned interpreter and native installer cannot fetch public distributions.
 probe_env={**base_env,'UV_OFFLINE':'0','UV_HTTP_RETRIES':'0'}
 probes=[]
 for command in [[str(PY),'-c','import socket; socket.create_connection(("1.1.1.1",443),timeout=2)'],[str(UV),'pip','install','--python',str(PY),'--no-deps','https://example.com/reviewer_probe-1.0-py3-none-any.whl']]:
  p=subprocess.run(command,env=probe_env,capture_output=True,text=True,timeout=20);probes.append({'command':command,'code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
 (WORK/'network-proof.json').write_text(json.dumps({'probes':probes,'deniedProxy':denied,'mechanism':'Python child socket.connect guard plus deny-only HTTP(S) proxy; uv --offline/no-index/no-cache, local fixed wheels only; all core child envs inherit restrictions'},indent=2))
 # Run all real CLI paths; no selector, backend, Git, metadata or subprocess is mocked.
 items=[('pkgs/core','Core.Lib'),('pkgs/client','client-app',['core_lib>=999; python_version < "0"']),('pkgs/final','final-app',[],{'never':['client-app']}),('pkgs/unused','unused'),('pkgs/excluded','excluded')]
 r=workspace('closure',items,members=['pkgs/*'],exclude=['pkgs/excluded']);change(r,'pkgs/core/src/core_lib/__init__.py');x=run('closure',r,changed_args());expect_build(x,['pkgs/client','pkgs/core','pkgs/final']);check(x,'excludedAndUnrelatedAbsent',not any('unused' in f or 'excluded' in f for f in x['artifactsAfter']))
 r=workspace('mixed-states',[('a','a'),('b','b'),('c','c'),('d','d')]);change(r,'a/src/a/__init__.py');git(r,'add','a');git(r,'commit','-m','committed change');change(r,'b/src/b/__init__.py');git(r,'add','b');change(r,'c/src/c/__init__.py');write(r,'d/untracked.py','ignored');x=run('mixed-states',r,changed_args('HEAD~1'));expect_build(x,['a','b','c'])
 r=workspace('deep-paths',[('pkgs/foo','foo'),('pkgs/foobar','foobar'),('pkgs/foo/nested','nested'),('pkgs/has space','spaced')]);change(r,'pkgs/foo/nested/src/nested/__init__.py');change(r,'pkgs/has space/src/spaced/__init__.py');x=run('deep-paths',r,changed_args());expect_build(x,['pkgs/foo/nested','pkgs/has space'])
 r=workspace('rename-delete',[('a','a'),('b','b'),('c','c')]);write(r,'a/moving.txt','move');write(r,'c/deleted.txt','delete');git(r,'add','-A');git(r,'commit','-m','rename inputs');git(r,'mv','a/moving.txt','b/moving.txt');git(r,'rm','c/deleted.txt');x=run('rename-delete',r,changed_args());expect_build(x,['a','b','c'])
 r=workspace('orphan',[('pkgs/a','a'),('pkgs/b','b'),('pkgs/c','c')],members=['pkgs/*'],exclude=['pkgs/c']);change(r,'shared.txt');x=run('orphan',r,changed_args());expect_build(x,['pkgs/a','pkgs/b'])
 r=workspace('root-dedup',[('a','a')],root_project=True,members=['../root-dedu?','a']);change(r,'shared.txt');x=run('root-dedup',r,changed_args());expect_build(x,['.'])
 r=workspace('unchanged',[('a','a'),('dynamic','dynamic',[],None,True)]);write(r,'dist/sentinel.whl','do not alter');write(r,'a/untracked.txt','untracked');x=run('unchanged',r,changed_args('HEAD','--clean'));check(x,'noChangesSuccess',x['code']==0 and 'nothing to build' in x['stderr']+x['stdout']);check(x,'noBackendOrEnvironment',not x['events'] and not x['environmentPaths']);check(x,'artifactsUntouched',x['artifactsBefore']==x['artifactsAfter'])
 r=workspace('dynamic',[('core','Core.Lib'),('client','client-app'),('dynamic','dynamic-app',[],None,True),('unused','unused')]);change(r,'core/src/core_lib/__init__.py');x=run('dynamic',r,changed_args());expect_build(x,['core','dynamic']);check(x,'actualDynamicMetadata',any(e['phase']=='metadata' for e in x['events']))
 r=workspace('cycle',[('a','a',['b']),('b','b',['a']),('c','c')]);change(r,'a/src/a/__init__.py');x=run('cycle',r,changed_args());expect_build(x,['a','b'])
 r=workspace('invalid-ref',[('a','a')]);write(r,'dist/sentinel.whl','preserve');x=run('invalid-ref',r,changed_args('no-such-ref','--clean'));check(x,'locatedFailureBeforeSideEffects',x['code']!=0 and 'Invalid Git reference' in x['stderr']+x['stdout'] and not x['events'] and x['artifactsBefore']==x['artifactsAfter']);x=run('requires-all',r,['build','--changed-since','HEAD']);check(x,'requiresAll',x['code']!=0 and 'together with' in x['stderr']+x['stdout'] and not x['events'])
 r=workspace('cross-tree',[('a','a'),('b','b')]);git(r/'b','init');git(r/'b','config','user.name','review');git(r/'b','config','user.email','review@example.invalid');git(r/'b','add','-A');git(r/'b','commit','-m','nested independent repo');change(r,'a/src/a/__init__.py');x=run('cross-tree',r,changed_args('HEAD','--clean'));check(x,'crossTreeFailsBeforeBuild',x['code']!=0 and 'multiple working trees' in x['stderr']+x['stdout'] and not x['events'])
 r=workspace('duplicate-member-change',[('a','dupe.name'),('b','dupe-name')]);change(r,'a/src/dupe_name/__init__.py');write(r,'dist/dupe_name-1.0.0-py2.py3-none-any.whl','SENTINEL');x=run('duplicate-member-change',r,changed_args('HEAD','--clean'));check(x,'duplicateRejectedBeforeBuild',x['code']!=0 and 'normalize to the same name' in x['stderr']+x['stdout'] and not x['events'] and x['artifactsBefore']==x['artifactsAfter'])
 r=workspace('metadata-member-change',[('a','a'),('z-dynamic','dynamic-app',[],None,True)]);change(r,'a/src/a/__init__.py');write(r,'z-dynamic/fail-metadata','fail');write(r,'dist/a-1.0.0-py2.py3-none-any.whl','SENTINEL');x=run('metadata-member-change',r,changed_args('HEAD','--clean'));check(x,'metadataFailureBeforeBuild',x['code']!=0 and 'CONTROLLED_METADATA_FAILURE' in x['stderr']+x['stdout'] and not built(x) and x['artifactsBefore']==x['artifactsAfter']);(r/'z-dynamic/fail-metadata').unlink();x=run('metadata-member-repaired',r,changed_args(),env_name='metadata-member-change');expect_build(x,['a'])
 # Adversarial reachable combination: shared tracked input forces all before validation.
 for trial in range(1,3):
  r=workspace('duplicate-orphan-'+str(trial),[('a','dupe.name'),('b','dupe-name')]);change(r,'shared.txt');write(r,'dist/dupe_name-1.0.0-py2.py3-none-any.whl','SENTINEL');x=run('duplicate-orphan-'+str(trial),r,changed_args('HEAD','--clean'));check(x,'mustRejectDuplicateBeforeBuild',x['code']!=0 and not built(x) and x['artifactsBefore']==x['artifactsAfter']);x['observedDefect']='duplicate error bypassed' if x['code']==0 and len(built(x))==2 else None
  r=workspace('metadata-orphan-'+str(trial),[('a','a'),('z-dynamic','dynamic-app',[],None,True)]);change(r,'shared.txt');write(r,'z-dynamic/fail-metadata','fail');write(r,'dist/a-1.0.0-py2.py3-none-any.whl','SENTINEL');x=run('metadata-orphan-'+str(trial),r,changed_args('HEAD','--clean'));check(x,'mustPreflightAllMetadataBeforeBuild',x['code']!=0 and not built(x) and x['artifactsBefore']==x['artifactsAfter']);x['observedDefect']='a built and prior wheel overwritten before metadata failure' if built(x)==['a'] and 'CONTROLLED_METADATA_FAILURE' in x['stderr']+x['stdout'] else None
 # Default compatibility, explicit output, target and root semantics.
 r=workspace('default-all',[('a','a'),('b','b')],root_project=True,members=['a','b']);x=run('default-all',r,['build','output','--all']);check(x,'defaultAllOrder',built(x)==['.','a','b']);check(x,'defaultTargetsAndOutput',x['code']==0 and len(x['artifactsAfter'])==6 and all(f.startswith('output/') for f in x['artifactsAfter']))
 r=workspace('default-single',[('a','a')],root_project=True);x=run('default-single',r,['build','output','-t','wheel']);expect_build(x,['.']);check(x,'explicitOutput',all(f.startswith('output/') for f in x['artifactsAfter']))
except BaseException as e:
 import traceback
 results.append({'driverError':traceback.format_exc()});print(traceback.format_exc(),flush=True)
finally:
 proxy.shutdown();proxy.server_close()
 summary={'cases':len(results),'checks':sum(len(r.get('checks',{})) for r in results),'passed':sum(sum(r.get('checks',{}).values()) for r in results),'failed':[(r.get('name'),k) for r in results for k,v in r.get('checks',{}).items() if not v],'driverErrors':[r for r in results if 'driverError'in r]}
 (WORK/'verification.json').write_text(json.dumps({'results':results,'summary':summary,'sourceRoot':str(ROOT),'networkDeniedProxy':denied},ensure_ascii=False,indent=2),encoding='utf8')
 print(json.dumps(summary,ensure_ascii=False,indent=2),flush=True)
