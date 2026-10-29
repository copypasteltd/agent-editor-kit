"""Stage an unregistered64 Skill from verified63 bytes and a verified candidate."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-generation-20261030-r1'
RELEASE = 'v0.1.0-alpha.4-local.62'
REFERENCE = '''# Native neural music / CLI0.1.64

Use this for local original instrumental music or explicit singing requests.
`music compose` remains the separate CPU score synthesizer. `music generate`
uses ACE-Step1.5 Turbo through an existing native ComfyUI core, without a GUI,
HTTP service, shared queue, Docker or WSL. Keep one public Skill entry.

The application bundle does not include the 10 GB model pack or the external
native Torch/ComfyUI environment. Register the four pinned safetensors and
that existing environment explicitly; do not substitute YuE2, a quantized
checkpoint or an online service. Model and native-core declarations/limits:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/NEURAL_MUSIC_GENERATION.md
The local pack contains diffusion_model.safetensors, text_encoder.safetensors,
language_model.safetensors and vae.safetensors with the exact built-in hashes.

Use the exact CLI0.1.64 launcher in this Skill. The registration evidence and
license reference must be local files. URLs in the source declaration are
research metadata, not runtime license arguments. Complete model, interpreter,
ComfyUI source/resource and implementation checks precede execution. Cold
integrity reads can take minutes and are distinct from GPU inference time.

```powershell
& $avk music generator-adapter register --project $project --adapter-id ace15 `
  --model-path $models --runtime-root $core --executable $nativePython --evidence $evidence
& $avk music generator-adapter inspect --project $project --adapter-id ace15
& $avk music inspect-generation --input $request
& $avk music generate --project $project --adapter-id ace15 --input $request `
  --new-asset-id music01 --dry-run
& $avk music generate --project $project --adapter-id ace15 --input $request `
  --new-asset-id music01
```

Request JSON uses format `agent-neural-music-v1`, prompt, explicit instrumental,
lyrics, duration_seconds, bpm, language, keyscale, timesignature, seed, steps and
generate_audio_codes. Keep the client's original prompt and lyrics. Prompt is
1..4000 characters; lyrics at most 12000. Instrumental requires empty lyrics;
singing requires nonempty lyrics and an explicit language. Schema support for
languages is not acceptance of pronunciation or exact lyric delivery.

Duration accepts 10..600 seconds in 0.04 second increments. Only an actual observed
range/device is a tested range; do not promise long-song quality from this bound.
Default 8 steps uses Euler/simple/CFG1/flow shift3/multiplier1. BPM 10..300, signature
2/3/4/6, key names such as D minor, nonnegative 63 bit seed. Set
generate_audio_codes explicitly when changing the language-model path.

Text, optional language-model, diffusion and VAE forwards must actually execute
on CUDA 0. CPU weight offload is allowed; CPU neural inference fallback is not.
The exact output is 48 kHz stereo Float32 WAV: no padding, looping, resampling,
normalization or cropping to pretend that the requested duration was generated.
Check the model forward counts/devices, native samples and full PCM roundtrip.

Listen to the complete local WAV before selecting it for a client. Preserve the
asset ID, request, model/runtime hashes, seed and actual sample count. Show real
auditions; a waveform card is not listening or music-quality acceptance. Review
phrasing, instrumentation, structure, lyric delivery and level separately.
Generated rights remain unverified/internal until explicitly reviewed; model
license declarations do not automatically approve an individual output.

After selection, use --apply --track-id TRACK for an unlocked independent audio
track; inspect overlaps first. The saved source.music_generation recipe is an
editable request/provenance record, not MIDI, stems or editable musical notes.
Use --recipe-asset-id music01 --new-asset-id music02 to rerun its original
request with the same model/runtime bytes; edit a new JSON for a new request.
Seeds do not guarantee identical bytes across devices or library versions.

Set --cancel-file, --timeout-seconds and --storage-budget-mib as needed. The
default 1800 second budget covers the worker/output checks after command preflight.
Keep original assets and snapshots; a new result uses a new ID. On failure,
inspect the bounded redacted diagnostic and verify process cleanup before retry.
Export a project package and replay the whole WAV/recipe/encoded AV. The package
retains external model pins; it does not silently bundle or download the models.
Natural listening, broad singing/language/style quality, clean-host setup and
complete CapCut equivalence remain separate acceptance work.
'''


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--candidate-run', default='r1')
    args = parser.parse_args()
    assert all(v.replace('-', '').isalnum() for v in (args.run, args.candidate_run))
    candidate = BASE / ('candidate-' + args.candidate_run) / 'verification.json'
    if not candidate.is_file():
        print(json.dumps(dict(status='pending', missing=['verified candidate'], mutated=False)), flush=True)
        return 2
    report = load(candidate)
    assert report['status'] == 'installed-and-byte-verified' and report['cli_version'] == '0.1.64'
    installed = Path(report['installed'])
    assert all(sha(Path(path)) == pin for path,pin in report['registered_files'].items())
    assert report['source_hashes'] == {p.name:sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
    namespace, runtime = ROOT / 'agent-ffmpeg-local-install-manifest.json', ROOT / 'local/agent-ffmpeg/runtime.json'
    current = load(namespace)
    assert current['cli_version'] == '0.1.63' and len(current['files']) == 93 and current['module_count'] == 17
    home = ROOT / 'local/agent-ffmpeg' / ('music64-skill-stage-' + args.run)
    home.mkdir()
    folder = home / 'skills/agent-ffmpeg-local-editor'
    for item in current['files']:
        source, target = ROOT / item['path'], home / item['path']
        assert sha(source) == item['sha256']
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    entry = folder / 'SKILL.md'
    text = entry.read_text(encoding='utf-8')
    old = '`v0.1.0-alpha.4-local.61` / CLI `0.1.63`'
    assert text.count(old) == 1
    text = text.replace(old, '`' + RELEASE + '` / CLI `0.1.64`', 1)
    text = text.replace('music/SFX and quality checks', 'CUDA neural music, score/SFX and quality checks', 1)
    text += '\nFor native CUDA neural music, actual auditions and editable generation requests, read [neural music](references/neural-music.md). Keep this separate from CPU score synthesis and loop DSP; inspect the tested scope and review the actual WAV.\n'
    entry.write_text(text, encoding='utf-8', newline='\n')
    (folder / 'references/neural-music.md').write_text(REFERENCE, encoding='utf-8', newline='\n')
    file = folder / 'references/runtime.md'
    text = file.read_text(encoding='utf-8').replace('v0.1.0-alpha.4-local.61', RELEASE).replace('CLI 0.1.63', 'CLI 0.1.64')
    file.write_text(text, encoding='utf-8', newline='\n')
    file = folder / 'references/community-materials.md'
    text = file.read_text(encoding='utf-8')
    text = text.replace('rewriting,neural music and automatic visual semantic matching remain open.',
                        'rewriting and automatic visual semantic matching remain open. For the separate native neural generator, read [neural music](neural-music.md).')
    text += '\nFor CUDA neural composition rather than score synthesis or loop DSP, read [neural music](neural-music.md). Show actual WAV auditions and preserve the generation recipe.\n'
    file.write_text(text, encoding='utf-8', newline='\n')
    file = folder / 'references/modules/local-models/module.md'
    text = file.read_text(encoding='utf-8')
    text += '\nFor native CUDA neural music, pinned ACE1.5 registration and actual auditions, read [neural music](../../neural-music.md). External model/runtime dependencies and musical quality remain separately verified.\n'
    file.write_text(text, encoding='utf-8', newline='\n')
    file = folder / 'scripts/run.py'
    text = file.read_text(encoding='utf-8')
    for name, value in [('RELEASE', RELEASE), ('MANIFEST', report['manifest_sha256'])]:
        text, count = re.subn(r'^' + name + r" = '[^']+'$", name + ' = ' + repr(value), text, flags=re.M)
        assert count == 1
    compile(text, str(file), 'exec')
    file.write_text(text, encoding='utf-8', newline='\n')
    config = copy.deepcopy(load(runtime))
    config.update(release=RELEASE, installed_directory=str(installed), manifest_sha256=report['manifest_sha256'],
                  launcher_sha256=sha(installed / 'run.py'))
    config_path = home / 'local/agent-ffmpeg/runtime.json'
    config_path.parent.mkdir(parents=True)
    save(config_path, config)
    files = {p.relative_to(folder).as_posix():sha(p) for p in folder.rglob('*') if p.is_file()}
    assert len(files) == 94 and sum(Path(p).name == 'SKILL.md' for p in files) == 1
    assert len(list((folder / 'references/modules').glob('*/module.md'))) == 17
    assert all(sha(Path(path)) == pin for path,pin in report['registered_files'].items())
    save(home / 'STAGING.json', dict(status='unregistered-candidate', cli_version='0.1.64',
        skill=str(folder), installed=str(installed), public_entries=1, module_count=17,
        files=files, candidate_sha256=sha(candidate), runtime_sha256=sha(config_path),
        formal_skill_unchanged=True, registered_files=report['registered_files'],
        requires_installed_regressions=True, requires_actual_PowerShell_generation=True,
        generated_audio_published=False, formal_activation=False))
    print(json.dumps(dict(status='unregistered-candidate', files=94, skill=str(folder), formal_activation=False)), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
