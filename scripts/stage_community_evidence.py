"""Copy non-audio evidence from the final installed workflows into docs/."""
from pathlib import Path
import hashlib
import json
import shutil

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'product/.runtime/materials-20261024'
EVIDENCE = ROOT / 'docs/validation/evidence/community-materials-20261025-r1'


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def receipts(source, target):
    source, target = source.resolve(strict=True), target.resolve()
    if not source.is_relative_to(ROOT) or not target.is_relative_to(EVIDENCE):
        raise ValueError('Evidence must remain in the owned workspace')
    target.mkdir(parents=True, exist_ok=True)
    for path in source.rglob('*'):
        if not path.is_file() or path.suffix.lower() not in {'.json', '.txt', '.log', '.png'}:
            continue
        # Media, restored packages, fault-pack contents and project source media
        # remain local. Receipts and requested stills are copied separately.
        relative = path.relative_to(source)
        if any(part in {'restored', 'fault-pack', '可编辑示例 project', 'GPU 本地可编辑工程', 'public project', '模型 包'} for part in relative.parts):
            continue
        destination = target / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        if destination.exists() and destination.read_bytes() != path.read_bytes():
            raise ValueError('Preserve differing earlier evidence: ' + str(destination))
        if not destination.exists():
            shutil.copyfile(path, destination)


def main():
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    old_cpu = EVIDENCE / 'cpu'
    if old_cpu.exists():
        current = json.loads((old_cpu / 'verification.json').read_bytes())
        if current['installed'] != str(ROOT / 'local/agent-ffmpeg/v0.1.0-alpha.4-local.1/final/installed'):
            previous = EVIDENCE / 'history/integration-r3-receipts'
            if previous.exists():
                raise ValueError('Earlier CPU receipt archive already exists')
            old_cpu.rename(previous)
    for source, folder in [(WORK / 'integration-r4', 'cpu'), (WORK / 'integration-gpu-r2', 'gpu'),
        (ROOT / 'local/agent-ffmpeg/community-portable-r1', 'portable'),
        (WORK / 'public-demo-r2', 'public-demo'),
        (WORK / 'integration-gpu-r1', 'history/integration-gpu-r1'),
        (WORK / 'public-demo-r1', 'history/public-demo-r1')]:
        receipts(source, EVIDENCE / folder)
    # Copy inference request/response/log evidence, excluding model/media files.
    for project, label in [(WORK / 'integration-r4/可编辑示例 project', 'cpu'),
                            (WORK / 'integration-gpu-r2/GPU 本地可编辑工程', 'gpu')]:
        for path in project.rglob('*'):
            relative = path.relative_to(project)
            if path.is_file() and any('community-model' in part or 'community_model' in part for part in relative.parts) and path.suffix in {'.json', '.txt', '.log'}:
                target = EVIDENCE / label / 'workers' / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target)
    for source, name in [(ROOT / 'local/agent-ffmpeg/community-model-archives-r2/archives.json', 'model-archives-final.json'),
        (ROOT / 'product/src/ai_ad_editor/material_data/model-packs.json', 'model-pack-pins-final.json'),
        (ROOT / 'local/agent-ffmpeg/v0.1.0-alpha.4-local.1/final/installed/receipt.json', 'native-installation-receipt.json'),
        (WORK / 'app-bundle-r6/manifest.json', 'application-bundle-manifest.json')]:
        shutil.copyfile(source, EVIDENCE / name)
    latest = max((ROOT / 'local/agent-ffmpeg/activations').iterdir(), key=lambda p: p.name)
    receipts(latest, EVIDENCE / 'activation')
    app = ROOT / 'local/agent-ffmpeg/v0.1.0-alpha.4-local.1/agent-editor-kit-v0.1.0-alpha.4-local.1-cp313-win_amd64.zip'
    report = dict(status='verified-local-build', release='v0.1.0-alpha.4-local.1', cli_version='0.1.3',
        public_release_unchanged='v0.1.0-alpha.3', application_archive=str(app), bytes=app.stat().st_size,
        sha256=sha(app), manifest_sha256='sha256:' + sha(WORK / 'app-bundle-r6/manifest.json'),
        native_windows=True, virtualization=False, base_bundle_wheels=8, bundled_materials=359,
        optional_model_packs=4, registered_skills=1, internal_modules=17,
        tests_separate=dict(cpu=46, gpu=15, portable=8, skill=11, corrected_layout=8, public_demo=14),
        generated_speech_publication=False, human_listening=False, complete_capcut_parity=False)
    (EVIDENCE / 'delivery.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
