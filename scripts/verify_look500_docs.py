"""Check current readmes, all profile links, baseline compatibility and package inventory."""
from pathlib import Path
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
from urllib.parse import unquote
import zipfile

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/validation/evidence/look500-20261024-r1'


def sha(path):
    with Path(path).open('rb') as handle:return hashlib.file_digest(handle,'sha256').hexdigest()


def main():
    catalog_path=ROOT/'product/src/ai_ad_editor/look_data/catalog.json'
    value=json.loads(catalog_path.read_bytes());rows=value['records']
    assert len(rows)==value['count']==500
    assert [r['number'] for r in rows]==list(range(1,501))
    git='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
    old=subprocess.run([git,'-c','core.fsmonitor=false','show','cd9e21dadb46b0362d5a85a991288366e7994bac:product/src/ai_ad_editor/look_data/catalog.json'],cwd=ROOT,capture_output=True,check=True)
    baseline=json.loads(old.stdout)['records']
    for a,b in zip(baseline,rows[:100]):
        for key in ('id','lut','sha256','packed_sha256','preview_sha256'):
            assert a[key]==b[key],(a['id'],key)
    root_docs=[ROOT/name for name in ('README.md','README.zh-TW.md','README.en.md')]
    local_docs=[*(ROOT/'docs/local').glob('LOOK_PRESETS*.md'),*(ROOT/'docs/local').glob('FILTERS*.md'),
                *(ROOT/'docs/local/look-profiles').glob('*.md'),ROOT/'docs/local/INSTALLATION.md']
    other=[*(ROOT/'docs/releases/v0.1.0-alpha.3').glob('*.md'),ROOT/'docs/README.md',ROOT/'docs/validation/LOOK500_20261024.md']
    paths=root_docs+local_docs+other
    link_count=0
    report_path=EVIDENCE/'docs-verification.json'
    self_report_links=0
    for path in paths:
        text=path.read_text('utf-8')
        assert '\ufffd' not in text,path
        cleaned=re.sub(r'```[\s\S]*?```','',text)
        for link in re.findall(r'\]\(([^)\n]+)\)',cleaned):
            if link.startswith(('https://','http://','mailto:','codex:')):continue
            target=unquote(link.split('#',1)[0].split('?',1)[0]).strip('<>')
            if not target:continue
            resolved=(path.parent/target).resolve()
            if resolved==report_path:
                self_report_links+=1
                link_count+=1
                continue  # This verifier publishes its own receipt only after all checks pass.
            assert resolved.exists(),(str(path.relative_to(ROOT)),link)
            link_count+=1
            if '#preset-' in link:
                anchor=link.split('#',1)[1]
                assert f'id="{anchor}"' in resolved.read_text('utf-8'),(path,link)
    for suffix in ('','.zh-TW','.en'):
        contents='\n'.join(p.read_text('utf-8') for p in sorted((ROOT/'docs/local/look-profiles').glob('*'+suffix+'.md'))
                           if (suffix or not re.search(r'\.(zh-TW|en)\.md$',p.name)))
        anchors=re.findall(r'<a id="preset-([^"]+)"></a>',contents)
        assert len(anchors)==500 and set(anchors)=={r['id'] for r in rows},suffix
    fences=[]
    for path in root_docs:
        text=path.read_text('utf-8')
        assert re.findall(r'^\| (R\d+) \|',text,re.M)==[f'R{i:02}' for i in range(1,25)],path
        verification_table=re.search(r'^\| R01 \|[^\n]*(?:\n\| R\d+ \|[^\n]*)*',text,re.M)
        assert verification_table and len(verification_table.group().splitlines())==24,('Verification rows must form one table',path)
        assert re.findall(r'^\| (F\d+) \|',text,re.M)==[f'F{i:02}' for i in range(1,14)],path
        fences.append(re.findall(r'```[^\n]*\n([\s\S]*?)```',text))
    assert fences[0]==fences[1]==fences[2],'README commands changed during translation'
    data=catalog_path.parent
    assert {p.relative_to(data).as_posix() for p in (data/'luts').glob('*')}=={r['lut'] for r in rows}
    for row in rows:
        assert sha(data/row['lut'])==row['packed_sha256']
        assert sha(data/row['license']['file'])==row['license']['sha256']
    installed=json.loads((ROOT/'local/agent-ffmpeg/runtime.json').read_bytes())
    installed_catalog=Path(installed['installed_directory'])/'site/ai_ad_editor/look_data/catalog.json'
    assert installed['release']=='v0.1.0-alpha.3' and sha(installed_catalog)==sha(catalog_path)
    installed_luts=list((installed_catalog.parent/'luts').glob('*.cube.gz'));assert len(installed_luts)==500
    artifact=ROOT/'docs/releases/v0.1.0-alpha.3/artifacts'
    pieces=json.loads((artifact/'parts.json').read_bytes())
    for piece in pieces['parts']:
        assert piece['bytes']<=64*1024**2 and sha(artifact/piece['name'])==piece['sha256']
    old_zip=ROOT/'docs/releases/v0.1.0-alpha.2/artifacts/agent-video-kit-v0.1.0-alpha.2-cp313-win_amd64.zip'
    assert sha(old_zip)=='8910c3d26bba78133ee7177018da5ea2fcefda59eb995965ba34a8fd308d177f'
    report={'status':'passed','date_utc':datetime.now(timezone.utc).isoformat(),'catalog_version':value['version'],
        'looks':500,'profiles_per_language':500,'languages':3,'checked_markdown_files':len(paths),'local_links_checked':link_count,
        'license_counts':dict(Counter(r['license']['spdx'] for r in rows)),
        'existing_100_ids_lut_preview_hashes_preserved':True,'alpha2_zip_unchanged':True,
        'installed_luts':len(installed_luts),'binary_parts':len(pieces['parts']),
        'readme_function_rows':13,'readme_verification_rows':24,'readme_code_blocks_identical':True,
        'self_report_links_published_after_checks':self_report_links,
        'files':{p.relative_to(ROOT).as_posix():sha(p) for p in paths}}
    report_path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    assert report_path.is_file() and json.loads(report_path.read_bytes())['status']=='passed'
    print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False))


if __name__=='__main__':main()
