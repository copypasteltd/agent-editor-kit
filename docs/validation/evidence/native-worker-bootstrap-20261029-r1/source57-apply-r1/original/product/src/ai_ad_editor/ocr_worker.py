# PP-OCR preprocessing/DB/CTC adapted from PaddleOCR and RapidOCR.
# Copyright (c) 2020 PaddlePaddle Authors; RapidOCR Authors.
# Licensed under Apache-2.0; see PADDLE_OCR_LICENSE.txt and PADDLE_OCR_NOTICE.txt.
# Modified for explicit offline artifacts, bounded sequential inference,
# analytic rectangle expansion, original PTS and native process containment.
"""Isolated CPU ONNX text detector and recognizer; never installs/downloads."""
from __future__ import annotations
import json
import math
import os
import subprocess
import sys
import tempfile
import time
import traceback
from pathlib import Path


def ordered_box(rect, cv2, np):
    points = sorted(cv2.boxPoints(rect), key=lambda p: (p[0], p[1]))
    left = sorted(points[:2], key=lambda p: p[1]); right = sorted(points[2:], key=lambda p: p[1])
    return np.asarray([left[0], right[0], right[1], left[1]], dtype=np.float32)


def detect(image, session, limit, np, cv2):
    h, w = image.shape[:2]; ratio = min(1., limit/max(h,w))
    dh, dw = max(32, round(h*ratio/32)*32), max(32, round(w*ratio/32)*32)
    resized = cv2.resize(image, (dw,dh)).astype(np.float32)/255.
    tensor = ((resized-np.array([.485,.456,.406], dtype=np.float32))/np.array([.229,.224,.225], dtype=np.float32)).transpose(2,0,1)[None]
    output = session.run(None, {session.get_inputs()[0].name: tensor})[0]
    if output.shape != (1,1,dh,dw) or not np.isfinite(output).all() or output.min() < 0 or output.max() > 1:
        raise ValueError('OCR_DETECT_OUTPUT_INVALID')
    pred = output[0,0]
    contours, _ = cv2.findContours((pred>.3).astype(np.uint8), cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
    if len(contours) > 1000:
        raise ValueError('OCR_CONTOUR_BUDGET_EXCEEDED')
    found=[]
    for contour in contours:
        rect=cv2.minAreaRect(contour)
        rw,rh=rect[1]
        if min(rw,rh)<3:
            continue
        points=ordered_box(rect,cv2,np)
        x0,y0=np.floor(points.min(axis=0)).astype(int);x1,y1=np.ceil(points.max(axis=0)).astype(int)
        x0,y0=max(0,x0),max(0,y0);x1,y1=min(dw-1,x1),min(dh-1,y1)
        mask=np.zeros((y1-y0+1,x1-x0+1),np.uint8)
        cv2.fillPoly(mask, [np.rint(points-[x0,y0]).astype(np.int32)],1)
        score=float(cv2.mean(pred[y0:y1+1,x0:x1+1],mask)[0])
        if score<.5:
            continue
        # minAreaRect of a round-offset rectangle has these exact extents.
        # No general-polygon/curved text or upstream pyclipper equivalence claim.
        distance=rw*rh*1.6/(2*(rw+rh))
        points=ordered_box((rect[0], (rw+2*distance,rh+2*distance),rect[2]),cv2,np)
        points[:,0]=np.clip(np.round(points[:,0]/dw*w),0,w-1)
        points[:,1]=np.clip(np.round(points[:,1]/dh*h),0,h-1)
        if min(np.linalg.norm(points[0]-points[1]),np.linalg.norm(points[0]-points[3]))<5:
            continue
        found.append((points,score))
    if len(found)>128:
        raise ValueError('OCR_BOX_BUDGET_EXCEEDED')
    return sorted(found,key=lambda pair:(float(pair[0][:,1].min()),float(pair[0][:,0].min())))


def recognize(image, points, session, characters, max_width, np, cv2, decode):
    cw=max(1,round(max(np.linalg.norm(points[0]-points[1]),np.linalg.norm(points[2]-points[3]))))
    ch=max(1,round(max(np.linalg.norm(points[0]-points[3]),np.linalg.norm(points[1]-points[2]))))
    width=max(8,math.ceil(48*cw/ch))
    if width>max_width or cw*ch>16_000_000:
        raise ValueError('OCR_RECOGNITION_WIDTH_EXCEEDED')
    target=np.array([[0,0],[cw-1,0],[cw-1,ch-1],[0,ch-1]],np.float32)
    crop=cv2.warpPerspective(image,cv2.getPerspectiveTransform(points,target),(cw,ch),flags=cv2.INTER_CUBIC,borderMode=cv2.BORDER_REPLICATE)
    resized=cv2.resize(crop,(width,48)).astype(np.float32)
    tensor=((resized.transpose(2,0,1)/255.-.5)/.5)[None]
    result=session.run(None,{session.get_inputs()[0].name:tensor})[0]
    if result.ndim!=3 or result.shape[0]!=1 or result.shape[2]!=len(characters) or result.shape[1]>2048 or not np.isfinite(result).all():
        raise ValueError('OCR_RECOGNITION_OUTPUT_INVALID')
    return decode(result[0].argmax(axis=1).tolist(),result[0].max(axis=1).tolist(),characters)


def infer(plan, response):
    from ai_ad_editor.local_ocr import ENGINE, DET, REC, digest, verify_adapter
    from ai_ad_editor.utils import sha256_file
    from ai_ad_editor.ocr_geometry import ctc_decode
    from ai_ad_editor.yolo_worker import reject_external_tensors
    import numpy as np
    import cv2
    import onnx
    import onnxruntime as ort
    from fractions import Fraction
    ort.disable_telemetry_events();cv2.setNumThreads(plan['adapter']['threads'])
    source=plan['source'];adapter=plan['adapter'];programs={p['role']:p for p in plan['programs']}
    if not verify_adapter(adapter)['ok'] or 'sha256:'+sha256_file(Path(source['path']))!=source['sha256']:
        raise ValueError('OCR_INPUT_INTEGRITY_FAILED')
    for program in programs.values():
        if 'sha256:'+sha256_file(Path(program['path']))!=program['sha256']:
            raise ValueError('OCR_TOOL_CHANGED')
    sessions=[]
    for filename, rank in ((DET,4),(REC,3)):
        path=Path(adapter['model_path'])/filename
        graph=onnx.load(str(path),load_external_data=False)
        reject_external_tensors(graph,onnx);del graph
        options=ort.SessionOptions();options.intra_op_num_threads=adapter['threads'];options.inter_op_num_threads=1
        options.execution_mode=ort.ExecutionMode.ORT_SEQUENTIAL
        session=ort.InferenceSession(str(path),sess_options=options,providers=['CPUExecutionProvider'])
        inputs,outputs=session.get_inputs(),session.get_outputs()
        if session.get_providers()!=['CPUExecutionProvider'] or len(inputs)!=1 or len(outputs)!=1 or inputs[0].type!='tensor(float)' or len(inputs[0].shape)!=4 or inputs[0].shape[1]!=3 or len(outputs[0].shape)!=rank:
            raise ValueError('OCR_MODEL_SHAPE_UNSUPPORTED')
        sessions.append(session)
    detector,recognizer=sessions
    raw_chars=recognizer.get_modelmeta().custom_metadata_map.get('character','')
    if not raw_chars or len(raw_chars)>256_000:
        raise ValueError('OCR_MODEL_DICTIONARY_MISSING')
    characters=['']+raw_chars.splitlines()+[' ']
    if len(characters)!=recognizer.get_outputs()[0].shape[-1] or any(len(c)!=1 for c in characters[1:]):
        raise ValueError('OCR_MODEL_DICTIONARY_INVALID')
    fps=float(Fraction(source['fps']));indices=source['frame_indices']
    if source['kind']=='video':
        probe_command=[programs['ffprobe']['path'],'-v','error','-protocol_whitelist','file,pipe','-select_streams','v:0',
                       '-show_frames','-show_entries','frame=best_effort_timestamp_time','-of','json',source['path']]
        # File-backed output prevents an unbounded subprocess pipe allocation.
        with tempfile.TemporaryFile() as output, tempfile.TemporaryFile() as errors:
            p=subprocess.run(probe_command,stdin=subprocess.DEVNULL,stdout=output,stderr=errors,creationflags=subprocess.CREATE_NO_WINDOW)
            if p.returncode or output.tell()>16*1024**2:
                raise ValueError('OCR_CFR_PROBE_FAILED')
            output.seek(0);frames=json.load(output)['frames']
        pts=[float(f['best_effort_timestamp_time']) for f in frames]
        if len(pts)<=indices[-1] or len(pts)>36001 or any(not math.isfinite(t) or abs(t-i/fps)>.0015 for i,t in enumerate(pts)):
            raise ValueError('OCR_SOURCE_NOT_CFR')
    else:
        pts=[0.]
    select='+'.join(f'eq(n\\,{n})' for n in indices)
    command=[programs['ffmpeg']['path'],'-nostdin','-hide_banner','-loglevel','error','-protocol_whitelist','file,pipe','-noautorotate',
             '-i',source['path'],'-map','0:v:0','-an','-sn','-dn','-vf','select='+select,'-frames:v',str(len(indices)),
             '-fps_mode','passthrough','-pix_fmt','bgr24','-f','rawvideo','pipe:1']
    output_frames=[];recognitions=0
    with tempfile.TemporaryFile() as errors:
        process=subprocess.Popen(command,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=errors,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            expected=source['width']*source['height']*3
            for index in indices:
                raw=process.stdout.read(expected)
                if len(raw)!=expected:
                    raise ValueError('OCR_DECODE_INCOMPLETE')
                image=np.frombuffer(raw,np.uint8).reshape(source['height'],source['width'],3)
                boxes=[]
                for polygon,score in detect(image,detector,plan['limits']['det_max_edge'],np,cv2):
                    text,confidence=recognize(image,polygon,recognizer,characters,plan['limits']['rec_max_width'],np,cv2,ctc_decode)
                    recognitions+=1
                    if not text or confidence<.5:
                        continue
                    xs,ys=polygon[:,0],polygon[:,1]
                    boxes.append({'text':text,'confidence':confidence,'detection_score':score,'polygon':polygon.tolist(),
                                  'bbox':[float(xs.min()/source['width']),float(ys.min()/source['height']),
                                          float((xs.max()-xs.min())/source['width']),float((ys.max()-ys.min())/source['height'])]})
                output_frames.append({'frame_index':index,'pts_seconds':pts[index], 'decoded_bgr_sha256':'sha256:'+__import__('hashlib').sha256(raw).hexdigest(),'boxes':boxes})
            if process.stdout.read(1) or process.wait():
                raise ValueError('OCR_DECODE_FAILED')
        finally:
            if process.poll() is None:
                process.kill();process.wait()
            process.stdout.close()
    if not verify_adapter(adapter)['ok'] or 'sha256:'+sha256_file(Path(source['path']))!=source['sha256']:
        raise ValueError('OCR_INPUT_CHANGED')
    response.update(status='succeeded',engine=ENGINE,request_sha256=digest(plan),adapter_sha256=adapter['sha256'],source_sha256=source['sha256'],
                    frames=output_frames,device='cpu',providers=detector.get_providers(),detector_forwards=len(indices),recognizer_forwards=recognitions,
                    source_clock_frames_checked=len(pts),versions={'numpy':np.__version__,'opencv':cv2.__version__,'onnx':onnx.__version__,'onnxruntime':ort.__version__},
                    dictionary_characters=len(characters),decode_command_sha256=digest(command),
                    decode_protocol_whitelist=['file','pipe'],decode_stdout_format='rawvideo-bgr24')


def main():
    if sys.stdin.buffer.readline()!=b'run\n':
        return 2
    sys.dont_write_bytecode=True
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from ai_ad_editor.local_ocr import PROTOCOL
    from ai_ad_editor.yolo_worker import install_network_guard
    request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    response={'protocol':PROTOCOL,'status':'failed','network':'disabled','blocked_network_events':[]}
    start=time.monotonic()
    try:
        install_network_guard(response['blocked_network_events'])
        for key in ('TEMP','TMP','TMPDIR'):
            os.environ[key]=str(Path(request['runtime_root'])/'temp')
        tempfile.tempdir=os.environ['TEMP']
        infer(request['plan'],response)
        if response['blocked_network_events']:
            raise ValueError('OCR_NETWORK_ATTEMPT_REJECTED')
    except Exception as error:
        response.update(status='failed',error_type=type(error).__name__,message=str(error),traceback=traceback.format_exc()[-6000:])
    response['elapsed_seconds']=round(time.monotonic()-start,3)
    Path(request['response']).write_text(json.dumps(response,ensure_ascii=False,allow_nan=False,indent=2)+'\n',encoding='utf-8')
    return 0 if response['status']=='succeeded' else 1


if __name__=='__main__':
    raise SystemExit(main())
