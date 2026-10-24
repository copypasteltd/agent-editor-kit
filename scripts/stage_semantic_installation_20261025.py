"""Preserve native build/install receipts and compare every installed Python source."""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    installed=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.3/final/installed'
    bundle=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.3/candidate-r1/bundle'
    base=ROOT/'docs/validation/evidence/semantic-20261025-r1/installation'
    base.mkdir(parents=True,exist_ok=False)
    for path,name in [(installed/'receipt.json','native-install-receipt.json'),
                      (bundle/'manifest.json','bundle-manifest.json'),(bundle/'build.log','native-build.log')]:
        (base/name).write_bytes(path.read_bytes())
    sources=ROOT/'product/src/ai_ad_editor';records=[]
    for path in sorted(sources.rglob('*.py')):
        relative=path.relative_to(sources)
        records.append(dict(path=relative.as_posix(),source_sha256=sha(path),
                            installed_sha256=sha(installed/'site/ai_ad_editor'/relative)))
    assert all(row['source_sha256']==row['installed_sha256'] for row in records)
    archive=bundle.with_suffix('.zip')
    result=dict(status='installed_source_bytes_match',installed=str(installed),archive=str(archive),
        archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),manifest_sha256=sha(bundle/'manifest.json'),
        python_source_files=records,cli_version='0.1.5',native_windows=True,source_fallback=False,
        generator_sha256=sha(Path(__file__)))
    assert result['archive_sha256']=='804cac8e45d62b4440fb39423126a86d650e415e37ed3f9b7db724b65a2a62cd'
    assert result['manifest_sha256']=='29583211d5cf376f51c295b419ba7bdaaf9f46fa5314820fcc6e180f47a4f95f'
    (base/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(status=result['status'],python_files=len(records),zip_bytes=result['archive_bytes'])),flush=True)


if __name__=='__main__':main()
