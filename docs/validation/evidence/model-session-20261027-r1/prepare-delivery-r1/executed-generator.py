"""Pin the installed bundle and one Skill before independently testing the kit."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/model-session-20261027-r1'


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args()
    assert args.run.replace('-','').isalnum()
    out=BASE/('prepare-delivery-'+args.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    current=json.loads((BASE/'installation-final-r2/verification.json').read_bytes())
    assert current['status']=='installed-and-byte-verified' and current['source_file_count']==230
    previous=json.loads((ROOT/'docs/validation/evidence/video-generation-20261026-r1/installation-final-r1/verification.json').read_bytes())
    namespace=ROOT/'agent-ffmpeg-local-install-manifest.json';before=namespace.read_bytes();manifest=json.loads(before)
    manifest.update(release='v0.1.0-alpha.4-local.32',cli_version='0.1.34',manifest_sha256=current['manifest_sha256'])
    files=[]
    for path in sorted((ROOT/'skills/agent-ffmpeg-local-editor').rglob('*')):
        if path.is_file():
            data=path.read_bytes();files.append(dict(path=path.relative_to(ROOT).as_posix(),bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    assert len(files)==75 and sum(Path(row['path']).name=='SKILL.md' for row in files)==1
    manifest['files']=files;manifest['skills'][0]['skill_md_sha256']=next(row['sha256'] for row in files if row['path'].endswith('/SKILL.md'))
    manifest['skills'][0]['purpose_zh']='唯一入口：17内部模块、显式GPU模型常驻/同提示词复用、四模式生成与可编辑入轨、原生跟踪/烘焙、Float32/GPU合成、500滤镜、语义检索、字幕配音及四轨分离'
    namespace.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    path=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md';text=path.read_text('utf8')
    for old,new in [('local.31/final-r1/installed','local.32/final-r2/installed'),('local.31/candidate-r1/bundle.zip','local.32/candidate-r2/bundle.zip'),
        ('CLI 0.1.33','CLI 0.1.34'),('alpha.4-local.31','alpha.4-local.32'),('r34.zip','r35.zip'),('0.1.33-r34.json','0.1.34-r35.json'),
        (previous['archive_sha256'],current['archive_sha256']),(previous['manifest_sha256'],current['manifest_sha256'])]:text=text.replace(old,new)
    text+='\nCLI0.1.34/local.32/r35：[原生GPU模型会话](MODEL_SESSIONS.md) · [当前安装摘要](../releases/CLI_0.1.34_LOCAL.md)。新增启动/状态/停止和生成复用；首次全模型校验及首次加载费用单独记录。\n'
    path.write_text(text,encoding='utf8',newline='\n')
    path=ROOT/'docs/releases/CLI_0.1.34_LOCAL.md';assert not path.exists()
    path.write_text('# CLI0.1.34 · native model sessions · local.32\n\n'
        '已安装本地开发版，230产品文件与源码一致；真实GPU冷热复用/取消实测进行中。'
        'Installed local build; real CUDA cold/warm and cancellation acceptance is still running.\n\n'
        '[Workflow](../product/MODEL_SESSIONS.md) · [Local install](../product/COMMUNITY_LOCAL_DELIVERY.md)\n\n'
        'Application ZIP: `'+str(Path(current['archive']).relative_to(ROOT).as_posix())+'`\n\n'
        'ZIP bytes: `'+str(current['archive_bytes'])+'` · SHA256: `'+current['archive_sha256']+'`\n\n'
        'Manifest SHA256: `'+current['manifest_sha256']+'`\n\n'
        'Public alpha.3 / CLI0.1.2 remains unchanged; local updates are not a new public Release.\n',encoding='utf8',newline='\n')
    # Keep local documentation available inside the small community kit.
    path=ROOT/'scripts/package_community_skill.py';text=path.read_text('utf8')
    assert "'MODEL_SESSIONS.md'" not in text
    text=text.replace("'VIDEO_GENERATION.md',","'VIDEO_GENERATION.md', 'MODEL_SESSIONS.md',",1)
    path.write_text(text,encoding='utf8',newline='\n')
    report=dict(status='pinned-before-independent-checks',cli_version='0.1.34',skill_count=1,module_count=17,skill_files=75,
        namespace_before_sha256=hashlib.sha256(before).hexdigest(),namespace_sha256=hashlib.sha256(namespace.read_bytes()).hexdigest(),
        installation_sha256=current['archive_sha256'],actual_cuda_acceptance_pending=True)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(report),flush=True)


if __name__=='__main__':main()
