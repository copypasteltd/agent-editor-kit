from __future__ import annotations

import json
import shutil
import xml.etree.ElementTree as ET
import copy
import stat
import tempfile
import zipfile
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit
from .policy import assert_local_project_reference

from .media import classify_path, probe_media
from .project import TICKS_PER_SECOND, create_project, save_project
from .rights import add_record, load_ledger, save_ledger
from .sequence_canvas import sequence_canvas, validate_canvas
from .utils import atomic_write_json, new_id, now_iso, safe_filename, sha256_file


PROJECT_PACKAGE_VERSION = "0.1.0"
PROJECT_PACKAGE_MANIFEST = "package-manifest.json"
PROJECT_PACKAGE_REPORT = "conversion-report.json"
PROJECT_PACKAGE_ROOT_FILES = ("project.json", "rights-ledger.json", "project.lock.json", "models/audio-adapters.json", "models/visual-adapters.json")
# Assets are handled explicitly from project metadata so their URIs can be
# rewritten into the portable package namespace.  The remaining directories
# are small project-owned support payloads; render/cache/operation/history
# trees stay machine-local and are excluded.
PROJECT_PACKAGE_DIRECTORIES = ("fonts", "templates", "validation", "assets/look-evidence")


def report_item(capability: str, status: str, source: str, target: str | None = None, detail: str = "") -> dict[str, Any]:
    return {"capability": capability, "status": status, "source": source, "target": target, "detail": detail}


def _path_from_uri(value: str, base: Path | None = None) -> Path:
    """Resolve an OTIO/MLT local reference without changing the policy gate.

    OTIO permits relative ``target_url`` values.  They are relative to the
    interchange file, whereas the project runtime resolves paths from the
    project root.  Resolve that distinction before handing the value to the
    common local-only policy.
    """
    text = str(value)
    parsed = urlsplit(text)
    if base is not None and not parsed.scheme and not Path(text).expanduser().is_absolute():
        return (base / Path(text)).expanduser().resolve()
    return assert_local_project_reference(text, field="media_reference.target_url")


def _otio_rational_time(tick: int, tps: int) -> dict[str, Any]:
    """Represent project ticks exactly in an OTIO RationalTime."""
    return {"OTIO_SCHEMA": "RationalTime.1", "value": int(tick), "rate": int(tps)}


def _otio_time_range(start_tick: int, duration_tick: int, tps: int) -> dict[str, Any]:
    return {
        "OTIO_SCHEMA": "TimeRange.1",
        "start_time": _otio_rational_time(start_tick, tps),
        "duration": _otio_rational_time(max(1, duration_tick), tps),
    }


def _otio_ticks(value: Any, tps: int, default: int = 0) -> int:
    """Convert an OTIO RationalTime object to the project tick timebase."""
    if not isinstance(value, dict):
        return default
    try:
        raw_value = float(value.get("value", 0))
        rate = max(float(value.get("rate", 1)), 1e-9)
        return int(round(raw_value / rate * tps))
    except (TypeError, ValueError):
        return default


def export_agent_project(root: Path, project: dict[str, Any], output: Path) -> dict[str, Any]:
    output.parent.mkdir(parents=True, exist_ok=True)
    exported = copy.deepcopy(project)
    for asset in exported.get("assets", []):
        uri = Path(str(asset.get("uri", "")))
        if not uri.is_absolute():
            uri = root / uri
        if uri.exists():
            asset["uri"] = str(uri)
    exported.setdefault("provenance", {}).setdefault("change_log", []).append({"command": "convert.export", "at": now_iso(), "source_project": str(root)})
    atomic_write_json(output, exported)
    report = {
        "report_version": "0.1.0",
        "direction": "export",
        "source_format": "agent-project/0.1.0",
        "target_format": "agent-project/0.1.0",
        "created_at": now_iso(),
        "items": [report_item("project-model", "Exact", "Agent Project JSON", "Agent Project JSON")],
        "warnings": [],
        "failures": [],
    }
    report_path = output.with_suffix(output.suffix + ".conversion-report.json")
    atomic_write_json(report_path, report)
    return {"output": str(output), "report": str(report_path), "report_data": report}


def _package_relative(path: Path) -> str:
    """Return a portable forward-slash package path."""
    return path.as_posix().lstrip("/")


def _package_files(root: Path) -> list[Path]:
    """Return the bounded project payload eligible for a portable package.

    Render outputs, caches, operation journals and history snapshots are
    intentionally excluded: they are machine-local or ephemeral and should
    never be mistaken for the editable project source of truth.
    """
    files: list[Path] = []
    for name in PROJECT_PACKAGE_ROOT_FILES:
        path = root / name
        if path.is_file():
            files.append(path)
    for directory_name in PROJECT_PACKAGE_DIRECTORIES:
        directory = root / directory_name
        if not directory.is_dir():
            continue
        files.extend(path for path in directory.rglob("*") if path.is_file())
    return sorted(files, key=lambda path: _package_relative(path.relative_to(root)))


def _package_json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _package_asset_map(root: Path, project: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Path], list[dict[str, Any]]]:
    """Copy referenced asset metadata into a portable namespace in memory.

    Asset URIs are rewritten in the packaged project, so an imported package
    never depends on the source machine's absolute path.  Missing assets are a
    hard export failure because a package claiming portability must be complete.
    """
    packaged = json.loads(json.dumps(project, ensure_ascii=False))
    files: dict[str, Path] = {}
    failures: list[dict[str, Any]] = []
    assets = packaged.get("assets", [])
    if not isinstance(assets, list):
        raise ValueError("项目 assets 必须是数组，无法创建项目包")
    for index, asset in enumerate(assets):
        if not isinstance(asset, dict):
            failures.append(report_item("asset", "Failed", f"assets[{index}]", None, "资产项必须是对象"))
            continue
        asset_id = safe_filename(str(asset.get("id") or f"asset_{index + 1}"))
        raw_uri = str(asset.get("uri", ""))
        source = Path(raw_uri).expanduser()
        if not source.is_absolute():
            source = root / source
        source = source.resolve()
        if not source.is_file():
            failures.append(report_item("asset", "Failed", str(source), str(asset.get("id", "")), "资产文件不存在，项目包拒绝生成"))
            continue
        target_name = safe_filename(source.name)
        try:
            relative = source.relative_to(root.resolve())
        except ValueError:
            relative = None
        # Semantic index/vector/preview/profile bindings rely on this owned
        # tree. Preserving all project-owned assets also avoids renaming source
        # URIs unnecessarily. External files still become local package assets.
        package_path = (relative.as_posix() if relative and relative.parts[0] == 'assets'
                        else f"assets/{asset_id}_{target_name}")
        # IDs are normally unique, but avoid silently overwriting a duplicate.
        if package_path in files and files[package_path] != source:
            package_path = f"assets/{asset_id}_{index + 1}_{target_name}"
        files[package_path] = source
        asset["uri"] = package_path
    return packaged, files, failures


def _zip_write_bytes(archive: zipfile.ZipFile, name: str, data: bytes) -> None:
    """Write deterministic UTF-8 bytes without host filesystem timestamps."""
    info = zipfile.ZipInfo(name)
    info.date_time = (1980, 1, 1, 0, 0, 0)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 0
    info.external_attr = 0o600 << 16
    archive.writestr(info, data)


def _export_project_package(root: Path, project: dict[str, Any], output: Path, *, transformation_report: dict | None = None) -> dict[str, Any]:
    """Export a self-contained, local-only Agent Project package."""
    packaged_project, asset_files, failures = _package_asset_map(root, project)
    if failures:
        raise ValueError("项目包含缺失素材，无法生成可移植项目包")
    lut_count = _package_luts(root, packaged_project, asset_files)
    icc_files=_package_icc_profiles(root,packaged_project,asset_files)
    from .semantic_package import prepare as prepare_semantic
    semantic_files, semantic_ledger, semantic_summary = prepare_semantic(root, project, packaged_project)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and output.is_dir():
        raise ValueError(f"项目包输出必须是文件: {output}")
    source_files: dict[str, bytes] = {}
    source_files["project.json"] = _package_json_bytes(packaged_project)
    # Built-in look IDs retain their project-local registry identity, so
    # imported projects can inspect/reapply them and keep relative evidence.
    from .lut_library import load_lut_library
    library = load_lut_library(root)
    portable_records = [row for row in library['records'] if row.get('uri') in asset_files]
    if portable_records:
        portable_library = dict(library, records=portable_records)
        source_files['assets/lut-library.json'] = _package_json_bytes(portable_library)
    ledger_path = root / "rights-ledger.json"
    if semantic_ledger is not None:
        source_files["rights-ledger.json"] = _package_json_bytes(semantic_ledger)
    elif ledger_path.is_file():
        source_files["rights-ledger.json"] = ledger_path.read_bytes()
    else:
        source_files["rights-ledger.json"] = _package_json_bytes({"schema_version": "0.2.0", "records": []})
    lock_path = root / "project.lock.json"
    if lock_path.is_file():
        source_files["project.lock.json"] = lock_path.read_bytes()
    for path in _package_files(root):
        relative = _package_relative(path.relative_to(root))
        if relative in PROJECT_PACKAGE_ROOT_FILES[:3]:
            continue
        source_files.setdefault(relative, path.read_bytes())
    for package_path, source in asset_files.items():
        source_files[package_path] = icc_files[package_path] if package_path in icc_files else source.read_bytes()
    source_files.update(semantic_files)
    entries = [
        {"path": name, "size": len(data), "sha256": sha256_file_bytes(data)}
        for name, data in sorted(source_files.items())
    ]
    manifest = {
        "package_format": "agent-project-package",
        "package_version": PROJECT_PACKAGE_VERSION,
        "created_at": now_iso(),
        "project_id": packaged_project.get("project", {}).get("id"),
        "project_schema_version": packaged_project.get("schema_version"),
        "files": entries,
        "excluded": ["renders/", "cache/", "operations/", "history/"],
        "network": "disabled",
        "upstream_runtime": "none",
    }
    manifest_bytes = _package_json_bytes(manifest)
    report = {
        "report_version": "0.1.0",
        "direction": "export",
        "source_format": "agent-project/0.1.0",
        "target_format": f"agent-project-package/{PROJECT_PACKAGE_VERSION}",
        "created_at": now_iso(),
        "items": [report_item("project-package", "Exact", str(root), str(output), "项目、登记权利和本地素材已写入自包含 ZIP")],
        "warnings": [report_item("package-excluded-runtime", "Approximate", "project runtime", str(output), "renders/cache/operations/history 未打包")],
        "failures": [],
    }
    if lut_count:
        report['items'].append(report_item('lut-resources', 'Mapped', 'local paths / lut_id',
            'assets/luts/', f'{lut_count} 个引用改写为包内内容寻址路径；关键帧及 LUT 原字节保留，缓存不打包'))
    if icc_files:
        report['items'].append(report_item('icc-source-profiles','Mapped','explicit pixel_pipeline source signals',
            'assets/ / assets/color-profiles/',f'{len(icc_files)} 个原生检查并持锁读取的ICC配置保留原字节和SHA；作者工程不改写，权利证据不推定'))
    if semantic_summary['indexes'] or semantic_summary['calibrations']:
        report['items'].append(report_item('semantic-project-data', 'Mapped', 'local_semantic',
            'assets/semantic/ + assets/semantic-calibration/',
            '受管目录、向量、采样时码与校准数据保留；必要的 URI 派生绑定已校验并记录'))
        report['semantic_data'] = semantic_summary
        report['warnings'].append(report_item('semantic-native-runtime', 'Approximate',
            'external adapter/runtime/model pins', detail='原生模型依赖不打包也不重新信任；实际检索仍验证原 pin'))
    if transformation_report:
        report['items'].extend(transformation_report['items'])
        report['warnings'].extend(transformation_report['items'])
        report.update({k:v for k,v in transformation_report.items() if k != 'items'})
    report_bytes = _package_json_bytes(report)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as archive:
        _zip_write_bytes(archive, PROJECT_PACKAGE_MANIFEST, manifest_bytes)
        for name, data in sorted(source_files.items()):
            _zip_write_bytes(archive, name, data)
        _zip_write_bytes(archive, PROJECT_PACKAGE_REPORT, report_bytes)
    report_path = output.with_suffix(output.suffix + ".conversion-report.json")
    atomic_write_json(report_path, report)
    return {"output": str(output), "report": str(report_path), "report_data": report, "manifest": manifest}


def _package_icc_profiles(root,project,files):
    """Close explicit native source-profile dependencies before any ZIP publish."""
    from .icc_profiles import ICCSourceSignal,parse_source_signal,profile_path,ProfileTransform
    pipeline=(project.get('settings',{}).get('pixel_pipeline') or {})
    snapshots={}
    if pipeline.get('engine')!='float32-native-v1':return snapshots
    for spec in pipeline.get('sources',{}).values():
        signal=parse_source_signal(spec['source_signal'])
        if not isinstance(signal,ICCSourceSignal):continue
        path=profile_path(root,signal)
        with ProfileTransform(root,signal):data=path.read_bytes()
        relative=path.relative_to(Path(root).resolve())
        target=relative.as_posix() if relative.parts[0]=='assets' else 'assets/color-profiles/'+signal.sha256[7:]+'.icc'
        if target in files and files[target]!=path:raise ValueError('ICC工程包依赖路径冲突')
        files[target]=path;snapshots[target]=data;spec['source_signal']['icc_profile']=target
    return snapshots


def _package_luts(root: Path, project: dict[str, Any], files: dict[str, Path]) -> int:
    """Close local LUT dependencies wherever an effect occurs in the graph.

    Registered IDs are resolved now and materialized as portable paths, like
    fragment export. Missing/outside resources fail before opening the ZIP;
    a successful import must not silently lose an unregistered local look.
    """
    from .lut_library import resolve_lut_path
    from .policy import resolve_local_path
    count = 0
    def visit(value):
        nonlocal count
        if isinstance(value, list):
            for item in value: visit(item)
        elif isinstance(value, dict):
            if str(value.get('type', '')).lower().replace('-', '_') in {'lut3d','lut','cube','look'}:
                parameters = value.get('parameters') if isinstance(value.get('parameters'), dict) else value
                lut_id = parameters.get('lut_id')
                if lut_id:
                    found = resolve_lut_path(root, str(lut_id))
                    if found is None:
                        raise ValueError(f'LUT 登记不存在，无法生成可移植项目包: {lut_id}')
                    path = found[0].resolve()
                    if not path.is_file() or 'sha256:'+sha256_file(path) != found[1].get('sha256'):
                        raise ValueError('登记 LUT 的原字节摘要不匹配，无法生成可移植项目包')
                else:
                    raw = parameters.get('path', parameters.get('file', parameters.get('lut')))
                    if not raw:
                        raise ValueError('LUT 缺少本地路径，无法生成可移植项目包')
                    path = resolve_local_path(root, raw, field='package.lut').resolve()
                if not path.is_relative_to(root.resolve()) or not path.is_file():
                    raise ValueError('LUT 必须是项目内实际文件，无法生成可移植项目包')
                digest = sha256_file(path)
                builtin = bool(lut_id and isinstance(value.get('source'), dict)
                               and value['source'].get('look_catalog') in {'avk-looks-1.0.0', 'aek-looks-2.0.0'})
                relative = str(found[1]['uri']) if builtin else f'assets/luts/{digest}{path.suffix.lower()}'
                files[relative] = path
                if not builtin:
                    for key in ('path','file','lut','lut_id'): parameters.pop(key, None)
                    parameters['path'] = relative
                count += 1
            for item in list(value.values()): visit(item)
    visit(project)
    return count


def sha256_file_bytes(data: bytes) -> str:
    """Hash package bytes without writing temporary files."""
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _asset_uri(root: Path, asset: dict[str, Any]) -> Path:
    uri = Path(str(asset.get("uri", "")))
    return uri if uri.is_absolute() else root / uri


def _protect_export(root: Path, project: dict[str, Any], output: Path) -> None:
    protected = {(root / name).resolve() for name in PROJECT_PACKAGE_ROOT_FILES}
    protected.update(_asset_uri(root, asset).resolve() for asset in project.get('assets', []))
    targets = [output, output.with_suffix(output.suffix + '.conversion-report.json'),
               output.with_suffix(output.suffix + '.source-agent.json'),
               output.with_suffix(output.suffix + '.source-agent.json.conversion-report.json')]
    owned_inputs = [(root / name).resolve() for name in ('assets', 'fonts', 'models', 'templates')]
    if any(path.resolve() in protected or any(path.resolve().is_relative_to(base) for base in owned_inputs)
           for path in targets):
        raise ValueError('导出文件及旁车不能覆盖源工程、已登记素材或工程输入目录')


def _tracking_export_receipt(root, original, output, report, receipt, bound):
    if not bound: return {}
    sidecar = output.with_suffix(output.suffix + '.source-agent.json')
    export_agent_project(root, original, sidecar)
    report['preserved_source'] = sidecar.name
    report['source_root'] = str(root.resolve())
    if receipt: report['tracking_bake'] = receipt
    return {'source_sidecar': str(sidecar)}


def _export_otio(root: Path, project: dict[str, Any], output: Path) -> dict[str, Any]:
    from .bindings import bake_interchange_bindings
    original = project; bake_receipt = {}
    project,bound_clips = bake_interchange_bindings(project, root, receipt=bake_receipt)
    tps = int(project["settings"]["timebase"]["ticks_per_second"])
    assets = {str(asset.get("id")): asset for asset in project.get("assets", [])}
    tracks: list[dict[str, Any]] = []
    items: list[dict[str, Any]] = [report_item("project-model", "Mapped", "Agent Project JSON", "OpenTimelineIO JSON", "使用标准 Stack/Track/Gap/Clip 节点；完整本地片段保存在 ai_ad_editor metadata")]
    if project['settings'].get('sequence_sampling') is not None:
        items.append(report_item('sequence-sampling', 'Unsupported', 'settings.sequence_sampling', detail='外部格式不执行本地序列面积核或工作配额；完整配置请使用 agent-json 或 package'))
    from .edit_planner import interchange_features
    items.extend(report_item('timeline-editing', 'Unsupported', field, detail='外部格式不执行本地混合动画相对时钟、命名音频路由、关联/同步锁/主轨跟随、真实源句柄转场或文件字幕时钟偏移；metadata 保存不代表外部编辑等效') for field in interchange_features(project))
    items.extend(report_item('tracking-binding', 'Approximate', clip_id, detail='活动绑定按当前画布重算为关键帧；外部格式不保留绑定引用，视觉能力按格式报告复核') for clip_id in bound_clips)
    sequence = project.get("sequences", [{}])[0]
    items.extend(report_item('sequence-canvas', 'Unsupported', str(s.get('id')), detail='额外序列及其独立画布未导出；完整图请使用 agent-json 或 package')
                 for s in project.get('sequences', [])[1:] if s.get('canvas') is not None)
    if sequence.get('canvas') is not None:
        items.append(report_item('sequence-canvas', 'Approximate', str(sequence.get('id')), detail='首序列尺寸写入本地 metadata；外部 OTIO 播放器不保证执行该元数据'))
    for track in sorted(sequence.get("tracks", []), key=lambda item: int(item.get("order", 0))):
        kind = "Audio" if track.get("kind") == "audio" else "Video"
        track_metadata = {
            "track_id": track.get("id"),
            "track_kind": track.get("kind", "video"),
            "track_order": int(track.get("order", 0)),
        }
        otio_track: dict[str, Any] = {
            "OTIO_SCHEMA": "Track.1",
            "name": track.get("id", "track"),
            "kind": kind,
            "children": [],
            "metadata": {"ai_ad_editor": track_metadata},
        }
        cursor_tick = 0
        for clip in sorted(track.get("clips", []), key=lambda item: int(item.get("timeline_start_tick", 0))):
            asset = assets.get(str(clip.get("asset_id")))
            duration_tick = max(1, int(clip.get("duration_tick", 1)))
            timeline_start_tick = max(0, int(clip.get("timeline_start_tick", 0)))
            if timeline_start_tick > cursor_tick:
                otio_track["children"].append({
                    "OTIO_SCHEMA": "Gap.1",
                    "name": f"gap_{cursor_tick}_{timeline_start_tick}",
                    "source_range": _otio_time_range(0, timeline_start_tick - cursor_tick, tps),
                })
            elif timeline_start_tick < cursor_tick:
                items.append(report_item("timeline-overlap", "Approximate", str(clip.get("id")), otio_track["name"], "OTIO Track 是顺序容器；重叠片段保留 timeline_start_tick metadata，外部编辑器可能按顺序压平"))
            source_in_tick = max(0, int(clip.get("source_in_tick", 0)))
            local_metadata: dict[str, Any] = {
                "timeline_start_tick": timeline_start_tick,
                "duration_tick": duration_tick,
                "asset_id": asset.get("id") if asset else clip.get("asset_id"),
                "track_id": track.get("id"),
                "track_order": int(track.get("order", 0)),
                "clip": copy.deepcopy(clip),
            }
            child: dict[str, Any] = {
                "OTIO_SCHEMA": "Clip.2",
                "name": clip.get("id", "clip"),
                "source_range": _otio_time_range(source_in_tick, duration_tick, tps),
                "metadata": {"ai_ad_editor": local_metadata},
            }
            if asset:
                media_path = _asset_uri(root, asset)
                if media_path.exists():
                    child["media_reference"] = {"OTIO_SCHEMA": "ExternalReference.1", "target_url": media_path.resolve().as_uri()}
                else:
                    items.append(report_item("media-reference", "Failed", str(media_path), child["name"], "本地媒体文件不存在，保留 OTIO 引用但目标无法独立渲染"))
                    child["media_reference"] = {"OTIO_SCHEMA": "MissingReference.1", "name": media_path.name}
            elif isinstance(clip.get("generator"), dict) and str(clip["generator"].get("type", "")).lower() == "text" and isinstance(clip.get("subtitle"), dict):
                child["media_reference"] = {"OTIO_SCHEMA": "GeneratorReference.1", "generator_kind": "Text"}
                items.append(report_item("text-generator", "Mapped", str(clip.get("id")), child["name"], "文字生成器保留为 GeneratorReference，并在 ai_ad_editor metadata 保存完整片段"))
            elif isinstance(clip.get('generator'),dict) and clip['generator'].get('type')=='particles':
                child['media_reference']={'OTIO_SCHEMA':'GeneratorReference.1','generator_kind':'AgentParticles',
                    'parameters':copy.deepcopy(clip['generator'])}
                items.append(report_item('particle-generator','Mapped',str(clip.get('id')),child['name'],
                    '版本化粒子源完整保存于 Agent metadata；外部 OTIO 播放器不保证渲染该生成器'))
            else:
                items.append(report_item("media-reference", "Failed", str(clip.get("asset_id")), child["name"], "片段没有可导出的本地资产或受支持的文字生成器"))
                cursor_tick = max(cursor_tick, timeline_start_tick + duration_tick)
                continue
            feature_fields = [field for field in ("effects", "keyframes", "transition_in", "transition_out", "subtitle", "audio", "mask", "blend", "transform") if clip.get(field)]
            if feature_fields:
                items.append(report_item("clip-features", "Mapped", str(clip.get("id")), child["name"], f"完整字段保存在 metadata.ai_ad_editor.clip；外部 OTIO 播放器只保证基础媒体时间范围，字段: {','.join(feature_fields)}"))
            otio_track["children"].append(child)
            cursor_tick = max(cursor_tick, timeline_start_tick + duration_tick)
        tracks.append(otio_track)
    payload = {
        "OTIO_SCHEMA": "Timeline.1",
        "name": project.get("project", {}).get("name", "Agent Project"),
        "metadata": {"ai_ad_editor": {"schema_version": project.get("schema_version"), "ticks_per_second": tps, "duration_tick": int(sequence.get("duration_tick", 1)),
                                     "display_fps": copy.deepcopy(project['settings']['timebase']['display_fps']),
                                     "canvas": sequence_canvas(project, sequence), "sequence_canvas": copy.deepcopy(sequence.get('canvas')),
                                     "project_canvas": sequence_canvas(project, {'canvas':None})}},
        "tracks": {"OTIO_SCHEMA": "Stack.1", "name": "tracks", "children": tracks},
    }
    if any(isinstance(c.get('generator'),dict) and c['generator'].get('type')=='particles'
           for t in sequence.get('tracks',[]) for c in t.get('clips',[])):
        payload['metadata']['ai_ad_editor']['particle_render_settings']={k:copy.deepcopy(v)
            for k,v in project['settings'].items() if k in ('canvas','pixel_pipeline','color','output','projection_acceleration','sequence_sampling','acceleration')}
    atomic_write_json(output, payload)
    report = {"report_version": "0.1.0", "direction": "export", "source_format": "agent-project/0.1.0", "target_format": "opentimelineio-json", "created_at": now_iso(), "items": items, "warnings": [item for item in items if item["status"] in {"Approximate", "Unsupported"}], "failures": [item for item in items if item["status"] == "Failed"]}
    report_path = output.with_suffix(output.suffix + ".conversion-report.json")
    extra = _tracking_export_receipt(root, original, output, report, bake_receipt, bound_clips)
    atomic_write_json(report_path, report)
    return {"output": str(output), "report": str(report_path), "report_data": report, **extra}


def _export_kdenlive_xml(root: Path, project: dict[str, Any], output: Path) -> dict[str, Any]:
    from .bindings import bake_interchange_bindings
    original = project; bake_receipt = {}
    project,bound_clips = bake_interchange_bindings(project, root, receipt=bake_receipt)
    sequence = project.get('sequences', [{}])[0]
    canvas = sequence_canvas(project, sequence)
    tps = int(project["settings"]["timebase"]["ticks_per_second"])
    fps = project["settings"]["timebase"].get("display_fps", {"num": 30, "den": 1})
    fps_num = max(1, int(fps.get("num", 30)))
    fps_den = max(1, int(fps.get("den", 1)))
    profile = f"atsc_1080p_{fps_num}"
    assets = {str(asset.get("id")): asset for asset in project.get("assets", [])}
    root_element = ET.Element("mlt", {"version": "7.0", "profile": profile})
    ET.SubElement(root_element, "profile", {
        "description": "Agent Video Kit",
        "frame_rate_num": str(fps_num),
        "frame_rate_den": str(fps_den),
        "width": str(canvas['width']),
        "height": str(canvas['height']),
    })
    producers: list[tuple[str, dict[str, Any]]] = []
    items: list[dict[str, Any]] = [report_item("project-model", "Approximate", "Agent Project JSON", "Kdenlive MLT XML", "导出本地 producer 与顺序 playlist；复杂效果需在转换报告中复核")]
    if project['settings'].get('sequence_sampling') is not None:
        items.append(report_item('sequence-sampling', 'Unsupported', 'settings.sequence_sampling', detail='外部格式不执行本地序列面积核或工作配额；完整配置请使用 agent-json 或 package'))
    from .edit_planner import interchange_features
    items.extend(report_item('timeline-editing', 'Unsupported', field, detail='外部格式不执行本地混合动画相对时钟、关联/同步锁/主轨跟随、真实源句柄转场或文件字幕时钟偏移；metadata 保存不代表外部编辑等效') for field in interchange_features(project))
    items.extend(report_item('tracking-binding', 'Approximate', clip_id, detail='活动绑定按当前画布重算为关键帧；外部格式不保留绑定引用，视觉能力按格式报告复核') for clip_id in bound_clips)
    sequence = project.get("sequences", [{}])[0]
    items.extend(report_item('sequence-canvas', 'Unsupported', str(s.get('id')), detail='额外序列及其独立画布未导出；完整图请使用 agent-json 或 package')
                 for s in project.get('sequences', [])[1:] if s.get('canvas') is not None)
    playlists: list[str] = []
    producer_index = 0
    for track_index, track in enumerate(sorted(sequence.get("tracks", []), key=lambda item: int(item.get("order", 0)))):
        playlist_id = f"playlist{track_index}"
        playlists.append(playlist_id)
        playlist = ET.SubElement(root_element, "playlist", {"id": playlist_id})
        ET.SubElement(playlist, "property", {"name": "ai_ad_editor_track_kind"}).text = str(track.get("kind", "video"))
        ET.SubElement(playlist, "property", {"name": "ai_ad_editor_track_id"}).text = str(track.get("id", playlist_id))
        ET.SubElement(playlist, "property", {"name": "ai_ad_editor_track_order"}).text = str(int(track.get("order", track_index)))
        cursor_frame = 0
        for clip in sorted(track.get("clips", []), key=lambda item: int(item.get("timeline_start_tick", 0))):
            asset = assets.get(str(clip.get("asset_id")))
            if not asset:
                items.append(report_item("media-reference", "Failed", str(clip.get("asset_id")), None, "片段没有可导出的本地资产"))
                continue
            producer_id = f"producer{producer_index}"
            producer_index += 1
            media_path = _asset_uri(root, asset).resolve()
            producer = ET.SubElement(root_element, "producer", {"id": producer_id})
            ET.SubElement(producer, "property", {"name": "resource"}).text = str(media_path)
            duration_tick = max(1, int(clip.get("duration_tick", 1)))
            source_in_tick = max(0, int(clip.get("source_in_tick", 0)))
            duration_frames = max(1, round(duration_tick / tps * fps_num / fps_den))
            in_frame = max(0, round(source_in_tick / tps * fps_num / fps_den))
            timeline_start_tick = max(0, int(clip.get("timeline_start_tick", 0)))
            timeline_frame = max(0, round(timeline_start_tick / tps * fps_num / fps_den))
            if timeline_frame > cursor_frame:
                ET.SubElement(playlist, "blank", {"length": str(timeline_frame - cursor_frame)})
            elif timeline_frame < cursor_frame:
                items.append(report_item("timeline-overlap", "Approximate", str(clip.get("id")), playlist_id, "MLT playlist 是顺序容器；重叠片段保留 metadata，外部项目可能压平层级"))
            entry = ET.SubElement(playlist, "entry", {"producer": producer_id, "in": str(in_frame), "out": str(in_frame + duration_frames - 1)})
            ET.SubElement(entry, "property", {"name": "ai_ad_editor_clip_id"}).text = str(clip.get("id", producer_id))
            ET.SubElement(entry, "property", {"name": "ai_ad_editor_timeline_start_tick"}).text = str(timeline_start_tick)
            ET.SubElement(entry, "property", {"name": "ai_ad_editor_duration_tick"}).text = str(duration_tick)
            ET.SubElement(entry, "property", {"name": "ai_ad_editor_clip_json"}).text = json.dumps(clip, ensure_ascii=False, separators=(",", ":"))
            cursor_frame = max(cursor_frame, timeline_frame + duration_frames)
            if any(clip.get(field) for field in ("effects", "keyframes", "transition_in", "transition_out", "subtitle", "audio")):
                items.append(report_item("clip-features", "Mapped", str(clip.get("id")), producer_id, "完整片段字段写入 ai_ad_editor_clip_json；MLT 基础播放器不执行这些字段"))
    tractor = ET.SubElement(root_element, "tractor", {"id": "tractor0"})
    multitrack = ET.SubElement(tractor, "multitrack")
    for playlist_id in playlists:
        ET.SubElement(multitrack, "track", {"producer": playlist_id})
    output.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(root_element, space="  ")
    ET.ElementTree(root_element).write(output, encoding="utf-8", xml_declaration=True)
    report = {"report_version": "0.1.0", "direction": "export", "source_format": "agent-project/0.1.0", "target_format": "kdenlive-mlt-xml", "created_at": now_iso(), "items": items, "warnings": [item for item in items if item["status"] in {"Approximate", "Unsupported"}], "failures": [item for item in items if item["status"] == "Failed"]}
    report_path = output.with_suffix(output.suffix + ".conversion-report.json")
    extra = _tracking_export_receipt(root, original, output, report, bake_receipt, bound_clips)
    atomic_write_json(report_path, report)
    return {"output": str(output), "report": str(report_path), "report_data": report, **extra}


def export_external(root: Path, project: dict[str, Any], output: Path, target_format: str, *, strict: bool = False, bake_tracking: bool = False) -> dict[str, Any]:
    _protect_export(root, project, output)
    if bake_tracking:
        if strict or target_format not in {'agent-json', 'package'}:
            raise ValueError('--bake-tracking 适用于 agent-json/package；外部格式自动烘焙并报告损失')
        from .bindings import bake_interchange_bindings
        receipt = {}; baked, bound = bake_interchange_bindings(project, root, receipt=receipt)
        if not bound: return export_external(root, project, output, target_format)
        # Reuse the ordinary exporters; no binding-aware runtime is required in
        # the exported graph. Keep the original author graph in its own sidecar.
        transformation = dict(items=[report_item('tracking-binding', 'Baked', cid,
            detail='绑定烘焙为普通hold关键帧；只验收当前工程显示帧；完整原绑定保存在旁车') for cid in bound],
            preserved_source=output.with_suffix(output.suffix + '.source-agent.json').name,
            source_root=str(root.resolve()))
        if receipt: transformation['tracking_bake'] = receipt
        result = (_export_project_package(root, baked, output, transformation_report=transformation)
                  if target_format == 'package' else export_external(root, baked, output, target_format))
        report = result['report_data']
        if target_format != 'package':
            report['items'].extend(transformation['items'])
            report['warnings'].extend(transformation['items'])
        result.update(_tracking_export_receipt(root, project, output, report, receipt, bound))
        atomic_write_json(Path(result['report']), report)
        return result
    if target_format == "jianying-draft-json":
        from .draft_adapter import export_draft

        return export_draft(root, project, output, strict=strict)
    if strict:
        raise ValueError("--strict 当前适用于 jianying-draft-json 草稿适配器")
    if target_format == "agent-json":
        return export_agent_project(root, project, output)
    if target_format == "package":
        return _export_project_package(root, project, output)
    if target_format == "otio":
        return _export_otio(root, project, output)
    if target_format == "kdenlive-xml":
        return _export_kdenlive_xml(root, project, output)
    raise ValueError(f"不支持的导出格式: {target_format}")


def _asset_from_local(path: Path, root: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    probe = probe_media(path)
    asset_id = new_id("asset")
    destination = root / "assets" / f"{asset_id}_{safe_filename(path.name)}"
    shutil.copy2(path, destination)
    digest = sha256_file(destination)
    kind = classify_path(path, probe)
    asset = {"id": asset_id, "kind": kind, "uri": str(destination.relative_to(root)).replace("\\", "/"), "sha256": f"sha256:{digest}", "probe": probe, "rights_ref": asset_id, "source": {"source_url": f"local://{path}", "retrieved_at": now_iso(), "original_name": path.name}}
    rights = {"asset_id": asset_id, "kind": kind, "sha256": f"sha256:{digest}", "source_url": f"local://{path}", "source_version": "import", "retrieved_at": now_iso(), "creator": "unknown", "license_spdx": "LicenseRef-UNVERIFIED", "license_url": "", "attribution": "", "permitted_uses": ["internal"], "restrictions": [], "evidence": "", "verification_status": "unverified", "verified_by": "", "takedown_status": "clear", "notes": "Imported through local converter; verify before publish"}
    return asset, rights


def _import_otio(source: Path, destination: Path, payload: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    root, project = create_project(destination, name=payload.get("name") or source.stem)
    ledger = {"schema_version": "0.1.0", "updated_at": now_iso(), "records": [], "policy": {}}
    sequence = project["sequences"][0]
    metadata = payload.get('metadata') if isinstance(payload.get('metadata'), dict) else {}
    local = metadata.get('ai_ad_editor') if isinstance(metadata.get('ai_ad_editor'), dict) else {}
    if 'ticks_per_second' in local:
        value = local['ticks_per_second']
        if type(value) is not int or value <= 0: raise ValueError('OTIO本地metadata的ticks_per_second必须为正整数')
        project['settings']['timebase']['ticks_per_second'] = value
    if 'display_fps' in local:
        value = local['display_fps']
        if not isinstance(value, dict) or set(value) != {'num','den'} or any(type(value.get(k)) is not int or value[k] <= 0 for k in ('num','den')):
            raise ValueError('OTIO本地metadata的display_fps必须为正整数比')
        project['settings']['timebase']['display_fps'] = copy.deepcopy(value)
    if 'duration_tick' in local:
        value = local['duration_tick']
        if type(value) is not int or value < 1: raise ValueError('OTIO本地metadata的duration_tick必须为正整数')
        sequence['duration_tick'] = value
    if local.get('canvas') is not None:
        validate_canvas(local['canvas'], path='metadata.ai_ad_editor.canvas')
        sequence['canvas'] = copy.deepcopy(local['canvas'])
        if local.get('project_canvas') is not None:
            validate_canvas(local['project_canvas'], path='metadata.ai_ad_editor.project_canvas')
            project['settings']['canvas'].update(local['project_canvas'])
            if 'sequence_canvas' in local:
                validate_canvas(local['sequence_canvas'], path='metadata.ai_ad_editor.sequence_canvas')
                sequence['canvas'] = copy.deepcopy(local['sequence_canvas'])
    import_tps = int(project["settings"]["timebase"]["ticks_per_second"])
    report_items: list[dict[str, Any]] = [report_item("project-model", "Mapped", "OpenTimelineIO", "Agent Project JSON", "标准 Stack/Track/Gap/Clip 以及 ai_ad_editor metadata 已映射到本地时间线")]
    asset_by_uri: dict[str, dict[str, Any]] = {}
    native_asset_ids={}
    particle_settings=local.get('particle_render_settings')
    raw_tracks = payload.get("tracks")
    if isinstance(raw_tracks, dict):
        raw_tracks = raw_tracks.get("children", [])
    if not isinstance(raw_tracks, list) or not raw_tracks:
        raw_tracks = payload.get("children", [])

    def track_for(otio_track: dict[str, Any], track_index: int) -> dict[str, Any]:
        metadata = otio_track.get("metadata") if isinstance(otio_track.get("metadata"), dict) else {}
        local = metadata.get("ai_ad_editor") if isinstance(metadata.get("ai_ad_editor"), dict) else {}
        raw_kind = str(local.get("track_kind", otio_track.get("kind", "video"))).lower()
        kind = "audio" if raw_kind == "audio" else "subtitle" if raw_kind == "subtitle" else "video"
        if raw_kind=='overlay' and particle_settings is not None:kind='overlay'
        requested_id = str(local.get("track_id") or otio_track.get("name") or f"track_{kind}_{track_index + 1}")
        try:
            order = int(local.get("track_order", track_index))
        except (TypeError, ValueError):
            order = track_index
        for existing in sequence["tracks"]:
            if existing.get("id") == requested_id:
                return existing
        candidates = [item for item in sequence["tracks"] if item.get("kind") == kind and not item.get("clips")]
        if candidates and requested_id.startswith("track_"):
            track = candidates[0]
            track["id"] = requested_id
            track["order"] = order
            return track
        track = {"id": requested_id, "kind": kind, "order": order, "muted": False, "locked": False, "clips": []}
        sequence["tracks"].append(track)
        return track

    for track_index, otio_track in enumerate(raw_tracks if isinstance(raw_tracks, list) else []):
        if not isinstance(otio_track, dict):
            continue
        if otio_track.get("OTIO_SCHEMA", "").startswith("Stack."):
            nested_tracks = otio_track.get("children", [])
            for nested_index, nested in enumerate(nested_tracks if isinstance(nested_tracks, list) else []):
                if isinstance(nested, dict):
                    raw_tracks.append(nested)
            continue
        children = otio_track.get("children", []) if isinstance(otio_track.get("children"), list) else []
        track = track_for(otio_track, track_index)
        current_tick = 0
        for child_index, child in enumerate(children):
            if not isinstance(child, dict):
                continue
            schema = str(child.get("OTIO_SCHEMA", ""))
            if schema.startswith("Gap."):
                gap_range = child.get("source_range") if isinstance(child.get("source_range"), dict) else {}
                current_tick += _otio_ticks(gap_range.get("duration"), import_tps, 0)
                continue
            if not schema.startswith("Clip.") and child.get("media_reference") is None:
                report_items.append(report_item("timeline-item", "Unsupported", str(child.get("name", child_index)), track.get("id"), "仅支持 OTIO Clip 或带媒体引用的节点"))
                continue
            ref = child.get("media_reference") or {}
            uri = ref.get("target_url") or child.get("target_url")
            metadata = child.get("metadata") if isinstance(child.get("metadata"), dict) else {}
            local_metadata = metadata.get("ai_ad_editor") if isinstance(metadata.get("ai_ad_editor"), dict) else {}
            preserved_clip = local_metadata.get("clip") if isinstance(local_metadata.get("clip"), dict) else {}
            asset: dict[str, Any] | None = None
            if uri:
                path = _path_from_uri(str(uri), source.parent)
                if not path.exists():
                    report_items.append(report_item("media-reference", "Failed", str(uri), child.get("name"), "本地文件不存在"))
                    continue
                key = str(path.resolve())
                if key not in asset_by_uri:
                    asset, rights = _asset_from_local(path, root)
                    project["assets"].append(asset)
                    add_record(ledger, rights)
                    asset_by_uri[key] = asset
                asset = asset_by_uri[key]
            elif str(ref.get("OTIO_SCHEMA", "")).startswith("GeneratorReference.") and preserved_clip.get("generator"):
                kind=preserved_clip['generator'].get('type')
                report_items.append(report_item(kind+'-generator', 'Mapped',str(child.get('name')),track.get('id'),
                    'GeneratorReference 通过 Agent metadata 恢复完整本地生成器；其他播放器不保证渲染'))
            else:
                report_items.append(report_item("media-reference", "Unsupported", str(child.get("name", child_index)), track.get("id"), "缺少本地 target_url 或可恢复的本地生成器"))
                continue
            source_range = child.get("source_range") if isinstance(child.get("source_range"), dict) else {}
            duration_tick = _otio_ticks(source_range.get("duration"), import_tps, 0)
            source_in_tick = _otio_ticks(source_range.get("start_time"), import_tps, 0)
            if not duration_tick and asset:
                duration_tick = max(1, int(asset.get("probe", {}).get("duration_tick", TICKS_PER_SECOND)))
            duration_tick = max(1, duration_tick)
            timeline_start = max(current_tick, _otio_ticks(local_metadata.get("timeline_start"), import_tps, current_tick))
            if local_metadata.get("timeline_start_tick") is not None:
                try:
                    timeline_start = max(0, int(local_metadata["timeline_start_tick"]))
                except (TypeError, ValueError):
                    pass
            if preserved_clip:
                clip = copy.deepcopy(preserved_clip)
                clip["id"] = str(clip.get("id") or child.get("name") or new_id("clip"))
                clip["timeline_start_tick"] = timeline_start
                clip["duration_tick"] = max(1, int(clip.get("duration_tick", duration_tick)))
                clip["source_in_tick"] = max(0, int(clip.get("source_in_tick", source_in_tick)))
                clip["source_out_tick"] = max(clip["source_in_tick"] + 1, int(clip.get("source_out_tick", clip["source_in_tick"] + clip["duration_tick"])))
            else:
                clip = {"id": str(child.get("name") or new_id("clip")), "timeline_start_tick": timeline_start, "duration_tick": duration_tick, "source_in_tick": source_in_tick, "source_out_tick": source_in_tick + duration_tick}
            if asset:
                clip["asset_id"] = asset["id"]
                if local_metadata.get('asset_id'):native_asset_ids[local_metadata['asset_id']]=asset['id']
            else:
                clip.pop("asset_id", None)
            track.setdefault("clips", []).append(clip)
            current_tick = max(current_tick, timeline_start + int(clip.get("duration_tick", duration_tick)))
            sequence["duration_tick"] = max(sequence["duration_tick"], current_tick)
    if particle_settings is not None:
        if not isinstance(particle_settings,dict) or set(particle_settings)-{'canvas','pixel_pipeline','color','output','projection_acceleration','sequence_sampling','acceleration'}:
            raise ValueError('OTIO粒子渲染设置字段无效')
        project['settings'].update(copy.deepcopy(particle_settings))
        pipeline=project['settings'].get('pixel_pipeline') or {}
        pipeline['sources']={native_asset_ids[k]:v for k,v in pipeline.get('sources',{}).items() if k in native_asset_ids}
    save_project(root, project)
    save_ledger(root, ledger)
    return root, project, report_items


def _import_kdenlive_xml(source: Path, destination: Path) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    root, project = create_project(destination, name=source.stem)
    ledger = {"schema_version": "0.1.0", "updated_at": now_iso(), "records": [], "policy": {}}
    report_items: list[dict[str, Any]] = [report_item("project-model", "Mapped", "Kdenlive MLT XML", "Agent Project JSON", "读取 playlist/blank/entry 时间轴、profile 帧率和本地 producer")]
    tree = ET.parse(source)
    root_element = tree.getroot()
    profile = root_element.find("./profile")
    try:
        fps_num = max(1, int(profile.get("frame_rate_num", "30") if profile is not None else "30"))
        fps_den = max(1, int(profile.get("frame_rate_den", "1") if profile is not None else "1"))
    except (TypeError, ValueError):
        fps_num, fps_den = 30, 1
        report_items.append(report_item("timebase", "Approximate", "Kdenlive MLT XML", "Agent Project JSON", "profile 帧率无效，回退 30/1"))
    project['settings']['timebase']['display_fps'] = {'num':fps_num, 'den':fps_den}
    producers: dict[str, Path] = {}
    for producer in root_element.findall("./producer"):
        resource = producer.find("property[@name='resource']")
        if resource is not None and resource.text:
            path = _path_from_uri(resource.text, source.parent)
            if path.exists():
                producers[producer.get("id", new_id("producer"))] = path
    sequence = project["sequences"][0]
    if profile is not None and profile.get('width') is not None and profile.get('height') is not None:
        canvas = {'width':int(profile.get('width')), 'height':int(profile.get('height'))}
        validate_canvas(canvas, path='profile.canvas')
        sequence['canvas'] = canvas
    asset_by_path: dict[str, dict[str, Any]] = {}
    track_by_id: dict[str, dict[str, Any]] = {}
    def target_track(playlist: ET.Element, playlist_index: int) -> dict[str, Any]:
        raw_kind = (playlist.findtext("property[@name='ai_ad_editor_track_kind']") or "video").lower()
        kind = "audio" if raw_kind == "audio" else "subtitle" if raw_kind == "subtitle" else "video"
        track_id = playlist.findtext("property[@name='ai_ad_editor_track_id']") or playlist.get("id") or f"track_{kind}_{playlist_index + 1}"
        try:
            order = int(playlist.findtext("property[@name='ai_ad_editor_track_order']") or playlist_index)
        except (TypeError, ValueError):
            order = playlist_index
        if track_id in track_by_id:
            return track_by_id[track_id]
        for candidate in sequence["tracks"]:
            if candidate.get("kind") == kind and not candidate.get("clips") and track_id.startswith("track_"):
                candidate["id"] = track_id
                candidate["order"] = order
                track_by_id[track_id] = candidate
                return candidate
        track = {"id": track_id, "kind": kind, "order": order, "muted": False, "locked": False, "clips": []}
        sequence["tracks"].append(track)
        track_by_id[track_id] = track
        return track

    for playlist_index, playlist in enumerate(root_element.findall("./playlist")):
        track = target_track(playlist, playlist_index)
        cursor_frame = 0
        for child in list(playlist):
            if child.tag == "blank":
                try:
                    cursor_frame += max(0, int(child.get("length", "0")))
                except (TypeError, ValueError):
                    report_items.append(report_item("timeline-gap", "Approximate", playlist.get("id", "playlist"), track.get("id"), "MLT blank 长度无效，忽略该空隙"))
                continue
            if child.tag != "entry":
                continue
            producer_id = child.get("producer")
            path = producers.get(producer_id or "")
            if not path:
                report_items.append(report_item("media-reference", "Unsupported", str(producer_id), track.get("id"), "producer 未能解析为本地文件"))
                continue
            path_key = str(path.resolve())
            asset = asset_by_path.get(path_key)
            if asset is None:
                asset, rights = _asset_from_local(path, root)
                project["assets"].append(asset)
                add_record(ledger, rights)
                asset_by_path[path_key] = asset
            try:
                source_in_frame = max(0, int(child.get("in", "0")))
                source_out_frame = max(source_in_frame, int(child.get("out", str(source_in_frame))))
            except (TypeError, ValueError):
                source_in_frame, source_out_frame = 0, 0
                report_items.append(report_item("timebase", "Approximate", str(producer_id), track.get("id"), "entry 的 in/out 帧无效，使用 0"))
            duration_frames = max(1, source_out_frame - source_in_frame + 1)
            source_in_tick = int(round(source_in_frame * fps_den / fps_num * TICKS_PER_SECOND))
            duration_tick = int(round(duration_frames * fps_den / fps_num * TICKS_PER_SECOND))
            duration_tick = max(1, duration_tick)
            timeline_text = child.findtext("property[@name='ai_ad_editor_timeline_start_tick']")
            duration_text = child.findtext("property[@name='ai_ad_editor_duration_tick']")
            try:
                timeline_start = max(0, int(timeline_text)) if timeline_text is not None else int(round(cursor_frame * fps_den / fps_num * TICKS_PER_SECOND))
            except (TypeError, ValueError):
                timeline_start = int(round(cursor_frame * fps_den / fps_num * TICKS_PER_SECOND))
            try:
                duration_tick = max(1, int(duration_text)) if duration_text is not None else duration_tick
            except (TypeError, ValueError):
                pass
            clip_json = child.findtext("property[@name='ai_ad_editor_clip_json']")
            clip: dict[str, Any]
            if clip_json:
                try:
                    clip = json.loads(clip_json)
                except (TypeError, ValueError):
                    clip = {}
                    report_items.append(report_item("clip-metadata", "Approximate", str(producer_id), track.get("id"), "ai_ad_editor_clip_json 无法解析，使用基础片段"))
            else:
                clip = {}
            if not isinstance(clip, dict):
                clip = {}
            clip["id"] = str(child.findtext("property[@name='ai_ad_editor_clip_id']") or clip.get("id") or new_id("clip"))
            clip["asset_id"] = asset["id"]
            clip["timeline_start_tick"] = timeline_start
            clip["duration_tick"] = duration_tick
            clip["source_in_tick"] = max(0, int(clip.get("source_in_tick", source_in_tick)))
            clip["source_out_tick"] = max(clip["source_in_tick"] + 1, int(clip.get("source_out_tick", clip["source_in_tick"] + duration_tick)))
            track["clips"].append(clip)
            cursor_frame = max(cursor_frame, int(round((timeline_start / TICKS_PER_SECOND) * fps_num / fps_den)) + duration_frames)
            sequence["duration_tick"] = max(sequence["duration_tick"], timeline_start + duration_tick)
    project["sequences"][0]["duration_tick"] = max(sequence.get("duration_tick", 1), 1)
    save_project(root, project)
    save_ledger(root, ledger)
    return root, project, report_items


def _zip_member_path(name: str) -> Path:
    """Validate one ZIP member as a relative project path."""
    normalized = str(name).replace("\\", "/")
    candidate = Path(normalized)
    if not normalized or candidate.is_absolute() or candidate.drive or ':' in normalized or normalized.startswith("/"):
        raise ValueError(f"项目包包含绝对路径成员: {name}")
    parts = [part for part in normalized.split("/") if part not in {""}]
    if any(part in {".", ".."} for part in parts):
        raise ValueError(f"项目包包含路径穿越成员: {name}")
    if any("\x00" in part for part in parts):
        raise ValueError(f"项目包包含非法路径成员: {name}")
    if normalized != Path(*parts).as_posix() or any(part.endswith(('.', ' ')) for part in parts):
        raise ValueError(f"项目包包含非规范路径成员: {name}")
    reserved = {'con','prn','aux','nul',*(f'com{i}' for i in range(1,10)),*(f'lpt{i}' for i in range(1,10))}
    if any(part.split('.')[0].casefold() in reserved for part in parts):
        raise ValueError(f"项目包包含 Windows 保留文件名: {name}")
    return Path(*parts)


def _import_project_package(source: Path, destination: Path) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    """Validate in a fresh owned staging tree before publishing the import."""
    destination = destination.resolve()
    existed = destination.exists()
    if existed and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError(f"转换输出目录必须不存在或为空: {destination}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.aek-package-', dir=destination.parent) as raw:
        staging = Path(raw).resolve()
        if not staging.is_relative_to(destination.parent.resolve()):
            raise ValueError('Package staging directory outside requested parent')
        _, project, items = _read_project_package(source, staging)
        from .semantic_package import verify as verify_semantic
        verification = verify_semantic(staging, project)
        if verification['indexes'] or verification['calibrations']:
            items.append(report_item('semantic-project-data', 'Exact', 'package semantic payload',
                detail='索引/源/向量/预览/校准/权利绑定已验证；不执行或验证外部模型运行时'))
            items.append(report_item('semantic-native-runtime', 'Approximate', 'external adapter pins',
                detail='模型、原生依赖及实现仍须在使用时通过固定 pin 校验；未下载或重登记'))
        for item in items:
            if item.get('target') == str(staging):
                item['target'] = str(destination)
        if existed:
            destination.rmdir()  # Only the previously confirmed empty directory.
        try:
            staging.rename(destination)
        except BaseException:
            if existed and not destination.exists():
                destination.mkdir()
            raise
        return destination, project, items


def _read_project_package(source: Path, destination: Path) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    """Import and verify a self-contained local Agent Project ZIP."""
    if destination.exists() and any(destination.iterdir()):
        raise ValueError(f"转换输出目录必须不存在或为空: {destination}")
    destination.mkdir(parents=True, exist_ok=True)
    report_items: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(source, "r") as archive:
            raw_infos = [info for info in archive.infolist() if not info.is_dir()]
            if len({_zip_member_path(info.filename).as_posix().casefold() for info in raw_infos}) != len(raw_infos):
                raise ValueError("项目包包含重复 ZIP 成员")
            infos = {info.filename: info for info in raw_infos}
            if PROJECT_PACKAGE_MANIFEST not in infos:
                raise ValueError("项目包缺少 package-manifest.json")
            manifest = json.loads(archive.read(PROJECT_PACKAGE_MANIFEST).decode("utf-8-sig"))
            if manifest.get("package_format") != "agent-project-package" or manifest.get("package_version") != PROJECT_PACKAGE_VERSION:
                raise ValueError("项目包格式或版本不受支持")
            entries = manifest.get("files")
            if not isinstance(entries, list):
                raise ValueError("项目包 manifest.files 必须是数组")
            expected: dict[str, dict[str, Any]] = {}
            for entry in entries:
                if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
                    raise ValueError("项目包 manifest.files 含有无效项")
                relative = _zip_member_path(entry["path"]).as_posix()
                if relative.casefold() in {path.casefold() for path in expected}:
                    raise ValueError(f"项目包 manifest 存在重复路径: {relative}")
                expected[relative] = entry
            for required in PROJECT_PACKAGE_ROOT_FILES[:2]:
                if required not in expected or required not in infos:
                    raise ValueError(f"项目包缺少必需文件: {required}")
            missing_members = sorted(name for name in expected if name not in infos)
            if missing_members:
                raise ValueError(f"项目包缺少 manifest 登记成员: {','.join(missing_members)}")
            validated_data: dict[str, bytes] = {}
            for name in infos:
                if name in {PROJECT_PACKAGE_MANIFEST, PROJECT_PACKAGE_REPORT}:
                    continue
                relative = _zip_member_path(name).as_posix()
                if relative not in expected:
                    raise ValueError(f"项目包含有未登记成员: {name}")
                info = infos[name]
                mode = (info.external_attr >> 16) & 0o170000
                if mode == stat.S_IFLNK:
                    raise ValueError(f"项目包禁止符号链接成员: {name}")
                data = archive.read(info)
                entry = expected[relative]
                if int(entry.get("size", -1)) != len(data) or str(entry.get("sha256", "")).lower() != sha256_file_bytes(data):
                    raise ValueError(f"项目包哈希或大小校验失败: {relative}")
                validated_data[relative] = data
            project_payload = json.loads(validated_data["project.json"].decode("utf-8-sig"))
            if not isinstance(project_payload, dict) or project_payload.get("schema_version") != "0.1.0":
                raise ValueError("项目包 project.json 不是受支持的 Agent Project 版本")
            for relative, data in validated_data.items():
                destination_path = destination / Path(relative)
                destination_path.parent.mkdir(parents=True, exist_ok=True)
                destination_path.write_bytes(data)
            report_items.append(report_item("project-package", "Exact", str(source), str(destination), "manifest、文件哈希和本地路径安全检查通过"))
            report_items.append(report_item("project-model", "Exact", "agent-project-package/0.1.0", "Agent Project JSON"))
            report_items.append(report_item("rights-ledger", "Exact", "rights-ledger.json", "项目 Rights Ledger"))
            return destination, project_payload, report_items
    except (OSError, zipfile.BadZipFile, json.JSONDecodeError) as exc:
        raise ValueError(f"项目包无法读取或解析: {exc}") from exc


def import_external(source: Path, destination: Path, *, strict: bool = False) -> dict[str, Any]:
    if source.suffix.lower() in {".json", ".otio"}:
        try:
            payload = json.loads(source.read_text(encoding="utf-8-sig"))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise ValueError("只支持 UTF-8 明文交换 JSON；不解密或修复加密草稿") from exc
        if not isinstance(payload, dict):
            raise ValueError("交换 JSON 顶层必须是对象；只支持明文草稿")
        from .draft_adapter import import_draft, is_draft

        if is_draft(payload):
            return import_draft(source, destination, payload, _asset_from_local, strict=strict)
        if "canvas_config" in payload or "materials" in payload:
            raise ValueError("草稿 materials/tracks/canvas_config 结构无效；只支持明文 JSON")
    if strict:
        raise ValueError("--strict 当前适用于 jianying-draft-json 草稿适配器")
    if source.suffix.lower() in {".zip", ".aevpkg"}:
        root, project, items = _import_project_package(source, destination)
        report = {"report_version": "0.1.0", "direction": "import", "source_format": f"agent-project-package/{PROJECT_PACKAGE_VERSION}", "target_format": "agent-project/0.1.0", "created_at": now_iso(), "items": items, "warnings": [item for item in items if item['status'] in {'Approximate','Unsupported'}], "failures": []}
        report_path = root / "validation" / f"conversion_{new_id('report')}.json"
        atomic_write_json(report_path, report)
        return {"root": str(root), "project": str(root / "project.json"), "report": str(report_path), "report_data": report}
    payload: dict[str, Any] | None = None
    if source.suffix.lower() in {".json", ".otio"}:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
        if payload.get("schema_version") == "0.1.0":
            root, project = create_project(destination, name=payload.get("project", {}).get("name") or source.stem)
            report_items = [report_item("project-model", "Exact", str(source), "Agent Project JSON")]
            ledger = {"schema_version": "0.1.0", "updated_at": now_iso(), "records": [], "policy": {}}
            for asset in payload.get("assets", []):
                original = Path(str(asset.get("uri", "")))
                if not original.is_absolute():
                    original = source.parent / original
                if original.exists():
                    copied = root / "assets" / f"{asset.get('id', new_id('asset'))}_{safe_filename(original.name)}"
                    shutil.copy2(original, copied)
                    asset["uri"] = str(copied.relative_to(root)).replace("\\", "/")
                    asset["sha256"] = f"sha256:{sha256_file(copied)}"
                    record = {"asset_id": asset.get("rights_ref") or asset.get("id"), "kind": asset.get("kind", "video"), "sha256": asset["sha256"], "source_url": asset.get("source", {}).get("source_url", f"local://{original}"), "source_version": "import", "retrieved_at": now_iso(), "creator": "unknown", "license_spdx": "LicenseRef-UNVERIFIED", "license_url": "", "attribution": "", "permitted_uses": ["internal"], "restrictions": [], "evidence": "", "verification_status": "unverified", "verified_by": "", "takedown_status": "clear", "notes": "Imported project asset; verify before publish"}
                    add_record(ledger, record)
                else:
                    report_items.append(report_item("asset", "Failed", str(original), asset.get("id"), "资产文件不存在，已保留项目引用"))
            project = payload
            save_project(root, project)
            save_ledger(root, ledger)
            report = {"report_version": "0.1.0", "direction": "import", "source_format": "agent-project/0.1.0", "target_format": "agent-project/0.1.0", "created_at": now_iso(), "items": report_items, "warnings": [item for item in report_items if item["status"] in {"Approximate", "Unsupported"}], "failures": [item for item in report_items if item["status"] == "Failed"]}
            report_path = root / "validation" / f"conversion_{new_id('report')}.json"
            atomic_write_json(report_path, report)
            return {"root": str(root), "project": str(root / "project.json"), "report": str(report_path), "report_data": report}
        root, _, items = _import_otio(source, destination, payload)
    elif source.suffix.lower() in {".xml", ".kdenlive", ".mlt"}:
        root, _, items = _import_kdenlive_xml(source, destination)
    else:
        raise ValueError(f"不支持的外部格式: {source.suffix}")
    report = {"report_version": "0.1.0", "direction": "import", "source_format": source.suffix.lower().lstrip("."), "target_format": "agent-project/0.1.0", "created_at": now_iso(), "items": items, "warnings": [item for item in items if item["status"] in {"Approximate", "Unsupported"}], "failures": [item for item in items if item["status"] == "Failed"]}
    report_path = root / "validation" / f"conversion_{new_id('report')}.json"
    atomic_write_json(report_path, report)
    return {"root": str(root), "project": str(root / "project.json"), "report": str(report_path), "report_data": report}
