"""Prepare real registered CLI61 entry cases and r58 independent delivery checks.

Preparation never activates a Skill. Each generated runner checks completed
activation and installed contracts before creating its case directory.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation'


def replace(text, old, new, count=None):
    assert old in text, old
    return text.replace(old, new) if count is None else text.replace(old, new, count)


def write(name, text):
    path = BASE/name
    assert not path.exists(), path
    compile(text, str(path), 'exec')
    path.write_text(text, encoding='utf-8', newline='\n')


def registered(text, argument):
    text = replace(text, f'    skill={argument}.skill.resolve()', f'''    skill=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert {argument}.skill==skill and skill.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    activation=load(BASE/'skill61-activation-r1/verification.json')
    assert activation['status']=='activated-and-entry-verified'
    contracts=load(BASE/'installed61-contracts-r1/verification.json')
    assert contracts['status']=='passed' and contracts['tests']==403 and contracts['frozen_equal']
    assert Path(contracts['installed']).resolve()==installed
    assert sha(ROOT/'agent-ffmpeg-local-install-manifest.json')==activation['namespace_sha256']
    assert sha(ROOT/'local/agent-ffmpeg/runtime.json')==activation['runtime_sha256']''')
    text = text.replace("    assert skill.is_relative_to((ROOT/'local/agent-ffmpeg').resolve())\n", '')
    text = replace(text, "stage=load(skill.parents[1]/'STAGING.json')",
                   "stage=load(ROOT/'local/agent-ffmpeg/music61-skill-stage-r1/STAGING.json')")
    text = replace(text, 'candidate_registered=False,',
                   'candidate_registered=True,actual_C_drive_entry=True,activated=True,')
    text = text.replace("registered_skill_cli='0.1.59'", "registered_skill_cli='0.1.61'")
    text = text.replace('registered59_namespace_runtime_frozen=True', 'registered61_namespace_runtime_frozen=True')
    text = text.replace('live_skill_activation=False', 'live_skill_activation=True')
    return text


def main():
    text = registered((BASE/'run_staged61_loop_case.py').read_text(encoding='utf-8'), 'a')
    text = replace(text, 'music-loop61-staged-case-', 'music-loop61-registered-case-')
    text = replace(text, "('staged-actual-case-'+a.run)", "('registered-actual-case-'+a.run)")
    text = replace(text, "assert manifest['cli_version']=='0.1.59'", "assert manifest['cli_version']=='0.1.61'")
    write('run_registered61_loop_case.py', text)

    text = registered((BASE/'run_staged61_gpu_case.py').read_text(encoding='utf-8'), 'args')
    text = replace(text, "mode = 'staged61'", "mode = 'registered61'")
    text = replace(text, "BASE/'staged-actual-case-r1/verification.json'", "BASE/'registered-actual-case-r1/verification.json'")
    write('run_registered61_gpu_case.py', text)

    text = registered((BASE/'run_staged61_lipsync_case.py').read_text(encoding='utf-8'), 'args')
    text = replace(text, "mode='staged61'", "mode='registered61'")
    write('run_registered61_lipsync_case.py', text)

    text = (BASE/'build_source60_final_kit.py').read_text(encoding='utf-8')
    text = text.replace('CLI60', 'CLI61').replace('0.1.60', '0.1.61')
    text = text.replace('music-loop-20261029-r1', 'lipsync-timeout-20261029-r1')
    text = text.replace('skill60', 'skill61').replace('registered60', 'registered61').replace('music60', 'music61')
    text = replace(text, "    out = BASE/('formal-kit-build-'+args.run)", '''    loop=load(BASE/'registered-actual-case-r1/verification.json')
    assert loop['status']=='passed' and loop['actual_C_drive_entry'] and loop['actual_PowerShell_entry']
    assert loop['complete_package_recipe_repair_PCM_equal'] and loop['complete_repaired_PCM_bytes']==2557440
    lipsync=load(BASE/'registered61-lipsync-cuda-r1/verification.json')
    assert lipsync['status']=='passed' and lipsync['cli_version']=='0.1.61'
    for flag in ['actual_C_drive_entry','actual_PowerShell_entry','actual_MuseTalk_CUDA',
                 'complete_source_installed_master_and_render_equal',
                 'complete_package_rendered_RGBA_PCM_equal','owned_process_cleanup_passed']:
        assert lipsync[flag] is True,flag
    assert lipsync['frames']==133 and lipsync['complete_master_RGBA_bytes']==139460608
    assert not lipsync['model_execution']['CPU_fallback']
    out = BASE/('formal-kit-build-'+args.run)''')
    text = replace(text, 'actual_registered_GPU_case_accepted=True,',
                   'actual_registered_GPU_case_accepted=True,actual_registered_loop_case_accepted=True,actual_registered_MuseTalk_case_accepted=True,')
    write('build_source61_final_kit.py', text)

    text = (BASE/'verify_source60_final_kit.py').read_text(encoding='utf-8')
    text = text.replace('CLI60', 'CLI61').replace('0.1.60', '0.1.61').replace('music60', 'music61')
    text = text.replace('music-loop-20261029-r1', 'lipsync-timeout-20261029-r1')
    write('verify_source61_final_kit.py', text)
    print('Prepared CLI61 registered loop/DF3/MuseTalk checks and independent r58 package checks; no activation performed.')


if __name__ == '__main__':
    main()
