"""Acquire pinned data blobs, never execute upstream code (native Windows only)."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'sources/look500-research-20261024'
EVIDENCE = ROOT / 'docs/validation/evidence/look500-sources-20261024-r1'
GIT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
NATRON = 'af7b50d4caf6244fb6895a647f5b6a84efe7931a'
LUTR = '32fe087a3269fde38f3177563c1e0a77d9ec1a9e'


def git(snapshot, *argv, data=None):
    env = dict(os.environ)
    env['PATH'] = str(GIT.parent) + os.pathsep + env.get('PATH', '')
    done = subprocess.run([str(GIT), '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0',
                           '-c', 'maintenance.auto=false', '-C', str(snapshot), *argv],
                          input=data, env=env, capture_output=True, timeout=300)
    if done.returncode:
        raise RuntimeError(done.stderr.decode('utf-8', 'replace')[-3000:])
    return done.stdout


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    captures = json.loads((ROOT/'docs/validation/evidence/lut-research-20261024-r1/NatronGitHub--clut/capture.json').read_bytes())
    folders = {'bw', 'instant_consumer', 'instant_pro', 'negative_color', 'negative_new',
               'negative_old', 'picturefx', 'colorslide'}
    candidates = []
    for row in captures['candidate_files_not_all_looks']:
        folder = row['path'].split('/')[0]
        if folder not in folders:
            continue
        candidates.append(dict(repository='NatronGitHub/clut', commit=NATRON, path=row['path'],
            git_blob=row['git_blob'], bytes=row['bytes'], license='CC-BY-SA-4.0',
            creator='Marc Roovers' if folder == 'picturefx' else 'Pat David',
            title=Path(row['path']).stem.replace('_', ' '),
            input_basis='Display-referred photographic Hald CLUT; upstream transfer unspecified.',
            source_url=f'https://github.com/NatronGitHub/clut/blob/{NATRON}/{row["path"]}'))
    catalog = json.loads((RAW/'lutr-catalog.json').read_bytes())
    tree = {r['path']:r for r in json.loads((RAW/'lutr-tree.json').read_bytes())['tree']}
    for row in catalog['luts']:
        # Do not silently classify camera-log, HLG, linear, or unknown as SDR.
        if (row['collectionId'] != 'freshluts-community' or row['inputColorSpace'] != 'rec709'
                or row['colorSpaceConfidence'] != 'inferred-from-source-label' or row['cubeKind'] != '3D'):
            continue
        if re.search(r'\b(hlg|hdr|logc|s-?log|v-?log|d-?log|cineon|linear)\b', row['title'], re.I):
            continue
        path = 'site/' + row['clientLut'] + '.gz'
        item = tree[path]
        candidates.append(dict(repository='cyberhirsch/LUTr', commit=LUTR, path=path,
            git_blob=item['sha'], bytes=item['size'], license='CC0-1.0',
            creator=row['author'] or 'FreshLUTs community contributor', title=row['title'],
            upstream_id=row['id'], source_url=row['assetUrl'], tags=row['tags'],
            source_labels=row['sourceLabels'], input_basis='Rec.709 label supplied by uploader; not independently camera-calibrated.',
            upstream_metadata=row))
    candidates.sort(key=lambda r:(r['repository'], r['path']))
    for repo in ('NatronGitHub/clut', 'cyberhirsch/LUTr'):
        rows = [r for r in candidates if r['repository'] == repo]
        snapshot = (ROOT/'sources/lut-research-20261024/NatronGitHub--clut' if repo.startswith('Natron')
                    else RAW/'cyberhirsch--LUTr')
        destination = RAW/'blobs'/repo.replace('/', '--')
        destination.mkdir(parents=True, exist_ok=True)
        missing = [r for r in rows if not (destination/r['path']).is_file()]
        if missing:
            print(json.dumps({'fetch':repo, 'blobs':len(missing)}), flush=True)
            archive=RAW/(repo.replace('/', '--')+'.zip')
            commit=rows[0]['commit']
            if not archive.exists():
                url=f'https://codeload.github.com/{repo}/zip/{commit}'
                req=urllib.request.Request(url,headers={'User-Agent':'agent-editor-kit-source-audit'})
                temporary=archive.with_suffix('.download')
                with urllib.request.urlopen(req,timeout=120) as incoming, temporary.open('wb') as outgoing:
                    while chunk:=incoming.read(1024*1024):
                        outgoing.write(chunk)
                        if outgoing.tell()>768*1024**2:raise ValueError('Source archive exceeds bounded budget')
                temporary.replace(archive)
            with zipfile.ZipFile(archive) as zipped:
                for row in missing:
                    member=repo.split('/')[1]+'-'+commit+'/'+row['path']
                    info=zipped.getinfo(member)
                    if info.file_size!=row['bytes']:raise ValueError('Pinned tree size mismatch')
                    target=destination/row['path'];target.parent.mkdir(parents=True,exist_ok=True)
                    target.write_bytes(zipped.read(info))
        for row in rows:
            target = destination/row['path']
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(git(snapshot, 'cat-file', 'blob', row['git_blob']))
            raw = target.read_bytes()
            if len(raw) != row['bytes'] or hashlib.sha1(f'blob {len(raw)}\0'.encode()+raw).hexdigest() != row['git_blob']:
                raise ValueError('Git object mismatch: '+str(target))
            row['local_path'] = target.relative_to(ROOT).as_posix()
            row['sha256'] = hashlib.sha256(raw).hexdigest()
        print(json.dumps({'acquired':repo, 'blobs':len(rows)}), flush=True)
    snapshot = ROOT/'sources/lut-research-20261024/NatronGitHub--clut'
    (EVIDENCE/'Natron-README.md').write_bytes(git(snapshot,'show',NATRON+':README.md'))
    urls = {'CC-BY-SA-4.0.txt':'https://creativecommons.org/licenses/by-sa/4.0/legalcode.txt',
            'CC0-1.0.txt':'https://creativecommons.org/publicdomain/zero/1.0/legalcode.txt',
            'FreshLUTs-terms.html':'https://freshluts.com/termsandconditions'}
    for name,url in urls.items():
        path = EVIDENCE/name
        if not path.exists():
            req=urllib.request.Request(url,headers={'User-Agent':'agent-editor-kit-source-audit'})
            path.write_bytes(urllib.request.urlopen(req,timeout=60).read())
    (EVIDENCE/'LUTr-ingest.md').write_bytes((RAW/'lutr-ingest.md').read_bytes())
    value = {'captured_at_utc':datetime.now(timezone.utc).isoformat(), 'candidates':candidates,
             'policy':'Pinned numeric data only; camera/unknown inputs, conflicting licenses and duplicate transforms excluded during compilation.',
             'notices':[{ 'path':p.name, 'sha256':hashlib.sha256(p.read_bytes()).hexdigest(), 'url':urls.get(p.name)}
                        for p in sorted(EVIDENCE.iterdir()) if p.is_file() and p.name!='acquisition.json']}
    (EVIDENCE/'acquisition.json').write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'candidate_count':len(candidates),'status':'acquired'}))


if __name__=='__main__':
    main()
