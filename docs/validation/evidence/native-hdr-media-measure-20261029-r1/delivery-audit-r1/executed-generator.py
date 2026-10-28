"""Audit actual installed HDR delivery, original history, Skill pins, kit and case evidence."""
from pathlib import Path
import argparse,ast,hashlib,json,re,subprocess,zipfile
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-hdr-media-measure-20261029-r1'
BASELINE='1e15148d28a52d5fa8473adda0cefc1547079bda'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
DOCS=['.gitattributes','README.md','README.en.md','README.zh-TW.md','agent-ffmpeg-local-install-manifest.json','scripts/package_community_skill.py',
 'docs/README.md','docs/product/GOAL_GAPS_20261025.md','docs/product/HDR_MEDIA_MEASUREMENT.md','docs/product/HDR_MEASUREMENT.md',
 'docs/product/CASES.md','docs/product/COMMUNITY_LOCAL_DELIVERY.md','docs/releases/CLI_0.1.50_LOCAL.md','docs/releases/CLI_0.1.50_SOURCE.md',
 'docs/validation/编码后成片安装与跨编码实测_2026-10-29.md','docs/product/hdr-media-measure-capabilities-cli-0.1.50.json',
 'docs/skills/agent-editor-kit-community-unified-skill-r51.zip','docs/skills/community-unified-skill-package-0.1.50-r51.json']
for suffix in ('','.en','.zh-TW'):
 DOCS += ['docs/product/CAPABILITIES'+suffix+'.md','docs/product/SKILLS'+suffix+'.md','docs/skills/UNIFIED_SKILL'+suffix+'.md']
SCRIPTS=['build_hdr_media_measure','pin_hdr_media_measure','activate_hdr_media_measure','validate_hdr_media_skill',
 'run_hdr_media_installed_case','review_hdr_media_installed_case','verify_hdr_media_replay','document_hdr_media_delivery',
 'write_hdr_media_delivery_reports','verify_hdr_media_kit','publish_hdr_media_kit','audit_hdr_media_delivery']
OWNED=DOCS+['scripts/'+n+'_20261029.py' for n in SCRIPTS]


def load(p):return json.loads(Path(p).read_bytes())
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def git(*args):return subprocess.run([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,capture_output=True,check=True).stdout
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
 out=BASE/('delivery-audit-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
 product=ROOT/'product/src/ai_ad_editor';pins={p.name:sha(p) for p in product.glob('*.py')};assert len(pins)==276
 assert pins==load(BASE/'source-r3/verification.json')['product_files']
 install=load(BASE/'installation-final-r1/verification.json');assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.50'
 installed=Path(install['installed']);assert pins=={p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
 assert sha(Path(install['archive']))==install['archive_sha256'] and Path(install['archive']).stat().st_size==install['archive_bytes']==303217936
 assert 'sha256:'+sha(installed.parents[1]/'unpacked-r1/manifest.json')==install['manifest_sha256']
 for name,n in [('installed-r1',29),('installed-boundary-r1',42),('installed-compat-r1',352)]:
  r=load(BASE/name/'verification.json');assert r['status']=='passed' and r['tests']==n and r['failures']==r['errors']==r['skipped']==0
  assert r['product_files']==pins and Path(r['installed'])==installed
  for key,digest in r['test_files'].items():assert sha(ROOT/'product/tests'/(key+'.py'))==sha(BASE/name/'executed-tests'/(key+'.py'))==digest
 namespace=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(namespace)
 assert (m['release'],m['cli_version'],m['manifest_sha256'])==('v0.1.0-alpha.4-local.48','0.1.50',install['manifest_sha256'])
 assert m['skill_count']==1 and m['module_count']==17 and len(m['files'])==89
 assert sum(Path(r['path']).name=='SKILL.md' for r in m['files'])==1
 for row in m['files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
 assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==ROOT/'skills/agent-ffmpeg-local-editor'
 runtime=load(ROOT/'local/agent-ffmpeg/runtime.json');assert Path(runtime['installed_directory'])==installed and runtime['manifest_sha256']==m['manifest_sha256'] and runtime['release']==m['release']
 activation=load(BASE/'activation-final-r1/activation-and-registration.json');assert activation['status']=='passed' and len(activation['activation']['verified_packs'])==4
 validation=load(BASE/'skill-validation-r1/verification.json');assert validation['status']=='passed' and validation['namespace_manifest_sha256']==sha(namespace) and validation['skill_files']==89
 assert load(BASE/'skill-pin-r1/verification.json')['namespace_manifest_sha256']==sha(namespace)
 caps=load(BASE/'installation-final-r1/capabilities.stdout.json')['data']['capabilities'];assert len(caps)==88
 assert 'surface.measure-media' in caps['native_hdr_light_measurement']['commands']
 assert (ROOT/'docs/product/hdr-media-measure-capabilities-cli-0.1.50.json').read_bytes()==(BASE/'installation-final-r1/capabilities.stdout.json').read_bytes()
 for suffix in ('','.en','.zh-TW'):
  name='README'+suffix+'.md';text=(ROOT/name).read_text('utf8');original=git('show',BASELINE+':'+name).decode('utf8')
  rows=lambda s:[l for l in s.splitlines() if re.match(r'^\| R\d+ \|',l)]
  assert len(rows(original))==335 and len(rows(text))==340 and rows(text)[:335]==rows(original)
  assert [int(re.match(r'^\| R(\d+) ',l).group(1)) for l in rows(text)]==list(range(1,341))
  for prefix,n in [('F',75),('S',30),('K',17)]:assert len(re.findall(r'^\| '+prefix+r'\d+ \|',text,re.M))==n
  assert 'CLI0.1.50 / alpha.4-local.48 / r51 kit' in text and '383999' in text
  doc=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf8')
  recorded={k:json.loads(v) for k,v in re.findall(r'^### `([^`]+)`\s*\n\n```json\n(.*?)\n```',doc,re.M|re.S)}
  assert set(recorded)==set(caps) and all(recorded[k]==v for k,v in caps.items())
 old=git('show',BASELINE+':docs/product/GOAL_GAPS_20261025.md').decode('utf8');now=(ROOT/'docs/product/GOAL_GAPS_20261025.md').read_text('utf8')
 rows=lambda s:{l.split('|')[1].strip():l for l in s.splitlines() if re.match(r'^\| G\d+ \|',l)}
 arows,brows=rows(old),rows(now);assert len(arows)==len(brows)==38
 assert all(arows[k].split('|')[-3]==brows[k].split('|')[-3] for k in arows)
 assert all(arows[k]==brows[k] for k in arows if k!='G08')
 case_dir=BASE/'installed-case-r1';case=load(case_dir/'verification.json');assert case['status']=='passed' and case['installed_skill_used'] and case['namespace_manifest_sha256']==sha(namespace)
 assert case['checks']==23 and all(r['passed'] for r in load(case_dir/'checks.json'))
 public=ROOT/'docs/assets/native-hdr-media-installed-20261029-r1';work=ROOT/'local/agent-ffmpeg/native-hdr-media-installed-case-r1'
 for label in ('pq420','hlg420'):
  r=case['cases'][label];assert r['frames']==48 and r['pixels']==11059200 and r['maximum_metric_error_nits']<1e-7 and r['reject_failed']
  independent=load(case_dir/(label+'-independent-oracle.json'));meter=load(public/(label+'-measurement.json'))
  assert independent['no_product_colour_or_meter_helpers'] and independent['decoded_RGBA32_sha256']==meter['decoded_RGBA32_sha256']==r['decoded_RGBA32_sha256']
  assert meter['native_clock_sha256']==independent['native_clock_sha256'] and meter['frames']==48
  assert meter['analyzed_duration_seconds']=='498/125' and meter['native_clock']['native_span_seconds']=='4' and meter['native_clock']['gaps_between_declared_exposures']==16
  assert meter['native_decoder_exit_code']==0 and meter['owned_threads_terminated'] and meter['range_counts']['policy']=='clip'
  reject=load(case_dir/(label+'-reject.stdout.json'));assert not reject['ok'] and reject['errors'][0]['code']=='HDR_MEASURE_RANGE'
  assert sha(public/(label+'.mkv'))==sha(work/'project/renders'/(label+'.mkv'))
  assert r['range_counts']['negative_components']==independent['negative_components'] and r['range_counts']['over_one_components']==independent['over_one_components']
 replay=load(case_dir/'replay-review-r1/verification.json');assert replay['status']=='passed' and replay['complete_source_original_replay_PCM_equal']
 assert replay['PCM_bytes']==1536000 and replay['PCM_scalars']==384000 and replay['nonzero_PCM_scalars']==383999
 assert sha(work/'source-pcm.f32')==sha(work/'original-pcm.f32')==sha(work/'replay-pcm.f32')==replay['PCM_sha256']
 review=load(case_dir/'preview-review/verification.json');assert review['status']=='passed' and review['agent_static_PNG_view_completed'] and review['GIF']['frames']==24 and review['GIF']['total_duration_ms']==4000
 for name,digest in review['files'].items():assert sha(public/name)==digest
 for row in load(public/'media-manifest.json')['files']:assert sha(public/row['path'])==row['sha256'] and (public/row['path']).stat().st_size==row['bytes']
 kit=ROOT/'docs/skills/agent-editor-kit-community-unified-skill-r51.zip';meta=load(ROOT/'docs/skills/community-unified-skill-package-0.1.50-r51.json');assert sha(kit)==meta['sha256'] and meta['files']==146 and meta['cli_version']=='0.1.50'
 with zipfile.ZipFile(kit) as zipped:
  inventory=json.loads(zipped.read('KIT-FILES.json'));assert len(inventory['files'])==145 and len(zipped.namelist())==146
  for row in inventory['files']:
   data=zipped.read(row['path']);assert hashlib.sha256(data).hexdigest()==row['sha256'] and len(data)==row['bytes']
   if row['path'].startswith('skills/'):assert data==(ROOT/row['path']).read_bytes()
 acceptance=load(BASE/'kit-r1/verification.json');assert acceptance['status']=='passed' and acceptance['files']==146 and acceptance['skill_files']==89 and acceptance['actual_post_codec_48_frames_validated'] and not acceptance['real_discovery_changed']
 paths={ROOT/p for p in OWNED};paths.update(ROOT/row['path'] for row in m['files']);paths.update(p for p in BASE.rglob('*') if p.is_file() and out not in p.parents);paths.update(p for p in public.rglob('*') if p.is_file())
 links=0
 for p in sorted(paths):
  assert p.is_file(),p
  if p.suffix=='.py':ast.parse(p.read_text('utf8'))
  if p.suffix!='.md':continue
  for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',p.read_text('utf8')):
   target=target.strip('<>');plain=unquote(target.split('#',1)[0])
   if not plain or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',plain):continue
   if any(c in plain for c in ['{','}','<','>']):continue
   assert (p.parent/plain).resolve().exists(),(p.relative_to(ROOT),target)
   links+=1
 (out/'file-hashes.json').write_text(json.dumps({p.relative_to(ROOT).as_posix():sha(p) for p in sorted(paths)},ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
 report=dict(status='passed',product_files=276,installed_tests=29,boundary_tests=42,compatibility_tests=352,case_checks=23,
  movies=2,frames_per_movie=48,pixels_per_movie=11059200,skill_files=89,kit_files=146,capabilities=88,F=75,S=30,K=17,R=340,
  historical_R_rows_retained=335,original_G_closures_retained=38,source_unchanged=True,files_inventoried=len(paths),local_links_checked=links,whole_goal_complete=False)
 (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report))
if __name__=='__main__':main()
