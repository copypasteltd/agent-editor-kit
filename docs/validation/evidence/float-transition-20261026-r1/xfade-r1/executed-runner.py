"""Compare all 57 opaque patterns against an independent native FFmpeg graph.

The fixed oracle is a 64x40 binary16 RGB grid, 10fps and the exact midpoint
of a four-frame overlap. Non-wind error limit: four 16-bit code values.
Wind uses a platform-dependent sinf hash: differences are reported, not
accepted as bit parity. Alpha/linear-light tests are separate.
"""
import argparse,hashlib,json,subprocess,sys,time
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True)
    parser.add_argument('--installed',type=Path);args=parser.parse_args()
    assert args.run.replace('-','').isalnum()
    out=ROOT/'docs/validation/evidence/float-transition-20261026-r1'/('xfade-'+args.run)
    out.mkdir(parents=True,exist_ok=False);(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'workspace'/('float-transition-20261026-xfade-'+args.run);work.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(args.installed/'site' if args.installed else ROOT/'product/src'))
    import numpy as np
    from ai_ad_editor.runtime import configure_local_runtime
    from ai_ad_editor.media import ffmpeg_path
    from ai_ad_editor.render import XFADE_TRANSITIONS
    from ai_ad_editor.float_transitions import transition_rgba
    configure_local_runtime()
    rng=np.random.default_rng(58009);codes=[rng.integers(4096,61440,(40,64,3),dtype=np.uint16) for _ in range(2)]
    sources=[]
    for i,c in enumerate(codes):
        path=work/('source-'+str(i)+'.gbrp16')
        path.write_bytes(np.moveaxis(c[:,:,[1,2,0]],2,0).astype('<u2').tobytes()*10);sources.append(path)
    a,b=[np.concatenate((c.astype(np.float32)/65535,np.ones((40,64,1),np.float32)),2) for c in codes]
    rows=[];started=time.perf_counter()
    report={'status':'running','protocol':'fixed-native-xfade-57-pattern-oracle-v1','code_error_limit':4,
        'wind_bit_parity_claimed':False,'frames_compared_per_pattern':1,'calls':rows,
        'installed':str(args.installed) if args.installed else None,'virtualization':False}
    def save():
        (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    try:
        for kind in sorted(XFADE_TRANSITIONS):
            command=[ffmpeg_path(),'-nostdin','-v','error','-filter_complex_threads','1']
            for source in sources:command+=['-f','rawvideo','-pixel_format','gbrp16le','-video_size','64x40','-framerate','10','-i',str(source)]
            command+=['-filter_complex',f'[0:v][1:v]xfade=transition={kind}:duration=0.4:offset=0.6,select=eq(n\\,8)[v]',
                '-map','[v]','-frames:v','1','-pixel_format','gbrp16le','-f','rawvideo','pipe:1']
            result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            (out/(kind+'.stderr.txt')).write_bytes(result.stderr)
            assert result.returncode==0,(kind,result.stderr[-2000:])
            native=np.frombuffer(result.stdout,'<u2').reshape(3,40,64)[[2,0,1]].transpose(1,2,0)
            value,meta=transition_rgba(a,b,.5,kind=kind)
            actual=np.rint(value[:,:,:3].astype(np.float64)*65535).astype(np.int64)
            delta=np.abs(actual-native.astype(np.int64));maximum=int(delta.max())
            row={'type':kind,'argv':command,'exit_code':result.returncode,
                'native_sha256':hashlib.sha256(result.stdout).hexdigest(),'float_surface_sha256':hashlib.sha256(value.tobytes()).hexdigest(),
                'max_code_error':maximum,'mean_code_error':float(delta.mean()),
                'pixels_exceeding_four_codes':int(np.any(delta>4,axis=2).sum()),
                'bit_parity_expected':False,'fixed_oracle_passed':maximum<=4 if not kind.endswith('wind') else None}
            rows.append(row);save()
            print(json.dumps({k:row[k] for k in ('type','max_code_error','fixed_oracle_passed')}),flush=True)
        assert len(rows)==57
        bad=[r['type'] for r in rows if r['fixed_oracle_passed'] is False]
        assert not bad,bad
        report.update(status='passed',non_wind_patterns_checked=53,wind_patterns_reported=4,
            elapsed_seconds=time.perf_counter()-started,finished_at_utc=datetime.now(timezone.utc).isoformat())
        save()
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save();raise

if __name__=='__main__':main()
