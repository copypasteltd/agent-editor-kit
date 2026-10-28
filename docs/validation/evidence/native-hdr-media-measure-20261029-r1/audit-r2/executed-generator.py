"""Narrow immutable-source/evidence/document audit, retaining original goal rows."""
from pathlib import Path
import argparse, ast, hashlib, json, re, subprocess
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1]
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
BASELINE='c7192cd7'
BASE=ROOT/'docs/validation/evidence/native-hdr-media-measure-20261029-r1'
OWNED=['.gitattributes','README.md','README.zh-TW.md','README.en.md','docs/README.md',
 'docs/product/GOAL_GAPS_20261025.md','docs/product/HDR_MEASUREMENT.md','docs/product/HDR_MEDIA_MEASUREMENT.md',
 'docs/releases/CLI_0.1.50_SOURCE.md','docs/validation/编码后成片光量核验_2026-10-29.md',
 'product/pyproject.toml','product/src/ai_ad_editor/__init__.py','product/src/ai_ad_editor/capabilities.py',
 'product/src/ai_ad_editor/cli.py','product/src/ai_ad_editor/hdr_measure.py',
 'product/src/ai_ad_editor/hdr_media_measure.py','product/tests/test_hdr_media_measure.py',
 'scripts/test_hdr_media_measure_20261029.py','scripts/run_hdr_media_measure_case_20261029.py',
 'scripts/audit_hdr_media_measure_20261029.py']


def sha(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()
def load(p):return json.loads(p.read_bytes())
def git(*args):
 r=subprocess.run([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,capture_output=True,check=True)
 return r.stdout

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
 out=BASE/('audit-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
 source=ROOT/'product/src/ai_ad_editor';pins={p.name:sha(p) for p in source.glob('*.py')};assert len(pins)==276
 for run,count in [('source-r2',29),('boundary-r1',42)]:
  record=load(BASE/run/'verification.json')
  assert record['status']=='passed' and record['tests']==count
  assert record['failures']==record['errors']==record['skipped']==0 and record['frozen_equal']
  assert record['product_files']==pins
  for name,digest in record['test_files'].items():
   assert sha(ROOT/'product/tests'/(name+'.py'))==digest
   assert sha(BASE/run/'executed-tests'/(name+'.py'))==digest
 first=load(BASE/'source-r1/verification.json');assert first['status']=='failed' and first['tests']==27 and first['errors']==1
 case=load(BASE/'case-r1/verification.json');assert case['status']=='passed' and case['product_files']==pins
 assert case['frames']==48 and case['pixels']==11059200 and case['maximum_metric_error_nits']<1e-7
 assert case['source_only'] and not case['installed_skill_used'] and case['original_project_and_movie_bytes_unchanged']
 meter=load(BASE/'case-r1/measurement.json');oracle=load(BASE/'case-r1/independent-oracle.json')
 assert meter['decoded_RGBA32_sha256']==oracle['decoded_RGBA32_sha256']
 assert meter['codec_output_measured'] and meter['native_decoder_exit_code']==0 and meter['owned_threads_terminated']
 assert meter['analyzed_duration_seconds']=='498/125' and meter['native_clock']['native_span_seconds']=='4'
 assert meter['native_clock']['gaps_between_declared_exposures']==16
 manifest=load(ROOT/'docs/assets/native-hdr-measure-20261029-r2/hdr-master.manifest.json')
 assert sha(Path(manifest['output']))==oracle['original_media_sha256']
 original_gaps=git('show',BASELINE+':docs/product/GOAL_GAPS_20261025.md').decode('utf8')
 current=(ROOT/'docs/product/GOAL_GAPS_20261025.md').read_text('utf8')
 rows=lambda s:[l for l in s.splitlines() if re.match(r'^\| G\d+ \|',l)]
 assert rows(original_gaps)==rows(current) and len(rows(current))==38
 for name in ['README.md','README.zh-TW.md','README.en.md']:
  original=git('show',BASELINE+':'+name).decode('utf8');now=(ROOT/name).read_text('utf8')
  old=[l for l in original.splitlines() if re.match(r'^\| R\d+ \|',l)]
  new=[l for l in now.splitlines() if re.match(r'^\| R\d+ \|',l)]
  assert len(old)==332 and len(new)==335 and new[:332]==old
  assert [int(re.match(r'^\| R(\d+) ',l).group(1)) for l in new]==list(range(1,336))
  assert '0.1.50' in now and '0.1.49' in now
 # Installed namespace/public Skill bytes remain the previous verified version.
 for name in ['agent-ffmpeg-local-install-manifest.json','skills/agent-ffmpeg-local-editor/SKILL.md','skills/agent-ffmpeg-local-editor/scripts/run.py']:
  assert git('show',BASELINE+':'+name)==(ROOT/name).read_bytes()
 assert load(ROOT/'agent-ffmpeg-local-install-manifest.json')['cli_version']=='0.1.49'
 links=0
 for name in OWNED:
  p=ROOT/name;assert p.is_file()
  if p.suffix=='.py':ast.parse(p.read_text('utf8'))
  if p.suffix!='.md':continue
  for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',p.read_text('utf8')):
   target=target.strip('<>');raw=unquote(target.split('#',1)[0])
   if not raw or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',raw):continue
   # README historical command examples can contain documentation placeholders.
   if any(c in raw for c in ['{','}','<','>']):continue
   assert (p.parent/raw).resolve().exists(),(name,target)
   links+=1
 for p in source.glob('*.py'):ast.parse(p.read_text('utf8'))
 files=[ROOT/n for n in OWNED]+[p for p in BASE.rglob('*') if p.is_file() and out not in p.parents]
 (out/'file-hashes.json').write_text(json.dumps({p.relative_to(ROOT).as_posix():sha(p) for p in files},ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 report=dict(status='passed',product_files=276,source_tests=29,boundary_tests=42,case_frames=48,
             original_R_rows_retained=332,current_R_rows=335,original_G_rows_unchanged=38,
             local_links_checked=links,files_inventoried=len(files),installed_skill_unchanged_CLI='0.1.49',
             new_source_CLI='0.1.50',installed_acceptance_complete=False)
 (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report))

if __name__=='__main__':main()
