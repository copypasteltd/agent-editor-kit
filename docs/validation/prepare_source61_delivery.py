"""Derive new CLI61 gates/cases/builder without changing frozen historical tools."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'docs/validation'

def derive(old,new):
    s=(OUT/old).read_text(encoding='utf-8')
    for a,b in [('CLI60','CLI61'),('source60','source61'),('installed60','installed61'),
                ('loop60','loop61'),('0.1.60','0.1.61'),
                ('music-loop-20261029-r1','lipsync-timeout-20261029-r1')]:s=s.replace(a,b)
    return s

def write(name,s):
    p=OUT/name;compile(s,str(p),'exec')
    if p.exists():
        if p.read_text(encoding='utf-8')!=s:
            # Only the not-yet-executed builder may gain stricter gates.
            assert name=='build_source61_delivery.py'
            assert not (ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1/installation-candidate-r1').exists()
            assert not (ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.59').exists()
            p.write_text(s,encoding='utf-8',newline='\n')
    else:p.write_text(s,encoding='utf-8',newline='\n')

def main():
    s=derive('run_music_loop_case.py','run_source61_loop_case.py')
    s=s.replace("BASE/'targeted-r1/verification.json'","BASE/'source61-loop-r1/verification.json'")
    write('run_source61_loop_case.py',s)
    write('run_source61_gpu_case.py',derive('run_source60_gpu_case.py','run_source61_gpu_case.py'))
    write('run_installed61_loop_case.py',derive('run_installed60_loop_case.py','run_installed61_loop_case.py'))
    s=(OUT/'run_native_worker_lipsync_case.py').read_text(encoding='utf-8')
    s=s.replace('CLI57','CLI61').replace('installed57','installed61').replace('0.1.57','0.1.61')
    s=s.replace('native-worker-bootstrap-20261029-r1','lipsync-timeout-20261029-r1')
    s=s.replace("parser.add_argument('--installed', type=Path, required=True)","parser.add_argument('--installed', type=Path)")
    start=s.index('    installed = args.installed.resolve()')
    end=s.index('    protected = ',start)
    s=s[:start]+'''    installed = args.installed.resolve() if args.installed else None
    source = ROOT/'product/src/ai_ad_editor'
    mode='installed61' if installed else 'source61'
    if installed:assert installed.is_relative_to((ROOT/'local/agent-ffmpeg').resolve())
    gate = load(BASE/(mode+'-bootstrap-'+args.gate_run)/'verification.json')
    assert gate['status']=='passed' and gate['cli_version']=='0.1.61' and gate['frozen_equal']
    if installed:
        assert gate['source_and_installed_equal'] and Path(gate['installed']).resolve()==installed
    assert all(sha(ROOT/name)==pin for name,pin in gate['file_hashes'].items())
    package = installed/'site/ai_ad_editor' if installed else source
    pins = {p.name:sha(p) for p in package.glob('*.py')}
    assert len(pins)==283 and pins=={p.name:sha(p) for p in source.glob('*.py')}
'''+s[end:]
    s=s.replace("BASE/('installed61-lipsync-'+args.run)","BASE/(mode+'-lipsync-cuda-'+args.run)")
    s=s.replace("('native-worker-installed61-lipsync-'+args.run)","('native-worker-'+mode+'-lipsync-'+args.run)")
    s=s.replace("prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', installed/'run.py']", "prefix = ([sys.executable,'-I','-S','-B','-u','-X','utf8',installed/'run.py'] if installed else [sys.executable,'-E','-B','-u','-X','utf8',str(ROOT/'scripts/run_source_editor.py')])")
    s=s.replace('installed=str(installed)','installed=str(installed) if installed else None')
    s=s.replace('source_installed_281_modules_frozen_equal=True','source_and_package_283_modules_frozen_equal=True')
    s=s.replace('registered56_namespace_runtime_frozen=True','registered59_namespace_runtime_frozen=True')
    s=s.replace("    ffmpeg = shutil.which('ffmpeg')", "    sys.path.insert(0,str(package.parent))\n    from ai_ad_editor.runtime import configure_local_runtime\n    configure_local_runtime()\n    ffmpeg = shutil.which('ffmpeg')")
    write('run_source61_lipsync_case.py',s)
    s=derive('build_source60_delivery.py','build_source61_delivery.py')
    s=s.replace('v0.1.0-alpha.4-local.58','v0.1.0-alpha.4-local.59')
    s=s.replace("'targeted-r1'","'source61-loop-r1'")
    s=s.replace('(37,31,57,104,400,19)','(37,31,57,104,403,19)')
    s=s.replace("'actual-case-r1','publication-r1']","'actual-case-r1','publication-r1','source61-gpu-r1','source61-lipsync-cuda-r1']")
    needle="    assert gates[6]['registered_skill_unchanged']\n"
    assert needle in s
    s=s.replace(needle,needle+"    assert gates[8]['actual_CUDA_model'] and gates[8]['complete_PCM_replay_equal']\n"
        +"    assert gates[8]['cli_version']=='0.1.61' and gates[8]['frozen_equal']\n"
        +"    assert gates[8]['complete_PCM_bytes']==1124160\n")
    needle="    assert gates[8]['complete_PCM_bytes']==1124160\n"
    s=s.replace(needle,needle+"    assert gates[9]['actual_MuseTalk_CUDA'] and gates[9]['owned_process_cleanup_passed']\n"
        +"    assert gates[9]['complete_package_rendered_RGBA_PCM_equal'] and gates[9]['cli_version']=='0.1.61'\n")
    needle='    gates = [json.loads(p.read_bytes()) for p in gate_paths]\n'
    assert needle in s
    s=s.replace(needle,"    missing=[str(p.relative_to(ROOT)) for p in gate_paths if not p.is_file()]\n"
        +"    if missing:raise SystemExit(json.dumps(dict(status='rejected',reason='missing acceptance gates',missing=missing,skill_activation=False)))\n"+needle)
    write('build_source61_delivery.py',s)
    print('Prepared separate CLI61 source/installed cases and local59 builder; full403 required.',flush=True)

if __name__=='__main__':main()
