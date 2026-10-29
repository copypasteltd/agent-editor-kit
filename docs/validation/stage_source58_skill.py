"""Stage one CLI58 Skill only after independent installation and actual cases pass."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/ad-content-uniqueness-20261029-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--installation-run', default='r1')
    parser.add_argument('--gate-run', default='r1')
    args = parser.parse_args()
    assert all(x.replace('-', '').isalnum() for x in [args.run, args.installation_run, args.gate_run])
    installation = load(BASE/('installation-candidate-'+args.installation_run)/'verification.json')
    assert installation['status'] == 'installed-and-byte-verified'
    assert installation['cli_version'] == '0.1.58' and installation['source_file_count'] == 281
    installed = Path(installation['installed']).resolve()
    release = 'v0.1.0-alpha.4-local.56'
    assert installed.is_relative_to((ROOT/'local/agent-ffmpeg'/release).resolve())
    gate_paths = []
    for group, count in [('bootstrap', 31), ('selection', 57), ('control', 19), ('semantic', 104), ('contracts', 400)]:
        path = BASE/('installed58-'+group+'-'+args.gate_run)/'verification.json'
        gate = load(path)
        assert gate['status'] == 'passed' and gate['cli_version'] == '0.1.58'
        assert gate['tests'] == count and gate['frozen_equal'] and gate['source_and_installed_equal']
        assert Path(gate['installed']).resolve() == installed
        assert gate['failures'] == gate['errors'] == gate['skipped'] == 0
        assert all(sha(ROOT/name) == pin for name, pin in gate['file_hashes'].items())
        gate_paths.append(path)
    gpu_path = BASE/('installed58-gpu-'+args.gate_run)/'verification.json'
    gpu = load(gpu_path)
    assert gpu['status'] == 'passed' and gpu['actual_CUDA_model']
    assert gpu['installed_actual_CUDA_case_accepted'] and gpu['complete_PCM_replay_equal']
    assert gpu['complete_source_installed_PCM_equal'] and Path(gpu['installed']).resolve() == installed
    content_path = BASE/('installed-content-case-'+args.gate_run)/'verification.json'
    content = load(content_path)
    assert content['status'] == 'passed' and content['cli_version'] == '0.1.58'
    assert content['independent_installed_case'] and content['complete_RGBA_replay_equal']
    assert Path(content['installed']).resolve() == installed
    gate_paths += [gpu_path, content_path]
    source = ROOT/'product/src/ai_ad_editor'
    source_pins = {p.name:sha(p) for p in source.glob('*.py')}
    assert len(source_pins) == 281
    assert source_pins == {p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
    namespace = ROOT/'agent-ffmpeg-local-install-manifest.json'
    runtime = ROOT/'local/agent-ffmpeg/runtime.json'
    protected = {namespace:sha(namespace), runtime:sha(runtime)}
    manifest = load(namespace)
    assert manifest['cli_version'] == '0.1.56' and manifest['skill_count'] == 1
    assert manifest['module_count'] == 17 and len(manifest['files']) == 93
    files = []
    for row in manifest['files']:
        relative = Path(row['path'])
        assert not relative.is_absolute() and '..' not in relative.parts
        assert relative.parts[:2] == ('skills', 'agent-ffmpeg-local-editor')
        original = ROOT/relative
        assert original.stat().st_size == row['bytes'] and sha(original) == row['sha256']
        protected[original] = row['sha256']
        files.append(relative)
    gate_pins = {str(p):sha(p) for p in gate_paths}
    stage = ROOT/'local/agent-ffmpeg'/('content58-skill-stage-'+args.run)
    stage.mkdir(exist_ok=False)
    for relative in files:
        target = stage/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((ROOT/relative).read_bytes())
    skill = stage/'skills/agent-ffmpeg-local-editor'
    path = skill/'SKILL.md'
    text = path.read_text(encoding='utf-8')
    text = text.replace('`v0.1.0-alpha.4-local.54` / CLI `0.1.56`', '`'+release+'` / CLI `0.1.58`', 1)
    old = 'and per-shot receipts before client approval; asset-ID uniqueness does not\nexclude duplicate content aliases.'
    assert old in text
    text = text.replace(old, 'and per-shot receipts before client approval. CLI58 defaults to exact-source\nSHA256 uniqueness; this excludes byte-identical aliases, not perceptually\nsimilar shots. The reference explains explicit reuse and actual previews.', 1)
    path.write_text(text, encoding='utf-8', newline='\n')
    path = skill/'references/ad-selection.md'
    text = path.read_text(encoding='utf-8').replace('Use installed CLI0.1.56 or newer', 'Use installed CLI0.1.58 or newer', 1)
    text = text.replace('"unique_assets":true', '"unique_assets":true,\n  "unique_content":true', 1)
    old = ('the quantized similarity sum globally. Default uniqueness is asset IDs, not\n'
           'content hashes: aliases with different IDs can still repeat the same picture.\n'
           'Use `unique_assets:false` only when deliberate reuse is appropriate.')
    assert old in text
    text = text.replace(old, '''the quantized similarity sum globally. CLI58 groups exact source SHA256
aliases before joint assignment, and reserves the content of fixed shots.
`unique_content` defaults to `unique_assets` (normally true). Set
`unique_content:false` with `unique_assets:true` for the old ID-only behavior;
set both false for deliberate reuse. Both options require actual booleans.
Missing or malformed SHA256 cannot silently fall back to asset IDs.
This is exact file identity, not perceptual or cross-transcode deduplication.''', 1)
    text += '''
## Explain source selection to a client

Inspect `uniqueness_group`, source SHA256 and the original preview reference.
Show the actual selected source, crop and complete shot before approval.
The C74 demonstration has real byte-identical aliases, default/ID-only
selection, editable timelines and120-frame complete RGBA package replay:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/validation/CLI58内容去重实测_2026-10-29.md
Its search scores are explicitly synthetic; do not present it as model or
natural-semantic accuracy. A low score, absent candidate or inadequate
candidate limit cannot be repaired by inventing a preview or selection.
'''
    path.write_text(text, encoding='utf-8', newline='\n')
    path = skill/'references/runtime.md'
    text = path.read_text(encoding='utf-8').replace('v0.1.0-alpha.4-local.54', release)
    text = text.replace('CLI 0.1.56', 'CLI 0.1.58', 1)
    text += '\nCLI58 waits retained owned Windows process handles during cleanup; preprocessing tool deadlines map to pipeline TIMEOUT while outer budget interruptions retain their original meaning. Native model dependencies remain isolated. See complete failure and repair evidence in docs/product/OWNED_PROCESS_CLEANUP.md; do not classify a timed-out job as completed.\n'
    path.write_text(text, encoding='utf-8', newline='\n')
    path = skill/'scripts/run.py'
    text = path.read_text(encoding='utf-8')
    for key, value in [('MANIFEST', installation['manifest_sha256']), ('RELEASE', release)]:
        text, count = re.subn(r'^'+key+r" = '[^']+'$", key+' = '+repr(value), text, count=1, flags=re.M)
        assert count == 1
    path.write_text(text, encoding='utf-8', newline='\n')
    candidate = [p for p in skill.rglob('*') if p.is_file()]
    assert len(candidate) == 93 and sum(p.name == 'SKILL.md' for p in candidate) == 1
    assert all(sha(p) == pin for p, pin in protected.items())
    assert gate_pins == {p:sha(Path(p)) for p in gate_pins}
    report = dict(status='unregistered-candidate', cli_version='0.1.58', skill=str(skill),
        live_skill_changed=False, public_entries=1, modules=17, files=93,
        runtime_manifest_sha256=installation['manifest_sha256'], gates=gate_pins,
        requires_actual_staged_entry_case_before_activation=True)
    (stage/'STAGING.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
