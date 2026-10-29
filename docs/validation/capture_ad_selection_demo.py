"""Capture actual source CLI55 semantic-selection movies, GIFs and source credits."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/process-budget-20261029-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--cli-version', choices=('0.1.55', '0.1.56'), default='0.1.55')
    parser.add_argument('--source-run', default='r3')
    parser.add_argument('--run', default='r1')
    parser.add_argument('--evidence-series', default='process-budget-20261029-r1')
    args = parser.parse_args()
    assert all(s.replace('-', '').isalnum() for s in (args.source_run, args.run, args.evidence_series))
    base = ROOT/'docs/validation/evidence'/args.evidence_series
    case = base/('case-'+args.source_run)
    proof = json.loads((case/'verification.json').read_bytes())
    assert proof['status'] == 'passed' and proof['source_cli'] == args.cli_version
    assert proof['actual_GPU_semantic_search'] and proof['full_project_replay_equal']
    project = ROOT/'local/agent-ffmpeg'/('ad-selection-20261029-'+args.source_run)/'project'
    out = ROOT/'docs/assets'/('ad-selection-source'+args.cli_version.rsplit('.', 1)[1]+'-20261029-'+args.run)
    evidence = base/('demo-'+args.run)
    out.mkdir(parents=True, exist_ok=False)
    evidence.mkdir(exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    ffmpeg = shutil.which('ffmpeg')
    assert ffmpeg
    calls = []
    for variant in ('wide', 'vertical'):
        original = project/('renders/'+variant+'.mp4')
        movie = out/(variant+'.mp4')
        shutil.copyfile(original, movie)
        assert sha(original) == sha(movie)
        for kind, tail in [
            ('gif', ['-vf', 'fps=10,split[a][b];[a]palettegen[p];[b][p]paletteuse', '-loop', '0']),
            ('png', ['-ss', '0.5', '-frames:v', '1']),
        ]:
            command = [ffmpeg, '-nostdin', '-v', 'error', '-i', str(movie), *tail, str(out/(variant+'.'+kind))]
            result = subprocess.run(command, capture_output=True, timeout=120,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            (evidence/(variant+'-'+kind+'.stderr')).write_bytes(result.stderr)
            calls.append(dict(argv=command, exit_code=result.returncode))
            assert result.returncode == 0, result.stderr.decode('utf-8', 'replace')
    selection = json.loads((case/'select.stdout').read_bytes())['data']['selection']
    upstream = json.loads((ROOT/'docs/assets/semantic-package-20261025-r1/SOURCE.json').read_bytes())
    selected_ids = set(proof['selection'].values())
    credits = [row for row in upstream['assets'] if row['asset_id'] in selected_ids]
    assert len(credits) == 3 and all(row['license_spdx'] == 'CC0-1.0' for row in credits)
    metadata = json.loads((project/'project.json').read_bytes())
    # Keep the actual project rights record, not an invented publication grant.
    rights_files = sorted(project.glob('*rights*'))
    rights = {p.name: json.loads(p.read_bytes()) for p in rights_files if p.suffix == '.json'}
    assert rights, 'Missing project rights records'
    source = dict(cli_version=args.cli_version, generated_from_actual_case=True,
                  source_case=(case/'verification.json').relative_to(ROOT).as_posix(),
                  selected=proof['selection'], selected_image_credits=credits,
                  font_and_music_assets=[a for a in metadata['assets'] if a['id'] in ('font', 'music')],
                  project_rights=rights, selection_receipts=selection['selected'],
                  editable_package_local=str(project/'exports/editable.zip'),
                  editable_package_published=False, natural_quality_accepted=False,
                  independent_agent_benchmark=False,
                  files=[dict(path=p.name, bytes=p.stat().st_size, sha256=sha(p))
                         for p in sorted(out.iterdir()) if p.is_file()])
    (out/'SOURCE.json').write_text(json.dumps(source, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    (evidence/'calls.json').write_text(json.dumps(calls, indent=2)+'\n', encoding='utf-8', newline='\n')
    (evidence/'verification.json').write_text(json.dumps(dict(status='passed', actual_source_movies=2,
        gifs=2, frames=2, original_movie_bytes_equal=True, source_metadata=str(out/'SOURCE.json'),
        source_metadata_sha256=sha(out/'SOURCE.json'), broader_quality_claim=False), indent=2)+'\n', encoding='utf-8', newline='\n')
    print('Captured two actual movies, two GIFs and two frames with source/rights records.')


if __name__ == '__main__':
    main()
