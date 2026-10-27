"""Preserve the discovered tiny-sigma failure and apply overflow-safe weights."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json
import sys

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/highlight-glow-20261027-r1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')

def main():
    prior=json.loads((BASE/'installed-regression-r1/verification.json').read_bytes())
    assert prior['tests']==733 and prior['frozen_equal'] and prior['test_frozen_equal']
    out=BASE/'tiny-radius-correction-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    sys.path.insert(0,str(ROOT/'product/src'))
    from ai_ad_editor.float_glow import kernel
    records=[]
    for value in (1e-5,1e-160,5e-324):
        try:records.append(dict(radius=value,result=list(kernel(value))))
        except Exception as exc:records.append(dict(radius=value,error=type(exc).__name__,message=str(exc)))
    assert records[1]['error']=='OverflowError'
    p=ROOT/'product/src/ai_ad_editor/float_glow.py';before=sha(p);s=p.read_text('utf8')
    old="weights = [math.exp(-.5 * (i / radius)**2) for i in range(-support, support + 1)] if support else [1.]"
    new="weights = [math.exp((-.5 * (i / radius)) * (i / radius)) for i in range(-support, support + 1)] if support else [1.]"
    assert s.count(old)==1;write(p,s.replace(old,new))
    p=ROOT/'product/tests/test_float_glow.py';s=p.read_text('utf8')
    marker='    def test_flat_clamped_field_has_exact_soft_knee_energy(self):'
    assert marker in s
    addition='''    def test_extremely_small_nonzero_radius_is_stable_instead_of_scalar_overflow(self):
        a = impulse()
        expected, _ = apply(a, effect(radius=0, threshold=0, knee=0))
        for radius in (1e-5, 1e-160, 5e-324):
            actual, _ = apply(a, effect(radius=radius, threshold=0, knee=0))
            np.testing.assert_array_equal(actual, expected)

'''
    s=s.replace(marker,addition+marker,1)
    s=s.replace('for radius in (0., .2, 1.25, 32.):','for radius in (0., 1e-160, 5e-324, .2, 1.25, 32.):')
    s=s.replace("['glow'], 48)","['glow'], 72)",1)
    s=s.replace("[('glow_bright', 48), ('glow_blur', 96), ('glow_merge', 48)]","[('glow_bright', 72), ('glow_blur', 144), ('glow_merge', 72)]")
    s=s.replace("group='glow-48-actual-operations'","group='glow-72-actual-operations'")
    write(p,s)
    p=ROOT/'product/tests/test_cli.py';s=p.read_text('utf8')
    old="optical = {item['id']: item for item in catalog['data']['effects'] if item['category']=='optical'}"
    new="optical = {item['id']: item for item in catalog['data']['effects'] if item['backend']=='native:float32-optics'}"
    assert s.count(old)==1;s=s.replace(old,new)
    marker='        frame_interpolation = next(item for item in catalog["data"]["effects"] if item["id"] == "frame_interpolation")'
    assert marker in s
    s=s.replace(marker,"        glow = {item['id']: item for item in catalog['data']['effects'] if item['backend']=='native:float32-glow'}\n"
        "        self.assertEqual(set(glow), {'bloom','halation'})\n"
        "        self.assertTrue(all(item['category']=='optical' and item['keyframable'] for item in glow.values()))\n"+marker,1)
    write(p,s)
    report=dict(status='corrected_pending_final_installed_validation',at_utc=datetime.now(timezone.utc).isoformat(),
        reproduced_original_cases=records,original_source_sha256=before,
        corrected_source_sha256=sha(ROOT/'product/src/ai_ad_editor/float_glow.py'),
        prior_installed_run_status=prior['status'],prior_installed_tests=733,
        final_numeric_tests=21,final_GPU_parameter_combinations=72,final_expected_regressions=734,
        scope='Scalar squaring overflow fixed by IEEE multiplication; tiny nonzero sigma tends to an identity kernel. No acceptance threshold relaxed.')
    write(out/'verification.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report))

if __name__=='__main__':main()
