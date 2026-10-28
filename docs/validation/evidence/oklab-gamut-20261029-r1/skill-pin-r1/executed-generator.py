"""Pin the single public Skill to the byte-verified native OKLab gamut mapper and preview inheritance."""
from pathlib import Path
import argparse,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/oklab-gamut-20261029-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
REFERENCE='# Explicit OKLab gamut reduction and SDR preview selection\n\nAvailable in pinned installed CLI0.1.51. In native `float32-native-v1`, author\nall source/working/output signals and nits explicitly. Use the mapping object:\n\n```json\n{"operator":"reinhard-luminance","source_peak_nits":1000,"target_peak_nits":100,"exposure_stops":0,"gamut_policy":"oklab-chroma"}\n```\n\nSet `settings.pixel_pipeline.display_mapping` for formal SDR delivery, with\nBT.709/D65 output and `reference_white_nits` equal to `target_peak_nits`.\nSet `preview_mapping` for a separate HDR-master viewing trim. Explicit\n`preview_mapping` overrides the delivery mapping; otherwise previews inherit\nformal `display_mapping` once, including output proofing, before display-linear\nresizing. With no declared mapping, HDR previews fail rather than invent a trim.\n\nUse the Skill\'s pinned `scripts/run.ps1`:\n\n```powershell\n& $aekSkill validate --project PROJECT\n& $aekSkill preview frame --project PROJECT --frame 0 --height 720\n& $aekSkill preview range --project PROJECT --start-frame 0 --end-frame 30 --height 720\n```\n\nSet `$aekSkill` to the absolute installed Skill launcher. Select a valid author\nframe range and even height64..2160; requested height does not upscale a small\ncanvas. Inspect the returned PNG and MP4 alongside their explicit settings.\nShow a clip-policy comparison generated from the same authored input; keep\nclient selection tied to the actual preview, mapping and output signal. Do not\nuse the unrelated 500 style-filter gallery as an OKLab/HDR accuracy reference.\n\nThe algorithm applies a modified-Reinhard luminance shoulder then reduces OKLab\na/b along constant L/hue to fit BT.709. It preserves perceptual L, not CIE Y.\nBlack/near-white endpoint mappings are counted separately; alpha is preserved.\nKeep `last_preview_mapping`, `preview_delivery_boundary`, full-frame gamut and\nclipping counters with delivery reports. PNG16 and Float32 range reference are\nnot the same as the compressed viewing MP4 or a physical HDR master.\n\nCPU tiled execution; no GPU colour-kernel, soft-knee, ACES or monitor claim.\nReject invalid targets, negative CIE Y or undeclared signal assumptions.\nC61 historical source package reused `sound` as both asset and clip ID; use the\ncorrected package in the preview-fix report, validate after import, then export\nand re-import to verify editability. Do not silently bypass project validation.\n\nFull parameter contract and real previews:\nhttps://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/OKLAB_GAMUT.md\nHistorical C61 correction and actual candidate previews:\nhttps://github.com/copypasteltd/agent-editor-kit/blob/main/docs/validation/SDR预览映射修复_2026-10-29.md\n'

def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
 out=BASE/('skill-pin-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
 install=load(BASE/'installation-final-r2/verification.json')
 assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.51'
 pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
 for run,count in [('installed-measure-r1',64),('installed-preview-r1',18),('installed-compat-r2',352)]:
  t=load(BASE/run/'verification.json');assert t['status']=='passed' and t['tests']==count and t['product_files']==pins
 assert pins=={p.name:sha(p) for p in (Path(install['installed'])/'site/ai_ad_editor').glob('*.py')}
 folder=ROOT/'skills/agent-ffmpeg-local-editor'
 for name in ('SKILL.md','references/runtime.md'):
  p=folder/name;write(p,p.read_text('utf8').replace('v0.1.0-alpha.4-local.48','v0.1.0-alpha.4-local.49').replace('0.1.50','0.1.51'))
 p=folder/'SKILL.md';s=p.read_text('utf8');needle='For final encoded HDR media'
 assert needle in s and 'references/oklab-gamut.md' not in s
 s=s.replace(needle,'For HDR-to-SDR colour selection and wide-gamut previews, read\n[OKLab mapping and preview inheritance](references/oklab-gamut.md). Show actual\nclip/OKLab outputs with their mapping settings before client selection.\n'+needle,1);write(p,s)
 write(folder/'references/oklab-gamut.md',REFERENCE)
 p=folder/'references/hdr-display.md';s=p.read_text('utf8')
 s=s.replace('zero black is\n  the explicit implementation assumption.', 'black lift is explicit; read `hlg-black-level.md` for nonzero display black.')
 s=s.replace('gamut_policy=reject|clip`','gamut_policy=reject|clip|oklab-chroma`')
 s=s.replace('This does not implement ICC, nonzero-black HLG display calibration, perceptual\ngamut mapping, mastering-display/CLL/dynamic metadata or Dolby Vision.', 'Current CLI adds RGB ICC, nonzero HLG black, optional HDR10 static metadata\nand explicit OKLab chroma reduction through their linked references. Dynamic\nmetadata, Dolby Vision and physical display calibration remain unimplemented.')
 write(p,s)
 p=folder/'scripts/run.py';s=p.read_text('utf8')
 s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
 s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.49'",s,count=1,flags=re.M);assert n==1;write(p,s)
 p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(p);m.update(release='v0.1.0-alpha.4-local.49',cli_version='0.1.51',manifest_sha256=install['manifest_sha256'])
 m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md')
 m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
 assert len(m['files'])==90 and sum(Path(r['path']).name=='SKILL.md' for r in m['files'])==1
 write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
 report=dict(status='pinned-for-installed-acceptance',product_files=len(pins),skill_files=90,public_entries=1,modules=17,installed_measure_tests=64,installed_preview_tests=18,installed_compatibility_tests=352,source_fallback=False,namespace_manifest_sha256=sha(p))
 write(out/'verification.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
