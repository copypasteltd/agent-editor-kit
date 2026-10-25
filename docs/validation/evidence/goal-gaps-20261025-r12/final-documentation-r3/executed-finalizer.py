"""Append a final documentation audit while retaining the initial audit unchanged."""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import re

import assess_goal_gaps_20261025_r12 as review


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--revision', default='r3')
    args = parser.parse_args()
    assert re.fullmatch(r'r[1-9][0-9]*', args.revision)
    original = review.OUT
    final = original / ('final-documentation-' + args.revision)
    final.mkdir(exist_ok=False)
    copies = []
    for name in ('inventory.json', 'installed-source-comparison.json',
                 'logs/capabilities.stdout.json'):
        source = original / name
        (final / name).parent.mkdir(parents=True, exist_ok=True)
        with (final / name).open('xb') as stream:
            stream.write(source.read_bytes())
        assert review.digest(source) == review.digest(final / name)
        copies.append(dict(source=source.relative_to(review.ROOT).as_posix(),
                           sha256=review.digest(source)))
    with (final / 'executed-finalizer.py').open('xb') as stream:
        stream.write(Path(__file__).read_bytes())
    record = dict(started_at_utc=datetime.now(timezone.utc).isoformat(),
                  output_override=final.relative_to(review.ROOT).as_posix(),
                  original_receipts=copies, source=Path(__file__).name,
                  initial_audit_preserved=True, product_source_changed=False)
    review.OUT = final
    try:
        review.audit()
    except Exception as exc:
        record['status'] = 'failed'
        record['error'] = str(exc)
        with (final / 'finalizer-verification.json').open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(record, stream, ensure_ascii=False, indent=2)
            stream.write('\n')
        raise
    record['status'] = 'passed'
    record['finished_at_utc'] = datetime.now(timezone.utc).isoformat()
    with (final / 'finalizer-verification.json').open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(record, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


if __name__ == '__main__':
    main()
