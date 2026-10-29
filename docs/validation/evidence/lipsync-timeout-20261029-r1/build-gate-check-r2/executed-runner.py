"""Exercise CLI61 build rejection with missing gates and verify no activation."""
import argparse,hashlib,json,subprocess,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args()
    assert args.run.replace('-','').isalnum()
    old=json.loads((ROOT/'docs/validation/evidence/music-loop-20261029-r1/installation-candidate-r1/verification.json').read_bytes())
    pins=old['registered_skill_file_hashes']
    assert len(pins)==95 and all(sha(p)==v for p,v in pins.items())
    candidate=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.59'
    receipt=BASE/('installation-candidate-gate-'+args.run)
    assert not candidate.exists() and not receipt.exists()
    full=BASE/'source61-contracts-r1/verification.json'
    assert not full.exists(),'Use a later negative-gate scenario after full contracts finish'
    out=BASE/('build-gate-check-'+args.run);out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    builder=ROOT/'docs/validation/build_source61_delivery.py';pin=sha(builder)
    p=subprocess.run([sys.executable,'-E','-B','-u','-X','utf8',str(builder),'--run','gate-'+args.run],
        cwd=ROOT,capture_output=True,timeout=120)
    (out/'stdout').write_bytes(p.stdout);(out/'stderr').write_bytes(p.stderr)
    assert p.returncode!=0
    rejection=json.loads(p.stderr.decode('utf-8').strip())
    assert rejection['status']=='rejected' and rejection['reason']=='missing acceptance gates'
    assert 'docs/validation/evidence/lipsync-timeout-20261029-r1/source61-contracts-r1/verification.json' in [p.replace('\\','/') for p in rejection['missing']]
    assert not candidate.exists() and not receipt.exists()
    assert sha(builder)==pin and all(sha(p)==v for p,v in pins.items())
    report=dict(status='passed',actual_build_rejected=True,actual_exit_code=p.returncode,
        missing=rejection['missing'],protected_files_unchanged=95,no_candidate_created=True,
        formal_skill_cli='0.1.59',new_candidate_cli='0.1.61',formal_skill_activation=False,
        builder_sha256=pin)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
