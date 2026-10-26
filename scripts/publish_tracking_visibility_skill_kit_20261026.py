"""Copy the verified local kit into the versioned documentation assets."""
import hashlib
import json
import argparse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',default='r1');args=ap.parse_args()
    assert args.run.replace('-','').isalnum()
    folder = ROOT/('local/agent-ffmpeg/tracking-visibility-kit-build-final-'+args.run)
    metadata = json.loads((folder/'package.json').read_bytes())
    assert metadata['cli_version'] == '0.1.31' and metadata['files'] == 111
    source = Path(metadata['archive'])
    data = source.read_bytes()
    assert hashlib.sha256(data).hexdigest() == metadata['sha256'] and len(data) == metadata['bytes']
    target = ROOT/'docs/skills/agent-editor-kit-community-unified-skill-r32.zip'
    receipt = ROOT/'docs/skills/community-unified-skill-package-0.1.31-r32.json'
    assert not target.exists() and not receipt.exists()
    target.write_bytes(data)
    metadata['archive'] = target.relative_to(ROOT).as_posix()
    receipt.write_text(json.dumps(metadata, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps(metadata, ensure_ascii=False))


if __name__ == '__main__':
    main()
