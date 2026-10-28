"""Audit actual all-frame HDR metering, historical contracts, staged bytes and ordinary push."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,re,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-hdr-measure-20261028-r1'
BASELINE='f338da947d4bb79321c55783ba133ded7b3f7b1e'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
# Limit worktree enumeration to this delivery. The shared repository has over
# 100000 tracked historical evidence files; do not rehash unrelated history or
# include another task's changes in our staging/publication audit.
SCOPE=['.gitattributes','agent-ffmpeg-local-install-manifest.json','README.md','README.zh-TW.md','README.en.md',
 'product/src/ai_ad_editor','product/tests/test_hdr_measure.py','product/pyproject.toml',
 'scripts/*hdr_measure*20261029.py','scripts/package_community_skill.py',
 'skills/agent-ffmpeg-local-editor','docs/README.md','docs/product/HDR_MEASUREMENT.md',
 'docs/product/hdr-measure-capabilities-cli-0.1.49.json','docs/product/HDR_DISPLAY.md','docs/product/HDR_METADATA.md','docs/product/ICC_OUTPUT.md',
 'docs/product/CASES.md','docs/product/COMMUNITY_LOCAL_DELIVERY.md','docs/product/GOAL_GAPS_20261025.md',
 'docs/product/CAPABILITIES*.md','docs/product/SKILLS*.md','docs/skills/UNIFIED_SKILL*.md',
 'docs/skills/community-unified-skill-package-0.1.49-r50.json','docs/skills/agent-editor-kit-community-unified-skill-r50.zip',
 'docs/releases/CLI_0.1.49_LOCAL.md','docs/validation/全帧HDR光量与裁切汇总实测_2026-10-29.md',
 'docs/validation/evidence/native-hdr-measure-20261028-r1','docs/assets/native-hdr-measure-20261029-*']

def git(*args):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT)
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d+)\s*\|.*$',s,re.M)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--staged',action='store_true');ap.add_argument('--postpush',action='store_true');a=ap.parse_args();assert a.run.replace('-','').isalnum()
 out=ROOT/'local/agent-ffmpeg'/('native-hdr-measure-postpush-'+a.run) if a.postpush else BASE/(('staged-' if a.staged else 'final-')+a.run)
 out.mkdir(parents=True,exist_ok=False);(out/'executed-auditor.py').write_bytes(Path(__file__).read_bytes())
 report=dict(status='running',at_utc=datetime.now(timezone.utc).isoformat(),whole_goal_complete=False)
 try:
  install=load(BASE/'installation-final-r1/verification.json');installed=Path(install['installed']);source=ROOT/'product/src/ai_ad_editor'
  assert install['cli_version']=='0.1.49' and install['status']=='installed-and-byte-verified'
  pins={p.name:sha(p) for p in source.glob('*.py')};assert len(pins)==275 and pins=={p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
  counts={}
  for run in ('source-r4','installed-r1','installed-compat-r1'):
   test=load(BASE/run/'verification.json');assert test['status']=='passed' and test['failures']==test['errors']==test['skipped']==0 and test['product_files']==pins
   counts[run]=test['tests']
   for n,d in test['test_files'].items():assert sha(ROOT/'product/tests'/(n+'.py'))==d
  assert counts=={'source-r4':19,'installed-r1':19,'installed-compat-r1':352}
  assert sha(install['archive'])==install['archive_sha256'] and Path(install['archive']).stat().st_size==install['archive_bytes']
  assert 'sha256:'+sha(ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.47/unpacked-r1/manifest.json')==install['manifest_sha256']
  for name,d in install['native_ICC_artifacts'].items():assert sha(source/name)==sha(installed/'site/ai_ad_editor'/name)==d
  assert (source/'agent-project.schema.json').read_bytes()==(ROOT/'docs/specs/agent-project.schema.json').read_bytes()==(installed/'site/ai_ad_editor/agent-project.schema.json').read_bytes()
  case=load(BASE/'case-r2/verification.json');assert case['status']=='passed'
  assert all(c['ok'] for c in load(BASE/'case-r2/checks.json'))
  assert case['frames']==48 and case['independent_pixels']==11059200 and case['encoded_video_bytes']==66355200 and case['PCM_scalar_count']==384000
  assert case['GPU_Bloom_calls']==48 and case['native_proof_frames']==48 and case['independent_maximum_error_nits']<1e-8
  assert not case['human_listening'] and not case['continuous_human_playback'] and not case['HDR_monitor_accepted'] and not case['whole_goal_complete']
  oracle=load(BASE/'case-r2/independent-oracle.json');assert oracle['status']=='passed' and not oracle['product_modules_imported']
  assert oracle['frames']==48 and oracle['pixels']==11059200 and oracle['maximum_error_nits']<1e-8
  measured=load(BASE/'case-r2/measure.stdout.json')['data'];replayed=load(BASE/'case-r2/replay-measure.stdout.json')['data']
  assert measured['encoder_RGB16_input_sha256']==oracle['encoder_RGB16_input_sha256']
  for key in ('peak_pixel','maximum_frame_average','framed_metrics_sha256','encoder_RGB16_input_sha256','analyzed_duration_seconds'):assert measured[key]==replayed[key]
  assert measured['all_timeline_frames_measured'] and measured['full_canvas_measured'] and measured['frames']==48
  work=Path(case['work'])
  for first,second in [('original-video.bin','replay-video.bin'),('original-pcm.bin','replay-pcm.bin')]:assert sha(work/first)==sha(work/second)
  gm=load(BASE/'case-r2/gpu-measure.stdout.json')['data'];gr=load(BASE/'case-r2/gpu-render.stdout.json')['data']
  assert gm['encoder_RGB16_input_sha256']==gr['delivery']['pixel_pipeline']['transport']['video_input_sha256']
  gpu=gm['timeline']['projection_acceleration'];proof=gm['timeline']['ICC_proofing']
  assert gpu['operations']['glow']==48 and gpu['worker_closed'] and gpu['control']['threads_closed'] and proof['converted_frames']==48 and proof['native_handles_closed']
  assert load(BASE/'case-r1/verification.json')['status']=='failed'
  public=ROOT/'docs/assets/native-hdr-measure-20261029-r2';media=load(public/'media-manifest.json')
  assert {p.name for p in public.iterdir() if p.is_file() and p.name!='media-manifest.json'}=={r['path'] for r in media['files']}
  for row in media['files']:assert sha(public/row['path'])==row['sha256'] and (public/row['path']).stat().st_size==row['bytes']
  review=load(BASE/'static-review.json');assert review['status']=='static-image-inspected' and sha(public/'actual-frame.png')==review['sha256']
  ns=load(ROOT/'agent-ffmpeg-local-install-manifest.json');assert ns['cli_version']=='0.1.49' and len(ns['files'])==88 and len(ns['skills'])==1
  for row in ns['files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
  assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
  activation=load(BASE/'activation-final-r2/activation-and-registration.json');reg=activation['registration']
  assert activation['status']=='passed' and reg['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json') and reg['launcher_preflight_verified'] and reg['registered_cli_version']=='0.1.49'
  kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.49-r50.json');fresh=load(BASE/'kit-r1/verification.json')
  assert fresh['status']=='passed' and fresh['files']==144 and fresh['skill_files']==88 and not fresh['real_discovery_changed'] and sha(ROOT/kit['archive'])==kit['sha256']
  with zipfile.ZipFile(ROOT/kit['archive']) as z:
   assert len(z.namelist())==144 and 'docs/product/HDR_MEASUREMENT.md' in z.namelist()
   for row in json.loads(z.read('KIT-FILES.json'))['files']:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
  caps=load(ROOT/'docs/product/hdr-measure-capabilities-cli-0.1.49.json')['data']['capabilities'];assert len(caps)==88
  documents=[]
  for suffix in ('','.zh-TW','.en'):
   p='README'+suffix+'.md';s=(ROOT/p).read_text('utf8');old=rows(git('show',BASELINE+':'+p).decode('utf8'),'R');now=rows(s,'R')
   assert len(old)==327 and len(now)==332 and all(now[k]==v for k,v in old.items())
   assert len(rows(s,'F'))==75 and len(rows(s,'S'))==30 and len(rows(s,'K'))==17
   assert 'CLI0.1.49 / alpha.4-local.47 / r50 kit' in s and 'local.47/final-r1/installed' in s;documents.append(ROOT/p)
   manual=ROOT/('docs/product/CAPABILITIES'+suffix+'.md');m=manual.read_text('utf8');documents.append(manual)
   assert len(rows(m,'F'))==75 and len(rows(m,'S'))==30
   for key,value in caps.items():
    section=re.search(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n(.*?)\n```',m,re.M|re.S);assert section and json.loads(section[1])==value,key
   documents.extend([ROOT/('docs/product/SKILLS'+suffix+'.md'),ROOT/('docs/skills/UNIFIED_SKILL'+suffix+'.md')])
  p='docs/product/GOAL_GAPS_20261025.md';old=rows(git('show',BASELINE+':'+p).decode('utf8'),'G');now=rows((ROOT/p).read_text('utf8'),'G')
  assert len(old)==len(now)==38 and all(now[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
  documents.extend(ROOT/p for p in ['docs/README.md','docs/product/HDR_MEASUREMENT.md','docs/product/ICC_OUTPUT.md','docs/product/HDR_DISPLAY.md','docs/product/HDR_METADATA.md','docs/product/GOAL_GAPS_20261025.md','docs/product/CASES.md','docs/product/COMMUNITY_LOCAL_DELIVERY.md','docs/releases/CLI_0.1.49_LOCAL.md','docs/validation/全帧HDR光量与裁切汇总实测_2026-10-29.md'])
  links=[]
  for path in documents:
   for m in re.finditer(r'!?\[[^\]]*\]\(([^\n)]+)\)',path.read_text('utf8')):
    target=m[1].split('#')[0]
    if not target or re.match(r'^[a-zA-Z]+:',target):continue
    assert (path.parent/target).resolve().exists(),(path,target);links.append(dict(document=str(path.relative_to(ROOT)),target=m[1]))
  changes=[v.decode('utf8') for v in git('diff','--name-only','-z',BASELINE,'--',*SCOPE).split(b'\0') if v]
  if not a.postpush:changes += [v.decode('utf8') for v in git('ls-files','--others','--exclude-standard','-z','--',*SCOPE).split(b'\0') if v]
  assert not any(p.startswith('sources/littlecms-2.19.1/') for p in changes);checked=[]
  for name in sorted(set(changes)):
   path=ROOT/name;assert path.is_file(),name
   if path.resolve().is_relative_to(out.resolve()):continue
   if a.staged or a.postpush:assert hashlib.sha256(git('show',('HEAD:' if a.postpush else ':')+name)).hexdigest()==sha(path),name
   checked.append(dict(path=name,bytes=path.stat().st_size,sha256=sha(path)))
  assert git('branch','--show-current').decode().strip()=='main' and git('remote','get-url','--push','origin').decode().strip()=='git@github.com:copypasteltd/agent-editor-kit.git'
  if a.postpush:
   head=git('rev-parse','HEAD').decode().strip();origin=git('rev-parse','origin/main').decode().strip();advertised=git('ls-remote','origin','refs/heads/main').decode().split()[0]
   assert head==origin==advertised and not git('status','--porcelain','--untracked-files=normal','--',*SCOPE).strip()
   report.update(HEAD=head,origin_main=origin,advertised_main=advertised,clean_task_paths=True,whole_worktree_status_not_claimed=True)
  report.update(status='passed',product_files=275,capabilities=88,skill_files=88,public_skills=1,internal_modules=17,tests=counts,
   F=75,S=30,K=17,R=332,prior_R_retained=327,G_closure_cells_retained=38,local_links_checked=len(links),files_checked=len(checked),files=checked,installed=str(installed),staged=a.staged,postpush=a.postpush)
  (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False),flush=True)
 except BaseException as e:
  report.update(status='failed',error=repr(e));(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n');raise
if __name__=='__main__':main()
