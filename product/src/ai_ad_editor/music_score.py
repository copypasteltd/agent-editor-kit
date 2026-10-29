"""Editable, deterministic, weight-free music/SFX synthesis for agents.

This is an analytical CPU synthesizer, not a text-to-music neural model.
"""
from __future__ import annotations

import contextlib
import copy
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import shutil
import time
import wave

import numpy as np

from .errors import AppError, argument_error
from .execution_control import checkpoint
from .material_project import append_audio, commit_asset, new_asset_id
from .media import probe_media
from .utils import assert_id, atomic_write_json, ensure_inside, now_iso, sha256_file

ENGINE = 'agent-editable-score-cpu-v1'
RATE = 48000
INSTRUMENTS = ('sine', 'pluck', 'bell', 'pad', 'kick', 'snare', 'hihat', 'sweep')
EFFECTS = ('whoosh', 'riser', 'impact', 'chime')


def effect_score(preset, duration, seed=0, pitch=60):
    if preset not in EFFECTS:
        raise argument_error('Unknown procedural effect', 'preset')
    number(duration, 'duration_seconds', .01, 60)
    beats = duration*2
    voices = {'whoosh':['sweep'], 'riser':['sweep', 'pad'], 'impact':['kick', 'snare'], 'chime':['bell']}[preset]
    return dict(format='agent-music-score-v1', tempo_bpm=120, duration_beats=beats, seed=seed,
                master_gain_db=-6, tracks=[dict(id=f'fx_{i}', instrument=voice, gain_db=-12,
                    notes=[dict(id='effect', start_beat=0, duration_beats=beats, pitch=pitch,
                                velocity=.8)]) for i, voice in enumerate(voices)])


def number(value, name, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or not low <= value <= high:
        raise argument_error(f'{name} requires a finite number in [{low}, {high}]', name)
    return value


def fields(value, allowed, name):
    if not isinstance(value, dict) or set(value)-set(allowed):
        raise argument_error('Unknown fields or non-object '+name, name)


def samples(beats, bpm):
    return round(Fraction(str(beats))*60*RATE/Fraction(str(bpm)))


def prepare(payload):
    fields(payload, ['format', 'tempo_bpm', 'duration_beats', 'seed', 'master_gain_db', 'limiter', 'tracks'], 'score')
    if payload.get('format') != 'agent-music-score-v1':
        raise argument_error('Expected agent-music-score-v1', 'format')
    bpm = number(payload.get('tempo_bpm'), 'tempo_bpm', 20, 300)
    duration = number(payload.get('duration_beats'), 'duration_beats', .0001, 3000)
    seed = payload.get('seed', 0)
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 0xffffffff:
        raise argument_error('seed requires an unsigned32 integer', 'seed')
    gain = number(payload.get('master_gain_db', -6), 'master_gain_db', -60, 0)
    limiter = payload.get('limiter', 'none')
    if limiter not in ['none', 'tanh']:
        raise argument_error('limiter requires none or explicit tanh', 'limiter')
    frames = samples(duration, bpm)
    if not 1 <= frames <= RATE*600:
        raise argument_error('Score must span one sample to600 seconds', 'duration_beats')
    tracks = payload.get('tracks')
    if not isinstance(tracks, list) or not 1 <= len(tracks) <= 16:
        raise argument_error('Score needs1–16 tracks', 'tracks')
    clean, compiled, track_ids, total_notes, work_samples = [], [], set(), 0, 0
    for track in tracks:
        fields(track, ['id', 'instrument', 'gain_db', 'pan', 'notes'], 'track')
        ident = track.get('id')
        if not isinstance(ident, str):
            raise argument_error('track.id requires a string', 'track.id')
        assert_id(ident, 'track.id')
        if ident in track_ids:
            raise argument_error('Duplicate track.id', 'track.id')
        track_ids.add(ident)
        instrument = track.get('instrument')
        if instrument not in INSTRUMENTS:
            raise argument_error('Unknown analytical instrument', 'instrument')
        track_gain = number(track.get('gain_db', -12), 'gain_db', -60, 0)
        pan = number(track.get('pan', 0), 'pan', -1, 1)
        notes = track.get('notes')
        if not isinstance(notes, list) or not 1 <= len(notes) <= 512:
            raise argument_error('Each track needs1–512 notes', 'notes')
        note_ids, normalized_notes, events = set(), [], []
        for note in notes:
            fields(note, ['id', 'start_beat', 'duration_beats', 'pitch', 'velocity'], 'note')
            nid = note.get('id')
            if not isinstance(nid, str):
                raise argument_error('note.id requires a string', 'note.id')
            assert_id(nid, 'note.id')
            if nid in note_ids:
                raise argument_error('Duplicate note.id in track', 'note.id')
            note_ids.add(nid)
            start = number(note.get('start_beat'), 'start_beat', 0, duration)
            length = number(note.get('duration_beats'), 'note.duration_beats', .000001, duration)
            pitch = note.get('pitch', 60)
            if isinstance(pitch, bool) or not isinstance(pitch, int) or not 21 <= pitch <= 108:
                raise argument_error('pitch requires integer MIDI21–108', 'pitch')
            velocity = number(note.get('velocity', .7), 'velocity', 0, 1)
            end_beat = Fraction(str(start))+Fraction(str(length))
            first, end = samples(start, bpm), round(end_beat*60*RATE/Fraction(str(bpm)))
            if end_beat > Fraction(str(duration)) or not first < end <= frames:
                raise argument_error('Every note must occupy at least one sample inside the score', 'note')
            fingerprint = f'{seed}:{ident}:{nid}'.encode('utf-8')
            events.append(dict(id=nid, first=first, end=end, pitch=pitch, velocity=velocity,
                               seed=int.from_bytes(hashlib.sha256(fingerprint).digest()[:4], 'little')))
            normalized_notes.append(dict(id=nid, start_beat=start, duration_beats=length, pitch=pitch, velocity=velocity))
            work_samples += end-first
        total_notes += len(notes)
        clean.append(dict(id=ident, instrument=instrument, gain_db=track_gain, pan=pan,
                          notes=sorted(normalized_notes, key=lambda n:n['id'])))
        compiled.append(dict(id=ident, instrument=instrument, gain=10**(track_gain/20),
                             left=math.cos((pan+1)*math.pi/4), right=math.sin((pan+1)*math.pi/4),
                             events=sorted(events, key=lambda n:n['id'])))
    if total_notes > 2048 or work_samples > RATE*1800:
        raise argument_error('Score exceeds2048 notes or1800 note-seconds', 'tracks')
    canonical = dict(format='agent-music-score-v1', tempo_bpm=bpm, duration_beats=duration,
                     seed=seed, master_gain_db=gain, limiter=limiter, tracks=sorted(clean, key=lambda t:t['id']))
    return canonical, dict(frames=frames, tracks=sorted(compiled, key=lambda t:t['id']),
                          master_gain=10**(gain/20), notes=total_notes, note_samples=work_samples)


def noise(indices, seed):
    # Stateless counter noise keeps samples stable across chunk sizes and note reordering.
    value = (indices.astype(np.uint64)+np.uint64(seed)) & np.uint64(0xffffffff)
    value = ((value ^ (value >> 16))*np.uint64(0x45d9f3b)) & np.uint64(0xffffffff)
    value = ((value ^ (value >> 16))*np.uint64(0x45d9f3b)) & np.uint64(0xffffffff)
    value ^= value >> 16
    return value.astype(np.float64)/2147483648.-1.


def oscillator(instrument, event, indices):
    count = event['end']-event['first']
    t = indices.astype(np.float64)/RATE
    position = indices.astype(np.float64)/max(1, count-1)
    hz = 440*2**((event['pitch']-69)/12)
    phase = 2*math.pi*hz*t
    edge = np.minimum(1., indices/max(1, min(round(.005*RATE), count//8)))
    edge *= np.minimum(1., (count-1-indices)/max(1, min(round(.02*RATE), count//8)))
    if instrument == 'sine':
        value = np.sin(phase)*edge
    elif instrument == 'pluck':
        value = (np.sin(phase)+.3*np.sin(2*phase)+.1*np.sin(3*phase))/1.4
        value *= np.exp(-6*position)*edge
    elif instrument == 'bell':
        value = (np.sin(phase)*np.exp(-3*position)+.3*np.sin(2.01*phase)*np.exp(-7*position)+.15*np.sin(3.9*phase)*np.exp(-12*position))/1.45
        value *= edge
    elif instrument == 'pad':
        value = (np.sin(phase)+.2*np.sin(2*phase)+.1*np.sin(3*phase))/1.3
        value *= np.sin(math.pi*position)**2
    elif instrument == 'kick':
        value = np.sin(2*math.pi*(hz*t+100*.035*(1-np.exp(-t/.035))))*np.exp(-7*position)*edge
    elif instrument == 'snare':
        value = (.8*noise(indices, event['seed'])+.2*np.sin(2*math.pi*185*t))*np.exp(-8*position)*edge
    elif instrument == 'hihat':
        value = .5*(noise(indices, event['seed'])-noise(indices-1, event['seed']))*np.exp(-12*position)*edge
    else:
        value = noise(indices, event['seed'])*np.sin(math.pi*position)**2*np.sin(phase*(1+3*position))
    return value*event['velocity']


def synthesize(canonical, plan, directory, *, stems=False, block_size=4096):
    """Write an owned directory only. Publication/cleanup belongs to generate()."""
    if isinstance(block_size, bool) or not isinstance(block_size, int) or not 1 <= block_size <= 65536:
        raise argument_error('block_size requires integer1–65536', 'block_size')
    tracks, frames = plan['tracks'], plan['frames']
    if frames*4*(1+len(tracks)*bool(stems)) > 512*1024*1024:
        raise argument_error('Master plus stems exceeds512MiB PCM quota', 'stems')
    started = time.perf_counter()
    digest, peak, square_sum, nonzero, limited, pcm_peak = hashlib.sha256(), 0., 0., 0, 0, 0
    outputs = {}
    with contextlib.ExitStack() as stack:
        def writer(name):
            wav = stack.enter_context(wave.open(str(directory/name), 'wb'))
            wav.setnchannels(2); wav.setsampwidth(2); wav.setframerate(RATE)
            return wav
        master = writer('master.wav')
        stem_writers = [writer(f'stem-{i:02d}.wav') for i in range(len(tracks))] if stems else []
        for first in range(0, frames, block_size):
            checkpoint()
            end = min(frames, first+block_size)
            mixed = np.zeros((end-first, 2), dtype=np.float64)
            for i, track in enumerate(tracks):
                mono = np.zeros(end-first, dtype=np.float64)
                for event in track['events']:
                    lo, hi = max(first, event['first']), min(end, event['end'])
                    if hi > lo:
                        indices = np.arange(lo-event['first'], hi-event['first'], dtype=np.int64)
                        mono[lo-first:hi-first] += oscillator(track['instrument'], event, indices)
                stereo = mono[:, None]*np.array([track['left'], track['right']])*track['gain']
                mixed += stereo
                if stems:
                    if np.max(np.abs(stereo), initial=0) >= 1:
                        raise AppError('MUSIC_SCORE_CLIPPING', 'Stem clips; lower track gain', exit_code=6)
                    stem_writers[i].writeframesraw(np.rint(stereo*32767).astype('<i2').tobytes())
            mixed *= plan['master_gain']
            before = float(np.max(np.abs(mixed), initial=0))
            peak = max(peak, before)
            limited += int(np.count_nonzero(np.abs(mixed) >= 1))
            if canonical['limiter'] == 'none' and before >= 1:
                raise AppError('MUSIC_SCORE_CLIPPING', 'Master clips; lower gain or explicitly choose tanh', exit_code=6)
            if canonical['limiter'] == 'tanh':
                mixed = np.tanh(mixed)
            if not np.isfinite(mixed).all():
                raise AppError('MUSIC_SCORE_INVALID_PCM', 'Non-finite synthesized PCM', exit_code=6)
            pcm = np.rint(mixed*32767).astype('<i2')
            pcm_peak = max(pcm_peak, int(np.abs(pcm.astype(np.int32)).max(initial=0)))
            raw = pcm.tobytes()
            digest.update(raw); master.writeframesraw(raw)
            square_sum += float(np.sum((pcm.astype(np.float64)/32768.)**2))
            nonzero += int(np.count_nonzero(pcm))
    if nonzero == 0:
        raise AppError('MUSIC_SCORE_SILENT', 'Score produces silent PCM', exit_code=6)
    for i, track in enumerate(tracks):
        if stems:
            name = f'stem-{i:02d}.wav'
            outputs[track['id']] = dict(file=name, sha256='sha256:'+sha256_file(directory/name))
    return dict(engine=ENGINE, device='cpu', neural_model=False, model_forwards=0,
                sample_rate=RATE, channels=2, frames=frames, duration_seconds=frames/RATE,
                PCM_sha256=digest.hexdigest(), PCM_bytes=frames*4,
                pre_limiter_peak=peak, over_unit_pre_limiter_samples=limited, limiter=canonical['limiter'],
                sample_peak=pcm_peak/32768., true_peak_accepted=False,
                rms=math.sqrt(square_sum/(frames*2)), nonzero_samples=nonzero, stems=outputs,
                render_seconds=time.perf_counter()-started, note_samples=plan['note_samples'])


def generate(root, project, payload, *, new_id=None, stems=False, placement=None, dry_run=False,
             command='music.compose'):
    if command not in ['music.compose', 'music.effect']:
        raise argument_error('Unknown score generation command', 'command')
    canonical, plan = prepare(payload)
    if not isinstance(stems, bool):
        raise argument_error('stems requires boolean', 'stems')
    placement = placement or dict(apply=False, sequence_id=None, track_id=None, start=0.)
    ident = new_asset_id(project, new_id, 'asset_score')
    directory = ensure_inside(root/'assets', root/'assets/music-scores'/ident)
    if directory.exists():
        raise argument_error('Score output directory already exists', str(directory))
    append_audio(root, copy.deepcopy(project), dict(id=ident, kind='audio', probe=dict(duration_seconds=plan['frames']/RATE)), **placement)
    estimate = plan['frames']*4*(1+len(plan['tracks'])*stems)
    if estimate > 512*1024*1024:
        raise argument_error('Master plus stems exceeds512MiB PCM quota', 'stems')
    if dry_run:
        return dict(engine=ENGINE, asset_id=ident, canonical_score=canonical, frames=plan['frames'],
                    output_PCM_bytes=estimate, device=dict(selected='cpu', backend='numpy-analytical'),
                    neural_model=False, network='disabled')
    directory.mkdir(parents=True, exist_ok=False)
    try:
        atomic_write_json(directory/'score.json', canonical)
        stats = synthesize(canonical, plan, directory, stems=stems)
        output = directory/'master.wav'
        digest = 'sha256:'+sha256_file(output)
        evidence = (directory/'SOURCE.json').relative_to(root).as_posix()
        source = dict(engine=ENGINE, command=command, score_sha256='sha256:'+sha256_file(directory/'score.json'),
                      score_uri=(directory/'score.json').relative_to(root).as_posix(),
                      audio_sha256=digest, audio=stats, copied_recordings=False, model_weights=False,
                      user_score_rights_verified=False)
        atomic_write_json(directory/'SOURCE.json', source)
        asset = dict(id=ident, kind='audio', uri=output.relative_to(root).as_posix(), sha256=digest,
                     probe=probe_media(output), rights_ref=ident,
                     source=dict(source_url='local://'+evidence, source_version=ENGINE,
                                 retrieved_at=now_iso(), original_name=output.name, generation=source))
        rights = dict(asset_id=ident, kind='audio', sha256=digest, source_url='local://'+evidence,
                      source_version=ENGINE, creator='agent-authored score / analytical synthesis',
                      license_spdx='LicenseRef-UNVERIFIED', license_url='', attribution='',
                      permitted_uses=['internal'], restrictions=[], evidence=evidence,
                      verification_status='unverified', verified_by='', takedown_status='clear',
                      retrieved_at=now_iso(), notes='Weight-free synthesis does not verify caller score/output rights.')
        result = commit_asset(root, project, asset, rights, command=command,
                              report=dict(engine=ENGINE, score=source, audio_stats=stats), **placement)
        return dict(result, engine=ENGINE, score=source, audio_stats=stats, review_required=True)
    except BaseException:
        # This new, bounded directory is exclusively owned by this operation.
        if directory.resolve().is_relative_to((root/'assets/music-scores').resolve()):
            shutil.rmtree(directory)
        raise
