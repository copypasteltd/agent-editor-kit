"""Package the new offline look release; keep every alpha.1 asset immutable."""
from pathlib import Path
import hashlib
import json
import shutil
import zipfile

ROOT=Path(__file__).resolve().parents[1]
TAG="v0.1.0-alpha.3"
BUNDLE=ROOT/"product/.runtime/look500-release-20261024/bundle-policy"
ARTIFACTS=ROOT/"docs/releases"/TAG/"artifacts"


def sha(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle,"sha256").hexdigest()


def main():
    ARTIFACTS.mkdir(parents=True,exist_ok=True)
    archive=BUNDLE.parent/f"agent-editor-kit-{TAG}-cp313-win_amd64.zip"
    if archive.exists():raise ValueError("An existing release archive is preserved")
    manifest=json.loads((BUNDLE/"manifest.json").read_bytes())
    product=next((BUNDLE/'wheels').glob('ai_ad_editor*.whl'))
    catalog=json.loads((ROOT/'product/src/ai_ad_editor/look_data/catalog.json').read_bytes())
    with zipfile.ZipFile(product) as wheel:
        names=set(wheel.namelist())
        actual={n.split('/look_data/',1)[1] for n in names if '/look_data/luts/' in n}
        if actual!={r['lut'] for r in catalog['records']}:raise ValueError('Application wheel look inventory differs from the 500-look catalog')
    version={"release":TAG,"cli_version":"0.1.2","manifest_sha256":"sha256:"+sha(BUNDLE/"manifest.json"),
             "schema_sha256":manifest["schema_sha256"],"look_catalog_version":"2.0.0","look_count":500,
             "look_catalog_sha256":sha(ROOT/"product/src/ai_ad_editor/look_data/catalog.json"),
             "target":"cp313-win_amd64","network":"disabled","python_included":False,"ffmpeg_included":False,
             "status":"local-tested-build","public_github_release_created":False}
    (ARTIFACTS/"version.json").write_text(json.dumps(version,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    rows=[(p,"bundle/"+p.relative_to(BUNDLE).as_posix()) for p in BUNDLE.rglob("*") if p.is_file()]
    rows += [(ARTIFACTS/"version.json","version.json"),(ROOT/"LICENSE","LICENSE")]
    for filename in ("USAGE.md","THIRD_PARTY.md"):
        rows.append((ARTIFACTS.parent/filename,filename))
    with zipfile.ZipFile(archive,"x",compression=zipfile.ZIP_DEFLATED,compresslevel=6) as zipped:
        for path,name in sorted(rows,key=lambda x:x[1]):zipped.write(path,name)
    parts=[]
    with archive.open('rb') as incoming:
        while chunk:=incoming.read(64*1024**2):
            path=ARTIFACTS/(archive.name+f'.part{len(parts)+1:02}')
            with path.open('xb') as outgoing:outgoing.write(chunk)
            parts.append({'name':path.name,'bytes':len(chunk),'sha256':sha(path)})
    inventory={'release':TAG,'archive_name':archive.name,'bytes':archive.stat().st_size,'sha256':sha(archive),'parts':parts}
    (ARTIFACTS/'parts.json').write_text(json.dumps(inventory,indent=2)+'\n',encoding='utf-8')
    shutil.copyfile(ROOT/'scripts/assemble_look500_release.py',ARTIFACTS/'assemble.py')
    files=[ARTIFACTS/p['name'] for p in parts]+[ARTIFACTS/'parts.json',ARTIFACTS/'assemble.py',ARTIFACTS/"version.json"]
    (ARTIFACTS/"SHA256SUMS.txt").write_text("".join(sha(p)+"  "+p.name+"\n" for p in files),encoding="ascii")
    print(json.dumps({"archive":str(archive),"bytes":archive.stat().st_size,"sha256":sha(archive),"parts":len(parts),"version":version}))


if __name__=="__main__":main()
