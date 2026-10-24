"""Measure actual music attenuation from delivered PCM mixes and voice stem."""
from pathlib import Path
import argparse
import json
import subprocess
import wave
import numpy as np


def pcm(path):
    with wave.open(str(path), 'rb') as w:
        assert w.getframerate() == 48000 and w.getnchannels() == 2 and w.getsampwidth() == 2
        return np.frombuffer(w.readframes(w.getnframes()), dtype='<i2').reshape(-1, 2).astype(float) / 32768


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    root = args.project.resolve(strict=True)
    audio = root / 'assets/community-audio'
    plain, duck = pcm(audio / 'asset_mix_plain.wav'), pcm(audio / 'asset_mix_duck.wav')
    assert plain.shape == duck.shape
    samples = len(plain)
    ref = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(audio / 'asset_voice_zh.wav'),
                          '-af', f'aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,apad,atrim=end_sample={samples},asetpts=PTS-STARTPTS,alimiter=limit=0.95:level=0:latency=1',
                          '-f', 'f32le', '-acodec', 'pcm_f32le', '-'], capture_output=True, check=True, timeout=90)
    voice = np.frombuffer(ref.stdout, dtype='<f4').reshape(-1, 2)
    assert voice.shape == plain.shape
    music_plain, music_duck = plain - voice, duck - voice
    rows = []
    for start in range(0, samples - 12000 + 1, 12000):
        v = voice[start:start+12000]
        a, b = music_plain[start:start+12000], music_duck[start:start+12000]
        vrms = float(np.sqrt(np.mean(v*v)))
        ar, br = float(np.sqrt(np.mean(a*a))), float(np.sqrt(np.mean(b*b)))
        rows.append(dict(start_seconds=start/48000, voice_rms=vrms, plain_music_rms=ar, ducked_music_rms=br,
                         reduction_db=float(20*np.log10(max(br, 1e-9)/max(ar, 1e-9)))))
    active = [r['reduction_db'] for r in rows if r['voice_rms'] > 0.025 and r['plain_music_rms'] > 0.001]
    assert active and float(np.median(active)) < -2, active
    report = dict(status='passed', method='Subtract the same resampled voice stem from unclipped PCM mixes; 250 ms windows',
                  active_windows=len(active), median_active_music_reduction_db=float(np.median(active)),
                  plain_peak=float(np.abs(plain).max()), ducked_peak=float(np.abs(duck).max()),
                  voice_peak=float(np.abs(voice).max()), limiter_limit=0.95, output_frames=samples,
                  human_listening=False, windows=rows)
    assert report['plain_peak'] < 0.95 and report['ducked_peak'] < 0.95
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8')
    print(json.dumps({k:v for k,v in report.items() if k != 'windows'}), flush=True)


if __name__ == '__main__':
    main()
