"""Add verified r53 kit links without changing any file inside the verified kit."""
from pathlib import Path
import hashlib,json,re,zipfile
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/gpu-gamut-20261029-r1'
def load(p):return json.loads(Path(p).read_bytes())
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
def main():
    kit=load(BASE/'kit-r1/verification.json');assert kit['status']=='passed' and kit['files']==150
    audit=load(BASE/'delivery-audit-r1/verification.json');assert audit['status']=='passed'
    metadata=load(ROOT/'docs/skills/community-unified-skill-package-0.1.52-r53.json');assert metadata['sha256']==kit['kit_sha256']
    out=BASE/'final-docs-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    for suffix in ('','.zh-TW','.en'):
        for stem in ('README','docs/product/CAPABILITIES','docs/product/SKILLS','docs/skills/UNIFIED_SKILL'):
            p=ROOT/(stem+suffix+'.md');s=p.read_text('utf8');before=re.findall(r'^\| R\d+ .*$',s,re.M)
            needle='**CLI0.1.52 / local.50 · 1 Skill / 17 modules / 91 files.**';assert needle in s
            if stem=='README':link='docs/skills/agent-editor-kit-community-unified-skill-r53.zip';digest='docs/skills/community-unified-skill-package-0.1.52-r53.json'
            elif stem=='docs/skills/UNIFIED_SKILL':link='agent-editor-kit-community-unified-skill-r53.zip';digest='community-unified-skill-package-0.1.52-r53.json'
            else:link='../skills/agent-editor-kit-community-unified-skill-r53.zip';digest='../skills/community-unified-skill-package-0.1.52-r53.json'
            s=s.replace(needle,'**CLI0.1.52 / local.50 / r53 kit · 1 Skill / 17 modules / 91 files.**\n\n[Verified small kit]('+link+') · [SHA256 / inventory]('+digest+')',1)
            assert re.findall(r'^\| R\d+ .*$',s,re.M)==before;write(p,s)
    p=ROOT/'docs/releases/CLI_0.1.52_LOCAL.md';s=p.read_text('utf8');s+='''
## 匹配统一 Skill kit / Matched unified kit

[r53 ZIP](../skills/agent-editor-kit-community-unified-skill-r53.zip)，716918 bytes，SHA256 `e43354629090d0c339ec3e752bc54670455cabc5ac1a15cc3f72911aae2a126f`。[独立包摘要](../skills/community-unified-skill-package-0.1.52-r53.json)。该小包包含Skill与原生安装/注册辅助文件，应用ZIP和可选模型包分别提供，不能独立充当应用运行包。

[独立解压/配置/注册实测](../validation/evidence/gpu-gamut-20261029-r1/kit-r1/verification.json)：150归档条目、149清单条目、91 Skill文件，实际GPU frame/range与48帧编码后光量复核通过。真实C盘发现联接保持不变；同机隔离注册不等于陌生主机/跨GPU厂商验收。
''';write(p,s)
    p=ROOT/'docs/validation/GPU色域映射安装与统一Skill交付_2026-10-29.md';s=p.read_text('utf8')
    needle='| D06 | 中/繁/英README、参数、安装、服务/能力及Skill说明同步 | [工作流](../product/GPU_GAMUT.md) · [使用逻辑](../releases/CLI_0.1.52_LOCAL.md) |';assert needle in s
    s=s.replace(needle,needle+'\n| D07 | r53独立解压/配置/注册与实际GPU预览通过 | [kit](evidence/gpu-gamut-20261029-r1/kit-r1/verification.json)，150归档条目/149清单/91 Skill文件 |',1)
    s=s.replace('静态PNG视觉查看另记录','静态PNG已实际查看')
    s=s.replace('| P01 | r53小kit打包、独立解压/配置/注册与实际GPU预览验收 | 交付/G08/G32 |','| P01 | 陌生主机离线安装与更广设备验收 | 交付/G32 |')
    s+='\n最终[交付审计](evidence/gpu-gamut-20261029-r1/delivery-audit-r1/verification.json)通过：当前README各362条核验记录，原358条历史逐行保留；全部38项原关闭条件未变。r53小kit已验收；完整剪映等价目标继续开发。\n';write(p,s)
    p=ROOT/'docs/validation/GPU色域映射源码实测_2026-10-29.md';s=p.read_text('utf8');s=s.replace('\n\n','\n\nHistorical source/candidate stage; superseded by [actual installed CLI52 and unified Skill delivery](GPU色域映射安装与统一Skill交付_2026-10-29.md). 下方当时CLI51与待验收状态为历史，当前已安装CLI52/local50/r53。\n\n',1);write(p,s)
    p=ROOT/'docs/README.md';s=p.read_text('utf8');s=s.replace('**CLI0.1.52 / local.50**','**CLI0.1.52 / local.50 / r53 kit**',1);s+='\nCurrent verified [r53 kit](skills/agent-editor-kit-community-unified-skill-r53.zip) · [digest](skills/community-unified-skill-package-0.1.52-r53.json) · [actual installation delivery](validation/GPU色域映射安装与统一Skill交付_2026-10-29.md).\n';write(p,s)
    # The ZIP and all included Skill/guide files stay byte-exact after final docs.
    archive=ROOT/metadata['archive'];assert hashlib.sha256(archive.read_bytes()).hexdigest()==metadata['sha256']
    with zipfile.ZipFile(archive) as z:
        inventory=json.loads(z.read('KIT-FILES.json'))
        for row in inventory['files']:
            if row['path'].startswith('skills/'):assert z.read(row['path'])==(ROOT/row['path']).read_bytes()
    result=dict(status='passed',cli='0.1.52',release='local.50',kit='r53',kit_files=150,skill_files=91,README_R_rows=362,kit_sha256=metadata['sha256'],kit_included_skill_files_unchanged=True,whole_goal_complete=False)
    write(out/'verification.json',json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
