"""Finalize candidate two while retaining candidate-one code/media evidence."""
import argparse
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/motion-pack-20261025-r1'


def load(path):return json.loads(path.read_bytes())
def write(path,text):path.write_text(text,encoding='utf8',newline='\n')


def prepare():
    one=load(BASE/'installation-r1/verification.json');two=load(BASE/'installation-r2/verification.json')
    assert two['status']=='installed-and-byte-verified'
    path=ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md';text=path.read_text('utf8')
    text=text.replace('v0.1.0-alpha.4-local.14/final-r1','v0.1.0-alpha.4-local.14/final-r2')
    text=text.replace('v0.1.0-alpha.4-local.14/candidate-r1','v0.1.0-alpha.4-local.14/candidate-r2')
    text=text.replace(one['archive_sha256'],two['archive_sha256']).replace(one['manifest_sha256'],two['manifest_sha256'])
    text=text.replace(str(one['archive_bytes']),str(two['archive_bytes']))
    text=text.replace('unified-skill-r15.zip','unified-skill-r16.zip').replace('package-0.1.16.json','package-0.1.16-r2.json')
    text+='\n最终候选 r2 补齐捕获/查询幂等键拒绝和负增量缩放边界；最终匹配 r16 kit。r1 候选与 r15 kit/首次测试及媒体记录均保留。默认六包和渲染实现保持，最终安装/Skill 重新核验；这不增加自然质量通过结论。\n'
    write(path,text)
    (ROOT/'docs/product/motion-pack-capabilities-cli-0.1.16.json').write_bytes((BASE/'installation-r2/capabilities.stdout.json').read_bytes())


def docs():
    for run,count in (('development-r3',22),('native-development-r3',5),('installed-contracts-r2',22),('installed-native-r2',5),('installed-cli-r2',122)):
        proof=load(BASE/'tests'/run/'verification.json');assert proof['status']=='passed' and proof['result']['methods']==count
    for phase in ('skill-r2','kit-r2'):assert load(BASE/phase/'verification.json')['status']=='passed'
    for name in ('README.md','README.zh-TW.md','README.en.md'):
        path=ROOT/name;text=path.read_text('utf8');lines=[]
        for line in text.splitlines():
            historical=re.match(r'^\| R(\d+)\s*\|',line)
            if not historical or int(historical[1])>117:
                line=line.replace('r15 kit','r16 kit').replace('[r15 Skill kit]','[r16 Skill kit]').replace('unified-skill-r15.zip','unified-skill-r16.zip')
                line=line.replace('v0.1.0-alpha.4-local.14/final-r1','v0.1.0-alpha.4-local.14/final-r2')
                if historical:
                    line=line.replace('installation-r1/','installation-r2/').replace('installed-native-r1/','installed-native-r2/')
                    line=line.replace('skill-r1/','skill-r2/').replace('installed-cli-r1/','installed-cli-r2/').replace('final-delivery-r1/','final-delivery-r2/')
                    line=line.replace('20/20','22/22')
            lines.append(line)
        write(path,'\n'.join(lines)+'\n')
    for name in ('docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md',
                 'docs/product/SKILLS.md','docs/product/SKILLS.zh-TW.md','docs/product/SKILLS.en.md',
                 'docs/skills/UNIFIED_SKILL.md','docs/skills/UNIFIED_SKILL.zh-TW.md','docs/skills/UNIFIED_SKILL.en.md'):
        path=ROOT/name;text=path.read_text('utf8').replace('r15 kit','r16 kit').replace('[r15 kit]','[r16 kit]').replace('unified-skill-r15.zip','unified-skill-r16.zip')
        if 'GOAL_GAPS' in name:text=text.replace('motion-pack-20261025-r1/installation-r1/','motion-pack-20261025-r1/installation-r2/')
        write(path,text)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--phase',choices=('prepare','docs'),required=True)
    {'prepare':prepare,'docs':docs}[parser.parse_args().phase]()
