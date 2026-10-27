"""Capture actual source/installed tests with immutable attempt directories."""
from pathlib import Path
import argparse,hashlib,json,os,sys,tempfile,unittest
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-hdr-20261027-r1'
GROUPS={'emitters':['test_emitter_animation.EmitterNumericTests','test_emitter_animation.EmitterCLITests'], 'emitter-gpu':['test_emitter_animation.EmitterGPUTests'], 'control':['test_float_gpu_control'],
    'particles':['test_procedural_particles.ParticleTests','test_procedural_particles.ParticleCLITests'],
    'particle-gpu':['test_procedural_particles.ParticleGPUTests'],
    'integration':['test_procedural_particles.ParticleIntegrationTests'],
    'gpu':['native_float_gpu'],
    'render':['test_float_standard_render','test_float_stream','test_float_preview'],
    'audio':['test_float_audio_graph','test_source_transitions','test_nested_transitions'],
    'float':['test_float_timeline','test_float_composite','test_float_geometry','test_float_crop','test_float_mask'],
    'editing':['test_clip_windows','test_range_edits','test_linked_edit','test_source_edits','test_retime_edits'],
    'legacy':['test_cli','test_timeline_preview','test_queue_reuse','test_schema_contract'],
}
GROUPS['native-regression']=[name for group in ('gpu','render','audio','float','editing') for name in GROUPS[group]]
GROUPS['emitter-integration']=['test_emitter_animation.EmitterIntegrationTests']
GROUPS['optics']=['test_float_optics.OpticalNumericTests']
GROUPS['optics-gpu']=['test_float_optics.OpticalGPUTests']
GROUPS['optics-integration']=['test_float_optics.OpticalIntegrationTests']
GROUPS['glow']=['test_float_glow.GlowNumericTests']
GROUPS['glow-gpu']=['test_float_glow.GlowGPUTests']
GROUPS['glow-integration']=['test_float_glow.GlowIntegrationTests']
GROUPS['prior-delivery-regression']=[name for group in ('glow','glow-gpu','glow-integration','optics','optics-gpu','optics-integration','emitters','emitter-gpu','emitter-integration','control','native-regression','particles','particle-gpu','integration','legacy')
                               for name in GROUPS[group]]
GROUPS['particle-files']=['test_procedural_particles.ParticleCLITests.'+name for name in (
    'test_custom_source_file_is_loaded_and_seed_override_is_retained',
    'test_empty_explicit_signal_file_is_loaded_for_a_new_project',
    'test_invalid_missing_and_oversize_JSON_return_structured_error_and_no_mutation')]
GROUPS['hdr']=['test_float_hdr.HDRNumericTests']
GROUPS['hdr-integration']=['test_float_hdr.HDRIntegrationTests']
GROUPS['hdr-compat']=['test_float_color_signal','test_float_curves','test_float_lut','test_float_bundle','test_float_bundle_source','test_float_balance','test_float_levels','test_float_tone']
GROUPS['delivery-regression']=GROUPS['prior-delivery-regression']+GROUPS['hdr']+GROUPS['hdr-integration']+GROUPS['hdr-compat']

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pins(package):return {p.name:sha(p) for p in package.glob('*.py')}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--installed',type=Path)
    ap.add_argument('--group',choices=GROUPS,default='particles');a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/a.run;out.mkdir(parents=True,exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('highlight-glow-tests-'+a.run);work.mkdir(parents=True,exist_ok=False)
    os.environ.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work));tempfile.tempdir=str(work)
    source=ROOT/'product/src/ai_ad_editor';package=a.installed.resolve()/'site/ai_ad_editor' if a.installed else source
    before=pins(source);assert pins(package)==before
    sys.path[:0]=[str(package.parent),str(ROOT/'product/tests')]
    rubberband=ROOT/'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe'
    assert rubberband.is_file();os.environ['AI_AD_EDITOR_TEST_RUBBERBAND']=str(rubberband)
    suite=unittest.defaultTestLoader.loadTestsFromNames(GROUPS[a.group])
    selected={name.split('.')[0] for name in GROUPS[a.group]}
    test_paths=[ROOT/'product/tests'/(name+'.py') for name in sorted(selected)]
    frozen_tests={p.name:sha(p) for p in test_paths}
    (out/'executed-tests').mkdir()
    for p in test_paths:(out/'executed-tests'/p.name).write_bytes(p.read_bytes())
    with (out/'tests.log').open('w',encoding='utf8',newline='\n') as f:
        result=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
    save=lambda name,value:(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    evidence={}
    for name,module in list(sys.modules.items()):
        if name.startswith('test_') or name=='native_float_gpu':
            rows={k:v for k,v in vars(module).items() if k in ('RECEIPTS','NATIVE_CALLS','RENDER_RECEIPTS','ERROR_RECEIPTS')}
            if rows:evidence[name]=rows
    save('receipts.json',evidence)
    test_unchanged=frozen_tests=={p.name:sha(p) for p in test_paths}
    record={'status':'passed' if result.wasSuccessful() and not result.skipped and pins(source)==before and test_unchanged else 'failed',
        'tests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'skipped':len(result.skipped),
        'group':a.group,'modules':GROUPS[a.group],'product_files':before,'frozen_equal':pins(source)==before,
        'installed':str(a.installed) if a.installed else None,'at_utc':datetime.now(timezone.utc).isoformat(),
        'test_files':frozen_tests,'test_frozen_equal':test_unchanged}
    save('verification.json',record)
    print(json.dumps({k:v for k,v in record.items() if k not in ('product_files','test_files')},ensure_ascii=False))
    if record['status']!='passed':print((out/'tests.log').read_text(encoding='utf8')[-11000:]);raise SystemExit(1)
if __name__=='__main__':main()
