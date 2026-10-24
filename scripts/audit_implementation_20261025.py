"""Audit current delivery, unchanged prior archives, complete manuals and gaps."""
from pathlib import Path
import argparse
import hashlib
import json
import re
from urllib.parse import unquote
import zipfile

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT/'docs/validation/evidence/implementation-20261025-r1'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    assert not output.exists()
    tests={}
    for name,count in [('audio-channel-tests-r1',23),('audio-regression-r1',168),('capture-contract-r1',10),('installed-channel-tests-r1',23)]:
        row=json.loads((EVIDENCE/(name+'.json')).read_bytes())
        assert row['methods']==count and row['exit_code']==0 and row['skipped']==0 and row['frozen_equal'] and row['terminal_ok']
        tests[name]=count
    actual={}
    for name,count in [('native-capture-development-r2',10),('native-capture-installed-r3',10),('skill',11)]:
        row=json.loads((EVIDENCE/name/'verification.json').read_bytes())
        assert row['status']=='passed' and row['commands']==count
        actual[name]=count
    research=json.loads((EVIDENCE/'native-aligner-research/quality.json').read_bytes())
    assert research['results'][0]['model_forward_calls']==2 and not research['results'][0]['passed_both_fixtures']
    assert [c['max_error_ms'] for c in research['results'][0]['cases']]==[220.,161.]
    assert research['unchanged_max_error_seconds']==2/30
    package=json.loads((EVIDENCE/'local-package.json').read_bytes())
    assert sha(ROOT/package['archive'])==package['sha256']=='4e406058e082d1c9d778e9c4665f307d5027f17542c6fabfbc9d8d72ac0a2333'
    old=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.1/agent-editor-kit-v0.1.0-alpha.4-local.1-cp313-win_amd64.zip'
    assert sha(old)=='cf4e55f410582547d7fe56549d4594b4d8f0ee6aff8be24f77408c035fd74ead'
    assert sha(ROOT/'docs/skills/agent-editor-kit-community-unified-skill-r2.zip')=='b8b069ad3edea129bfb4e6356d159b5d596a7c37e4693745a6c0bc787ede6033'
    kit=json.loads((ROOT/'docs/skills/community-unified-skill-package-0.1.4.json').read_bytes())
    assert sha(ROOT/kit['archive'])==kit['sha256']
    manifest=json.loads((ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes())
    assert manifest['release']=='v0.1.0-alpha.4-local.2' and manifest['cli_version']=='0.1.4'
    with zipfile.ZipFile(ROOT/kit['archive']) as z:
        assert [n for n in z.namelist() if Path(n).name=='SKILL.md']==['skills/agent-ffmpeg-local-editor/SKILL.md']
        inventory=json.loads(z.read('KIT-FILES.json'))
        for row in inventory['files']:
            data=z.read(row['path'])
            assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
        for row in manifest['files']:
            path=ROOT/row['path']
            assert sha(path)==row['sha256'] and z.read(row['path'])==path.read_bytes()
    root_docs=[ROOT/n for n in ('README.md','README.zh-TW.md','README.en.md')]
    readme_commands=[]
    for path in root_docs:
        text=path.read_text('utf-8')
        counts={c:re.findall(r'^\| ('+c+r'\d\d)(?: /| \|)',text,re.M) for c in 'FSKR'}
        assert {c:len(v) for c,v in counts.items()}=={'F':49,'S':17,'K':17,'R':42},(path,counts)
        assert all(len(v)==len(set(v)) for v in counts.values())
        assert len(text)>35000
        readme_commands.append(re.findall(r'```powershell\n(.*?)```',text,re.S))
    assert readme_commands[0]==readme_commands[1]==readme_commands[2]
    gaps=(ROOT/'docs/product/GOAL_GAPS_20261025.md').read_text('utf-8')
    assert re.findall(r'^\| (G\d\d) \|',gaps,re.M)==[f'G{i:02}' for i in range(1,39)]
    paths=root_docs+[ROOT/p for p in ('docs/README.md','docs/product/COMMUNITY_LOCAL_DELIVERY.md',
          'docs/product/NATIVE_CAPTURE.md','docs/product/CASES.md','docs/product/GOAL_GAPS_20261025.md',
          'docs/product/IMPLEMENTATION_PLAN_20261025.md','docs/validation/补齐实施首批实测_2026-10-25.md')]
    paths+=list((ROOT/'skills/agent-ffmpeg-local-editor').rglob('*.md'))
    checked_links=0
    for path in paths:
        text=path.read_text('utf-8')
        plain=re.sub(r'```[\s\S]*?```','',text)
        plain=re.sub(r'`[^`\n]+`','',plain)
        for link in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)',plain):
            if re.match(r'^[a-z]+:',link) or link.startswith('#'):
                continue
            target=(path.parent/unquote(link.split('#')[0])).resolve()
            assert target.exists(),(path,link)
            checked_links+=1
    media=json.loads((ROOT/'docs/assets/native-capture-20261025-r1/verification.json').read_bytes())
    for row in media['files']:
        assert sha(ROOT/row['path'])==row['sha256']
    output.parent.mkdir(parents=True,exist_ok=True)
    result={'status':'passed','test_scopes_overlap_do_not_sum':True,'tests':tests,'separate_cli_scopes':actual,
            'qwen_failed_original_gates_preserved':True,'readme_ids':{'F':49,'S':17,'K':17,'R':42},
            'three_readme_commands_identical':True,'local_links_checked':checked_links,'stable_gap_groups':38,
            'old_archives_unchanged':True,'skill_count':1,'module_count':17,'release':manifest['release'],
            'generator_sha256':sha(Path(__file__)),'complete_capcut_goal_accepted':False}
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False),flush=True)


if __name__=='__main__':
    main()
