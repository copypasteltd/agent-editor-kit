"""Frozen-source, historical-row and actual case audit for source CLI0.1.51."""
from pathlib import Path
import argparse,ast,hashlib,json,re,subprocess
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/oklab-gamut-20261029-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
BASELINE='faf0cab06a8336b157965f583ce16afe08781566'
PRODUCT=['__init__.py','float_gamut.py','float_hdr.py','float_standard_render.py','float_bundle.py','float_preview.py','colour_audit.py','capabilities.py','schema_contract.py','agent-project.schema.json']
OWNED=['.gitattributes','README.md','README.en.md','README.zh-TW.md','product/pyproject.toml','product/tests/test_float_gamut.py',
 'docs/README.md','docs/specs/agent-project.schema.json','docs/product/GOAL_GAPS_20261025.md','docs/product/OKLAB_GAMUT.md','docs/product/CASES.md',
 'docs/product/oklab-gamut-capabilities-cli-0.1.51.json','docs/validation/OKLab色域映射源码实测_2026-10-29.md','docs/releases/CLI_0.1.51_SOURCE.md']
OWNED+=['product/src/ai_ad_editor/'+n for n in PRODUCT]
OWNED+=['scripts/'+n+'_20261029.py' for n in ['test_oklab_gamut','run_oklab_gamut_case','review_oklab_gamut_case','probe_oklab_gamut_4k','document_oklab_gamut','audit_oklab_gamut']]
OWNED+=['docs/product/CAPABILITIES'+suffix+'.md' for suffix in ('','.en','.zh-TW')]


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def old(path):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','show',BASELINE+':'+path],cwd=ROOT).decode('utf8')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();out=BASE/('audit-'+a.run);out.mkdir(exist_ok=False)
 (out/'executed-auditor.py').write_bytes(Path(__file__).read_bytes())
 source=ROOT/'product/src/ai_ad_editor';pins={p.name:sha(p) for p in source.glob('*.py')};assert len(pins)==277
 for folder,n in [('source-r3',62),('schema-r1',17)]:
  r=load(BASE/folder/'verification.json');assert r['status']=='passed' and r['tests']==n and r['failures']==r['errors']==r['skipped']==0
  assert r['frozen_equal'] and r['product_files']==pins
  for name,digest in r['test_files'].items():assert sha(ROOT/'product/tests'/(name+'.py'))==sha(BASE/folder/'executed-tests'/(name+'.py'))==digest
 compat=load(BASE/'compat-r1/verification.json');assert compat['status']=='failed' and compat['tests']==352 and compat['failures']==1 and compat['errors']==compat['skipped']==0 and compat['product_files']==pins and compat['frozen_equal']
 assert 'FAIL: test_contract_packaged_and_documented_bytes_match' in (BASE/'compat-r1/tests.log').read_text('utf8')
 assert (source/'agent-project.schema.json').read_bytes()==(ROOT/'docs/specs/agent-project.schema.json').read_bytes()
 from_schema=load(source/'agent-project.schema.json');contract=(source/'schema_contract.py').read_text('utf8')
 assert "SCHEMA_SHA256='"+sha(source/'agent-project.schema.json')+"'" in contract
 assert 'oklab-chroma' in json.dumps(from_schema)
 case_dir=BASE/'case-r3';case=load(case_dir/'verification.json');assert case['status']=='passed' and case['source_files']==pins
 assert not case['installed_Skill_used'] and case['frames']==10 and case['width']==384 and case['height']==216
 assert case['complete_independent_RGB16_payload_equal'] and case['native_reference_maximum_code_difference']==0 and case['maximum_10bit_code_error']<3
 assert case['complete_replay_pixels_equal'] and case['complete_source_original_replay_PCM_equal'] and case['PCM_bytes']==384000
 assert case['all_frame_gamut_counts']['gamut_pixels_mapped']==338688 and case['all_frame_gamut_counts']['negative_components_clipped']==0
 k4=load(BASE/'4k-r1/verification.json');assert k4['status']=='passed' and k4['source_files']==pins and k4['all_pixels_compared'] and k4['pixels']==8294400 and k4['maximum_linear_RGB_error']<1e-6
 oracle=load(case_dir/'oracle.json');assert oracle['no_product_colour_helpers'] and oracle['complete_independent_RGB16_payload_equal'] and oracle['reference_includes_same_native_codec']
 preview=load(case_dir/'preview-review/verification.json');assert preview['status']=='passed' and preview['agent_static_PNG_view_completed'] and preview['GIF']['frames']==10 and preview['GIF']['duration_ms']==1000
 public=ROOT/'docs/assets/oklab-gamut-20261029-r3'
 for row in load(public/'media-manifest.json')['files']:assert sha(public/row['path'])==row['sha256'] and (public/row['path']).stat().st_size==row['bytes']
 for name,digest in preview['files'].items():assert sha(public/name)==digest
 namespace=ROOT/'agent-ffmpeg-local-install-manifest.json';ns=load(namespace);assert ns['cli_version']=='0.1.50'
 assert namespace.read_text('utf8')==old('agent-ffmpeg-local-install-manifest.json')
 for entry in ns['files']:assert sha(ROOT/entry['path'])==entry['sha256']
 runtime=load(ROOT/'local/agent-ffmpeg/runtime.json');assert runtime['release']=='v0.1.0-alpha.4-local.48' and runtime['manifest_sha256']==ns['manifest_sha256']
 for suffix in ('','.en','.zh-TW'):
  name='README'+suffix+'.md';s=(ROOT/name).read_text('utf8');r=lambda text:[l for l in text.splitlines() if re.match(r'^\| R\d+ \|',l)]
  assert len(r(s))==344 and r(s)[:340]==r(old(name))
  assert [int(re.match(r'^\| R(\d+)',l).group(1)) for l in r(s)]==list(range(1,345))
  assert 'CLI0.1.51' in s and 'CLI0.1.50/local.48/r51' in s
  for prefix,n in [('F',75),('S',30),('K',17)]:assert len(re.findall(r'^\| '+prefix+r'\d+ \|',s,re.M))==n
 p='docs/product/GOAL_GAPS_20261025.md';r=lambda text:{l.split('|')[1].strip():l for l in text.splitlines() if re.match(r'^\| G\d+ \|',l)}
 before,after=r(old(p)),r((ROOT/p).read_text('utf8'));assert len(before)==len(after)==38
 assert all(before[k].split('|')[-3]==after[k].split('|')[-3] for k in before)
 assert all(before[k]==after[k] for k in before if k!='G08')
 caps=load(ROOT/'docs/product/oklab-gamut-capabilities-cli-0.1.51.json');assert len(caps['data']['capabilities'])==88
 assert 'opt_in_OKLab_constant_lightness_hue_BT709_chroma_boundary_reduction' in caps['data']['capabilities']['native_hdr_display_pipeline']['features']
 paths={ROOT/name for name in OWNED};paths.update(p for p in BASE.rglob('*') if p.is_file() and out not in p.parents);paths.update(public.iterdir());links=0
 for p in sorted(paths):
  assert p.is_file(),p
  if p.suffix=='.py':ast.parse(p.read_text('utf8'))
  if p.suffix!='.md':continue
  for target in re.findall(r'!?\[[^\]]*\]\(([^)]+)\)',p.read_text('utf8')):
   value=unquote(target.strip('<>').split('#',1)[0])
   if not value or re.match(r'^[A-Za-z][A-Za-z0-9+.-]*:',value) or any(c in value for c in '{}<>'):continue
   assert (p.parent/value).resolve().exists(),(p,target)
   links+=1
 (out/'file-hashes.json').write_text(json.dumps({p.relative_to(ROOT).as_posix():sha(p) for p in sorted(paths)},ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
 report=dict(status='passed',source_version='0.1.51',installed_version='0.1.50',product_files=277,specific_tests=62,compatibility_initial_tests=352,compatibility_initial_passed=351,compatibility_initial_failures=1,schema_after_documentation_fix_passed=17,
  case_frames=10,independent_RGB16_exact=True,independent_encoded_YUV_max_code_difference=0,all_frame_chroma_mapped_pixels=338688,
  R=344,historical_R_rows_retained=340,original_G_closures_retained=38,local_links_checked=links,files_inventoried=len(paths),whole_goal_complete=False)
 (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
