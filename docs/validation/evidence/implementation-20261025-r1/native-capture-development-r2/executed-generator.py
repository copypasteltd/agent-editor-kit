"""Record only this script's generated test window, then close its owned player.

No desktop-wide capture, camera, microphone or browser is opened by this test.
The source is FFmpeg's generated test pattern; no unrelated application is read.
"""
from __future__ import annotations

import contextlib
import argparse
import ctypes
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import threading
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "product/src"), str(ROOT / "scripts")]
from ai_ad_editor.cli import main as cli_main
from ai_ad_editor.runtime import configure_local_runtime
from run_frozen_regression import frozen


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', default='r2')
    arguments = parser.parse_args()
    if arguments.run_id not in {'r2', 'r3', 'r4'}:
        raise ValueError('Choose an explicit owned rerun ID')
    evidence = ROOT / ("docs/validation/evidence/implementation-20261025-r1/native-capture-development-" + arguments.run_id)
    evidence.mkdir(parents=True, exist_ok=False)
    project = ROOT / ("workspace/implementation-capture-20261025-" + arguments.run_id)
    assert not project.exists()
    before = frozen()
    configure_local_runtime()
    calls = []
    def cli(*args, expect=True):
        output, error = io.StringIO(), io.StringIO()
        start = time.monotonic()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            code = cli_main(list(map(str, args)))
        response = json.loads(output.getvalue())
        calls.append({"args": list(map(str, args)), "exit_code": code, "result": response,
                      "stderr": error.getvalue(), "seconds": round(time.monotonic() - start, 3)})
        (evidence / f"{len(calls):02}.json").write_text(json.dumps(calls[-1], ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        assert (code == 0 and response['ok']) == expect, response
        print(json.dumps({"call": len(calls), "args": list(map(str, args[:2])), "exit_code": code}), flush=True)
        return response
    title = "aek-generated-capture-" + uuid.uuid4().hex
    player = None
    try:
        cli("project", "init", project)
        cli("capture", "devices")
        player = subprocess.Popen([shutil.which("ffplay"), "-hide_banner", "-loglevel", "error", "-f", "lavfi",
            "-i", "testsrc2=size=480x270:rate=15", "-an", "-window_title", title, "-autoexit", "-t", "90"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW)
        user = ctypes.windll.user32
        user.FindWindowW.argtypes = [ctypes.c_wchar_p, ctypes.c_wchar_p]
        user.FindWindowW.restype = ctypes.c_void_p
        user.SetWindowPos.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_uint]
        deadline = time.monotonic() + 12
        while time.monotonic() < deadline:
            hwnd = user.FindWindowW(None, title)
            if hwnd:
                user.SetWindowPos(hwnd, 0, 20, 20, 500, 320, 0x0040)
                break
            if player.poll() is not None:
                raise RuntimeError("Owned test-pattern player exited before capture")
            time.sleep(.1)
        else:
            raise RuntimeError("Owned test-pattern window did not appear")
        common = ["capture", "record", "--project", project, "--kind", "window", "--window-title", title,
                  "--duration-seconds", "2", "--fps", "15"]
        planned = cli(*common, "--asset-id", "planned", "--dry-run")
        assert planned['status'] == 'planned' and not (project / 'assets/captures/planned').exists()
        outputs = []
        for ident, encoder in [('cpu-window', 'libx264'), ('gpu-window', 'h264_nvenc')]:
            response = cli(*common, "--asset-id", ident, "--encoder", encoder)
            data = response['data']
            assert data['capture']['selected_encoder'] == encoder and data['capture']['full_decode']
            output = project / data['asset']['uri']
            frames = subprocess.run([shutil.which('ffmpeg'), '-v', 'error', '-nostdin', '-i', str(output),
                '-vf', 'scale=48:27', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'], capture_output=True, timeout=30)
            assert frames.returncode == 0 and len(frames.stdout) >= 2*48*27*3
            size = 48*27*3
            first, last = frames.stdout[:size], frames.stdout[-size:]
            assert first != last and max(first) - min(first) > 150, 'Capture must contain the changing generated pattern'
            outputs.append({'asset_id': ident, 'encoder': encoder, 'file': str(output),
                            'sha256': hashlib.sha256(output.read_bytes()).hexdigest(),
                            'frames': len(frames.stdout)//size, 'changing_pixels': True, 'full_decode': True})
        immutable = (project / 'project.json').read_bytes()
        cli(*common, '--asset-id', 'cpu-window', expect=False)
        assert (project / 'project.json').read_bytes() == immutable
        # Missing titles and pre-cancelled requests may not publish assets.
        cli('capture', 'record', '--project', project, '--kind', 'window', '--window-title', title+'-missing',
            '--duration-seconds', '1', '--encoder', 'libx264', '--asset-id', 'missing', expect=False)
        assert not (project / 'assets/captures/missing').exists()
        (project / 'cancel-capture').touch()
        cli(*common, '--cancel-file', 'cancel-capture', '--asset-id', 'cancelled', expect=False)
        assert not (project / 'assets/captures/cancelled').exists()
        running_cancel = project / 'cancel-running'
        timer = threading.Timer(.8, running_cancel.touch)
        timer.start()
        try:
            cli(*common, '--cancel-file', 'cancel-running', '--asset-id', 'cancelled-running', expect=False)
        finally:
            timer.cancel()
            timer.join(timeout=3)
        assert not (project / 'assets/captures/cancelled-running').exists()
        assert (project / 'project.json').read_bytes() == immutable
        cli('validate', '--project', project)
        after = frozen()
        assert before == after
        report = {'status': 'passed', 'development_source_only': True, 'installed_release_tested': False,
                  'commands': len(calls), 'outputs': outputs, 'frozen_equal': before == after,
                  'unrelated_windows_captured': False, 'microphone_opened': False, 'camera_opened': False,
                  'av_sync_accepted': False, 'human_viewing_accepted': False,
                  'source': 'FFmpeg testsrc2 in this script owned window',
                  'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
        (evidence / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    finally:
        if player and player.poll() is None:
            player.terminate()
            try:
                player.wait(timeout=10)
            except subprocess.TimeoutExpired:
                player.kill()
                player.wait(timeout=10)


if __name__ == '__main__':
    main()
