"""Publish completed diagnostic media while retaining the actual package failure."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-decision-20261025-r1'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    original = BASE / 'demo-installed-r1'
    output = ROOT / 'docs/assets/semantic-decision-20261025-r1/demo-installed-r1'
    evidence = BASE / 'demo-finalization-r1'
    evidence.mkdir(exist_ok=False)
    (evidence / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    assert not (original / 'verification.json').exists()
    failure = json.loads((original / 'failure.json').read_bytes())
    calls = json.loads((original / 'calls.json').read_bytes())
    error = json.loads((original / '19.stdout.json').read_bytes())
    assert failure['status'] == 'failed' and len(calls) == 19
    assert all(c['exit_code'] == 0 for c in calls[:18]) and calls[18]['exit_code'] != 0
    assert error['errors'][0]['code'] == 'SEMANTIC_INDEX_INVALID'
    assert error['errors'][0]['cause'] == 'Manifest outside project semantic asset tree'
    decoded = [(original / f'decoded-{i}.framemd5').read_bytes() for i in range(2)]
    frames = [[l for l in data.splitlines() if l and not l.startswith(b'#')] for data in decoded]
    assert len(frames[0]) == 360 and frames[0] == frames[1]
    probe = json.loads((original / 'probe.json').read_bytes())
    visual = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    assert int(visual['nb_read_frames']) == 360 and visual['avg_frame_rate'] == '30/1'
    with Image.open(output / 'decisions.gif') as gif:
        durations = []
        for i in range(gif.n_frames):
            gif.seek(i)
            durations.append(gif.info.get('duration', 0))
    assert sum(durations) == 12000 and len(durations) > 1
    shutil.copyfile(ROOT / 'docs/assets/semantic-decision-20261025-r1/SOURCE.json', output / 'SOURCE.json')
    shutil.copyfile(output.parent / 'installed-r1/SOURCE_AND_LICENSES.md', output / 'SOURCE_AND_LICENSES.md')
    (output / 'KNOWN_ISSUE.md').write_text('''# Actual package failure / 工程迁移失败

CLI 0.1.10: six image-card clips export/import/render correctly and all 360
decoded frames match. The separate retrieval project exports, imports and
passes general validate, but its calibrated search dry run fails with
`SEMANTIC_INDEX_INVALID`: `Manifest outside project semantic asset tree`.

The retrieval package is a retained reproduction of this failure, not a
verified portable semantic index/profile. Do not edit fingerprints or trust
the general validator as proof. Explicitly re-register the local adapter,
rebuild the index and recalibrate after moving; this workaround was not
executed as part of this diagnostic. A clean-host migration is not established.

See the original 19 CLI receipts and failure under
`docs/validation/evidence/semantic-decision-20261025-r1/demo-installed-r1/`.
The MP4/GIF are actual silent diagnostic output, not an execution recording or
a natural advertising benchmark. Typography is rasterized in six individually
editable image clips. All three known query mistakes are shown.
''', encoding='utf-8', newline='\n')
    report = dict(status='completed-media-with-known-retrieval-package-failure',
        original_failure_retained=True, original_evidence=original.relative_to(ROOT).as_posix(),
        cli_version='0.1.10', calls=19, successful_calls=18, expected_failure_after_observation=False,
        duration_seconds=12, frames=360, fps='30', dimensions=[960, 540], full_video_decode=True,
        card_package_decoded_pixels_equal=True, retrieval_profile_package_verified_same_host=False,
        retrieval_package_search_error=error['errors'], selected_cards=6, selected_known_errors=3,
        gif_frames=len(durations), gif_duration_ms=sum(durations), gif_sample_fps=5,
        gif_frame_durations_ms=durations, new_model_forwards=0, new_renders=0,
        original_actual_renders=2, human_continuous_viewing=False, human_listening=False,
        natural_action_benchmark=False, card_typography_rasterized=True,
        files=[dict(path=p.relative_to(ROOT).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
               for p in sorted(output.iterdir()) if p.is_file()],
        finished_at_utc=datetime.now(timezone.utc).isoformat())
    data = json.dumps(report, ensure_ascii=False, indent=2) + '\n'
    (evidence / 'verification.json').write_text(data, encoding='utf-8', newline='\n')
    (output / 'verification.json').write_text(data, encoding='utf-8', newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('files','gif_frame_durations_ms')}, ensure_ascii=False))


if __name__ == '__main__':
    main()
