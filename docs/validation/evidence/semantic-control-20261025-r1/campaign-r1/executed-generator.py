"""Sequential real-model regression using the original frozen query protocol."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-control-20261025-r1'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', type=Path, required=True)
    args = parser.parse_args()
    out = BASE / 'campaign-r1'; out.mkdir(parents=True, exist_ok=False)
    (out / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report = dict(status='running', started_at_utc=datetime.now(timezone.utc).isoformat(), calls=[])
    steps = [('setup','cuda'),('index','cuda'),('calibrate','cuda'),('calibrate','cpu'),
        ('before','cuda'),('before','cpu'),('roundtrip','cuda'),('after','cuda'),('after','cpu')]
    def save():
        (out / 'verification.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8', newline='\n')
    save()
    try:
        for phase, device in steps:
            name = phase + '-' + device
            command = [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
                str(ROOT / 'scripts/run_semantic_control_normal_20261025.py'), '--installed', str(args.installed),
                '--run', 'installed-r1', '--phase', phase, '--device', device]
            print(name + ' started', flush=True)
            with (out / (name+'.log')).open('xb') as stream:
                result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT,
                    timeout=2400, creationflags=subprocess.CREATE_NO_WINDOW)
            report['calls'].append(dict(phase=phase, device=device, argv=command, exit_code=result.returncode))
            save()
            assert result.returncode == 0, name
            print(name + ' completed', flush=True)
        report.update(status='completed-with-existing-quality-limits', finished_at_utc=datetime.now(timezone.utc).isoformat())
        save()
    except BaseException as exc:
        report.update(status='failed', error=repr(exc)); save(); raise


if __name__ == '__main__':
    main()
