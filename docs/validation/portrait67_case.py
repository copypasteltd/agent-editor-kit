"""Actual installed portrait batch: CUDA, all-frame invariants, migration and faults.

Neural media stay in ignored E-drive workspaces. Public evidence contains
receipts and hashes, never a claim of natural beauty or listening acceptance.
"""
from __future__ import annotations
import contextlib
from fractions import Fraction
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def run(args, h, frozen):
    out = h.proof('native-case', args.run)
    stage = h.load(h.BASE / ('skill-entry-' + args.stage_run) / 'verification.json')
    installed, home = Path(stage['installed']), Path(stage['home'])
    task = h.LOCAL / ('actual-' + args.run)
    task.mkdir(exist_ok=False)
    sys.path.insert(0, str(installed / 'site'))
    import numpy as np
    from PIL import Image, ImageDraw
    import ai_ad_editor
    from ai_ad_editor.media import ffmpeg_path, probe_media
    from ai_ad_editor.local_matting import _windows_job
    from ai_ad_editor.reverse_video_clock import probe_frames
    assert ai_ad_editor.VERSION == '0.1.67'
    assert Path(ai_ad_editor.__file__).resolve() == (installed / 'site/ai_ad_editor/__init__.py').resolve()
    ffmpeg = Path(ffmpeg_path()).resolve()
    entry = home / 'skills/agent-ffmpeg-local-editor/scripts/run.ps1'
    prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', entry]
    project = task / '原生人像 工程'
    calls = []
    env = dict(os.environ, TEMP=str(h.LOCAL / 'native-temp'), TMP=str(h.LOCAL / 'native-temp'),
               TMPDIR=str(h.LOCAL / 'native-temp'), PYTHONDONTWRITEBYTECODE='1')

    def digest(raw):
        return 'sha256:' + hashlib.sha256(raw).hexdigest()

    def record_call(name, command, returncode, elapsed):
        calls.append(dict(name=name, argv=list(map(str, command)), exit_code=returncode, elapsed_seconds=elapsed))
        h.save(out / 'calls.json', calls)

    def command(name, argv, *, cli=False, timeout=1800):
        began = time.monotonic()
        result = subprocess.run(list(map(str, argv)), cwd=h.ROOT, env=env, capture_output=True,
                                timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
        (out / (name + '.stdout')).write_bytes(result.stdout)
        (out / (name + '.stderr')).write_bytes(result.stderr)
        record_call(name, argv, result.returncode, time.monotonic() - began)
        assert result.returncode == 0, (name, result.stdout[-4000:], result.stderr[-4000:])
        if cli:
            value = json.loads(result.stdout)
            assert value['ok'] and value['provenance']['cli_version'] == '0.1.67', (name, value)
            print(json.dumps(dict(step=name, status='passed')), flush=True)
            return value['data']
        return result.stdout

    def cli(name, *argv):
        return command(name, [*prefix, *argv], cli=True)

    def decode(path, *, gray=False):
        result = subprocess.run([str(ffmpeg), '-nostdin', '-v', 'error', '-noautorotate', '-i', str(path),
            '-map', '0:v:0', '-an', '-pix_fmt', 'gray' if gray else 'rgba', '-fps_mode', 'passthrough',
            '-f', 'rawvideo', 'pipe:1'], capture_output=True, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0, result.stderr[-3000:]
        channels = () if gray else (4,)
        return np.frombuffer(result.stdout, np.uint8).reshape((-1, height, width, *channels))

    def media_proof(path):
        info = probe_media(path)
        pixels = decode(path)
        audio = []
        for index, stream in enumerate(s for s in info['streams'] if s.get('codec_type') == 'audio'):
            pcm = subprocess.run([str(ffmpeg), '-nostdin', '-v', 'error', '-i', str(path), '-map', f'0:a:{index}',
                '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le', 'pipe:1'], capture_output=True, timeout=180,
                creationflags=subprocess.CREATE_NO_WINDOW)
            assert pcm.returncode == 0, pcm.stderr[-2000:]
            audio.append(dict(index=index, sample_rate=int(stream['sample_rate']), channels=int(stream['channels']),
                samples=len(pcm.stdout)//(4*int(stream['channels'])), sha256=digest(pcm.stdout),
                start_seconds=str(Fraction(int(stream.get('start_pts', 0))) * Fraction(stream['time_base']))))
        pts, durations, native, _ = probe_frames(str(path), timeout=180)
        return dict(RGBA_sha256=digest(pixels.tobytes()), frames=len(pixels),
            clock_seconds=[str(Fraction(point)*Fraction(native['time_base'])) for point in pts], audio=audio)

    def get_asset(root, ident):
        data = json.loads((root / 'project.json').read_bytes())
        row = next(a for a in data['assets'] if a['id'] == ident)
        return row, root / row['uri']

    def check_processing(data, action, frames):
        processing = data['processing']; worker = processing['worker']; execution = worker['execution']
        assert processing['complete_RGBA_roundtrip_verified'] and processing['complete_labels_roundtrip_verified']
        assert processing['complete_source_PCM_verified'] and not processing['natural_quality_accepted']
        assert worker['providers'] == ['torch-cuda'] and not execution['CPU_fallback']
        assert execution['cuda_peak_allocated_bytes'] > 0
        assert execution['parser_forwards'] == (frames if action == 'parse' else 0)
        assert execution['region_frames'] == (frames if action == 'retouch' else 0)
        assert execution['model_loads'] == (1 if action == 'parse' else 0)
        assert all(p['exited'] and p['returncode'] == 0 and p['stdout_closed'] for p in processing['cleanup']['processes'])
        assert not processing['cleanup']['warnings']
        return dict(execution=execution, metrics=worker['metrics'], cleanup=processing['cleanup'],
                    complete_source_PCM_verified=True, complete_RGBA_roundtrip_verified=True)

    def compare_retouch(original, edited, labels, protected):
        source, result = decode(original), decode(edited)
        semantic, guard = decode(labels, gray=True), decode(protected, gray=True)
        if len(guard) == 1:
            guard = np.repeat(guard, len(source), axis=0)
        assert source.shape == result.shape and semantic.shape == guard.shape == source.shape[:-1]
        # Literal IDs from the independently documented pinned-model label order.
        allowed = np.isin(semantic, [1, 10, 12, 13, 17]) & (source[..., 3] != 0) & (guard == 0)
        changed = np.any(source[..., :3] != result[..., :3], axis=3)
        np.testing.assert_array_equal(source[..., 3], result[..., 3])
        np.testing.assert_array_equal(source[~allowed], result[~allowed])
        np.testing.assert_array_equal(source[guard != 0], result[guard != 0])
        assert changed.any() and not np.any(changed & ~allowed), 'No actual regional change, or changed outside literal allowed labels'
        assert np.any(np.isin(semantic, [1, 10])) and np.any(semantic == 17), 'Actual parser must identify skin and hair in this case'
        return dict(frames=len(source), changed_pixels=int(changed.sum()), allowed_pixels=int(allowed.sum()),
                    protected_pixels=int((guard != 0).sum()), alpha_equal=True, all_outside_RGBA_equal=True,
                    all_explicit_protection_equal=True, labels_min=int(semantic.min()), labels_max=int(semantic.max()))

    width, height, frames, fps = 768, 432, 6, 10
    original_sha = h.sha(args.source_image)
    with Image.open(args.source_image) as mother:
        resized = mother.convert('RGBA').resize((width, height), Image.Resampling.LANCZOS)
    rgba = np.array(resized); rgba[:, :4, 3] = 0; rgba[:, 4:8, 3] = 127
    source_image = task / '原图透明度夹具.png'; Image.fromarray(rgba).save(source_image)
    sequence = np.stack([np.roll(rgba, i, axis=1) for i in range(frames)])
    video_raw = task / 'source.rgba'; video_raw.write_bytes(sequence.tobytes())
    stereo = np.stack([.12*np.sin(2*np.pi*440*np.arange(28800)/48000),
                       .10*np.sin(2*np.pi*550*np.arange(28800)/48000)], axis=1).astype('<f4')
    mono = (.09*np.sin(2*np.pi*660*np.arange(13230)/22050)).astype('<f4')
    first_pcm, second_pcm = task/'stereo.f32', task/'mono.f32'
    first_pcm.write_bytes(stereo.tobytes()); second_pcm.write_bytes(mono.tobytes())
    source_movie = task / '双音轨连续源.mov'
    command('make-source', [ffmpeg, '-nostdin', '-v', 'error', '-n', '-f', 'rawvideo', '-pixel_format', 'rgba',
        '-video_size', f'{width}x{height}', '-framerate', str(fps), '-i', video_raw,
        '-f', 'f32le', '-ar', '48000', '-ac', '2', '-i', first_pcm,
        '-f', 'f32le', '-ar', '22050', '-ac', '1', '-i', second_pcm,
        '-map', '0:v:0', '-map', '1:a:0', '-map', '2:a:0', '-c:v', 'qtrle', '-pix_fmt', 'argb',
        '-c:a', 'pcm_f32le', '-video_track_timescale', str(fps), '-color_primaries', 'bt709',
        '-color_trc', 'iec61966-2-1', source_movie])
    mask = np.zeros((height, width), np.uint8); mask[:, 330:350] = 1
    static_mask = task / '非零灰度保护.png'; Image.fromarray(mask).save(static_mask)
    moving_mask = np.stack([np.roll(mask, i*2, axis=1) for i in range(frames)])
    mask_raw = task/'protect.gray'; mask_raw.write_bytes(moving_mask.tobytes()); animated_mask = task/'动态保护.nut'
    command('make-animated-protection', [ffmpeg, '-nostdin', '-v', 'error', '-n', '-f', 'rawvideo',
        '-pixel_format', 'gray', '-video_size', f'{width}x{height}', '-framerate', str(fps), '-i', mask_raw,
        '-c:v', 'ffv1', '-level', '3', '-fps_mode', 'passthrough', animated_mask])
    box = [round(width*.33), round(height*.05), round(width*.57), round(height*.58)]
    boxes = task/'boxes.json'; h.save(boxes, dict(clock='source-frame-index', keys=[dict(frame=0, box=box),
        dict(frame=frames-1, box=[box[0]+frames-1, box[1], box[2]+frames-1, box[3]])]))
    controls = task/'controls.json'; h.save(controls, dict(feather_pixels=2, regions=dict(
        skin=dict(exposure_ev=.18, saturation=1.05, smooth=.35),
        lips=dict(tint=[.55,.08,.13], tint_strength=.3), hair=dict(exposure_ev=-.15, saturation=.9))))
    neutral = task/'neutral.json'; h.save(neutral, {})
    cli('project-init', 'project', 'init', project, '--name', 'CLI67 actual native portrait')
    for ident, path in [('original', source_image), ('movie', source_movie), ('protect', static_mask), ('moving_protect', animated_mask)]:
        cli('ingest-'+ident, 'media', 'ingest', '--project', project, '--input', path, '--asset-id', ident)
    weights = h.ROOT/'product/.runtime/models/musetalk-v15-20261027/parser/model.safetensors'
    provenance = weights.parent.parent/'conversion.json'
    cli('adapter-register', 'portrait', 'adapter', 'register', '--project', project, '--adapter-id', 'portrait19',
        '--model-path', weights, '--executable', args.native_python, '--evidence', provenance)
    common = ['--project', project, '--adapter-id', 'portrait19']
    image_parse = cli('image-parse', 'portrait', 'parse', *common, '--source-asset-id', 'original',
        '--labels-asset-id', 'image_labels', '--preview-asset-id', 'image_regions', '--face-box', *map(str, box))
    video_parse = cli('video-parse', 'portrait', 'parse', *common, '--source-asset-id', 'movie',
        '--labels-asset-id', 'video_labels', '--preview-asset-id', 'video_regions', '--boxes-file', boxes)
    image_edit = cli('image-retouch', 'portrait', 'retouch', *common, '--labels-asset-id', 'image_labels',
        '--asset-id', 'image_edited', '--controls-file', controls, '--protection-asset-id', 'protect')
    video_edit = cli('video-retouch', 'portrait', 'retouch', *common, '--labels-asset-id', 'video_labels',
        '--asset-id', 'video_edited', '--controls-file', controls, '--protection-asset-id', 'moving_protect')
    repeated = cli('recipe-rerun', 'portrait', 'retouch', *common, '--recipe-asset-id', 'video_edited', '--asset-id', 'video_retry')
    no_change = cli('neutral-rerun', 'portrait', 'retouch', *common, '--recipe-asset-id', 'video_edited',
        '--asset-id', 'video_neutral', '--controls-file', neutral)
    results = {'image_parse':check_processing(image_parse, 'parse', 1), 'video_parse':check_processing(video_parse, 'parse', frames),
        'image_retouch':check_processing(image_edit, 'retouch', 1), 'video_retouch':check_processing(video_edit, 'retouch', frames),
        'recipe_rerun':check_processing(repeated, 'retouch', frames), 'neutral_rerun':check_processing(no_change, 'retouch', frames)}
    _, image_out = get_asset(project, 'image_edited'); _, image_labels = get_asset(project, 'image_labels')
    _, video_out = get_asset(project, 'video_edited'); _, video_labels = get_asset(project, 'video_labels')
    _, video_preview = get_asset(project, 'video_regions'); _, retry_out = get_asset(project, 'video_retry')
    _, neutral_out = get_asset(project, 'video_neutral')
    results['image_invariants'] = compare_retouch(source_image, image_out, image_labels, static_mask)
    results['video_invariants'] = compare_retouch(source_movie, video_out, video_labels, animated_mask)
    source_proof, edited_proof = media_proof(source_movie), media_proof(video_out)
    preview_proof = media_proof(video_preview)
    assert source_proof['audio'] == edited_proof['audio'] == preview_proof['audio']
    assert source_proof['clock_seconds'] == edited_proof['clock_seconds'] == preview_proof['clock_seconds']
    assert len(source_proof['audio']) == 2 and source_proof['audio'][0]['samples'] == 28800 and source_proof['audio'][1]['samples'] == 13230
    assert media_proof(retry_out) == edited_proof
    assert media_proof(neutral_out) == source_proof
    results['all_streams'] = dict(source=source_proof, edited=edited_proof, preview=preview_proof,
        neutral_all_frames_equal=True, recipe_all_frames_equal=True)
    oracle = out/'GPU-oracle.json'
    command('independent-GPU-oracle', [args.native_python, '-I', '-B', '-u', '-X', 'utf8',
        Path(__file__).with_name('portrait67_gpu_oracle.py'), '--installed', installed, '--output', oracle])
    results['independent_GPU_oracle'] = h.load(oracle)

    # First source audio stream is explicitly represented by a separate timeline clip.
    data = json.loads((project/'project.json').read_bytes()); sequence_data = data['sequences'][0]
    data['settings']['canvas'].update(width=width, height=height)
    h.save(project/'project.json', data)
    video_track = next(t['id'] for t in sequence_data['tracks'] if t['kind'] == 'video')
    audio_track = next(t['id'] for t in sequence_data['tracks'] if t['kind'] == 'audio')
    duration = round(frames/fps*data['settings']['timebase']['ticks_per_second'])
    changes = task/'timeline.json'
    h.save(changes, dict(operations=[dict(op='append_clip', id=ident, asset_id='video_edited', track_id=track,
        timeline_start_tick=0, duration_tick=duration, source_in_tick=0, source_out_tick=duration)
        for ident, track in [('portrait_video',video_track), ('portrait_audio',audio_track)]]))
    cli('compose', 'timeline', 'compose', '--project', project, '--input', changes)
    cli('validate', 'validate', '--project', project)
    baseline = task/'timeline.mp4'; cli('render', 'render', '--project', project, '--output', baseline)
    archive = task/'portrait-package.zip'
    cli('package-export', 'convert', 'export', '--project', project, '--target-format', 'package', '--output', archive)
    restored = task/'迁移 工程'; cli('package-import', 'convert', 'import', '--input', archive, '--output', restored)
    old = json.loads((project/'project.json').read_bytes()); new = json.loads((restored/'project.json').read_bytes())
    new_assets = {a['id']:a for a in new['assets']}
    for asset in old['assets']:
        other = new_assets[asset['id']]
        assert asset['sha256'] == other['sha256'] == 'sha256:'+h.sha(restored/other['uri'])
        assert asset.get('source',{}).get('portrait') == other.get('source',{}).get('portrait')
    restored_movie = task/'restored.mp4'; cli('package-render', 'render', '--project', restored, '--output', restored_movie)
    assert media_proof(baseline) == media_proof(restored_movie)
    moved_common = ['--project', restored, '--adapter-id', 'portrait19']
    moved = cli('package-recipe-rerun', 'portrait', 'retouch', *moved_common,
        '--recipe-asset-id', 'video_edited', '--asset-id', 'migrated_retry')
    results['migrated_retouch'] = check_processing(moved, 'retouch', frames)
    assert media_proof(get_asset(restored,'migrated_retry')[1]) == edited_proof
    results['package'] = dict(all_asset_bytes_and_portrait_recipes_equal=True,
        all_timeline_RGBA_PCM_clock_equal=True, actual_retouch_after_migration_equal=True,
        archive_sha256=h.sha(archive), timeline=media_proof(baseline))

    def core_state():
        paths = list(project.glob('*.json'))
        for folder in ('licenses', 'rights', 'models'):
            directory = project/folder
            if directory.exists(): paths += list(directory.rglob('*.json'))
        return {p.relative_to(project).as_posix():h.sha(p) for p in paths}

    def owned_jobs():
        directory = project/'cache/managed-jobs'
        return list(directory.iterdir()) if directory.exists() else []

    def fault(name, source_id, *, trigger=None, budget=300):
        assert not owned_jobs(), 'Unexpected existing workspaces in the isolated case project'
        before = core_state(); cancel_file = task/(name+'.cancel')
        output_id, labels_id = name+'_preview', name+'_labels'
        argv = [*prefix, 'portrait', 'parse', *common, '--source-asset-id', source_id,
            '--labels-asset-id', labels_id, '--preview-asset-id', output_id,
            '--face-box', *map(str,box), '--timeout-seconds', str(budget), '--storage-budget-mib', '4096']
        if trigger == 'cancel': argv += ['--cancel-file', cancel_file]
        target = project/'assets/derived'/(output_id+'.mov')
        foreign = b'foreign-output-created-during-real-CUDA-inference\n'
        observed_frames = 0; observed_stage = None; fired = False; began=time.monotonic()
        with _windows_job() as assign, (out/(name+'.stdout')).open('xb') as stdout, (out/(name+'.stderr')).open('xb') as stderr:
            process = subprocess.Popen(list(map(str,argv)),cwd=h.ROOT,env=env,stdout=stdout,stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW)
            assign(process)
            try:
                while process.poll() is None:
                    assert time.monotonic()-began < 360, 'Owned fault case exceeded its independent observation deadline'
                    for workspace in owned_jobs():
                        progress = workspace/'pipeline/progress.json'
                        if progress.exists():
                            try: value=json.loads(progress.read_bytes())
                            except (ValueError,OSError): continue
                            observed_frames=max(observed_frames,value.get('frames',0)); observed_stage=value.get('stage')
                    if trigger and not fired and observed_frames >= 1:
                        assert process.poll() is None, 'Do not inject after the owned process has exited'
                        if trigger == 'cancel': cancel_file.write_text('cancel owned portrait case','utf-8')
                        else:
                            target.parent.mkdir(parents=True,exist_ok=True)
                            with target.open('xb') as stream:stream.write(foreign)
                        fired=True
                    time.sleep(.025)
                code=process.wait(timeout=10)
            finally:
                if process.poll() is None:process.kill();process.wait(timeout=10)
        record_call(name,argv,code,time.monotonic()-began)
        value=json.loads((out/(name+'.stdout')).read_bytes()); errors=value['errors']
        expected={'cancel':'CANCELLED','conflict':'PORTRAIT_OUTPUT_CONFLICT',None:'TIMEOUT'}[trigger]
        assert code != 0 and not value['ok'] and errors[0]['code']==expected,(name,value)
        assert core_state()==before and not owned_jobs()
        after=json.loads((project/'project.json').read_bytes())
        assert not any(a['id'] in (labels_id,output_id) for a in after['assets'])
        assert not (project/'assets/derived'/(labels_id+'.nut')).exists()
        if trigger: assert fired and observed_frames>=1
        if trigger=='conflict':
            assert target.read_bytes()==foreign
            details=errors[0].get('diagnostics') or value.get('diagnostics') or {}
            # The error must carry the completed real inference, not preflight refusal.
            assert details['completed_execution']['parser_forwards']==240 and details['complete_RGBA_roundtrip_verified'] is True,(name,value)
        else:assert not target.exists()
        result=dict(error_code=expected,owned_entry_exited=True,observed_GPU_frames=observed_frames,
            observed_stage=observed_stage,injected_after_real_frame=fired,metadata_byte_equal=True,
            no_failed_asset_registered=True,owned_workspaces_removed=True,foreign_target_preserved=trigger=='conflict',
            elapsed_seconds=time.monotonic()-began)
        h.save(out/(name+'-verification.json'),result);print(json.dumps(dict(step=name,**result)),flush=True)
        return result

    for ident, loops in [('fault_source',39),('timeout_source',99)]:
        path=task/(ident+'.mov')
        command('make-'+ident,[ffmpeg,'-nostdin','-v','error','-n','-stream_loop',str(loops),'-i',source_movie,
            '-map','0:v:0','-an','-c:v','copy',path])
        cli('ingest-'+ident,'media','ingest','--project',project,'--input',path,'--asset-id',ident)
    results['faults']={'cancel':fault('cancel_actual','fault_source',trigger='cancel'),
        'conflict':fault('conflict_actual','fault_source',trigger='conflict'),
        'timeout':fault('timeout_actual','timeout_source',budget=6)}

    # Local client previews only: model-output redistribution rights are unverified.
    _, semantic_path=get_asset(project,'image_regions')
    panels=[Image.open(p).convert('RGB') for p in (source_image,semantic_path,image_out)]
    contact=Image.new('RGB',(width*3,height+32),(20,20,20));draw=ImageDraw.Draw(contact)
    for i,(picture,label) in enumerate(zip(panels,['Original + alpha fixture','Actual semantic regions','Protected regional grade'])):
        contact.paste(picture,(i*width,32));draw.text((i*width+12,8),label,fill='white')
    contact_path=task/'actual-comparison.png';contact.save(contact_path)
    preview_gif=task/'actual-comparison.gif'
    panels[0].save(preview_gif,save_all=True,append_images=[panels[2]],duration=1200,loop=0)
    assert h.sha(args.source_image)==original_sha
    assert not owned_jobs();h.unchanged(frozen)
    receipt=dict(status='passed',cli_version='0.1.67',actual_installed_PowerShell_entry=True,
        source_fallback=False,formal_activation=False,source_mother_unchanged=True,
        mother_sha256=original_sha,results=results,local_project=str(project),local_contact=str(contact_path),
        local_GIF=str(preview_gif),media_published=False,rights='internal-unverified',
        actual_continuous_playback_review=False,human_listening=False,natural_quality_accepted=False,
        full_goal_closed=False)
    h.save(out/'verification.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k!='results'},ensure_ascii=False),flush=True)
    return 0
