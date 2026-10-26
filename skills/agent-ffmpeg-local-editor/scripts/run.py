"""Forward exact arguments to the pinned offline installation; never use source."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

MANIFEST = 'sha256:9fc746f1af66d40f96446ff327147995300f6996ce708db695361e26bfc0c239'
RELEASE = 'v0.1.0-alpha.4-local.24'


def launch():
    config = json.loads(Path(sys.argv[1]).read_bytes())
    installed = Path(config['installed_directory'])
    launcher = installed / 'run.py'
    receipt = json.loads((installed / 'receipt.json').read_bytes())
    if config['release'] != RELEASE or config['manifest_sha256'] != MANIFEST or receipt['manifest_sha256'] != MANIFEST:
        raise ValueError('Installed release does not match the Skill runtime pin')
    if not Path(sys.executable).samefile(config['python']) or sys.prefix != sys.base_prefix:
        raise ValueError('Use the registered native Python interpreter')
    if hashlib.sha256(launcher.read_bytes()).hexdigest() != config['launcher_sha256']:
        raise ValueError('Installed launcher changed; reinstall the reviewed release')
    env = dict(os.environ)
    temporary = installed / 'runtime/temp'
    temporary.mkdir(parents=True, exist_ok=True)
    env.update(TMP=str(temporary), TEMP=str(temporary), TMPDIR=str(temporary),
               AI_AD_EDITOR_RUNTIME_DIR=str(installed / 'runtime'),
               HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1')
    if config.get('community_config'):
        env['AEK_COMMUNITY_DEVICE_CONFIG'] = str(Path(config['community_config']).resolve(strict=True))
    command = [sys.executable, '-I', '-S', '-B', '-X', 'utf8', str(launcher), *sys.argv[2:]]
    # The CLI writes its JSON directly. No shell, re-parsing or source fallback.
    return subprocess.run(command, env=env, stdout=sys.stdout, stderr=sys.stderr,
                          creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0)).returncode


if __name__ == '__main__':
    try:
        code = launch()
    except (OSError, ValueError, KeyError, IndexError) as exc:
        print(json.dumps({'ok': False, 'status': 'failed', 'errors': [
            {'code': 'LOCAL_SKILL_RUNTIME_UNAVAILABLE', 'message': str(exc)}]}, ensure_ascii=False))
        code = 2
    raise SystemExit(code)
