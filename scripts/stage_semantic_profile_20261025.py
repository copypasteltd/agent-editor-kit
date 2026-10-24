"""Write an explicit local model profile from the successful installed registration."""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]


def main():
    source=ROOT/'docs/validation/evidence/semantic-20261025-r1/installed-r1/setup/13.stdout.json'
    response=json.loads(source.read_bytes())
    assert response['ok'] and response['data']['verification']['ok']
    adapter=response['data']['adapter']
    evidence=next(r for r in adapter['artifacts'] if r['role']=='evidence')
    model=next(r for r in adapter['artifacts'] if Path(r['path']).name=='model.safetensors')
    profile=dict(format='agent-local-semantic-runtime-v1',python_executable=adapter['python_executable'],
        model_path=adapter['model_path'],evidence=evidence['path'],creator='Google',license_spdx='Apache-2.0',
        verification_status='verified',model_weights_sha256=model['sha256'],model_weights_bytes=model['bytes'],
        registration_response_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
        registration_adapter_sha256=adapter['sha256'],runtime_versions=adapter['runtime_versions'],
        origin='https://huggingface.co/google/siglip2-base-patch16-224',
        acquisition_snapshot='e8632ce825c01c31e138f83852c01b643941c2fe',
        automatic_registration=False,automatic_download=False)
    for key in ('python_executable','model_path','evidence'):assert Path(profile[key]).exists()
    destination=ROOT/'local/agent-ffmpeg/semantic-runtime.json'
    with destination.open('x',encoding='utf8',newline='\n') as stream:
        stream.write(json.dumps(profile,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(dict(status='profile_staged',path=str(destination),automatic_download=False)),flush=True)


if __name__=='__main__':main()
