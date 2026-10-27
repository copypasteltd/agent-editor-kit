"""Pin a byte-verified candidate for real Skill tests; final audit gates delivery."""
from pathlib import Path
import hashlib
import json
import re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/highlight-glow-20261027-r1'

def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')

def main():
    out=BASE/'skill-pin-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    install=load(BASE/'installation-final-r2/verification.json')
    assert install['status']=='installed-and-byte-verified' and install['source_file_count']==239
    pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    for attempt,count in [('source-glow-r2',21),('source-glow-gpu-r2',3)]:
        tests=load(BASE/attempt/'verification.json')
        assert tests['status']=='passed' and tests['tests']==count and not tests['failures'] and not tests['errors'] and not tests['skipped']
        assert tests['frozen_equal'] and tests['test_frozen_equal'] and tests['product_files']==pins
    assert pins=={p.name:sha(p) for p in (Path(install['installed'])/'site/ai_ad_editor').glob('*.py')}
    folder=ROOT/'skills/agent-ffmpeg-local-editor'
    assert (folder/'references/highlight-glow.md').is_file()
    for name in ('SKILL.md','references/runtime.md'):
        p=folder/name;s=p.read_text('utf8').replace('alpha.4-local.36','alpha.4-local.37').replace('0.1.38','0.1.39')
        if name=='SKILL.md':
            s=s.replace('editable GPU flare/light leaks/chromatic split,','editable GPU flare/light leaks/chromatic split and highlight Bloom/Halation,')
            marker='For repeated GPU generation with the same prompt, read'
            assert marker in s
            s=s.replace(marker,'For actual image-highlight Bloom and film Halation, read\n'
                '[highlight glow](references/highlight-glow.md). Inspect `native:float32-glow`,\n'
                'author radius/threshold/knee/tint keys in explicit linear RGB, and preview\n'
                'the original alongside actual encoded light spread before client selection.\n'+marker,1)
        write(p,s)
    p=folder/'references/optical-effects.md';s=p.read_text('utf8')
    s=s.replace('Nine named main probe dispatches include three optical cases; probe\nsuccess is separate from edited-frame operations. Other effects remain CPU.',
        'Seventeen named main probe kernels include three analytic optical cases and\neight highlight-glow kernels; auxiliary subnormal probes are separate. Probe\nsuccess is separate from edited-frame operations. Other effects remain CPU.')
    s=s.replace('physical lens calibration, bloom/halation/depth or complete CapCut library claim.',
        'physical lens calibration, depth or complete CapCut library claim. Actual\nimage-highlight Bloom/Halation is separately available in [highlight glow](highlight-glow.md).')
    write(p,s)
    for name,body in {
        'references/projection-gpu.md':
            'CLI0.1.39 also runs [highlight Bloom and Halation](highlight-glow.md).\n'
            'Each active glow operation uses four device kernels with one final\n'
            'readback; intermediate images stay on device. Seventeen named main\n'
            'probe kernels include eight glow kernels; auxiliary subnormal probes\n'
            'are separate. `operations.glow` counts edited-frame work.\n',
        'references/float-adjustments.md':
            'CLI0.1.39 adds [highlight Bloom/Halation](highlight-glow.md) to selected-root\n'
            'intervals, using the same local author clock and one post-composition\n'
            'application. Native optics/glow can use the actual owned GPU; other\n'
            'adjustment operators retain their existing CPU implementation.\n',
    }.items():
        p=folder/name;s=p.read_text('utf8');first=s.index('\n')
        write(p,s[:first]+'\n\n'+body+s[first:])
    p=folder/'scripts/run.py';s=p.read_text('utf8')
    s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
    s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.37'",s,count=1,flags=re.M);assert n==1
    write(p,s)
    p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(p)
    m.update(release='v0.1.0-alpha.4-local.37',cli_version='0.1.39',manifest_sha256=install['manifest_sha256'])
    m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
        for p in sorted(folder.rglob('*')) if p.is_file()]
    assert len(m['files'])==78 and sum(Path(v['path']).name=='SKILL.md' for v in m['files'])==1
    m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md');write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
    result=dict(status='candidate_pinned_for_real_skill_acceptance',cli_version='0.1.39',source_numeric_and_GPU_tests=24,product_files=239,
        final_734_installed_regression_required_by_delivery_audit=True,
        single_entry=True,internal_modules=17,skill_files=78,source_fallback=False,
        namespace_manifest_sha256=sha(p))
    write(out/'verification.json',json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
