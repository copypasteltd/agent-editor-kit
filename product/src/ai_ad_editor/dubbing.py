"""Strict cue clocks and bounded, whole-utterance Kokoro batch generation."""
from __future__ import annotations

import math
from pathlib import Path
import re
import wave

SAMPLE_RATE = 24000
MAX_SAMPLES = SAMPLE_RATE * 300
MAX_ATTEMPTS = 3
TIME = r'(\d{2}):([0-5]\d):([0-5]\d)[,.](\d{3})'
TIMING = re.compile(TIME + r'\s+-->\s+' + TIME)


def parse_srt(text):
    """Refuse skipped blocks and preserve source order/IDs and integer milliseconds."""
    text = text.lstrip('\ufeff').replace('\r\n', '\n').replace('\r', '\n').strip()
    if not text:
        raise ValueError('Empty SRT')
    result, seen = [], set()
    for block in re.split(r'\n[ \t]*\n', text):
        lines = block.splitlines()
        if len(lines) < 3 or not re.fullmatch(r'[0-9]+', lines[0].strip()):
            raise ValueError('Every SRT block requires a numeric ID, timing and text')
        ident = lines[0].strip()
        canonical_id = str(int(ident))
        match = TIMING.fullmatch(lines[1].strip())
        body = '\n'.join(lines[2:]).strip()
        if canonical_id in seen or not match or not body or len(body) > 3000:
            raise ValueError('Duplicate cue ID, invalid timing, empty or oversized cue')
        if re.search(r'<[^>]*>|\{\\|-->', body) or any(ord(c) < 32 and c not in '\n\t' for c in body):
            raise ValueError('Use plain SRT text without markup, controls or timing directives')
        numbers = [int(value) for value in match.groups()]
        start, end = [((h*60+m)*60+s)*1000+ms for h,m,s,ms in (numbers[:4], numbers[4:])]
        if not 0 <= start < end <= 86400000:
            raise ValueError('Cue times must be positive windows within 24 hours')
        result.append(dict(index=len(result)+1, source_id=ident, start_ms=start, end_ms=end,
            start=start/1000, end=end/1000, text=body, slot_samples=(end-start)*24))
        seen.add(canonical_id)
    if not 1 <= len(result) <= 1000:
        raise ValueError('Expected 1–1000 cues')
    return result


def next_speed(speed, samples, slot_samples, maximum):
    return min(maximum, speed * samples / slot_samples * 1.03)


def inspect_wave(path):
    import numpy as np
    with wave.open(str(path), 'rb') as audio:
        frames = audio.getnframes()
        if (audio.getnchannels(), audio.getsampwidth(), audio.getframerate(), audio.getcomptype()) != (1,2,SAMPLE_RATE,'NONE'):
            raise ValueError('Expected mono 24kHz PCM16 WAV')
        if not 0 < frames <= MAX_SAMPLES:
            raise ValueError('Voice output exceeds the 300-second cue budget or is empty')
        raw = audio.readframes(frames)
        if len(raw) != frames*2 or audio.readframes(1):
            raise ValueError('WAV frame count disagrees with actual PCM')
    pcm = np.frombuffer(raw, dtype='<i2').astype(np.float64) / 32768
    rms = float(np.sqrt(np.mean(pcm*pcm)))
    if not math.isfinite(rms) or rms <= 0.0001:
        raise ValueError('Voice output is silent or invalid')
    return dict(samples=frames, sample_rate=SAMPLE_RATE, channels=1, duration_seconds=frames/SAMPLE_RATE,
        peak=float(np.abs(pcm).max()), rms=rms)


def synthesize_segments(engine, payload):
    """The caller creates one engine; retries regenerate the complete unchanged text."""
    import numpy as np
    import time
    segments = []
    for spec in payload['segments']:
        speed, attempts = float(payload['speed']), []
        directory = Path(spec['output_directory'])
        directory.mkdir(parents=True, exist_ok=False)
        for index in range(MAX_ATTEMPTS):
            started = time.perf_counter()
            audio = engine.generate(spec['text'], sid=spec['speaker_id'], speed=speed)
            samples = np.asarray(audio.samples, dtype=np.float32)
            if audio.sample_rate != SAMPLE_RATE or samples.ndim != 1 or not 0 < samples.size <= MAX_SAMPLES or not np.isfinite(samples).all():
                raise ValueError('Invalid or oversized batch speech output')
            pcm = (np.clip(samples, -1, 1)*32767).round().astype('<i2')
            output = directory / f'attempt-{index+1}.wav'
            with output.open('xb') as stream:
                with wave.open(stream, 'wb') as wav:
                    wav.setnchannels(1)
                    wav.setsampwidth(2)
                    wav.setframerate(SAMPLE_RATE)
                    wav.writeframes(pcm.tobytes())
            measured = inspect_wave(output)
            attempts.append(dict(output=str(output), speed=speed, generation_seconds=time.perf_counter()-started,
                clipped_float_samples=int(np.count_nonzero(np.abs(samples)>1)), **measured))
            if measured['samples'] <= spec['slot_samples'] or payload['fit'] == 'reject' or speed >= payload['max_speed']:
                break
            speed = next_speed(speed, measured['samples'], spec['slot_samples'], payload['max_speed'])
        fits = attempts[-1]['samples'] <= spec['slot_samples']
        segments.append(dict(cue_index=spec['cue_index'], voice_id=spec['voice_id'], speaker_id=spec['speaker_id'],
            slot_samples=spec['slot_samples'], attempts=attempts, final_attempt=len(attempts)-1,
            fit_status='fits' if fits else 'overflow'))
        if not fits:
            break
    return dict(segments=segments, processed_cues=len(segments), requested_cues=len(payload['segments']),
        fit_status='fits' if len(segments)==len(payload['segments']) and all(s['fit_status']=='fits' for s in segments) else 'overflow',
        model_initializations=1, total_generations=sum(len(s['attempts']) for s in segments),
        time_fit='complete_utterance_regeneration', truncation=False)
