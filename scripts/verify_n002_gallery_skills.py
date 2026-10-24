"""Validate registered Skills and exercise the actual client-selection helper and pinned launcher."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from PIL import Image

from verify_agent_ffmpeg_local import validate_registered_skills

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/validation/evidence/looks-n002-20261024-r1'
ASSETS = ROOT / 'docs/assets/looks-n002-20261024-r1'
HELPER = ROOT / 'skills/agent-ffmpeg-local-editor/scripts/look_gallery.py'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    manifest = json.loads((ROOT / 'agent-ffmpeg-local-install-manifest.json').read_bytes())
    registered = validate_registered_skills(manifest)
    (EVIDENCE / 'registered-skills.json').write_text(json.dumps(registered,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    commands = []
    def run(label, argv, expect=0):
        done = subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,timeout=180,
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (EVIDENCE/(label+'.stdout.txt')).write_bytes(done.stdout)
        (EVIDENCE/(label+'.stderr.txt')).write_bytes(done.stderr)
        assert done.returncode==expect,(label,done.returncode,done.stderr.decode('utf-8','replace'))
        commands.append({'id':label,'argv':list(map(str,argv)),'exit_code':done.returncode,'expected_exit_code':expect})
        return done.stdout
    base=[sys.executable,'-I','-S','-B','-X','utf8',HELPER]
    found=json.loads(run('helper-search',base+['--query','黑白','--limit','6']))
    assert found['ok'] and found['total']>0 and len(found['records'])==6
    output=ASSETS/'client-shortlist-example'
    ids=['t3-fuji-superia-800','nt-bw-agfa-apx-100','fl-0000634-darkblue']
    result=json.loads(run('helper-board',base+['--ids',*ids,'--output',output]))
    assert result['ok'] and not result['project_modified']
    selection=json.loads((output/'selection.json').read_bytes())
    assert [row['id'] for row in selection['looks']]==ids
    assert selection['preview_strength']==1 and selection['schema']=='aek-look-shortlist-v1'
    for row in selection['looks']:
        assert sha(Path(row['preview']))==row['full_sha256']
    with Image.open(output/'board.jpg') as board:
        assert board.width>=1120 and board.height>=400
    original_hash=sha(output/'board.jpg')
    run('helper-existing-output-refused',base+['--ids',*ids,'--output',output],1)
    assert sha(output/'board.jpg')==original_hash
    invalid=ROOT/'product/.runtime/looks-n002-20261024-r1/invalid-shortlist'
    run('helper-unknown-id-refused',base+['--ids','not-a-look','--output',invalid],2)
    assert not invalid.exists()
    discovery=Path(manifest['codex_skills_directory'])
    launcher=discovery/'agent-ffmpeg-local-editor/scripts/run.ps1'
    def cli(label, argv):
        result=json.loads(run(label,['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',launcher,*argv]))
        assert result['ok']
        return result
    version=cli('registered-version',['version'])
    cli('registered-inspect',['look','inspect','--id',ids[0]])
    preview=ROOT/'product/.runtime/looks-n002-20261024-r1/registered-preview.png'
    cli('registered-preview',['look','preview','--id',ids[0],'--input',ASSETS/'source.png','--output',preview,'--strength','1'])
    row=next(r for r in json.loads((ASSETS/'manifest.json').read_bytes())['records'] if r['id']==ids[0])
    with Image.open(preview) as actual, Image.open(ASSETS/row['full']) as reference:
        assert actual.convert('RGB').tobytes()==reference.convert('RGB').tobytes()
    (EVIDENCE/'skill-commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    report={'status':'passed','registered_skills':len(registered),'helper_commands':4,
            'helper_expected_refusals':2,'registered_launcher_commands':3,
            'registered_preview_matches_published_pixels':True,'client_candidate_ids':ids,
            'project_modified':False,'source_fallback':False,'board_sha256':original_hash,
            'scope':'format/junction checks plus search/board/export and actual pinned-launcher execution; not full Agent decision-quality acceptance'}
    (EVIDENCE/'skill-verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))


if __name__=='__main__':
    main()
