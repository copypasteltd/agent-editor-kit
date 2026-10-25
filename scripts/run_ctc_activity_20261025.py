"""Actual native model inference with frozen inputs and independent post-run scoring."""
from __future__ import annotations
import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
NATIVE = Path('D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe')


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('site', 'output', 'project-base'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--runner', type=Path)
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    parser.add_argument('--cases', nargs='+', choices=('original', 'heldout', 'awb', 'background', 'kal', 'kal16'),
                        default=['original', 'heldout', 'awb', 'background', 'kal', 'kal16'])
    args = parser.parse_args()
    site, output, base = args.site.resolve(strict=True), args.output.resolve(), args.project_base.resolve()
    assert output.is_relative_to(ROOT / 'docs/validation/evidence') and not output.exists()
    assert base.is_relative_to(ROOT / 'local/agent-ffmpeg') and not base.exists()
    output.mkdir(parents=True)
    base.mkdir(parents=True)
    sys.path.insert(0, str(site))
    from ai_ad_editor.cli import main as cli_main
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    fixtures = dict(original=('ctc-alignment-20261018', 'input.wav'),
                    heldout=('boundary-heldout-20261018', 'input.wav'),
                    awb=('ctc-activity-20261025-r1/input', 'input.wav'),
                    background=('ctc-activity-20261025-r1/input', 'input-dc-background.wav'),
                    kal=('ctc-activity-20261025-r1/holdout-kal', 'input.wav'),
                    kal16=('ctc-activity-20261025-r1/holdout-kal16', 'input.wav'))
    inputs = {name:ROOT / 'docs/assets' / fixtures[name][0] for name in args.cases}
    contract = ROOT / 'docs/specs/CTC声学活动边界契约_20261025.md'
    frozen_paths = sorted((site / 'ai_ad_editor').glob('*.py')) + [contract, Path(__file__)]
    for name, folder in inputs.items():
        frozen_paths.extend(folder / filename for filename in (fixtures[name][1], 'transcript.txt', 'input-provenance.json'))
    frozen_paths = sorted(set(frozen_paths))
    def frozen():
        return [dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path)) for path in frozen_paths]
    before = frozen()
    state = dict(status='running', started_at_utc=datetime.now(timezone.utc).isoformat(),
                 site=str(site), runner=str(args.runner) if args.runner else 'explicit development CLI',
                 frozen_before=before, native_windows=True, virtualization=False,
                 algorithm_reads_authored_reference=False, cases=[])
    (output / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    save(output / 'state.json', state)
    calls = []
    def cli(*argv):
        argv = list(map(str, argv))
        started = time.monotonic()
        if args.runner:
            result = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                     str(args.runner.resolve()), *argv], cwd=ROOT, capture_output=True, timeout=900)
            code, raw, err = result.returncode, result.stdout.decode('utf-8-sig'), result.stderr.decode('utf-8', errors='replace')
        else:
            out, errors = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(errors):
                code = cli_main(argv)
            raw, err = out.getvalue(), errors.getvalue()
        value = json.loads(raw)
        row = dict(argv=argv, exit_code=code, seconds=round(time.monotonic()-started,3), stderr=err, result=value)
        calls.append(row)
        save(output / 'cli' / f'{len(calls):03}.json', row)
        print(json.dumps(dict(call=len(calls), command=value.get('command'), code=code, seconds=row['seconds'])), flush=True)
        assert code == 0 and value['ok'], value
        return value
    try:
        for name in args.cases:
            folder, project = inputs[name], base / name
            cli('project','init',project)
            cli('asr','adapter','register','--project',project,'--adapter-id','ctc',
                '--engine','transformers-wav2vec2-ctc-local-v1','--python-executable',NATIVE,
                '--model-path',ROOT/'product/.runtime/models/ctc-en-runtime','--device',args.device,'--threads','4',
                '--evidence',ROOT/'docs/validation/evidence/ctc-model-conversion-20261018/en-runtime.json',
                '--license-spdx','Apache-2.0','--creator','upstream model authors')
            cli('media','ingest','--project',project,'--asset-id','speech','--input',folder/fixtures[name][1])
            command = ['subtitle','align','--project',project,'--asset-id','speech','--adapter-id','ctc',
                       '--transcript',folder/'transcript.txt','--output','assets/alignment/activity.json',
                       '--granularity','whitespace','--boundary-mode','activity','--timeout','600']
            cli(*command,'--dry-run')
            result = cli(*command)['data']['result']
            assert result['boundary_mode'] == 'activity' and result['worker']['blocked_network_events'] == []
            assert result['worker']['model_forward_calls'] == 1
            cli('validate','--project',project)
            save(output / (name + '-alignment.json'), result)
            # Only the independent scorer reads authored positions, after inference and controller validation.
            truth = json.loads((folder / 'input-provenance.json').read_text('utf-8'))
            segment = result['segments'][0]
            scores = {}
            for mode, units in (('raw_ctc',segment['raw_units']),('activity',segment['units'])):
                assert len(units) == len(truth['words'])
                words = []
                for actual, reference in zip(units, truth['words']):
                    assert actual['text'] == reference['word']
                    a, b = actual['start_sample'] - reference['start_sample'], actual['end_sample'] - reference['end_sample']
                    words.append(dict(word=actual['text'], start_error_samples=a, end_error_samples=b,
                                      start_error_ms=a/16, end_error_ms=b/16,
                                      passed=max(abs(a),abs(b))*30 <= 2*16000))
                maximum = max(abs(w[k]) for w in words for k in ('start_error_samples','end_error_samples'))
                scores[mode] = dict(max_error_samples=maximum,max_error_ms=maximum/16,
                                    passed=all(w['passed'] for w in words),words=words)
            row = dict(fixture=name, project=str(project), reference='authored word blocks, not phonetic truth',
                       immutable_threshold_seconds=2/30, quality=scores,
                       activity=segment['activity'], model_forward_calls=result['worker']['model_forward_calls'],
                       actual_device=result['worker']['device'], peak_cuda_bytes=result['worker']['peak_cuda_bytes'],
                       input_sha256=sha(folder/fixtures[name][1]), reference_sha256=sha(folder/'input-provenance.json'))
            state['cases'].append(row)
            save(output / (name + '-quality.json'), row)
            save(output / 'state.json',state)
            print(json.dumps(dict(fixture=name,raw_ms=scores['raw_ctc']['max_error_ms'],
                                  activity_ms=scores['activity']['max_error_ms'],passed=scores['activity']['passed'])),flush=True)
        state.update(status='executed',frozen_after=frozen(),cli_calls=len(calls),
                     model_forward_calls=sum(row['model_forward_calls'] for row in state['cases']),
                     all_activity_gates_passed=all(row['quality']['activity']['passed'] for row in state['cases']),
                     new_renders=0,human_listening=False,full_G15_closed=False)
        state['frozen_equal'] = before == state['frozen_after']
        assert state['frozen_equal']
    except BaseException as exc:
        state.update(status='failed',error=repr(exc),cli_calls=len(calls),frozen_after=frozen())
        raise
    finally:
        save(output / 'state.json',state)


if __name__ == '__main__':
    main()
