"""Build one self-contained, progressively loaded Skill from the reviewed 17 entries.

Keeps the split source directories and their provenance for historical reproduction.
Registration and packaging use only the unified manifest, never a directory glob.
"""
from pathlib import Path
import hashlib
import json
import re
import shutil

from readme_product_content import SKILLS

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / 'docs/validation/evidence/unified-skill-20261024-r1'
NAME = 'agent-ffmpeg-local-editor'
ENTRY = ROOT / 'skills' / NAME

INSTRUCTIONS = '''---
name: agent-ffmpeg-local-editor
description: "Edit and deliver local videos with agent editor kit: multitrack editing, keyframes, 500 filter previews, captions, audio, local model adapters and quality checks. Also use for ad planning, reference remakes, long-to-short clips, screen demos or supplied campaign data that feeds an edit."
---

# agent editor kit / unified local Skill

One public entry, 17 internal task modules. Select the relevant references below;
do not load every module or invoke separately registered specialist Skills.
The installed runtime is `v0.1.0-alpha.3` / CLI `0.1.2`.

## Runtime and common workflow

Read [runtime.md](references/runtime.md) for the installed-release contract and
response format. Use the pinned installation through this Skill's launcher:

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk doctor
& $avk capabilities
& $avk schema show
& $avk COMMAND --help
```

For an edit, turn the brief and actual local media into an explicit plan, ingest
assets, author a timeline, validate, preview, render, check the encoded output
and export an editable project package. Use returned asset/clip IDs. Audio needs
an explicit audio track. Planning-only requests do not require rendering.

## Choose the task references

MODULE_TABLE

For ordinary edits, start with editor/timeline and use quality for delivered
media. Add other modules when the request needs them. For example:

- Long interview to shorts: video-understand → long-to-short → timeline → quality.
- Product ad: ad-creative or content strategy → editor → timeline/template → quality.
- Client filter choice: [client-look-selection.md](references/client-look-selection.md)
  and [looks.md](references/looks.md); show actual candidate images, IDs, strength
  and license, record the chosen target, then test it on the client's footage.
- Local AI task: local-models plus the relevant media module; require existing
  registered dependencies and check actual inference artifacts.
- Campaign report: campaign-analytics; use its findings to propose an edit brief.

These are internal references, not separate registrations or autonomous agents.
Detailed source credits and licenses remain beside the relevant module resources.

## Execution invariants

- Use the installed release, never silently fall back to `product/src` or the
  source launcher. Missing dependencies are a reported capability gap.
- Native Windows tools only; no Docker, WSL, containers or virtual environments.
  Media and inference dependencies must already be local. No implicit downloads.
- Use argument arrays for paths, keep new artifacts in the owned project and
  preserve input files and existing output. Check exit code plus `ok`, `status`,
  `errors`, `warnings` and `artifacts`; a dry run is not a render.
- Consult installed capabilities and command help before using an effect or model.
  Candidate development commands are not installed release capabilities.
- Record actual source/license evidence. Unknown rights stay unverified;
  `render --publish` is a local rights gate, not an upload.
- Distinguish automatic decode/PCM checks, still inspection, continuous playback
  and human listening. This release has not achieved full CapCut parity.
- Close unused browser tabs after any separately used browser operation.
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    manifest_path = ROOT / 'agent-ffmpeg-local-install-manifest.json'
    current = json.loads(manifest_path.read_bytes())
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    snapshot = EVIDENCE / 'before-manifest.json'
    originals_path = EVIDENCE / 'source-instructions.json'
    if not snapshot.exists():
        if current['skill_count'] != 17 or current['format'] != 'agent-ffmpeg-local-skills-v1':
            raise ValueError('Expected the reviewed split namespace before the first consolidation')
        snapshot.write_bytes(manifest_path.read_bytes())
        save(originals_path, {r['name']: (ROOT / 'skills' / r['name'] / 'SKILL.md').read_text('utf-8')
                              for r in current['skills']})
    original = json.loads(snapshot.read_bytes())
    texts = json.loads(originals_path.read_bytes())
    definitions = {r[0]: r for r in SKILLS}
    modules = []
    table = ['| ID | Task / when to read | Internal reference |', '|---|---|---|']
    resource_records = []
    for index, row in enumerate(original['skills'], 1):
        suffix = row['name'].removeprefix('agent-ffmpeg-local-')
        source = ROOT / 'skills' / row['name']
        target = ENTRY / 'references/modules' / suffix
        target.mkdir(parents=True, exist_ok=True)
        content = texts[row['name']]
        if hashlib.sha256(content.encode('utf-8')).hexdigest() != row['skill_md_sha256']:
            raise ValueError('Original instruction hash changed: ' + row['name'])
        workflow = content.split('## Workflow\n\n', 1)[1].split('## Execution contract', 1)[0].strip()
        workflow = workflow.replace('to the corresponding `agent-ffmpeg-local-` Skills.',
                                    'to the relevant internal references linked from the unified entry.')
        workflow = workflow.replace('for the editor Skill', 'for the editor module')
        workflow = workflow.replace('to the ad/editor Skills', 'to the ad/editor modules')
        workflow = workflow.replace('This Skill edits recordings', 'This module edits recordings')
        workflow = workflow.replace('this Skill provides', 'this module provides')
        module = '# ' + row['purpose_zh'] + ' / ' + suffix + '\n\n'
        module += '[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)\n\n'
        definition = definitions[suffix]
        module += definition[4] + '\n\nCommands: `' + definition[5] + '`. ' + definition[7] + '\n\n'
        module += '## Workflow\n\n' + workflow + '\n\n'
        if suffix in {'editor', 'timeline', 'quality', 'rights-ledger'}:
            module += ('For looks and client choices, read [looks](../../looks.md) and '
                       '[actual visual selection](../../client-look-selection.md).\n\n')
        if source != ENTRY and (source / 'references').is_dir():
            for path in sorted((source / 'references').rglob('*')):
                if not path.is_file() or '__pycache__' in path.parts:
                    continue
                destination = target / path.relative_to(source)
                destination.parent.mkdir(parents=True, exist_ok=True)
                data = path.read_bytes()
                source_hash = hashlib.sha256(data).hexdigest()
                changes = []
                if path.suffix == '.md':
                    text = data.decode('utf-8')
                    # The inherited project-policy link was already broken before
                    # the move. Bind the relocated reference to the real contract.
                    policy = 'Read the [local project policy](../../docs/specs/本地运行策略与远程引用审计契约_v0.1_2026-10-14.md) before running this local workflow.'
                    if policy in text:
                        import os
                        relative = Path(os.path.relpath(ENTRY / 'references/runtime.md', destination.parent)).as_posix()
                        text = text.replace(policy, 'Local execution follows the [installed runtime contract](' + relative + '). Older command examples are references, not permission to change runtimes.')
                        data = text.encode('utf-8')
                        changes.append('Rebind inherited broken project-policy link to the shared runtime contract')
                    old_contract = '../../docs/specs/本地HDemucs人声伴奏分离契约_v0.1_2026-10-16.md'
                    if old_contract in text:
                        import os
                        relative = Path(os.path.relpath(ENTRY / 'references/modules/local-models/module.md', destination.parent)).as_posix()
                        text = text.replace(old_contract, relative)
                        data = text.encode('utf-8')
                        changes.append('Rebind inherited missing separation contract to the local-models module')
                destination.write_bytes(data)
                resource_records.append({'source': path.relative_to(ROOT).as_posix(),
                                         'source_sha256': source_hash,
                                         'path': destination.relative_to(ROOT).as_posix(),
                                         'sha256': sha(destination), 'changes': changes})
            module += ('## Attributed resources\n\n[Upstream workflow](references/upstream/workflow.md) '
                       'retains author, source commit and license. Use specific frameworks/helpers only '
                       'when relevant; inspect their inputs and dependencies first. The shared runtime '
                       'contract governs execution.\n')
        path = target / 'module.md'
        path.write_text(module.rstrip() + '\n', encoding='utf-8', newline='\n')
        relative = path.relative_to(ENTRY).as_posix()
        modules.append({'id': f'K{index:02}', 'key': suffix, 'purpose_zh': row['purpose_zh'],
                        'purpose_en': definition[2], 'reference': relative,
                        'previous_skill': row['name'], 'previous_skill_md_sha256': row['skill_md_sha256']})
        table.append(f'| K{index:02} | {definition[2]} / {definition[1]} | [{suffix}]({relative}) |')
    (ENTRY / 'SKILL.md').write_text(INSTRUCTIONS.replace('MODULE_TABLE', '\n'.join(table)), encoding='utf-8', newline='\n')
    shutil.copyfile(ROOT / 'LICENSE', ENTRY / 'LICENSE')
    ui = ENTRY / 'agents/openai.yaml'
    text = ui.read_text('utf-8').replace('Agent FFmpeg Local Editor', 'agent editor kit')
    text = text.replace('Build and deliver local video edits', 'One entry for 17 local video workflows')
    text = text.replace('to edit advertising videos or assemble a local Agent Project using the installed agent editor kit CLI.',
                        'to plan, edit, preview and deliver a local video, selecting the relevant internal task modules.')
    ui.write_text(text, encoding='utf-8', newline='\n')
    runtime = ENTRY / 'references/runtime.md'
    text = runtime.read_text('utf-8').replace('The namespace manifest lists all 17 entries. Legacy `video-cut-` Skills are separate.',
        'The namespace manifest registers only `$agent-ffmpeg-local-editor`; its 17 modules are internal references. '
        'The registrar retires only this checkout\'s 16 previous specialist junctions. Legacy `video-cut-` Skills are separate.')
    runtime.write_text(text, encoding='utf-8', newline='\n')
    files = [{'path': p.relative_to(ROOT).as_posix(), 'bytes': p.stat().st_size, 'sha256': sha(p)}
             for p in sorted(ENTRY.rglob('*')) if p.is_file() and '__pycache__' not in p.parts and p.suffix not in {'.pyc', '.pyo'}]
    save(manifest_path, {'format': 'agent-ffmpeg-local-skills-v2', 'status': 'reviewed',
        'registration_mode': 'single', 'release': original['release'],
        'manifest_sha256': original['manifest_sha256'], 'runtime_config': original['runtime_config'],
        'skill_count': 1, 'module_count': len(modules), 'look_count': 500,
        'look_catalog_version': original['look_catalog_version'],
        'skills': [{'name': NAME, 'purpose_zh': '唯一入口：按需读取 17 项内部模块并调用已安装版',
                    'skill_md_sha256': sha(ENTRY / 'SKILL.md')}],
        'modules': modules, 'files': files,
        'retired_skills': [{'name': r['name'], 'skill_md_sha256': r['skill_md_sha256']}
                           for r in original['skills'] if r['name'] != NAME]})
    save(EVIDENCE / 'consolidation.json', {'status': 'built', 'source_namespace': original['format'],
        'registered_skill_count': 1, 'internal_module_count': len(modules),
        'source_snapshot': originals_path.relative_to(ROOT).as_posix(), 'source_snapshot_sha256': sha(originals_path),
        'relocated_resources': resource_records,
        'original_specialist_sources_preserved': True,
        'runtime_modified': False, 'runtime_release': original['release']})
    print(json.dumps({'status': 'built', 'registered_skills': 1, 'modules': len(modules),
                      'files': len(files), 'resources': len(resource_records)}))


if __name__ == '__main__':
    main()
