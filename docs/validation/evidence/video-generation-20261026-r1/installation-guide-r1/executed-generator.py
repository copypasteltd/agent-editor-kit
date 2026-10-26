"""Pin the known local installation guide before independent Skill-kit checks."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/video-generation-20261026-r1'


def sha(data):return hashlib.sha256(data).hexdigest()
def load(path):return json.loads(path.read_bytes())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args()
    assert a.run.replace('-','').isalnum()
    out=BASE/('installation-guide-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    current=load(BASE/'installation-final-r1/verification.json')
    old=load(ROOT/'docs/validation/evidence/tracking-bake-20261026-r1/installation-final-r3/verification.json')
    assert current['cli_version']=='0.1.33' and current['source_and_installed_equal']
    path=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md'
    before=path.read_bytes();text=before.decode('utf8')
    footer=re.search(r'^CLI0\.1\.32/local\.30/r33：.*$',text,re.M)
    if footer:text=text[:footer.start()]+'GENERATION_PREVIOUS_FOOTER'+text[footer.end():]
    for previous,new in [('local.30/final-r3/installed','local.31/final-r1/installed'),
        ('local.30/candidate-r3/bundle.zip','local.31/candidate-r1/bundle.zip'),
        ('CLI 0.1.32','CLI 0.1.33'),('alpha.4-local.30','alpha.4-local.31'),
        ('r33.zip','r34.zip'),('0.1.32-r33.json','0.1.33-r34.json'),
        (old['archive_sha256'],current['archive_sha256']),(old['manifest_sha256'],current['manifest_sha256'])]:
        text=text.replace(previous,new)
    if footer:text=text.replace('GENERATION_PREVIOUS_FOOTER','Historical / 历史：'+footer[0])
    text+='\nCLI0.1.33/local.31/r34：[GPU生成流程](VIDEO_GENERATION.md) · [版本/摘要](../releases/CLI_0.1.33_LOCAL.md)。VACE大权重与已有原生Torch/Diffusers运行时独立登记，不包含在四个配音/翻译模型包中。\n'
    path.write_text(text,encoding='utf8',newline='\n')
    release=ROOT/'docs/releases/CLI_0.1.33_LOCAL.md';assert not release.exists()
    release.write_text('# CLI0.1.33 · local GPU generation · local.31\n\n'
        '已安装的本地开发版本；四模式真实模型矩阵仍在执行，完整验收记录在执行后补齐。'
        'The native runtime is installed; the complete four-mode actual-model matrix is still running.\n\n'
        '[Workflow](../product/VIDEO_GENERATION.md) · [Local installation](../product/COMMUNITY_LOCAL_DELIVERY.md).\n\n'
        'Application ZIP SHA256: `'+current['archive_sha256']+'`\n\n'
        'Manifest SHA256: `'+current['manifest_sha256']+'`\n',encoding='utf8',newline='\n')
    record=dict(status='pinned',at_utc=datetime.now(timezone.utc).isoformat(),path=path.relative_to(ROOT).as_posix(),
        before_sha256=sha(before),sha256=sha(path.read_bytes()),cli_version='0.1.33',source_fallback=False,
        generation_modes_implemented=4,all_actual_modes_accepted=False,
        scope='Known installed archive and Skill paths only; does not claim the pending complete actual-model matrix has passed.')
    (out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(record,ensure_ascii=False))


if __name__=='__main__':main()
