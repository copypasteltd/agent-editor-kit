"""Sequential native validation phases; each phase preserves its own receipt."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', required=True)
    parser.add_argument('--section', choices=('normal', 'faults', 'migration'), required=True)
    args = parser.parse_args()
    common = [sys.executable, '-E', '-B', '-u', '-X', 'utf8']
    if args.section == 'normal':
        phases = [('index', 'cuda'), ('calibrate', 'cuda'), ('calibrate', 'cpu'), ('before', 'cuda'), ('before', 'cpu')]
    elif args.section == 'migration':
        phases = [('roundtrip', 'cuda'), ('after', 'cuda'), ('after', 'cpu')]
    else:
        phases = [('index-publication', None), ('calibration-publication', None), ('calibration-commit', None),
            ('search-hard-stop', None), ('search-cancel', None), ('search-timeout', None), ('cleanup', None)]
    for phase, device in phases:
        if device:
            argv = common + [str(ROOT / 'scripts/run_semantic_recovery_normal_20261025.py'),
                '--installed', args.installed, '--run', 'installed-r1', '--phase', phase, '--device', device]
        else:
            argv = common + [str(ROOT / 'scripts/run_semantic_recovery_faults_20261025.py'),
                '--installed', args.installed, '--run', 'faults-r1', '--case', phase]
        print(json.dumps(dict(section=args.section, phase=phase, device=device, state='starting')), flush=True)
        result = subprocess.run(argv, cwd=ROOT, timeout=1800, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise SystemExit(result.returncode)
    print(json.dumps(dict(section=args.section, status='terminal-passed')), flush=True)


if __name__ == '__main__': main()
