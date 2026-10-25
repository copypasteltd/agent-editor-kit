"""Freeze new authored audio before candidate execution; no phonetic-truth claim."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import shutil
import subprocess
import wave

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/assets/ctc-activity-20261025-r1/input'
WORDS = 'SHARP BRIGHT CAMERA FOLLOWS QUIET PEOPLE THROUGH WINTER'.split()
GAPS = [4320, 1280, 3040, 4960, 1920, 7360, 3680, 5920]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def wav(path, signal):
    with wave.open(str(path), 'wb') as stream:
        stream.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
        stream.writeframes(signal.astype('<i2').tobytes())


def main():
    assert not OUT.exists()
    OUT.mkdir(parents=True)
    ffmpeg = shutil.which('ffmpeg')
    assert ffmpeg
    pieces, references, sources, cursor = [], [], [], 0
    for word, gap in zip(WORDS, GAPS):
        path = OUT / (word.lower() + '-awb-raw.wav')
        command = [ffmpeg, '-v', 'error', '-nostdin', '-n', '-f', 'lavfi', '-i',
                   'flite=text=' + word.lower() + ':voice=awb', '-ar', '16000', '-ac', '1', '-c:a', 'pcm_s16le', str(path)]
        subprocess.run(command, check=True, capture_output=True, timeout=60)
        with wave.open(str(path), 'rb') as stream:
            signal = np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2')
        active = np.flatnonzero(np.abs(signal.astype(np.int32)) >= 32)
        assert len(active)
        a, b = int(active[0]), int(active[-1]) + 1
        pieces.extend([np.zeros(gap, dtype='<i2'), signal[a:b]])
        cursor += gap
        references.append(dict(word=word, start_sample=cursor, end_sample=cursor + b - a))
        cursor += b - a
        sources.append(dict(word=word, raw=path.name, sha256=sha(path), trim_start=a, trim_end=b, command=command))
    pieces.append(np.zeros(4640, dtype='<i2'))
    clean = np.concatenate(pieces)
    wav(OUT / 'input.wav', clean)
    background = clean.astype(np.int32) + 173 + np.where(np.arange(len(clean)) % 2, 5, -5)
    assert background.min() >= -32768 and background.max() <= 32767
    wav(OUT / 'input-dc-background.wav', background)
    (OUT / 'transcript.txt').write_text(' '.join(WORDS), encoding='utf-8')
    contract = ROOT / 'docs/specs/CTC声学活动边界契约_20261025.md'
    record = dict(format='ctc-activity-authored-blocks-v1', created_at_utc=datetime.now(timezone.utc).isoformat(),
        frozen_before_candidate_execution=True, sample_rate=16000, samples=len(clean), words=references,
        gaps_before_words_samples=GAPS, trailing_gap_samples=4640, voice='awb',
        reference='authored placement of abs>=32 trimmed word blocks; not phonetic labels or human annotations',
        boundary_error_seconds_max=2/30, background=dict(dc=173, alternating_amplitude=5, seed=None),
        original_word_sources=sources, contract_sha256=sha(contract), generator_sha256=sha(Path(__file__)),
        rights=dict(authored_text_and_placement='CC0-1.0',
                    speech='installed FFmpeg flite AWB; retain upstream voice copyright/license separately; not blanket CC0',
                    voice_clone=False),
        files={p.name:dict(bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(OUT.iterdir())})
    (OUT / 'input-provenance.json').write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    (OUT / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps(dict(words=len(WORDS), samples=len(clean), seconds=len(clean)/16000,
                          background_also_frozen=True, no_candidate_executed=True)))


if __name__ == '__main__':
    main()
