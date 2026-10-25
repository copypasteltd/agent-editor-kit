"""Compare the separately built and installed candidate, preserving archive hashes."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/validation/evidence/ctc-activity-20261025-r1'
BASE=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.6'


def main():
    out=EVIDENCE/'installation';out.mkdir(exist_ok=False)
    def sha(p):
        with p.open('rb') as f:return 'sha256:'+hashlib.file_digest(f,'sha256').hexdigest()
    def save(name,v):(out/name).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    bundle=BASE/'candidate-r2/bundle';installed=BASE/'final/installed'
    receipt=json.loads((installed/'receipt.json').read_bytes());manifest=json.loads((bundle/'manifest.json').read_bytes())
    assert receipt['manifest_sha256']==sha(bundle/'manifest.json')
    assert receipt['audit']['modules']['ai-ad-editor']['version']=='0.1.8'
    files=[]
    for source in sorted((ROOT/'product/src/ai_ad_editor').rglob('*.py')):
        relative=source.relative_to(ROOT/'product/src');target=installed/'site'/relative
        assert source.read_bytes()==target.read_bytes(),relative
        files.append(dict(path=relative.as_posix(),bytes=source.stat().st_size,sha256=sha(source)))
    assert len(files)==195
    archive=bundle.with_suffix('.zip')
    with zipfile.ZipFile(archive) as zipped:
        assert zipped.testzip() is None
        assert len(zipped.namelist())==len(set(zipped.namelist()))==len(manifest['files'])+1
        for name in zipped.namelist():assert zipped.read(name)==(bundle/name).read_bytes(),name
    for name in ('receipt.json','dependency-audit.json','requirements.lock','install.log'):
        (out/name).write_bytes((installed/name).read_bytes())
    save('source-python-files.json',files)
    result=dict(status='passed',release='v0.1.0-alpha.4-local.6',cli_version='0.1.8',installed=str(installed),
        archive=str(archive),archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),
        manifest_sha256=sha(bundle/'manifest.json'),source_python_files=len(files),all_source_python_bytes_equal=True,
        wheels=len(manifest['wheels']),bundle_manifest_files=len(manifest['files']),archive_files=len(manifest['files'])+1,
        heavy_model_runtime_and_weights_bundled=False,native_windows=True,virtual_environment=False,
        same_physical_host=True,public_release_changed=False,generator_sha256=sha(Path(__file__)))
    save('verification.json',result);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(result,ensure_ascii=False))


if __name__=='__main__':main()
