"""Native float texture and frame-clock experiment; not a product capability."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/opencl-projection-20261026-r1'

KERNEL = '''
#pragma OPENCL EXTENSION cl_khr_fp64 : enable
#pragma OPENCL FP_CONTRACT OFF
__kernel void copy_probe(write_only image2d_t destination, uint index,
                         read_only image2d_t source, read_only image2d_t parameters) {
    const int2 p = (int2)(get_global_id(0), get_global_id(1));
    const sampler_t nearest = CLK_NORMALIZED_COORDS_FALSE | CLK_ADDRESS_CLAMP_TO_EDGE | CLK_FILTER_NEAREST;
    const float marker = read_imagef(parameters, nearest, (int2)(3, 2)).x;
    const float4 input = read_imagef(source, nearest, p);
    const double value = (double)input.x;
    write_imagef(destination, p, (float4)(marker == 203.0f ? (float)value : NAN));
}
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    out = BASE/('preflight-'+args.run)
    out.mkdir(parents=True, exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    kernel = out/'copy.cl'
    kernel.write_text(KERNEL, encoding='utf8', newline='\n')
    calls = []
    def save(name, value):
        (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    def call(name, argv):
        process = subprocess.run(list(map(str, argv)), cwd=ROOT, capture_output=True, timeout=45,
                                 creationflags=subprocess.CREATE_NO_WINDOW)
        for label in ('stdout','stderr'):
            (out/(name+'.'+label)).write_bytes(getattr(process,label))
        calls.append(dict(id=name, argv=list(map(str,argv)), exit_code=process.returncode,
            stdout_bytes=len(process.stdout), stdout_sha256=hashlib.sha256(process.stdout).hexdigest(),
            stderr_sha256=hashlib.sha256(process.stderr).hexdigest()))
        save('calls.json', calls)
        print(json.dumps(dict(id=name, code=process.returncode)), flush=True)
        assert process.returncode == 0, process.stderr.decode('utf8','replace')[-4000:]
        return process.stdout
    report = dict(status='running', native_windows=True, virtualization=False, browser_ui=False,
                  started_at_utc=datetime.now(timezone.utc).isoformat(), product_integrated=False)
    save('verification.json',report)
    try:
        ffmpeg = shutil.which('ffmpeg')
        assert ffmpeg
        call('ffmpeg-version',[ffmpeg,'-version'])
        call('opencl-device',[ffmpeg,'-v','verbose','-nostdin','-init_hw_device','opencl=aek:0.0',
            '-f','lavfi','-i','nullsrc=s=2x2:d=0.04','-frames:v','1','-f','null','NUL'])
        special = (0.0, -0.0, 0.1, 0.5, 1.0, -2.5, 1023.0, 1e-40, 1e-45)
        data = b''.join(struct.pack('<f',special[(pixel+plane+frame)%len(special)])
                        for frame in range(8) for plane in range(4) for pixel in range(16*8))
        source = out/'input.gbrapf32le'
        source.write_bytes(data)
        inputs = ['-f','rawvideo','-pixel_format','gbrapf32le','-video_size','16x8','-framerate','10','-i',source]
        results=[]
        for name,clock in [('monotonic','N'),('repeat-backward','mod(N,2)')]:
            graph = f"[0:v]setpts='{clock}',split=2[s][p];[s]hwupload[sc];[p]scale=6:4:flags=neighbor," + \
                "geq=r='X+100*Y':g='X+100*Y':b='X+100*Y':a='X+100*Y',hwupload[pc];" + \
                f"[sc][pc]program_opencl=source='{kernel.relative_to(ROOT).as_posix()}':kernel=copy_probe:inputs=2:size=16x8," + \
                'hwdownload,format=gbrapf32le[v]'
            raw = call(name,[ffmpeg,'-v','error','-nostdin','-init_hw_device','opencl=aek:0.0',
                '-filter_hw_device','aek',*inputs,'-filter_complex',graph,'-map','[v]',
                '-frames:v','8','-fps_mode','passthrough','-f','rawvideo','pipe:1'])
            assert raw == data, (name,len(raw),len(data),sum(a!=b for a,b in zip(raw,data)))
            results.append(dict(clock=name,bytes=len(raw),bit_identical=True))
        report.update(status='passed',finished_at_utc=datetime.now(timezone.utc).isoformat(),
                      format='gbrapf32le', frames=8, raw_cases=results, fp64_kernel_compiled=True,
                      negative_and_gt_one_and_subnormal_preserved=True)
        save('verification.json', report)
        print(json.dumps(report,ensure_ascii=False),flush=True)
    except BaseException as exc:
        report.update(status='failed', error=repr(exc));save('verification.json', report)
        raise


if __name__ == '__main__':
    main()
