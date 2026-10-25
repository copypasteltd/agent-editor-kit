"""Retain dated activation and kit-verification helpers for the new delivery."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    for source, target in (
        ('activate_semantic_control_20261025.py', 'activate_ad_storyboard_20261025.py'),
        ('verify_semantic_control_skill_kit_20261025.py', 'verify_ad_storyboard_skill_kit_20261025.py'),
    ):
        data = (ROOT / 'scripts' / source).read_text('utf8')
        data = data.replace('evidence/semantic-control-20261025-r1', 'evidence/ad-storyboard-20261025-r1')
        data = data.replace('semantic-control-kit-', 'ad-storyboard-kit-')
        data = data.replace('single-entry r12 kit', 'single-entry r13 kit')
        data = data.replace('unified-skill-r12.zip', 'unified-skill-r13.zip')
        data = data.replace('0.1.13', '0.1.14')
        data = data.replace('v0.1.0-alpha.4-local.11/final-r1', 'v0.1.0-alpha.4-local.12/final-r2')
        output = ROOT / 'scripts' / target
        assert not output.exists(), output
        output.write_text(data, encoding='utf8', newline='\n')


if __name__ == '__main__':
    main()
