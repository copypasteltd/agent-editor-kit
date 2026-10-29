"""Read actual BF16 tensor fixtures with the native library; no model inference."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum() and sys.flags.isolated and sys.dont_write_bytecode
    proof = ROOT / 'docs/validation/evidence/music-loading-20261030-r1' / ('native-reader-' + args.run)
    proof.mkdir(parents=True)
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work = ROOT / 'local/agent-ffmpeg' / ('music65-reader-probe-' + args.run)
    work.mkdir()
    for name in ('TEMP', 'TMP', 'HF_HOME', 'TORCH_HOME', 'MPLCONFIGDIR', 'CUDA_CACHE_PATH'):
        directory = work / name.lower()
        directory.mkdir()
        os.environ[name] = str(directory)
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', PYTHONDONTWRITEBYTECODE='1')
    sys.path.insert(0, str(ROOT / 'product/src'))
    from ai_ad_editor.rvm_worker import install_network_guard
    from ai_ad_editor.music_generation_model import WEIGHT_NAMES, weight_reader, validate_weight_reads
    events = []
    install_network_guard(events)
    report = dict(status='failed', executable=sys.executable, fixture_only=True,
        model_loaded=False, music_generated=False, neural_forwards=0, network_events=events)
    started = time.monotonic()
    try:
        import torch
        import safetensors
        import safetensors.torch
        import_seconds = time.monotonic() - started
        expected = torch.arange(16, dtype=torch.float32).reshape(4, 4).to(dtype=torch.bfloat16)
        native = safetensors.safe_open
        reads = []
        for name in sorted(WEIGHT_NAMES):
            path = work / name
            safetensors.torch.save_file({'reference': expected}, str(path), metadata={'fixture': name})
            with weight_reader(work, (name,), read_report=reads):
                with safetensors.safe_open(str(path), framework='pt', device='cpu') as stream:
                    assert stream.keys() == ['reference']
                    actual = stream.get_tensor('reference')
                    assert actual.dtype == torch.bfloat16 and torch.equal(actual, expected)
                    assert stream.metadata() == {'fixture': name}
            assert safetensors.safe_open is native
        validate_weight_reads(reads)
        assert not events
        report.update(status='passed', torch=torch.__version__, safetensors=safetensors.__version__,
            actual_BF16_tensor_values_equal=True, actual_metadata_equal=True, reader_restored=True,
            local_weight_reads=reads, import_seconds=import_seconds,
            model_helper_sha256=sha(ROOT / 'product/src/ai_ad_editor/music_generation_model.py'))
    except BaseException as exc:
        report.update(error=repr(exc), traceback=traceback.format_exc())
    report['elapsed_seconds'] = time.monotonic() - started
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
