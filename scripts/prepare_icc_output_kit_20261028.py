"""Prepare independent r49 inventory/configuration/portable ICC plan checks."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
for source,target in [('publish_hlg_20261028.py','publish_icc_output_20261028.py'),('verify_hlg_kit_20261028.py','verify_icc_output_kit_20261028.py')]:
 s=(ROOT/'scripts'/source).read_text('utf8')
 for a,b in [('native-hlg-black','native-icc-output'),('0.1.47','0.1.48'),('r48','r49'),('==140','==142'),('files=140','files=142'),('==139','==141'),('==86','==87'),('skill_files=86','skill_files=87'),('editable-hlg-black','editable-icc-output'),('portable-hlg-black','portable-icc-output')]:s=s.replace(a,b)
 if source.startswith('verify_'):
  s=s.replace("assert caps['native_hlg_black_level']['protocol']=='explicit-HLG-display-black-float32-v1'","assert caps['native_icc_output_profiles']['protocol']=='agent-icc-png16-timeline-sequence-v1'")
  s=s.replace('docs/assets/native-icc-output-20261028-r1/','docs/assets/native-icc-output-20261028-r3/')
  start=s.index("    plan=cli('plan'");stop=s.index('    assert discovery.resolve()',start)
  s=s[:start]+'''    p=load(project/'project.json');profile=p['settings']['pixel_pipeline']['proofing']['profile']
    assert profile['icc_profile'].startswith('assets/color-profiles/')
    descriptor=home.parent/'target.json';descriptor.write_text(json.dumps(profile),encoding='utf8')
    plan=cli('plan','surface','render','--project',project,'--sequence-id',p['sequences'][0]['id'],
        '--output','renders/portable-icc','--output-profile-json',descriptor,'--range-policy','clip','--dry-run')
    assert plan['recipe']['softproof_applied_to_device_output'] is False
    assert plan['recipe']['stop_frame_exclusive']==48
    assert before==(project/'project.json').read_bytes() and not (project/'renders/portable-icc').exists()
'''+s[stop:]
  s=s.replace('portable_HLG_black_validated','portable_ICC_output_validated').replace('installed HLG black plan','installed ICC output plan')
 (ROOT/'scripts'/target).write_text(s,encoding='utf8',newline='\n')
p=ROOT/'scripts/package_community_skill.py';s=p.read_text('utf8')
if "'ICC_OUTPUT.md'" not in s:p.write_text(s.replace("'ICC_PROFILES.md',","'ICC_PROFILES.md', 'ICC_OUTPUT.md',",1),encoding='utf8',newline='\n')
p=ROOT/'.gitattributes';s=p.read_text('utf8')
if 'native-icc-output-20261028-r1/**' not in s:
 s+='''
# Preserve ICC output receipts/media and pinned capability bytes.
docs/validation/evidence/native-icc-output-20261028-r1/** -text -whitespace
docs/assets/native-icc-output-20261028-*/** -text -whitespace
docs/product/icc-output-capabilities-cli-0.1.48.json -text -whitespace
scripts/*icc_output*20261028.py text eol=lf
docs/product/ICC_OUTPUT.md text eol=lf
docs/releases/CLI_0.1.48_LOCAL.md text eol=lf
docs/validation/原生ICC输出与软打样实测_2026-10-29.md text eol=lf
''';p.write_text(s,encoding='utf8',newline='\n')
base=ROOT/'docs/validation/evidence/native-icc-output-20261028-r1'
research=dict(checked_date_local='2026-10-28/29',native_windows=True,GUI_browser_tabs_opened=0,
 sources=[dict(url='https://www.w3.org/TR/2025/REC-png-3-20250624/',facts=['RGBA color type6 supports16-bit channels','iCCP embeds zlib-compressed actual RGB ICC profile','avoid conflicting alternate color interpretation chunks']),
 dict(url='https://github.com/mm2/Little-CMS/tree/lcms2.19.1',commit='21c582a594fe5279f90c0b93437c398f93bf62b0',
 local_files=[dict(path=str(p.relative_to(ROOT)),sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in [ROOT/'sources/littlecms-2.19.1/source/src/cmsxform.c',ROOT/'sources/littlecms-2.19.1/source/src/cmsio1.c',ROOT/'sources/littlecms-2.19.1/source/include/lcms2.h']],
 facts=['cmsCreateProofingTransformTHR builds input/proof/proof/output profile chain','SOFTPROOFING is0x4000; BPC is0x2000','cmsIsIntentSupported checks output direction1; proof chain also requires relative-colorimetric input support'])],
 copyright='Original paraphrase/API facts; no standard pages or vendor profile collection redistributed')
(base/'primary-research.json').write_text(json.dumps(research,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
failed=ROOT/'docs/assets/native-icc-output-20261028-r1'
if failed.exists():
 (failed/'SOURCE.txt').write_text('C58 first attempt aborted before composition: a relative proof descriptor incorrectly included reference_white_nits:null and was rejected by Schema.\nOriginal contributor-generated RGB16 diagnostic chart, stereo tones and synthetic RGB/XYZ CLUT profile: CC0-1.0. No rendered/accepted output is claimed for this failed attempt. Successful run is sibling native-icc-output-20261028-r3.\n',encoding='utf8')
 files=[dict(path=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(failed.iterdir()) if p.is_file() and p.name!='media-manifest.json']
 (failed/'media-manifest.json').write_text(json.dumps(dict(status='failed-before-composition',rights='Original contributor CC0 diagnostics',files=files),indent=2)+'\n',encoding='utf8')
failed=ROOT/'docs/assets/native-icc-output-20261028-r2'
if failed.exists():
 (failed/'SOURCE.txt').write_text('C58 second attempt retained a fixture bookkeeping failure: its author snapshot was taken before normal render legitimately recorded history, so it did not isolate preview-only preservation.\nOriginal contributor-generated RGB16 chart, stereo tones and synthetic RGB/XYZ CLUT: CC0-1.0. This directory contains original inputs only,not an accepted delivery. Actual successful case is sibling native-icc-output-20261028-r3.\n',encoding='utf8')
 files=[dict(path=p.name,bytes=p.stat().st_size,sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(failed.iterdir()) if p.is_file() and p.name!='media-manifest.json']
 (failed/'media-manifest.json').write_text(json.dumps(dict(status='failed-fixture-snapshot-boundary',rights='Original contributor CC0 diagnostics',files=files),indent=2)+'\n',encoding='utf8')
print('Prepared r49 delivery tools and primary facts.')
