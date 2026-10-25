"""Activate the verified native bundle and retain actual structured registration."""
from pathlib import Path
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation/evidence/motion-pack-20261025-r1/activation-r1'


def main():
    OUT.mkdir(exist_ok=False)
    (OUT / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    command = [sys.executable,'-I','-B','-u','-X','utf8',str(ROOT/'scripts/activate_community_runtime.py'),
        '--installed',str(ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.14/final-r1/installed'),
        '--packs',str(ROOT/'local/agent-ffmpeg/community-portable-r1/模型 包'),
        '--voice-cuda-lib','E:/dev/sandbox/模型配乐/ComfyUI_windows_portable/python_embeded/Lib/site-packages/torch/lib',
        '--translation-cuda-lib','C:/Program Files/NVIDIA GPU Computing Toolkit/CUDA/v12.4/bin',
        '--semantic-config',str(ROOT/'local/agent-ffmpeg/semantic-runtime.json')]
    result = subprocess.run(command,cwd=ROOT,capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
    (OUT/'activation.stdout.json').write_bytes(result.stdout); (OUT/'activation.stderr.txt').write_bytes(result.stderr)
    assert result.returncode == 0,result.stderr.decode('utf-8','replace')
    report = json.loads(result.stdout)
    assert report['status'] == 'configured' and len(report['verified_packs']) == 4
    for path in Path(report['evidence']).iterdir():
        if path.is_file():
            (OUT/path.name).write_bytes(path.read_bytes())
    command = ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
        str(ROOT/'register-agent-ffmpeg-local-skills.ps1'),'-ReceiptPath',str(OUT/'registration.json')]
    result = subprocess.run(command,cwd=ROOT,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
    (OUT/'registration.stdout.txt').write_bytes(result.stdout); (OUT/'registration.stderr.txt').write_bytes(result.stderr)
    assert result.returncode == 0
    registration = json.loads((OUT/'registration.json').read_bytes())
    assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve() == (ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    (OUT/'activation-and-registration.json').write_text(json.dumps(dict(status='passed',activation=report,
        registration=registration,source_fallback=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(status='activated-and-registered',release=report['release'],verified_packs=4)))


if __name__ == '__main__':
    main()
