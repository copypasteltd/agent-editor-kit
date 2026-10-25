"""Preserve the failed v1 implementation and inspect its weak-onset rejection."""
from pathlib import Path
import hashlib
import json
import wave
import zipfile
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'docs/validation/evidence/ctc-activity-20261025-r1'


def main():
    run=json.loads((OUT/'development-r1/state.json').read_text('utf-8'))
    assert run['status']=='executed' and run['frozen_equal'] and len(run['cases'])==4
    target=OUT/'failed-v1-source.zip'
    assert not target.exists()
    rows=[]
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED) as archive:
        for row in run['frozen_before']:
            path=Path(row['path'])
            assert hashlib.sha256(path.read_bytes()).hexdigest()==row['sha256']
            archive.write(path,path.relative_to(ROOT).as_posix())
            rows.append(row)
    with wave.open(str(ROOT/'docs/assets/ctc-alignment-20261018/input.wav'),'rb') as stream:
        pcm=np.frombuffer(stream.readframes(stream.getnframes()),dtype='<i2').astype(np.int32)
    weak=[]
    for start in range(8000,11360,80):
        frame=pcm[start:start+80]
        weak.append(dict(start_sample=start,rms=float(np.sqrt(np.mean(frame.astype(float)**2))),
                         peak=int(np.max(np.abs(frame))),nonzero_samples=int(np.count_nonzero(frame))))
    record=dict(status='v1_quality_failure_preserved',unchanged_gate_ms=1000*2/30,
        cases=[dict(name=r['fixture'],raw_max_error_ms=r['quality']['raw_ctc']['max_error_ms'],
                    activity_max_error_ms=r['quality']['activity']['max_error_ms'],passed=r['quality']['activity']['passed'])
               for r in run['cases']],
        cause='v1 low=max(2,2*noise,ceil(reference/316)) yields 27 PCM; original weak onset RMS repeatedly 8..27 PCM is dropped while later vowel reference is 8377 PCM',
        original_reference_type='authored abs>=32 trimmed synthetic word blocks, not independent phonetic truth',
        weak_onset_frames=weak,source_snapshot=dict(path=target.name,bytes=target.stat().st_size,
                     sha256=hashlib.sha256(target.read_bytes()).hexdigest(),files=len(rows)),
        no_reference_or_gate_changes=True,no_v2_result_available=True,
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (OUT/'v1-failure-analysis.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'v1_failures':sum(not r['passed'] for r in record['cases']),'snapshot_files':len(rows)}))


if __name__=='__main__':main()
