"""Retain rejected development evidence and verify the actual encoding counterexample."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,subprocess
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-edits-20261026-r1'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    out=BASE/'development-attempts-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def load(p):return json.loads(Path(p).read_bytes())
    rows=[]
    for name,kind in [('editing-installed-r1','legacy minimal-binding compatibility read, fixed before final build'),
                      ('case-r1','10bit CRF0 was incorrectly assumed pixel-lossless'),
                      ('queue-r1','verifier wrongly rejected normal output/provenance/updated_at bookkeeping'),
                      ('chained-reference-source-r1','intermediate current pose incorrectly used its pinned ROI reference; fixed and regression-covered')]:
        path=BASE/name/'verification.json';report=load(path);assert report['status']=='failed'
        rows.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),reason=kind,
            tests=report.get('tests'),failures=report.get('failures'),errors=report.get('errors'),excluded_from_final_acceptance=True))
    first=load(BASE/'case-r1/verification.json');ffmpeg=next(c['argv'][0] for c in first['calls'] if c['name']=='edited-frames')
    movie=ROOT/'workspace/tracking-edits-20261026-case-r1/编辑 工程/renders/before.mkv'
    argv=[ffmpeg,'-hide_banner','-loglevel','info','-i',str(movie),'-map','0:v:0','-c','copy','-bsf:v','trace_headers','-frames:v','1','-f','null','-']
    r=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'trace-headers.stdout.log').write_bytes(r.stdout);(out/'trace-headers.stderr.log').write_bytes(r.stderr)
    assert r.returncode==0
    headers=[line for line in r.stderr.decode('utf8','replace').splitlines() if 'qpprime_y_zero_transform_bypass_flag' in line]
    assert headers and all(line.strip().endswith('= 0') for line in headers)
    work=ROOT/'workspace/tracking-edits-20261026-case-r1'
    a=np.fromfile(work/'before-pcm.stdout.bin','<f4').reshape(-1,2)
    b=np.fromfile(work/'edited-pcm.stdout.bin','<f4').reshape(-1,2)
    assert np.array_equal(np.concatenate((a[:48000],a[72000:])),b)
    case=BASE/'case-r1';x=np.load(case/'initial-diagnostic-float.npy');y=np.load(case/'edited-diagnostic-float.npy')
    assert np.array_equal(x,y)
    diag=load(case/'diagnostic.json');left=next(r['tracking'] for r in diag[0]['rows'] if 'tracking' in r)
    right=next(r['tracking'] for r in diag[1]['rows'] if 'tracking' in r)
    assert all(left[k]==right[k] for k in ('values','native_pts','native_frame_index','source_author_tick','source_time'))
    report=dict(status='passed',checked_at_utc=datetime.now(timezone.utc).isoformat(),failed_attempts=rows,
        legacy_errors=2,chain_failing_subtests=8,chain_test_case_failures=1,
        encoding_counterexample=dict(argv=argv,exit_code=r.returncode,headers=headers,
            stderr_sha256=sha(out/'trace-headers.stderr.log'),movie_sha256=sha(movie),
            first_different_frame_original=18,first_different_frame_edited=12,
            first_different_frame_float_pixels_and_geometry_equal=True,full_PCM_equal=True,
            final_diagnostic='explicit yuv444p 8bit CRF0 plus all retained Float32 pixels'),
        final_acceptance_only='final-r3 installed groups and case-r3; earlier candidates retained separately',
        virtualization=False,new_model_forwards=0)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(status='passed',retained_failed_attempts=len(rows),actual_H264_counterexample=True)))

if __name__=='__main__':main()
