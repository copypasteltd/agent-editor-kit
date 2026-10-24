"""Exercise the staged native Kokoro CPU engine; no downloads or installation."""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import sys
import time
import wave


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native', type=Path, required=True)
    parser.add_argument('--numpy-site', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    native = args.native.resolve(strict=True)
    model = native / 'models/kokoro-int8-multi-lang-v1_1'
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    sys.path[:0] = [str(native / 'site'), str(args.numpy_site.resolve(strict=True))]
    dlls = os.add_dll_directory(str(native / 'bin'))
    import numpy as np
    import sherpa_onnx

    # Windows FST readers use narrow paths. Resolve the Unicode directory with
    # Python, then pass only ASCII relative filenames to the native engine.
    os.chdir(model)
    config = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                model='model.int8.onnx', voices='voices.bin', tokens='tokens.txt',
                lexicon='lexicon-zh.txt,lexicon-us-en.txt,lexicon-gb-en.txt'),
            num_threads=2, provider='cpu'),
        rule_fsts='date-zh.fst,number-zh.fst,phone-zh.fst',
        max_num_sentences=1)
    assert config.validate()
    start = time.perf_counter()
    tts = sherpa_onnx.OfflineTts(config)
    loaded = time.perf_counter() - start
    rows = []
    for sid, voice, language, text in [
        (3, 'zf_001', 'zh', '从本地素材开始，生成可编辑的视频。原声、字幕和配乐均可独立调整。'),
        (58, 'zm_009', 'zh', '使用开源素材，保留项目来源。请先预览，再交付最终视频。'),
        (0, 'af_maple', 'en', 'Start with local media and create an editable video. Keep speech, captions, and music on separate tracks.'),
    ]:
        start = time.perf_counter()
        audio = tts.generate(text, sid=sid, speed=1.0)
        samples = np.asarray(audio.samples, dtype=np.float32)
        assert samples.size and np.isfinite(samples).all()
        pcm = (np.clip(samples, -1, 1) * 32767).round().astype('<i2')
        path = output / (voice + '.wav')
        with wave.open(str(path), 'wb') as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(audio.sample_rate)
            wav.writeframes(pcm.tobytes())
        row = dict(voice_id=voice, speaker_id=sid, language=language, text=text,
                   sample_rate=audio.sample_rate, channels=1, samples=int(samples.size),
                   duration_seconds=float(samples.size / audio.sample_rate),
                   peak=float(np.abs(samples).max()), rms=float(np.sqrt(np.mean(samples ** 2))),
                   inference_seconds=time.perf_counter() - start, file=path.name,
                   sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        assert row['rms'] > 0.001 and row['duration_seconds'] > 1
        rows.append(row)
        print(json.dumps(row, ensure_ascii=False), flush=True)
    report = dict(status='passed', checked_at_utc=datetime.now(timezone.utc).isoformat(),
                  engine_version=sherpa_onnx.__version__, provider='cpu',
                  speakers=tts.num_speakers, model_load_seconds=loaded, samples=rows,
                  unicode_directory_with_ascii_relative_native_paths=True,
                  listening_review=False, browser_invoked=False, virtualization_invoked=False)
    (output / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    dlls.close()


if __name__ == '__main__':
    main()
