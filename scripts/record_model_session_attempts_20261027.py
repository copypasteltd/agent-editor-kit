"""Keep failed development/frozen-candidate evidence apart from final acceptance."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/model-session-20261027-r1'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def load(path):return json.loads(Path(path).read_bytes())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args();assert args.run.replace('-','').isalnum()
    out=BASE/('development-attempts-'+args.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    source=load(BASE/'session-source-r2/verification.json');assert source['status']=='failed' and source['failures']==source['errors']==1
    corrected=load(BASE/'session-source-r3/verification.json');assert corrected['status']=='passed' and corrected['tests']==18
    rejected=load(BASE/'installation-final-r1/verification.json');assert rejected['status']=='failed' and 'model_session.py' in rejected['error']
    installed=load(BASE/'installation-final-r3/verification.json');assert installed['status']=='installed-and-byte-verified'
    stale=load(BASE/'vace-installed-r1/verification.json');assert stale['status']=='failed' and stale['failures']==1 and stale['frozen_equal']
    final=load(BASE/'vace-installed-r3/verification.json');assert final['status']=='passed' and final['tests']==161 and final['frozen_equal']
    earlier=load(BASE/'vace-source-r1/verification.json');assert earlier['status']=='failed' and not earlier['frozen_equal']
    names=['session-source-r1/verification.json','session-source-r2/verification.json','session-source-r3/verification.json',
           'generation-source-r1/verification.json','installation-final-r1/verification.json','installation-final-r2/verification.json',
           'vace-source-r1/verification.json','vace-installed-r1/verification.json','vace-installed-r2/verification.json',
           'session-installed-r1/verification.json','generation-installed-r1/verification.json','legacy-installed-r1/verification.json']
    old_archive=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.32/candidate-r1/bundle.zip'
    names += ['installation-final-r3/verification.json','control-lock-r1/verification.json','control-source-r1/verification.json',
              'control-source-r2/verification.json','control-fix-r1/verification.json','session-installed-r2/verification.json',
              'generation-installed-r2/verification.json','vace-installed-r3/verification.json','legacy-installed-r2/verification.json',
              'render-roundtrip-r1/verification.json','skill-registration-r1/verification.json','render-roundtrip-r2/verification.json',
              'registration-preflight-r1/verification.json']
    control=load(BASE/'control-fix-r1/verification.json');assert control['status']=='passed'
    failed_kit1=load(BASE/'kit-r1/failure.json');failed_kit2=load(BASE/'kit-r2/failure.json')
    final_kit=load(BASE/'kit-r3/verification.json');assert final_kit['status']=='passed'
    assert failed_kit1['status']==failed_kit2['status']=='failed'
    names += ['kit-r1/failure.json','kit-r2/failure.json','kit-r3/verification.json']
    record=dict(status='recorded',at_utc=datetime.now(timezone.utc).isoformat(),final_product_files=230,
        failed_attempts_retained=True,model_checks_weakened=False,other_user_processes_modified=False,
        rejected_session_tests=dict(tests=18,failures=1,errors=1,
            reason='Owner disconnect exposed an EOF status-query race, fixed in controller. A second failure was a test expecting an error code in the translated message rather than AppError.code.'),
        rejected_first_bundle=dict(activated=False,path=str(old_archive),sha256=sha(old_archive),
            reason='Controller fix occurred while the first candidate was being built; frozen byte comparison rejected it. The second candidate was rebuilt and fully installed/verified.'),
        rejected_source_vace=dict(tests=earlier['tests'],failures=earlier['failures'],frozen_equal=False,
            reason='Source changed during execution: old pinned adapters correctly rejected modified implementation bytes. Also retained an obsolete36-artifact fixture expectation.'),
        rejected_installed_vace=dict(tests=160,failures=1,frozen_equal=True,
            reason='Only the obsolete36-artifact fixture expectation failed; the session controller/worker/relay add3 required pinned artifacts. Corrected to39 and added an independent missing-session-inventory rejection test.'),
        control_fix=dict(real_gpu_observation='status returned PROJECT_WRITE_LOCKED during actual denoising',
            failed_before=True,passed_after=True,final_installed='final-r3',measured_gpu_installation='final-r2',
            byte_identical_inference_kernel=True,byte_identical_non_cli_product_files=229,
            reason='Only the model-session CLI control transaction/lock exemption changed. Actual GPU performance was measured on final-r2; final-r3 installed regressions verify the corrected controls.'),
        rejected_skill_call=dict(path='render-roundtrip-r1',exit_code=2,
            reason='Actual registered Skill retained the old local.31 launcher release/manifest pin. Corrected to the final local.32 manifest, refreshed all75 Skill file pins, registered again and reran actual rendering as render-roundtrip-r2. Registration now executes the reviewed launcher version before discovery mutation; an isolated deliberately stale pin is rejected without creating discovery or a success receipt.'),
        rejected_kit_verifiers=[dict(path='kit-r1',reason='Verifier copied a renamed generation protocol string. The installed API correctly retained local-vace-conditioned-video-generation-v1. Corrected the expected fixture; implementation unchanged.'),
            dict(path='kit-r2',reason='Verifier copied the historical tracking-retime fixture with the wrong date. Installed convert.import correctly rejected the missing input. Restored the existing20261026 fixture and preflight all fixture paths; implementation/kit bytes unchanged.')],
        accepted_final_kit=dict(path='kit-r3',sha256=final_kit['kit_sha256'],files=final_kit['files']),
        accepted_installed_groups=[dict(path=name,tests=load(BASE/name/'verification.json')['tests']) for name in
            ('session-installed-r2','generation-installed-r2','vace-installed-r3','legacy-installed-r2')],
        evidence=[dict(path=name,sha256=sha(BASE/name)) for name in names])
    (out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(status='recorded',failed_candidates_retained=True,final_vace_tests=161)),flush=True)


if __name__=='__main__':main()
