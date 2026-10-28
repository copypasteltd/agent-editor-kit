"""Bounded Float32 author frames plus common authored audio to lossless MKV.

This explicit library transport is not the default render/preview/queue path.
The only delivery boundary is straight GBR(A) 16-bit, nearest-even quantized
after the caller-selected relative RGB transfer. No HDR acceptance is implied.
"""
from __future__ import annotations
from collections import deque
from fractions import Fraction
import hashlib,math,os,queue,subprocess,threading,time,uuid
from pathlib import Path
import numpy as np
from .errors import AppError
from .float_audio_graph import PROTOCOL as AUDIO_PROTOCOL,project_digest,verify as verify_audio
from .float_color_signal import ColorSignal,convert_rgba
from .float_timeline import FloatTimeline
from .media import ffmpeg_path
from .native_audio_clock import cancel
from .sequence_canvas import sequence_canvas
from .utils import sha256_file

PROTOCOL='bounded-author-float32-to-FFV1-gbrap16-v1'
CHUNK_BYTES=65536
QUEUE_CHUNKS=4
MAX_SECONDS=3600

def error(code,message,**details):
    return AppError('FLOAT_STREAM_'+code,message,exit_code=6,diagnostics=details or None)

def digest(path):return 'sha256:'+sha256_file(Path(path))

class _EncoderPipe:
    """Own one native child and two threads; queued chunks own <=64KiB."""
    def __init__(self,command,*,cwd,cancel_file=None,timeout=MAX_SECONDS):
        self.marker=cancel_file;self.deadline=time.monotonic()+timeout
        self.queue=queue.Queue(maxsize=QUEUE_CHUNKS);self.tail=deque(maxlen=2)
        self.stop=threading.Event();self.failure=None;self.finished=False;self.closed=False
        self.bytes_written=0;self.maximum_queued_chunks=0
        self.process=subprocess.Popen(command,cwd=cwd,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,bufsize=0,creationflags=subprocess.CREATE_NO_WINDOW)
        def writer():
            try:
                while not self.stop.is_set():
                    try:block=self.queue.get(timeout=.1)
                    except queue.Empty:continue
                    if block is None:break
                    view=memoryview(block)
                    while view and not self.stop.is_set():
                        count=self.process.stdin.write(view)
                        if not count:raise BrokenPipeError('zero-byte stdin write')
                        self.bytes_written+=count;view=view[count:]
            except BaseException as exc:self.failure=exc
            finally:
                try:self.process.stdin.close()
                except OSError:pass
        def diagnostics():
            try:
                while block:=self.process.stderr.read(CHUNK_BYTES):self.tail.append(block)
            except OSError:pass
        self.threads=[threading.Thread(target=writer,name='float-encoder-stdin',daemon=True),
                      threading.Thread(target=diagnostics,name='float-encoder-stderr',daemon=True)]
        try:
            for thread in self.threads:thread.start()
        except BaseException:
            self.close();raise

    def stderr(self):return b''.join(self.tail).decode('utf8','replace')[-6000:]

    def check(self,*,allow_exit=False):
        cancel(self.marker)
        if time.monotonic()>self.deadline:raise error('TIMEOUT','有界编码管道超过时间预算')
        if self.failure is not None:raise error('ENCODE','编码器关闭输入管道',cause=repr(self.failure),stderr=self.stderr())
        code=self.process.poll()
        if code is not None and (code!=0 or not allow_exit):
            raise error('ENCODE','编码器在作者帧写入完成前退出' if not allow_exit else '编码器执行失败',exit_code=code,stderr=self.stderr())

    def put(self,block):
        if self.finished or self.closed:raise error('STATE','编码管道已经结束')
        if block is not None and (type(block) is not bytes or not 0<len(block)<=CHUNK_BYTES):
            raise error('CHUNK','管道分块须拥有最多64KiB的独立bytes')
        while True:
            self.check()
            try:
                self.queue.put(block,timeout=.1)
                self.maximum_queued_chunks=max(self.maximum_queued_chunks,self.queue.qsize());return
            except queue.Full:pass

    def finish(self):
        self.put(None);self.finished=True
        while self.process.poll() is None:
            self.check(allow_exit=True);self.stop.wait(.1)
        self.check(allow_exit=True)
        for thread in self.threads:thread.join(timeout=5)
        if any(thread.is_alive() for thread in self.threads):raise error('LIFECYCLE','编码线程未在正常结束后退出')

    def close(self):
        if self.closed:return
        self.closed=True;self.stop.set()
        if self.process.poll() is None:
            self.process.terminate()
            try:self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=5)
        for thread in self.threads:
            if thread.ident is not None:thread.join(timeout=5)
        for stream in (self.process.stdin,self.process.stderr):
            try:stream.close()
            except OSError:pass
        # Drop copied chunks immediately on failure/cancellation.
        while True:
            try:self.queue.get_nowait()
            except queue.Empty:break
        if any(thread.is_alive() for thread in self.threads):raise error('LIFECYCLE','编码器回收后仍有自有线程存活')

def _chunks(surface,*,range_policy,poll,stats,alpha_bits=16):
    pixels=surface.reshape(-1,4)
    # Every plane is emitted in independently owned <=64KiB chunks. Float64
    # scaling rounds only at this explicitly selected integer delivery edge.
    for channel in (1,2,0,3):
        for start in range(0,len(pixels),CHUNK_BYTES//2):
            poll();values=pixels[start:start+CHUNK_BYTES//2,channel].astype(np.float64)
            outside=(values<0)|(values>1)
            if np.any(outside):
                if channel==3 or range_policy=='reject':raise error('RANGE','整数交付范围之外的RGB须显式选择clip策略')
                stats['clipped_RGB_components']+=int(np.count_nonzero(outside));values=np.clip(values,0,1)
            if channel==3 and alpha_bits==8:
                yield (np.rint(values*255).astype('<u2')*257).tobytes()
            else:
                yield np.rint(values*65535).astype('<u2').tobytes()

def render_ffv1(root,timeline,output,*,output_signal,range_policy='reject',audio_plan=None,
                cancel_file=None,timeout=MAX_SECONDS,overwrite=False):
    """Stream real author frames; publish the file only after all final proofs.

    Audio, when supplied, must come from the same immutable author project.
    Unsupported file-based stretch jobs are explicitly rejected in this first
    transport rather than claiming a complete common-renderer replacement.
    """
    root=Path(root).resolve();output=Path(output).resolve();marker=Path(cancel_file) if cancel_file is not None else None
    cancel(marker)
    if not isinstance(timeline,FloatTimeline) or not isinstance(output_signal,ColorSignal):
        raise error('ARGUMENT','须提供明确的FloatTimeline与交付ColorSignal')
    if output_signal.primaries!='bt709' or output_signal.transfer not in {'linear','srgb','bt709-oetf'}:
        raise error('SIGNAL','当前无损传输只接受明确BT.709基色及linear/sRGB/BT.709-OETF')
    if range_policy not in {'reject','clip'} or type(overwrite) is not bool:
        raise error('ARGUMENT','范围策略或覆盖标记无效')
    if isinstance(timeout,bool) or not isinstance(timeout,(int,float)) or not math.isfinite(timeout) or not 0<timeout<=MAX_SECONDS:
        raise error('BUDGET','编码超时须在0..3600秒范围')
    if output.suffix.lower()!='.mkv' or not output.parent.is_dir():raise error('OUTPUT','当前传输要求已有目录下的MKV输出')
    if output.exists() and not overwrite:raise error('OUTPUT_EXISTS','输出已存在，须明确选择覆盖')
    sequence=timeline.sequences[timeline.sequence_id];canvas=sequence_canvas(timeline.project,sequence)
    binding=project_digest(timeline.project)
    if audio_plan is not None:
        if (audio_plan.get('protocol')!=AUDIO_PROTOCOL or audio_plan.get('project_sha256')!=binding or
            audio_plan.get('sequence_id')!=timeline.sequence_id or audio_plan.get('project_root')!=str(root)):
            raise error('AUDIO_BINDING','音频计划须绑定同一作者工程、目标序列与本地根目录')
        if any(row.get('audio_stretch') for row in audio_plan['metadata']):
            raise error('AUDIO_STRETCH_UNCONNECTED','文件型本地变速Job尚未连接此编码传输')
    tools={str(Path(p).resolve()):digest(p) for p in (ffmpeg_path(),__file__,Path(__file__).with_name('float_audio_graph.py'),
        Path(__file__).with_name('float_color_signal.py'),Path(__file__).with_name('float_hdr.py'),Path(__file__).with_name('float_chromatic.py'),Path(__file__).with_name('float_timeline.py'))}
    temporary=output.with_name('.float-'+uuid.uuid4().hex+'.mkv');pipe=None
    inputs=[] if audio_plan is None else list(audio_plan['inputs']);video_input=inputs.count('-i')
    command=[ffmpeg_path(),'-nostdin','-hide_banner','-v','error','-filter_complex_threads','1',*inputs,
        '-thread_queue_size','2','-f','rawvideo','-pixel_format','gbrap16le','-video_size',f'{canvas["width"]}x{canvas["height"]}',
        '-framerate',str(timeline.fps),'-i','pipe:0']
    if audio_plan is not None:command+=['-filter_complex',audio_plan['filter_complex']]
    command+=['-map',f'{video_input}:v:0']
    if audio_plan is not None:command+=['-map','[aout]','-c:a','pcm_f32le']
    else:command+=['-an']
    transfer={'linear':'linear','srgb':'iec61966-2-1','bt709-oetf':'bt709'}[output_signal.transfer]
    command+=['-c:v','ffv1','-level','3','-threads:v','1','-pix_fmt','gbrap16le','-color_range','pc',
        '-colorspace','rgb','-color_primaries','bt709','-color_trc',transfer,'-fps_mode','passthrough','-f','matroska',str(temporary)]
    stats={'clipped_RGB_components':0};payload=hashlib.sha256();frames=0;failure=None
    def poll():
        cancel(marker)
        if pipe is not None:pipe.check()
    def verify_inputs():
        cancel(marker);timeline.verify_sources()
        if project_digest(timeline.project)!=binding:raise error('INPUT_CHANGED','作者工程在编码期间变化')
        for path,expected in tools.items():
            if digest(path)!=expected:raise error('INPUT_CHANGED','编码器或执行实现字节变化',artifact=path)
        if audio_plan is not None:verify_audio(root,audio_plan,cancel_file=marker)
    try:
        verify_inputs();pipe=_EncoderPipe(command,cwd=root,cancel_file=marker,timeout=timeout)
        for index in range(timeline.frame_count):
            poll();surface,_=timeline.render_frame(index)
            if surface.shape!=(canvas['height'],canvas['width'],4):raise error('FRAME','作者宿主返回非目标尺寸')
            delivered,_=convert_rgba(surface,timeline.working,output_signal,cancel=poll)
            for chunk in _chunks(delivered,range_policy=range_policy,poll=poll,stats=stats):
                payload.update(chunk);pipe.put(chunk)
            frames+=1
        pipe.finish();verify_inputs()
        expected=frames*canvas['width']*canvas['height']*8
        if pipe.bytes_written!=expected or not temporary.is_file() or not temporary.stat().st_size:
            raise error('PAYLOAD','实际写入字节或编码输出不完整')
        output_sha=digest(temporary);output_bytes=temporary.stat().st_size;pipe.close()
        receipt={'protocol':PROTOCOL,'encoded_movie':True,'frames':frames,'display_fps':str(timeline.fps),
            'author_duration':str(Fraction(sequence['duration_tick'],timeline.tps)),
            'video_coverage_end':str(Fraction(frames,1)/timeline.fps),
            'audio_samples_48000':audio_plan['expected_samples_48000'] if audio_plan is not None else None,
            'output_signal':{'primaries':output_signal.primaries,'transfer':output_signal.transfer},
            'pixel_format':'gbrap16le','alpha_association':'straight-independent-coverage','quantization':'Float64 scaling;nearest-even-to-16bit',
            'range_policy':range_policy,**stats,'video_input_bytes':expected,'video_input_sha256':'sha256:'+payload.hexdigest(),
            'stdin_queue_chunks':QUEUE_CHUNKS,'chunk_bytes':CHUNK_BYTES,'maximum_queued_chunks':pipe.maximum_queued_chunks,
            'stderr_tail_maximum_bytes':2*CHUNK_BYTES,'input_queue_frames':2,'whole_movie_buffered':False,
            'owned_process_pid':pipe.process.pid,'owned_process_exit_code':pipe.process.returncode,
            'owned_threads_closed':all(not t.is_alive() for t in pipe.threads),'output':str(output),
            'output_sha256':output_sha,'output_bytes':output_bytes,'project_sha256':binding,'artifacts':tools,'command':command,
            'default_render_preview_queue_integrated':False,'HDR_accepted':False,'network':False}
        cancel(marker)
        if overwrite:os.replace(temporary,output)
        else:temporary.rename(output) # Windows atomic no-clobber rename.
        return receipt
    except BaseException as exc:
        failure=exc;raise
    finally:
        try:
            if pipe is not None:pipe.close()
        finally:
            if temporary.is_file():temporary.unlink()
            if isinstance(failure,AppError):
                failure.diagnostics={**(failure.diagnostics or {}),'command':command,'published':False,
                    'owned_process_pid':pipe.process.pid if pipe is not None else None,
                    'owned_process_exit_code':pipe.process.returncode if pipe is not None else None,
                    'owned_threads_closed':all(not t.is_alive() for t in pipe.threads) if pipe is not None else True,
                    'temporary_removed':not temporary.exists()}
