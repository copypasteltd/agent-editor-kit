"""Owned native CPU worker. All paths/dependencies are supplied local inputs."""
from __future__ import annotations
import hashlib
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import traceback


def read_exact(stream,size):
    chunks = []
    remaining = size
    while remaining:
        part = stream.read(remaining)
        if not part:
            break
        chunks.append(part); remaining -= len(part)
    return b''.join(chunks)


def clock(source,ffprobe,*,kind=None):
    from fractions import Fraction
    if (kind or source.get('kind')) == 'image':
        return [0.]
    command = [ffprobe,'-v','error','-protocol_whitelist','file,pipe','-select_streams','v:0',
               '-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',source['path']]
    with tempfile.TemporaryFile() as stdout,tempfile.TemporaryFile() as stderr:
        result = subprocess.run(command,stdin=subprocess.DEVNULL,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode or stdout.tell() > 1024*1024:
            raise ValueError('FACE_CFR_PROBE_FAILED')
        stdout.seek(0); rows = json.load(stdout)['frames']
    pts = [float(f['best_effort_timestamp_time']) for f in rows]
    fps = float(Fraction(source['fps']))
    if len(pts) != source['frame_count'] or any(not math.isfinite(t) or abs(t-i/fps) > .0015 for i,t in enumerate(pts)):
        raise ValueError('FACE_SOURCE_NOT_CFR')
    return pts


def decoder(ffmpeg,source):
    return [ffmpeg,'-nostdin','-hide_banner','-loglevel','error','-threads','1','-protocol_whitelist','file,pipe',
            '-noautorotate','-i',source,'-map','0:v:0','-an','-sn','-dn','-fps_mode','passthrough',
            '-pix_fmt','rgba','-f','rawvideo','pipe:1']


def pcm_digest(ffmpeg,path,index):
    command = [ffmpeg,'-nostdin','-hide_banner','-loglevel','error','-protocol_whitelist','file,pipe',
               '-i',path,'-map',f'0:a:{index}','-vn','-sn','-dn','-c:a','pcm_f64le','-f','f64le','pipe:1']
    digest = hashlib.sha256(); count = 0
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=errors,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            while part := process.stdout.read(65536):
                count += len(part); digest.update(part)
            if process.wait():
                raise ValueError('FACE_AUDIO_DECODE_FAILED')
        finally:
            if process.poll() is None:
                process.kill(); process.wait()
            process.stdout.close()
    return {'sha256':'sha256:'+digest.hexdigest(),'bytes':count,'format':'f64le-native-sample-rate-channels'}


def verify_encoded(plan,expected,ffmpeg,ffprobe):
    from ai_ad_editor.media import probe_media
    source = plan['source']
    output = {'path':plan['output'],**{k:source[k] for k in ('frame_count','fps')}}
    clock(output,ffprobe,kind='video')
    size = source['width']*source['height']*4
    with tempfile.TemporaryFile() as errors:
        process = subprocess.Popen(decoder(ffmpeg,plan['output']),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=errors,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            for sha in expected:
                raw = read_exact(process.stdout,size)
                if len(raw) != size or 'sha256:'+hashlib.sha256(raw).hexdigest() != sha:
                    raise ValueError('FACE_ENCODED_RGBA_MISMATCH')
            if process.stdout.read(1) or process.wait():
                raise ValueError('FACE_ENCODED_FRAME_COUNT_INVALID')
        finally:
            if process.poll() is None:
                process.kill();process.wait()
            process.stdout.close()
    encoded = probe_media(Path(plan['output']))['streams']
    video = next(s for s in encoded if s.get('codec_type') == 'video')
    transfer = {'srgb':'iec61966-2-1','bt709':'bt709','gamma22':'gamma22','gamma28':'gamma28'}[source['color_transfer']]
    if video.get('pix_fmt') != 'bgra' or video.get('color_transfer') != transfer or video.get('color_range') != 'pc' or video.get('color_space') != 'gbr':
        raise ValueError('FACE_ENCODED_COLOR_TAGS_CHANGED')
    if source.get('color_primaries') not in (None,'unknown','unspecified') and video.get('color_primaries') != source['color_primaries']:
        raise ValueError('FACE_ENCODED_COLOR_PRIMARIES_CHANGED')
    inputs = [s for s in probe_media(Path(source['path']))['streams'] if s.get('codec_type') == 'audio']
    outputs = [s for s in encoded if s.get('codec_type') == 'audio']
    if len(inputs) != len(outputs):
        raise ValueError('FACE_AUDIO_STREAM_COUNT_CHANGED')
    proofs = []
    for index,(a,b) in enumerate(zip(inputs,outputs)):
        original = pcm_digest(ffmpeg,source['path'],index)
        edited = pcm_digest(ffmpeg,plan['output'],index)
        if original != edited or any(a.get(k) != b.get(k) for k in ('sample_rate','channels')):
            raise ValueError('FACE_AUDIO_PCM_CHANGED')
        proofs.append({'stream_index':index,'source':original,'output':edited,'sample_rate':a.get('sample_rate'),'channels':a.get('channels')})
    return proofs


def infer(plan,response):
    from ai_ad_editor.local_face import ENGINE,RETOUCH,PROTOCOL,digest,verify_adapter,validate_recipe
    from ai_ad_editor.face_landmarks import FaceModels
    from ai_ad_editor.face_geometry import FaceAssociation,retouch_frame
    from ai_ad_editor.utils import sha256_file
    import numpy as np
    import cv2
    source = plan['source']; mode = plan['mode']
    if plan['protocol'] != PROTOCOL or mode not in ('scan','retouch') or plan['engine'] != (ENGINE if mode == 'scan' else RETOUCH):
        raise ValueError('FACE_REQUEST_CONTRACT_INVALID')
    programs = {r['role']:r for r in plan['programs']}
    ffmpeg,ffprobe = programs['ffmpeg']['path'],programs['ffprobe']['path']
    if plan['network'] != 'disabled' or 'sha256:'+sha256_file(Path(source['path'])) != source['sha256']:
        raise ValueError('FACE_INPUT_INTEGRITY_FAILED')
    for row in [*plan['programs'],*plan.get('implementation',[])]:
        if 'sha256:'+sha256_file(Path(row['path'])) != row['sha256']:
            raise ValueError('FACE_TOOL_CHANGED')
    if mode == 'scan' and not verify_adapter(plan['adapter'])['ok']:
        raise ValueError('FACE_ADAPTER_INTEGRITY_FAILED')
    if mode == 'retouch':
        validate_recipe(plan['recipe'])
    cv2.setNumThreads(plan.get('adapter',{}).get('threads',2))
    pts = clock(source,ffprobe)
    models = FaceModels(plan['adapter']['model_path'],threads=plan['adapter']['threads']) if mode == 'scan' else None
    association = FaceAssociation()
    frames,hashes,changed_counts,affected_counts = [],[],[],[]
    encoder = decode = None
    try:
        with tempfile.TemporaryFile() as errors,tempfile.TemporaryFile() as encode_errors:
            if mode == 'retouch':
                if Path(plan['output']).exists():
                    raise ValueError('FACE_OUTPUT_ALREADY_EXISTS')
                command = [ffmpeg,'-nostdin','-hide_banner','-loglevel','error','-protocol_whitelist','file,pipe',
                           '-f','rawvideo','-pixel_format','rgba','-video_size',f"{source['width']}x{source['height']}",
                           '-framerate',source['fps'],'-i','pipe:0','-protocol_whitelist','file,pipe','-noautorotate','-i',source['path'],
                           '-map','0:v:0','-map','1:a?','-c:v','ffv1','-level','3','-coder','1','-context','1',
                           '-pix_fmt','bgra','-threads','2','-fps_mode','passthrough','-c:a','copy','-f','matroska',plan['output']]
                transfer = {'srgb':'iec61966-2-1','bt709':'bt709','gamma22':'gamma22','gamma28':'gamma28'}[source['color_transfer']]
                metadata = ['-color_range','pc','-colorspace','rgb','-color_trc',transfer]
                if source.get('color_primaries') not in (None,'unknown','unspecified'):
                    metadata += ['-color_primaries',source['color_primaries']]
                # FFmpeg 8.1 can take unspecified input-frame tags over CLI
                # tags. Set frame properties as well, without altering pixels.
                params = 'setparams=range=full:colorspace=gbr:color_trc='+transfer
                if source.get('color_primaries') not in (None,'unknown','unspecified'):
                    params += ':color_primaries='+source['color_primaries']
                metadata += ['-vf',params]
                command[-1:-1] = metadata
                encoder = subprocess.Popen(command,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=encode_errors,creationflags=subprocess.CREATE_NO_WINDOW)
            decode = subprocess.Popen(decoder(ffmpeg,source['path']),stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=errors,creationflags=subprocess.CREATE_NO_WINDOW)
            size = source['width']*source['height']*4
            for index in range(source['frame_count']):
                response['stage'] = 'decode';response['last_frame'] = index
                raw = read_exact(decode.stdout,size)
                if len(raw) != size:
                    raise ValueError('FACE_DECODE_INCOMPLETE')
                sha = 'sha256:'+hashlib.sha256(raw).hexdigest()
                rgba = np.frombuffer(raw,np.uint8).reshape(source['height'],source['width'],4)
                if mode == 'scan':
                    response['stage'] = 'face-inference'
                    faces = models.infer(np.ascontiguousarray(rgba[:,:,:3]),**{k:v for k,v in plan['settings'].items() if k != 'cuts'})
                    faces = association.update(faces,cut=index in plan['settings']['cuts'])
                    frames.append({'frame_index':index,'pts_seconds':pts[index],'decoded_rgba_sha256':sha,'faces':faces})
                else:
                    authored = plan['recipe']['frames'][index]
                    if authored['decoded_rgba_sha256'] != sha:
                        raise ValueError('FACE_RECIPE_FRAME_BYTES_CHANGED')
                    response['stage'] = 'local-retouch'
                    output,affected = retouch_frame(rgba,authored['faces'],plan['recipe']['controls'],selected_ids=plan['recipe']['selected_ids'],transfer=source['color_transfer'])
                    hashes.append('sha256:'+hashlib.sha256(output.tobytes()).hexdigest())
                    changed_counts.append(int(np.count_nonzero(np.any(output[:,:,:3] != rgba[:,:,:3],axis=2))))
                    affected_counts.append(int(affected.sum()))
                    encoder.stdin.write(output.tobytes())
            if decode.stdout.read(1) or decode.wait():
                errors.seek(0)
                raise ValueError('FACE_DECODE_FAILED: '+errors.read(4000).decode('utf-8',errors='replace'))
            if encoder is not None:
                encoder.stdin.close()
                if encoder.wait():
                    encode_errors.seek(0)
                    raise ValueError('FACE_ENCODE_FAILED: '+encode_errors.read(4000).decode('utf-8',errors='replace'))
        if mode == 'scan':
            if not verify_adapter(plan['adapter'])['ok']:
                raise ValueError('FACE_ADAPTER_CHANGED')
            import onnxruntime as ort
            response.update(engine=ENGINE,adapter_sha256=plan['adapter']['sha256'],frames=frames,
                            providers=['CPUExecutionProvider'],detector_forwards=models.detector_forwards,
                            landmark_forwards=models.landmark_forwards,versions={'numpy':np.__version__,'opencv':cv2.__version__,'onnxruntime':ort.__version__})
        else:
            response['stage'] = 'independent-encoded-pixel-and-pcm-check'
            proofs = verify_encoded(plan,hashes,ffmpeg,ffprobe)
            response.update(engine=RETOUCH,model_forwards=0,output_frames=len(hashes),output_rgba_sha256=hashes,
                            changed_rgb_pixels=changed_counts,affected_pixels=affected_counts,alpha_mismatches=0,
                            protected_pixel_mismatches=0,audio_pcm=proofs,versions={'numpy':np.__version__,'opencv':cv2.__version__})
        if 'sha256:'+sha256_file(Path(source['path'])) != source['sha256']:
            raise ValueError('FACE_SOURCE_CHANGED')
        response.update(status='succeeded',device='cpu',request_sha256=digest(plan),source_sha256=source['sha256'],
                        source_clock_frames_checked=len(pts),stage='complete')
    finally:
        if models is not None:
            response['detector_forwards'] = models.detector_forwards
            response['landmark_forwards'] = models.landmark_forwards
        for process in (decode,encoder):
            if process is not None:
                if process.poll() is None:
                    process.kill();process.wait()
                for stream in (process.stdin,process.stdout):
                    if stream is not None and not stream.closed:
                        stream.close()


def main():
    if sys.stdin.buffer.readline() != b'run\n':
        return 2
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from ai_ad_editor.local_face import PROTOCOL,MAX_REPORT_BYTES
    from ai_ad_editor.yolo_worker import install_network_guard
    path = Path(sys.argv[1])
    if not 0 < path.stat().st_size <= MAX_REPORT_BYTES+1024*1024:
        return 2
    request = json.loads(path.read_text(encoding='utf-8'))
    response = {'protocol':PROTOCOL,'status':'failed','network':'disabled','blocked_network_events':[]}
    started = time.monotonic()
    try:
        install_network_guard(response['blocked_network_events'])
        for name in ('TEMP','TMP','TMPDIR'):
            os.environ[name] = str(Path(request['runtime_root'])/'temp')
        tempfile.tempdir = os.environ['TEMP']
        infer(request['plan'],response)
    except BaseException as exc:
        response.update(error=type(exc).__name__+': '+str(exc),traceback=traceback.format_exc()[-8000:])
    response['elapsed_seconds'] = time.monotonic()-started
    data = json.dumps(response,ensure_ascii=False,indent=2,allow_nan=False).encode('utf-8')
    if len(data) > MAX_REPORT_BYTES:
        response = {'protocol':PROTOCOL,'status':'failed','error':'FACE_RESPONSE_BUDGET_EXCEEDED'}
        data = json.dumps(response).encode()
    Path(request['response']).write_bytes(data)
    return 0 if response['status'] == 'succeeded' else 1


if __name__ == '__main__':
    raise SystemExit(main())
