"""Check the existing native headless ACE interfaces; does not load weights."""
import argparse
import ast
import inspect
import json
import os
from pathlib import Path
import socket
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]


def main():
    if not sys.flags.isolated or not sys.dont_write_bytecode:
        raise ValueError('Use the native embedded Python with -I -B')
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--runtime-root', type=Path,
                        default=Path('E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/ComfyUI'))
    args = parser.parse_args()
    run = args.run
    if not run.isalnum():
        raise ValueError('Run must be an alphanumeric identifier')
    work = ROOT / f'local/agent-ffmpeg/acestep15-native-probe-{run}'
    work.mkdir()
    proof = ROOT / f'docs/validation/evidence/acestep15-admission-20261029-r1/native-interface-{run}'
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    runtime = args.runtime_root.resolve()
    if not runtime.is_dir() or not (runtime / 'comfy_extras/nodes_ace.py').is_file():
        raise ValueError('An existing native Comfy core is required')
    for key in ('TEMP', 'TMP', 'HF_HOME', 'TORCH_HOME', 'CUDA_CACHE_PATH', 'MPLCONFIGDIR', 'XDG_CACHE_HOME'):
        p = work / key.lower()
        p.mkdir()
        os.environ[key] = str(p)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
    (work / 'empty-models').mkdir()
    def deny(*unused_args, **unused_kwargs):
        raise RuntimeError('NETWORK_FORBIDDEN_IN_NATIVE_INTERFACE_PROBE')
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.socket.bind = deny
    socket.socket.listen = deny
    report = dict(status='failed', native_windows=os.name == 'nt', runtime_root=str(runtime), model_loaded=False,
                  music_generated=False, model_forwards=0, service_started=False, shared_queue_touched=False)
    try:
        sys.path.insert(0, str(runtime))
        options_ast = ast.parse((runtime / 'comfy/cli_args.py').read_bytes())
        offline_flag = any(isinstance(node, ast.Constant) and node.value == '--offline' for node in ast.walk(options_ast))
        sys.argv = ['ace-interface-probe', '--base-directory', str(work), '--models-directory', str(work / 'empty-models')]
        if offline_flag:
            sys.argv.append('--offline')
        report.update(offline_cli_flag_supported=offline_flag, offline_environment=True, network_guard_installed=True,
                      product_cli_legacy_compatibility_accepted=False)
        import comfy.options
        comfy.options.enable_args_parsing()
        import torch
        import comfy.sd
        import comfy.sample
        import comfyui_version
        from comfy_extras.nodes_ace import TextEncodeAceStepAudio15, EmptyAceStep15LatentAudio
        from comfy_extras.nodes_audio import VAEDecodeAudio
        assert torch.cuda.is_available()
        signatures = {node.__name__:str(inspect.signature(node.execute)) for node in (TextEncodeAceStepAudio15, EmptyAceStep15LatentAudio, VAEDecodeAudio)}
        latent = EmptyAceStep15LatentAudio.execute(10, 1)[0]['samples']
        assert tuple(latent.shape) == (1, 64, 250)
        sys.path.insert(0, str(ROOT / 'product/src'))
        from ai_ad_editor.local_music_generation import runtime_files
        inventory = {p.resolve() for p in runtime_files(runtime)}
        loaded = sorted({Path(module.__file__).resolve() for module in list(sys.modules.values())
                         if getattr(module, '__file__', None) and Path(module.__file__).resolve().is_relative_to(runtime)})
        outside = [str(p.relative_to(runtime)) for p in loaded if p not in inventory]
        report.update(status='passed' if not outside else 'failed', python=sys.version.split()[0], executable=sys.executable,
                      torch=torch.__version__, cuda=torch.version.cuda, device=torch.cuda.get_device_name(0),
                      comfy_version=comfyui_version.__version__, signatures=signatures, latent_shape=list(latent.shape),
                      inventory_files=len(inventory), imported_runtime_files=len(loaded), outside_inventory=outside)
    except BaseException as exc:
        report.update(error=repr(exc), traceback=traceback.format_exc())
    (proof / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
