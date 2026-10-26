"""Pin the current single Skill to a separately built native offline bundle."""
from pathlib import Path
import argparse
import ast
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle', type=Path, required=True)
    p.add_argument('--release', default='v0.1.0-alpha.4-local.1')
    a = p.parse_args()
    bundle = a.bundle.resolve(strict=True)
    base = json.loads((bundle / 'manifest.json').read_bytes())
    version = next(r for r in base['wheels'] if r['name'] == 'ai-ad-editor')['version']
    declarations=ast.parse((ROOT/'product/src/ai_ad_editor/__init__.py').read_text('utf8')).body
    source_versions=[ast.literal_eval(n.value) for n in declarations if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='VERSION' for t in n.targets)]
    if source_versions!=[version]:
        raise ValueError('Bundle wheel version differs from source CLI VERSION; rebuild before pinning')
    if not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+[A-Za-z0-9.-]*', a.release):
        raise ValueError('Release name must be a safe version identifier')
    digest, release = 'sha256:' + sha(bundle / 'manifest.json'), a.release
    entry = ROOT / 'skills/agent-ffmpeg-local-editor'
    launcher = entry / 'scripts/run.py'
    text = launcher.read_text('utf8')
    text, count = re.subn(r"^MANIFEST = '[^']+'$", "MANIFEST = '" + digest + "'", text, flags=re.M)
    assert count == 1
    text, count = re.subn(r"^RELEASE = '[^']+'$", "RELEASE = '" + release + "'", text, flags=re.M)
    assert count == 1
    launcher.write_text(text, encoding='utf8', newline='\n')
    manifest_path = ROOT / 'agent-ffmpeg-local-install-manifest.json'
    manifest = json.loads(manifest_path.read_bytes())
    assert manifest['skill_count'] == 1 and manifest['module_count'] == 17
    manifest.update(release=release, manifest_sha256=digest, cli_version=version,
                    material_count=359, named_voice_count=103, optional_model_pack_count=4)
    manifest['skills'][0]['skill_md_sha256'] = sha(entry / 'SKILL.md')
    manifest['skills'][0]['purpose_zh'] = '唯一入口：17 项内部模块、原生PTS跟踪绑定/实际遮罩alpha/59转场来源足迹/共享变速/剪辑分片重规划/叠加轨嵌套声音、Float32全局/区间调整层、4K文字覆盖率复用/浮点GPU颜色与投影、逐词/打字机/SRT、浮点转场/真实句柄/组级空间进出场、原生 GPU 投影、可编辑广告分镜/返工、语义检索、字幕配音、四轨与 GPU 配音/翻译'
    manifest['files'] = [dict(path=f.relative_to(ROOT).as_posix(), bytes=f.stat().st_size, sha256=sha(f))
                         for f in sorted(entry.rglob('*')) if f.is_file()]
    assert sum(Path(r['path']).name == 'SKILL.md' for r in manifest['files']) == 1
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    print(json.dumps(dict(ok=True, release=release, manifest_sha256=digest, skills=1, modules=17, files=len(manifest['files']))))


if __name__ == '__main__':
    main()
