"""Real long/SRT/default-mode compatibility and cancellation through explicit CLI."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('site','project','output','reference-result'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--runner',type=Path)
    args = parser.parse_args()
    output, project, site = args.output.resolve(),args.project.resolve(strict=True),args.site.resolve(strict=True)
    assert output.is_relative_to(ROOT/'docs/validation/evidence') and not output.exists()
    output.mkdir(parents=True)
    sys.path.insert(0,str(site))
    from ai_ad_editor.cli import main as cli_main
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()
    def frozen(): return {str(p):sha(p) for p in sorted((site/'ai_ad_editor').glob('*.py'))}
    before=frozen(); calls=[]
    def save(name,value):
        (output/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    (output/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def cli(*argv,expected=0):
        argv=list(map(str,argv));start=time.monotonic()
        if args.runner:
            process=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(args.runner),*argv],
                                   cwd=ROOT,capture_output=True,timeout=900)
            code,raw,err=process.returncode,process.stdout.decode('utf-8-sig'),process.stderr.decode('utf-8','replace')
        else:
            stream,errors=io.StringIO(),io.StringIO()
            with contextlib.redirect_stdout(stream),contextlib.redirect_stderr(errors):code=cli_main(argv)
            raw,err=stream.getvalue(),errors.getvalue()
        value=json.loads(raw);calls.append(dict(argv=argv,exit_code=code,result=value,stderr=err,seconds=time.monotonic()-start))
        save(f'{len(calls):02}.json',calls[-1]);assert code==expected,value
        print(json.dumps(dict(call=len(calls),command=value['command'],code=code)),flush=True)
        return value
    original=ROOT/'docs/assets/ctc-alignment-20261018'
    reference=json.loads(args.reference_result.read_text('utf-8'))
    default=cli('subtitle','align','--project',project,'--asset-id','speech','--adapter-id','ctc',
        '--transcript',original/'transcript.txt','--output','assets/alignment/default.json','--granularity','whitespace')['data']['result']
    assert default['boundary_mode']=='ctc'
    assert default['segments'][0]['units']==reference['segments'][0]['raw_units']
    cli('media','ingest','--project',project,'--asset-id','long','--input',original/'input-long.wav')
    long=cli('subtitle','align','--project',project,'--asset-id','long','--adapter-id','ctc',
        '--transcript',original/'transcript-long.txt','--output','assets/alignment/long.json',
        '--granularity','whitespace','--boundary-mode','activity')['data']['result']
    assert long['samples']>30*16000 and long['worker']['model_forward_calls']>=2
    assert len(long['segments'][0]['windows'])>=2
    assert len(long['segments'][0]['units'])==36
    srt=project/'explicit-cues.srt'
    srt.write_text('1\n00:00:00,000 --> 00:00:03,900\nRED BLUE GREEN\n\n2\n00:00:03,900 --> 00:00:07,865\nRED BLUE GREEN\n',encoding='utf-8')
    segmented=cli('subtitle','align','--project',project,'--asset-id','speech','--adapter-id','ctc',
        '--transcript',srt,'--output','assets/alignment/segmented.json','--granularity','whitespace',
        '--boundary-mode','activity')['data']['result']
    assert len(segmented['segments'])==2 and segmented['segments'][1]['start_sample']==62400
    assert segmented['worker']['model_forward_calls']==2
    metadata=lambda:{name:sha(project/name) for name in ('project.json','project.lock.json','rights-ledger.json')}
    unchanged=metadata(); cancel=project/'cancel.flag';cancel.touch(exist_ok=False)
    cli('subtitle','align','--project',project,'--asset-id','speech','--adapter-id','ctc',
        '--transcript',original/'transcript.txt','--output','assets/alignment/cancel.json','--granularity','whitespace',
        '--boundary-mode','activity','--cancel-file',cancel,expected=8)
    assert metadata()==unchanged and not (project/'assets/alignment/cancel.json').exists()
    cancel.unlink()
    cli('subtitle','align','--project',project,'--asset-id','speech','--adapter-id','ctc',
        '--transcript',original/'transcript.txt','--output','assets/alignment/timeout.json','--granularity','whitespace',
        '--boundary-mode','activity','--timeout','0.001',expected=6)
    assert metadata()==unchanged and not (project/'assets/alignment/timeout.json').exists()
    cli('validate','--project',project)
    after=frozen();assert before==after
    save('verification.json',dict(status='passed',cli_calls=len(calls),model_forward_calls=sum(
        row['worker']['model_forward_calls'] for row in (default,long,segmented)),
        default_mode_exact_raw_units=True,long_windows=len(long['segments'][0]['windows']),srt_segments=2,
        cancellation_and_timeout_preserve_metadata=True,frozen_before=before,frozen_after=after,
        frozen_equal=True,new_renders=0,full_G15_closed=False,native_windows=True,virtualization=False))


if __name__=='__main__': main()
