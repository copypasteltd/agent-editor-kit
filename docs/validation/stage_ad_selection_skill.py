"""Prepare a pinned E-drive CLI54 Skill candidate without changing registration."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/ad-selection-20261029-r1'
REFERENCE = '''# Calibrated semantic ad selection

Use installed CLI0.1.54 or newer through this unified Skill launcher. Start
with `version` and `capabilities`; `ai.ad_storyboard` must include `ad.select`.
This connects sampled visual retrieval to ordinary editable ad plans. The
caller still supplies approved factual copy, intended audience, music and
variants. Similarity is not evidence for a product claim or whole-shot action.

## Prepare the library and request

Register a local semantic adapter, build an index and calibrate it against
explicit licensed positive/negative examples. Use the same actual device and
device index for calibration and selection. Prefer CUDA when available; a CPU
fallback cannot silently use a CUDA acceptance profile. Read the semantic
module for model registration, dependencies, budgets and rights.

The JSON input wraps the existing storyboard brief:

```json
{
  "brief": {
    "id":"campaign", "product":"Approved product", "audience":"Approved audience",
    "cta":"Approved call to action", "caption_style":{"font_asset_id":"font"},
    "shots":[{"id":"opening","text":"Approved factual caption"}],
    "variants":[{"id":"vertical","canvas":{"width":1080,"height":1920},"duration_seconds":6}]
  },
  "queries":[{"id":"opening","text":"A cup of coffee on a table"}],
  "unique_assets":true
}
```

Replace example IDs with registered project assets. A queried shot omits
`asset_id` and `source_in_tick`; fixed shots can still declare them. Query IDs
match shot IDs. Optional include/exclude clauses use the semantic query
contract. Keep a candidate limit large enough for competing shots (current
CLI limit1..20); a candidate omitted by that limit cannot be assigned.

## Select, build and review

Using `$avk` as defined in SKILL.md:

```powershell
& $avk ad select --project E:/video-work/demo --input E:/video-work/demo/brief.json `
  --output E:/video-work/demo/validation/selected.json --index-id visual `
  --calibration-id accepted-cuda --device cuda --kind image --limit 20 --dry-run
```

Dry-run checks the request and index/profile binding; it returns no selected
plan and performs no model forward. Run the same command without `--dry-run`
to select. Set an explicit adequate `--timeout-seconds` for model/artifact
loading; a timed-out attempt is a failure, not a selection receipt.

```powershell
& $avk ad build --project E:/video-work/demo --input E:/video-work/demo/validation/selected.json
```

Selection filters current source hashes, verified rights status, required
source audio and source length across every requested variant, then maximizes
the quantized similarity sum globally. Default uniqueness is asset IDs, not
content hashes: aliases with different IDs can still repeat the same picture.
Use `unique_assets:false` only when deliberate reuse is appropriate.

Inspect each shot's rationale receipt: original query, index/profile IDs,
source hash/start, score, required duration and preview reference. Validate
and render every variant, show actual previews to the client and use ordinary
`ad revise` for targeted changes. Preserve editable exports and verify complete
decoded video/PCM when package replay matters. Existing500-look previews are
available for an independent style selection; they are not semantic evidence.

A verified rights record is not publication clearance. Check permitted uses,
restrictions and source licenses before sharing the selected media. Calibrated
similarity is empirical, not a no-error guarantee. Review the complete shot,
copy, crop, rhythm and audio; natural ad quality and full parity are separate.

Full contracts and maintained examples:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/AD_SEMANTIC_SELECTION.md
'''


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--cli-version', choices=('0.1.54', '0.1.55', '0.1.56'), default='0.1.54')
    parser.add_argument('--evidence-series', default='ad-selection-20261029-r1')
    parser.add_argument('--installation-run', default='r2')
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    assert args.evidence_series.replace('-', '').isalnum() and args.installation_run.replace('-', '').isalnum()
    base = ROOT/'docs/validation/evidence'/args.evidence_series
    namespace = ROOT/'agent-ffmpeg-local-install-manifest.json'
    original = namespace.read_bytes()
    manifest = json.loads(original)
    assert manifest['cli_version'] == '0.1.53' and manifest['skill_count'] == 1
    assert manifest['module_count'] == 17 and len(manifest['files']) == 92
    installation = json.loads((base/('installation-candidate-'+args.installation_run)/'verification.json').read_bytes())
    assert installation['status'] == 'installed-and-byte-verified' and installation['source_file_count'] == 281
    assert installation['cli_version'] == args.cli_version
    release = Path(installation['installed']).parent.parent.name
    assert release == {'0.1.54':'v0.1.0-alpha.4-local.52', '0.1.55':'v0.1.0-alpha.4-local.53',
                       '0.1.56':'v0.1.0-alpha.4-local.54'}[args.cli_version]
    groups = [('selection', 45), ('semantic', 104)]
    if args.cli_version in ('0.1.55', '0.1.56'):
        groups.append(('deadline', 15))
    if args.cli_version == '0.1.56':
        groups.append(('bootstrap', 1))
    for group, count in groups:
        gate = json.loads((base/('installed-'+group+'-r1')/'verification.json').read_bytes())
        assert gate['status'] == 'passed' and gate['tests'] == count and gate['frozen_equal']
        assert Path(gate['installed']).resolve() == Path(installation['installed']).resolve()
    stage = ROOT/'local/agent-ffmpeg'/('ad-selection-skill-stage-'+args.run)
    stage.mkdir(parents=True, exist_ok=False)
    for row in manifest['files']:
        relative = Path(row['path'])
        assert not relative.is_absolute() and '..' not in relative.parts
        assert relative.parts[:2] == ('skills', 'agent-ffmpeg-local-editor')
        content = (ROOT/relative).read_bytes()
        assert len(content) == row['bytes'] and hashlib.sha256(content).hexdigest() == row['sha256']
        target = stage/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    skill = stage/'skills/agent-ffmpeg-local-editor'
    for relative in ('SKILL.md', 'references/runtime.md'):
        path = skill/relative
        text = path.read_text('utf-8').replace('v0.1.0-alpha.4-local.51', release).replace('0.1.53', args.cli_version)
        if relative == 'SKILL.md':
            text = text.replace('semantic search, voice/translation', 'calibrated semantic ad selection, semantic search, voice/translation', 1)
            needle = 'Native Float32 GPU operations'
            assert needle in text
            text = text.replace(needle, 'For calibrated visual selection into editable ads, read\n[semantic ad selection](references/ad-selection.md). Inspect actual previews\nand per-shot receipts before client approval; asset-ID uniqueness does not\nexclude duplicate content aliases.\n'+needle, 1)
        path.write_text(text, encoding='utf-8', newline='\n')
        if relative == 'references/runtime.md' and args.cli_version in ('0.1.55', '0.1.56'):
            with path.open('a', encoding='utf-8', newline='\n') as stream:
                stream.write('\nNative process waits under an operation budget now inherit ancestor deadlines and cancel markers. Interruption closes the owned Windows job/readers. This is cooperative control, not blocked-OS-call real-time preemption. Semantic implementation changes require explicit re-registration/reindexing; never hand-rebind old hashes.\n')
    reference = REFERENCE
    if args.cli_version in ('0.1.55', '0.1.56'):
        reference += '\nCLI55 inherits command budgets while waiting for native processes. Keep cold-load latency separate from neural inference time; preserve failures and use an explicit adequate budget, not a retuned acceptance threshold.\n'
    if args.cli_version == '0.1.56':
        reference = reference.replace('Use installed CLI0.1.54 or newer', 'Use installed CLI0.1.56 or newer')
        note = '\nCLI56 pins its own application package, then restores the native model runtime dependency search order. Controller-bundled NumPy/Pillow must not silently replace the registered model runtime. Keep runtime/version/path fingerprint checks enabled; register fresh implementation bindings after code changes.\n'
        reference += note
        with (skill/'references/runtime.md').open('a', encoding='utf-8', newline='\n') as stream:
            stream.write(note)
    (skill/'references/ad-selection.md').write_text(reference, encoding='utf-8', newline='\n')
    path = skill/'scripts/run.py'
    text = path.read_text('utf-8')
    text, count = re.subn(r"^MANIFEST = '[^']+'$", 'MANIFEST = '+repr(installation['manifest_sha256']), text, count=1, flags=re.M)
    assert count == 1
    text, count = re.subn(r"^RELEASE = '[^']+'$", 'RELEASE = '+repr(release), text, count=1, flags=re.M)
    assert count == 1
    path.write_text(text, encoding='utf-8', newline='\n')
    files = [p for p in skill.rglob('*') if p.is_file()]
    assert len(files) == 93 and sum(p.name == 'SKILL.md' for p in files) == 1
    assert namespace.read_bytes() == original
    assert all(sha(ROOT/r['path']) == r['sha256'] for r in manifest['files'])
    report = dict(status='unregistered-candidate', cli_version=args.cli_version, skill=str(skill),
        live_skill_changed=False, source_fallback=False, public_entries=1, modules=17,
        files=93, runtime_manifest_sha256=installation['manifest_sha256'],
        requires_actual_installed_case_before_activation=True)
    (stage/'STAGING.json').write_text(json.dumps(report, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
