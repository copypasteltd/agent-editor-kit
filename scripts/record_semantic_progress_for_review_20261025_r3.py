"""Copy actual candidate GPU-index evidence into the read-only goal review.

The source executions stay separate from installed-release acceptance.
"""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DEST=ROOT/'docs/validation/evidence/goal-gaps-20261025-r3'
SOURCE=ROOT/'docs/validation/evidence/semantic-20261025-r1/development-r1/index'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    copies=[]
    for name,target in [('verification.json','candidate-index.json'),('calls.json','candidate-index-calls.json'),
                        ('01.stdout.json','candidate-index.stdout.json'),('01.stderr.txt','candidate-index.stderr.txt'),
                        ('02.stdout.json','candidate-index-verify.stdout.json'),('02.stderr.txt','candidate-index-verify.stderr.txt')]:
        source=SOURCE/name;destination=DEST/target
        assert not destination.exists()
        destination.write_bytes(source.read_bytes())
        copies.append(dict(source=source.relative_to(ROOT).as_posix(),copy=target,sha256=sha(destination)))
    data=json.loads((DEST/'candidate-index.json').read_bytes())
    response=data['inference']['response']
    assert data['status']=='passed' and data['frozen_equal'] and data['development_source_only']
    assert data['commands']==2 and data['index_rows']==15 and data['source_assets']==10
    assert response['rows']==14 and response['model_forward_calls']==2 and response['device']=='cuda'
    result=dict(status='development_index_verified',recorded_at_utc=datetime.now(timezone.utc).isoformat(),
        source_evidence=copies,installed_or_skill_delivered=False,relevance_quality_accepted=False,
        source_assets=10,index_rows=15,unique_images_encoded=14,actual_image_forward_calls=2,
        device=response['device'],model_dtype=response['model_dtype'],gpu=response['actual_device'],
        model_loads=response['model_loads'],load_seconds=response['load_seconds'],
        inference_seconds=response['inference_seconds'],worker_total_seconds=response['elapsed_seconds'],
        peak_cuda_allocated_bytes=response['peak_cuda_allocated_bytes'],
        whole_phase_seconds=(datetime.fromisoformat(data['finished_at_utc'])-datetime.fromisoformat(data['started_at_utc'])).total_seconds(),
        runtime_includes_integrity_hashing_and_startup=True,
        limitations=['No text/image query relevance accepted','No CPU/GPU retrieval comparison yet',
                     'Still images and a still-image montage, not natural moving actions',
                     'No persistent model service; no installed or public delivery',
                     'No human viewing/listening acceptance'],
        complete_G26=False,generator_sha256=sha(Path(__file__)))
    path=DEST/'candidate-progress.json';assert not path.exists()
    path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('source_evidence','limitations')},ensure_ascii=False))


if __name__=='__main__':main()
