"""Read-only native YuE2 interface probe; never a music-generation acceptance test."""
import argparse
import hashlib
import inspect
import json
import os
from pathlib import Path
import socket
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--comfy-root', type=Path, default=Path('E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/ComfyUI'))
    parser.add_argument('--checkpoint', type=Path, default=Path('E:/dev/sandbox/模型配乐/models/checkpoints/yue2_3b_int8_convrot.safetensors'))
    args = parser.parse_args()
    assert sys.dont_write_bytecode and sys.flags.isolated
    work, output = args.work.resolve(), args.output.resolve()
    assert work.is_relative_to((ROOT/'local/agent-ffmpeg').resolve())
    assert output.is_relative_to((ROOT/'docs/validation/evidence').resolve())
    assert not work.exists() and not output.exists()
    assert args.comfy_root.is_dir() and args.checkpoint.is_file()
    work.mkdir(parents=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    for name in ['input', 'output', 'temp', 'user', 'hf', 'torch', 'cuda', 'mpl']:
        (work/name).mkdir()
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_DATASETS_OFFLINE='1',
                      HF_HOME=str(work/'hf'), TORCH_HOME=str(work/'torch'),
                      CUDA_CACHE_PATH=str(work/'cuda'), MPLCONFIGDIR=str(work/'mpl'),
                      TEMP=str(work/'temp'), TMP=str(work/'temp'), PYTHONDONTWRITEBYTECODE='1')

    def deny_connect(*unused_args, **unused_kwargs):
        raise RuntimeError('Network socket connections are forbidden in the native interface probe')

    socket.socket.connect = deny_connect
    socket.socket.connect_ex = deny_connect
    report = dict(status='failed', scope='native-import-and-interface-only',
                  music_generated=False, model_loaded=False, model_forwards=0,
                  model_weight_sha256_verified=False, commercial_backend_admitted=False,
                  product_cli_integrated=False, service_started=False, shared_queue_touched=False,
                  native_windows=os.name == 'nt', virtual_environment=False,
                  python_socket_connections_denied=True,
                  model_license='CC-BY-NC-4.0',
                  license_sources=['https://huggingface.co/m-a-p/YuE2-3B/raw/main/LICENSE',
                                   'https://huggingface.co/Comfy-Org/YuE2/raw/main/README.md'])
    try:
        sys.path.insert(0, str(args.comfy_root.resolve()))
        sys.argv = ['native-yue2-interface-probe', '--base-directory', str(work),
                    '--models-directory', str(args.checkpoint.parent.parent.resolve()), '--offline']
        import comfy.options
        comfy.options.enable_args_parsing()
        import torch
        import comfy.sd
        import comfy.sample
        import folder_paths
        from comfy_extras.nodes_yue2 import YuE2GenerateMusic, EmptyYuE2LatentAudio
        from comfy_extras.nodes_audio import VAEDecodeAudio
        assert torch.cuda.is_available(), 'CUDA is required; no silent CPU fallback'
        nodes = [YuE2GenerateMusic, EmptyYuE2LatentAudio, VAEDecodeAudio]
        for node in nodes:
            assert callable(node.execute) and callable(node.define_schema)
            assert Path(inspect.getfile(node)).resolve().is_relative_to(args.comfy_root.resolve())
        assert Path(folder_paths.input_directory).resolve() == work/'input'
        assert Path(folder_paths.output_directory).resolve() == work/'output'
        files = ['comfy_extras/nodes_yue2.py', 'comfy_extras/nodes_audio.py',
                 'comfy/sd.py', 'comfy/sample.py', 'comfy/text_encoders/yue2.py']
        report.update(status='passed', python=sys.version.split()[0], executable=sys.executable,
                      torch=torch.__version__, cuda=torch.version.cuda,
                      device=torch.cuda.get_device_name(0),
                      checkpoint_bytes=args.checkpoint.stat().st_size,
                      checkpoint=str(args.checkpoint.resolve()),
                      node_signatures={n.__name__:str(inspect.signature(n.execute)) for n in nodes},
                      checkpoint_loader_signature=str(inspect.signature(comfy.sd.load_checkpoint_guess_config)),
                      code_hashes={n:hashlib.sha256((args.comfy_root/n).read_bytes()).hexdigest() for n in files})
    except BaseException as error:
        report['error'] = repr(error)
        traceback.print_exc()
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
