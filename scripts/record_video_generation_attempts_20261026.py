"""Retain unsuccessful development attempts separately from accepted evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/video-generation-20261026-r1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_bytes())


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args()
    assert a.run.replace('-','').isalnum()
    out=BASE/('development-attempts-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    first=load(BASE/'source-r1/verification.json')
    interim=load(BASE/'source-r2/verification.json')
    final=load(BASE/'source-r3/verification.json')
    transition_before=load(BASE/'planning-transition-r1/verification.json')
    transition=load(BASE/'planning-transition-r2/verification.json')
    case=load(BASE/'case-r1/verification.json')
    failed_kit=load(BASE/'kit-r1/failure.json')
    accepted_kit=load(BASE/'kit-r2/verification.json')
    retained_kit=load(BASE/'kit-r1/retained-unaccepted-artifacts.json')
    assert first['status']=='failed' and first['tests']==13 and first['errors']==4
    assert interim['status']=='passed' and interim['tests']==13
    assert final['status']=='passed' and final['tests']==14 and final['frozen_equal']
    assert transition_before['status']=='failed-before-process-changes' and transition_before['processes_modified']==0
    assert transition['status']=='passed' and len(transition['stopped'])==2
    assert not transition['model_checks_weakened'] and not transition['other_processes_modified']
    assert len(case['modes'])==4 and case['status']=='passed_actual_four_mode_cuda_transport_and_editable_package'
    assert failed_kit['status']=='failed' and '180 seconds' in failed_kit['error']
    assert accepted_kit['status']=='passed' and accepted_kit['installer_timeout_preserves_prior_configuration']
    assert sha(ROOT/retained_kit['archive'])==retained_kit['sha256']
    paths=['source-r1/verification.json','source-r2/verification.json','source-r3/verification.json',
           'planning-transition-r1/verification.json','planning-transition-r2/verification.json',
           'case-r1/executed-generator.py','case-r1/executed-resume-generator.py',
           'case-r1/before-resume.json','case-r1/verification.json',
           'kit-r1/failure.json','kit-r1/retained-unaccepted-artifacts.json',
           'kit-r1/unaccepted-candidate.zip','kit-r1/unaccepted-package.json',
           'kit-r2/verification.json','kit-r2/expected-verification-timeout.json']
    records=[dict(path=name,sha256=sha(BASE/name)) for name in paths]
    report=dict(status='recorded',at_utc=datetime.now(timezone.utc).isoformat(),final_product_files=227,
        failed_attempts_retained=True,model_checks_weakened=False,other_user_processes_modified=False,
        prefinal_source_tests=dict(tests=13,errors=4,accepted=False,
            reason='Initial test fixture path errors and missing OS-write error conversion; fixed before the frozen build.'),
        interim_source_tests=dict(tests=13,accepted_for_final_build=False,
            reason='Passed before final default-window and installed-fixture changes; not counted as final delivery.'),
        final_source_tests=dict(tests=14,errors=0,product_files=len(final['product_files']),frozen_equal=True),
        failed_transition=dict(processes_modified=0,
            reason='Windows PowerShell CIM used the local output codepage; UTF-8 decoding failed before any stop.'),
        successful_transition=dict(intentional_stops=2,real_modes_before_stop=1,
            stopped_roles=['completed-mode original controller','identified next read-only image-mode dry-run'],
            reason='Four-mode planning was already covered by the installed14 tests. Avoid three redundant checkpoint reads; retain every actual-generation integrity check.',
            actual_model_worker_interrupted=False,original_controller_exit_expected=True),
        failed_independent_kit=dict(accepted=False,reason='Fixed180-second activation verification timeout during concurrent large-model I/O.',
            retained_candidate_sha256=retained_kit['sha256'],public_release_tags_changed=False),
        accepted_independent_kit=dict(default_per_pack_deadline_seconds=600,explicit_deadline_range=[1,3600],
            full_integrity_checks_retained=True,forced_one_second_timeout_preserves_both_prior_configs=True),
        synthetic_protocol_workers_are_real_model_evidence=False,evidence=records)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
