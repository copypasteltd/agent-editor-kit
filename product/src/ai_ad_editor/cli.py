from __future__ import annotations

import argparse
import copy
import contextlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import io
import json
import math
import os
import platform
import shutil
import sys
import uuid
from pathlib import Path
from typing import Any, Callable

from . import ENGINE_ID, SCHEMA_VERSION, VERSION
from . import schema_contract
from . import looks
from .clip_windows import apply_operation as apply_window_operation, OPERATIONS as WINDOW_OPERATIONS
from .ad_plan import build_ad_plan
from .captions import parse_caption_file, validate_cues, write_srt_file
from .convert import export_external, import_external
from .errors import AppError, argument_error, dependency_error
from .media import classify_path, ffmpeg_version, generate_proxy, generate_thumbnail, generate_waveform, probe_media, relink_missing_assets, stabilize_media
from .local_lipsync import ENGINE as LIPSYNC_ENGINE
from .local_interpolation import ENGINE as INTERPOLATION_ENGINE
from .project import (
    asset_map,
    create_project,
    find_sequence,
    find_track,
    create_snapshot,
    history_dir,
    ledger_file,
    load_project,
    load_snapshot,
    lock_file,
    project_file,
    project_transaction,
    queue_cancel_lock,
    project_write_lock,
    recover_pending_transaction,
    restore_snapshot,
    save_project,
    TICKS_PER_SECOND,
)
from .quality import GOLDEN_VERSION, build_golden_manifest, check_output, compare_golden_manifest, normalize_golden_constraints, validate_golden_manifest
from .sequence_sampling import configuration as sequence_sampling_configuration
from .edit_planner import build_edit_plan, project_fingerprint as edit_project_fingerprint
from .source_transitions import build_plan as build_source_transition_plan
from . import fragments
from . import html_motion
from . import mask_edit
from .mask_review import prepare as prepare_mask_review, review as review_mask
from .mask_tracking import ENGINE as MASK_TRACKING_ENGINE, prepare as prepare_mask_tracking, execute as execute_mask_tracking, public_plan as public_mask_tracking_plan
from .recommend import recommend_highlights
from .library import duplicate_groups, index_directory, search_catalog, visual_similarity_groups
from .lut_library import inspect_lut, list_luts, prepare_lut_registration, register_lut
from .batch import _load_variants, run_template_batch
from .capabilities import build_capability_manifest
from .transcribe import ffmpeg_whisper_available, transcribe_local, transcribe_local_ffmpeg_whisper, write_srt
from .local_asr import ASR_ENGINE, asr_registry, registry_item as asr_registry_item, prepare_adapter as prepare_asr_adapter, verify_adapter as verify_asr_adapter, transcribe_registered
from .local_ctc import ENGINE as CTC_ENGINE
from .ctc_cli import command_subtitle_align
from .asr_quality import evaluate_transcripts
from .subtitle_segments import (load_source as load_segment_source, checked_rules as checked_segment_rules,
    checked_corrections as checked_segment_corrections, segment_source, display_cues as segment_display_cues,
    srt_text as segmented_srt_text)
from .render import OUTPUT_CONTAINERS, OUTPUT_PIXEL_FORMATS, OUTPUT_PROFILES, output_settings, render_fingerprints, render_project, speed_curve_duration_seconds
from .sequence_canvas import sequence_canvas, validate_canvas, validate_output_alignment
from .rights import VALID_STATUSES, active_records, add_record, apply_disposition_to_project, check_project_rights, create_disposition_decision, disposition_decisions, effective_disposition_decisions, impacted_artifacts, load_ledger, record_history, release_manifest, revise_record, save_ledger
from .understand import detect_beats, understand_media
from .tracking import (
    MULTI_OBJECT_TRACKING_ENGINE,
    MULTI_OBJECT_TRACKING_ENGINES,
    OBJECT_TRACKING_ENGINE,
    build_reframe_plan,
    track_command_json,
    track_command_json_multi,
    track_media,
)
from .runtime import configure_local_runtime
from .template import apply_template_operations, instantiate
from .migration import SUPPORTED_SOURCE_VERSIONS, migrate_project_payload
from .speech import _validate_text as validate_flite_text, _validate_voice as validate_flite_voice, flite_available, synthesize_local_tts
from .local_tts import (
    SOULX_ENGINE, add_registration as add_tts_registration, local_path as tts_local_path,
    prepare_adapter as prepare_tts_adapter, prepare_voice as prepare_tts_voice,
    registry_item as tts_registry_item, require_verified_inputs as verify_tts_inputs,
    synthesize_soulx, tts_registry, validate_output as validate_tts_output,
    validate_text as validate_tts_text, verify_adapter as verify_tts_adapter,
    verify_voice as verify_tts_voice,
)
from .effects import EFFECT_CATALOG_VERSION, get_effect, list_effects
from .motion_presets import MOTION_PRESET_CATALOG_VERSION, canonical_motion_preset, get_motion_preset, list_motion_presets
from .scopes import SCOPE_VERSION, generate_scopes
from .policy import audit_local_tree, policy_error_from_findings, require_local_reference, resolve_local_path
from .render_queue import JOB_STATUSES, cancel_path, enqueue as enqueue_render_jobs, find_job, load_queue, normalize_job, queue_path, save_queue, set_status
from .smart_cut import SMART_CUT_VERSION, build_smart_cut_plan, match_transcript_phrases, replace_clip_with_smart_cut
from .beat_edit import BEAT_CUT_VERSION, build_beat_cut_plan
from .multicam import MULTICAM_SYNC_VERSION, build_switch_segments, new_multicam_clip_id, synchronize_multicam_sources
from .audio_tools import AUDIO_EXTRACT_VERSION, extract_audio, inspect_audio_source
from .audio_separation import AUDIO_SEPARATION_ENGINE, AUDIO_SEPARATION_VERSION, separate_command_json, separate_mid_side
from .local_separation import DEMUCS_ENGINE, separate_native
from .stem_separation import ENGINE as FOUR_STEM_ENGINE
from .local_matting import MATTING_ENGINE, prepare_plan as prepare_matting_plan, matte_native
from .local_segmentation import SEGMENTATION_ENGINE, load_prompts as load_segmentation_prompts
from .local_inpainting import INPAINT_ENGINE, prepare_mask as prepare_inpaint_mask, normalize_options as inpaint_options
from .local_vace import VACE_ENGINE, normalize_generation as vace_options, window_plan as vace_windows, buffer_budget as vace_buffer_budget
from .generation_cli import command as command_media_generate
from .model_session import command as command_model_session
from .model_registry import (
    MODEL_REGISTRY_VERSION,
    adapter_for,
    load_model_registry,
    load_visual_model_registry,
    prepare_audio_adapter,
    prepare_visual_adapter,
    registry_path,
    save_model_registry,
    save_visual_model_registry,
    verify_audio_adapter,
    verify_visual_adapter,
    visual_adapter_for,
    visual_registry_path,
)
from .utils import atomic_write_json, atomic_write_text, assert_id, ensure_inside, idempotency_record_path, load_json, new_id, now_iso, request_fingerprint, safe_filename, sha256_file
from .validator import validate_project


def _common(parser: argparse.ArgumentParser, *, suppress_defaults: bool = False) -> None:
    default = argparse.SUPPRESS if suppress_defaults else None
    parser.add_argument("--format", choices=("json", "text"), default="json" if not suppress_defaults else default, help="输出格式")
    parser.add_argument("--request-id", default=default)
    parser.add_argument("--idempotency-key", default=default)
    parser.add_argument("--dry-run", action="store_true", default=default)
    parser.add_argument("--no-network", action="store_true", default=default if suppress_defaults else True)
    parser.add_argument("--progress", choices=("none", "jsonl"), default="none" if not suppress_defaults else default)


def _leaf_common(parser: argparse.ArgumentParser) -> argparse.ArgumentParser:
    _common(parser, suppress_defaults=True)
    return parser


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-ad-editor", description="本地优先、面向 Agent 的广告视频 CLI")
    _common(parser)
    subs = parser.add_subparsers(dest="domain", required=True)
    from .procedural_cli import add_parser as add_vfx_parser
    add_vfx_parser(subs,_leaf_common)
    from .lipsync_cli import add_parser as add_lipsync_parser
    add_lipsync_parser(subs,_leaf_common)
    from .interpolation_cli import add_parser as add_interpolation_parser
    add_interpolation_parser(subs,_leaf_common)

    project = subs.add_parser("project", help="项目管理")
    ps = project.add_subparsers(dest="action", required=True)
    init = _leaf_common(ps.add_parser("init", help="创建项目"))
    init.add_argument("path", help="项目目录")
    init.add_argument("--name", default=None)
    init.add_argument("--project-id", default=None)
    inspect = _leaf_common(ps.add_parser("inspect", help="检查项目"))
    inspect.add_argument("--project", required=True)
    snapshot = _leaf_common(ps.add_parser("snapshot", help="创建项目快照"))
    snapshot.add_argument("--project", required=True)
    snapshot.add_argument("--label", default="manual")
    restore = _leaf_common(ps.add_parser("restore", help="恢复项目快照"))
    restore.add_argument("--project", required=True)
    restore.add_argument("--snapshot", required=True, help="快照 ID 或 history/*.json 路径")
    migrate = _leaf_common(ps.add_parser("migrate", help="将旧项目迁移到当前 Agent Project schema"))
    migrate.add_argument("--project", required=True)
    migrate.add_argument("--report", default=None, help="可选项目内迁移报告路径")
    recover = _leaf_common(ps.add_parser("recover", help="恢复上次中断的项目元数据事务"))
    recover.add_argument("--project", required=True)
    recover.add_argument("--cleanup-jobs", action="store_true", help="恢复元数据后回收有归属证据的中断任务；保留在用、已引用、已改动和未知文件")
    from .semantic_upgrade import add_parser as add_semantic_upgrade_parser
    add_semantic_upgrade_parser(ps, _leaf_common)

    diagnostics = subs.add_parser('diagnostics', help='检查及显式导出本地管道失败诊断')
    diagnostic_actions = diagnostics.add_subparsers(dest='action', required=True)
    diagnostic_list = _leaf_common(diagnostic_actions.add_parser('list', help='列出本项目已保存的有限诊断历史'))
    diagnostic_list.add_argument('--project', required=True)
    diagnostic_list.add_argument('--operation-id', default=None)
    for action in ('show', 'export'):
        diagnostic = _leaf_common(diagnostic_actions.add_parser(action))
        diagnostic.add_argument('--project', required=True)
        diagnostic.add_argument('--diagnostic-id', required=True)
        diagnostic.add_argument('--expected-manifest-sha256', default=None)
        if action == 'show':
            diagnostic.add_argument('--include-logs', action='store_true')
        else:
            diagnostic.add_argument('--output', required=True)

    media = subs.add_parser("media", help="素材管理")
    ms = media.add_subparsers(dest="action", required=True)
    from .generation_cli import add_parser as add_generation_parser
    add_generation_parser(ms, _leaf_common)
    from .model_session import add_parser as add_model_session_parser
    add_model_session_parser(ms, _leaf_common)
    ingest = _leaf_common(ms.add_parser("ingest", help="导入本地素材"))
    ingest.add_argument("--project", required=True)
    ingest.add_argument("--input", required=True)
    ingest.add_argument("--asset-id", default=None)
    ingest.add_argument("--source-url", default=None)
    ingest.add_argument("--license-spdx", default="LicenseRef-UNVERIFIED")
    ingest.add_argument("--license-url", default="")
    ingest.add_argument("--permitted-use", action="append", default=["internal"])
    ingest.add_argument("--verification-status", choices=("unverified", "verified", "restricted"), default="unverified")
    ingest.add_argument("--evidence", default="")
    ingest.add_argument("--creator", default="unknown")
    stabilize = _leaf_common(ms.add_parser("stabilize", help="使用本地 FFmpeg vidstab 两遍分析生成防抖派生素材"))
    stabilize.add_argument("--project", required=True)
    stabilize.add_argument("--asset-id", default=None, help="项目内视频资产 ID，与 --input 二选一")
    stabilize.add_argument("--input", default=None, help="本地视频路径，与 --asset-id 二选一")
    stabilize.add_argument("--derived-asset-id", default=None, help="生成的派生资产 ID；默认自动生成")
    stabilize.add_argument("--output", default=None, help="项目内输出视频路径；默认 assets/derived/stabilized_<id>.mp4")
    stabilize.add_argument("--shakiness", type=int, default=5)
    stabilize.add_argument("--accuracy", type=int, default=15)
    stabilize.add_argument("--stepsize", type=int, default=6)
    stabilize.add_argument("--mincontrast", type=float, default=0.25)
    stabilize.add_argument("--smoothing", type=int, default=15)
    stabilize.add_argument("--maxshift", type=int, default=-1)
    stabilize.add_argument("--maxangle", type=float, default=-1.0)
    stabilize.add_argument("--crop", choices=("keep", "black"), default="keep")
    stabilize.add_argument("--optzoom", type=int, choices=(0, 1, 2), default=1)
    stabilize.add_argument("--zoom", type=float, default=0.0)
    stabilize.add_argument("--interpol", choices=("no", "linear", "bilinear", "bicubic"), default="bilinear")
    stabilize.add_argument("--source-url", default=None)
    stabilize.add_argument("--license-spdx", default="LicenseRef-UNVERIFIED")
    stabilize.add_argument("--license-url", default="")
    stabilize.add_argument("--permitted-use", action="append", default=["internal"])
    stabilize.add_argument("--verification-status", choices=("unverified", "verified", "restricted"), default="unverified")
    stabilize.add_argument("--evidence", default="")
    stabilize.add_argument("--creator", default="unknown")
    understand = _leaf_common(ms.add_parser("understand", help="本地镜头/静音分析"))
    understand.add_argument("--project", required=True)
    understand.add_argument("--asset-id", default=None)
    understand.add_argument("--input", default=None)
    understand.add_argument("--scene-threshold", type=float, default=0.4)
    understand.add_argument("--beats", action="store_true", help="估计本地音频节拍锚点")
    understand.add_argument("--transcribe", action="store_true", help="使用已存在的本地 ASR 模型")
    understand.add_argument("--transcribe-engine", choices=("transformers", "ffmpeg-whisper"), default="transformers", help="本地 ASR 引擎；ffmpeg-whisper 使用 FFmpeg 内置 whisper.cpp 滤镜")
    understand_model = understand.add_mutually_exclusive_group()
    understand_model.add_argument("--model-path", default=None, help="离线 ASR 模型目录或 ffmpeg-whisper 模型文件；不会自动下载")
    understand_model.add_argument("--adapter-id", default=None, help="已登记并核验完整性的本地 Whisper 模型")
    understand.add_argument("--language", default=None)
    understand.add_argument("--use-gpu", action="store_true", help="ffmpeg-whisper 允许使用本地 GPU；默认 CPU")
    understand.add_argument("--srt", default=None, help="可选项目内 SRT 输出路径")
    prepare = _leaf_common(ms.add_parser("prepare", help="生成本地代理、缩略图和波形"))
    prepare.add_argument("--project", required=True)
    prepare.add_argument("--asset-id", default=None)
    prepare.add_argument("--input", default=None)
    prepare.add_argument("--proxy-width", type=int, default=0, help="大于 0 时生成 H.264 代理")
    prepare.add_argument("--thumbnail", action="store_true")
    prepare.add_argument("--waveform", action="store_true")
    prepare.add_argument("--at-seconds", type=float, default=0.0)
    contact = _leaf_common(ms.add_parser('contact-sheet', help='本地多时间锚点、透明与 Alpha 联系表'))
    contact.add_argument('--project', required=True)
    contact_source = contact.add_mutually_exclusive_group(required=True)
    contact_source.add_argument('--asset-id', default=None)
    contact_source.add_argument('--input', default=None)
    contact.add_argument('--output', required=True, help='项目内全新输出目录')
    contact.add_argument('--at-seconds', type=float, action='append', default=None)
    contact.add_argument('--count', type=int, default=8)
    contact.add_argument('--start-seconds', type=float, default=0)
    contact.add_argument('--end-seconds', type=float, default=None)
    contact.add_argument('--width', type=int, default=320)
    contact.add_argument('--height', type=int, default=180)
    contact.add_argument('--columns', type=int, default=2)
    contact.add_argument('--view', choices=('checker','light','dark','alpha'), action='append', default=None)
    contact.add_argument('--timeout', type=float, default=300)
    contact.add_argument('--cancel-file', default=None)
    highlights = _leaf_common(ms.add_parser("highlights", help="本地启发式高光候选"))
    highlights.add_argument("--project", required=True)
    highlights.add_argument("--asset-id", default=None)
    highlights.add_argument("--input", default=None)
    highlights.add_argument("--top-k", type=int, default=5)
    highlights.add_argument("--min-duration", type=float, default=1.0)
    highlights.add_argument("--max-duration", type=float, default=8.0)
    highlights.add_argument("--beats", action="store_true")
    highlights.add_argument("--sequence-id", default=None, help="应用时的目标序列 ID，默认主序列")
    highlights.add_argument("--track-id", default=None, help="应用时的目标视频轨道 ID")
    highlights.add_argument("--timeline-start-seconds", type=float, default=0.0, help="应用时的时间线起点")
    highlights.add_argument("--apply", action="store_true", help="创建快照并将高光片段写入目标视频轨道")
    highlights.add_argument("--replace-track", action="store_true", help="应用前清空目标视频轨道已有片段")
    highlights.add_argument("--output", default=None)
    beat_cut = _leaf_common(ms.add_parser("beat-cut", help="按本地音频节拍生成并应用卡点剪辑计划"))
    beat_cut.add_argument("--project", required=True)
    beat_audio = beat_cut.add_mutually_exclusive_group(required=True)
    beat_audio.add_argument("--audio-asset-id", default=None, help="项目内含音频流的资产 ID")
    beat_audio.add_argument("--input", default=None, help="本地音频/视频路径；仅用于节拍分析")
    beat_cut.add_argument("--source-asset-id", action="append", required=True, help="可重复：项目内视频素材 ID")
    beat_cut.add_argument("--track-id", required=True, help="目标视频轨道 ID")
    beat_cut.add_argument("--sequence-id", default=None, help="目标序列 ID，默认主序列")
    beat_cut.add_argument("--start-seconds", type=float, default=0.0, help="音频分析起点")
    beat_cut.add_argument("--end-seconds", type=float, default=None, help="音频分析终点；默认音频结束")
    beat_cut.add_argument("--timeline-start-seconds", type=float, default=0.0, help="写入时间线的起点")
    beat_cut.add_argument("--min-segment-seconds", type=float, default=0.2)
    beat_cut.add_argument("--max-clips", type=int, default=128)
    beat_cut.add_argument("--source-mode", choices=("cycle", "ordered"), default="cycle", help="源素材选择：循环或按顺序用完后复用最后一个")
    beat_cut.add_argument("--output", default=None, help="项目内卡点报告路径")
    beat_cut.add_argument("--apply", action="store_true", help="创建快照并将卡点片段写入目标视频轨道")
    beat_cut.add_argument("--replace-track", action="store_true", help="应用前清空目标视频轨道已有片段")
    multicam = _leaf_common(ms.add_parser("multicam", help="本地多机位音频同步与切换计划"))
    multicam.add_argument("--project", required=True)
    multicam.add_argument("--source-asset-id", action="append", required=True, help="可重复：含视频和音频流的机位资产 ID")
    multicam.add_argument("--reference-asset-id", default=None, help="参考机位资产 ID；默认第一个源素材")
    multicam.add_argument("--sequence-id", default=None, help="应用切换计划时的目标序列")
    multicam.add_argument("--track-id", default=None, help="应用切换计划时的目标视频轨道")
    multicam.add_argument("--switch-seconds", type=float, default=None, help="按固定秒数轮换机位；与 --switch-plan 二选一")
    multicam.add_argument("--switch-plan", default=None, help="项目内本地 JSON：数组或 {segments:[...]}，每项含 start_seconds/end_seconds/camera_asset_id")
    multicam.add_argument("--start-seconds", type=float, default=0.0)
    multicam.add_argument("--end-seconds", type=float, default=None)
    multicam.add_argument("--timeline-start-seconds", type=float, default=0.0)
    multicam.add_argument("--source-shortfall", choices=("reject", "trim", "stretch"), default="reject", help="机位覆盖不足：默认拒绝；trim 保留原速同步区间并留空；stretch 显式改变同步关系以填满")
    multicam.add_argument("--sample-rate", type=int, default=8000, help="本地同步 PCM 采样率")
    multicam.add_argument("--analysis-seconds", type=float, default=120.0, help="每个机位最多分析的前缀秒数")
    multicam.add_argument("--max-offset-seconds", type=float, default=30.0, help="互相关搜索的最大相对偏移")
    multicam.add_argument("--clock-model", choices=("offset", "affine"), default="offset", help="固定偏移或显式估计设备时钟漂移")
    multicam.add_argument("--max-drift-ppm", type=float, default=5000.0, help="仿射机位时钟的最大绝对速率漂移，最高20000ppm")
    multicam.add_argument("--drift-window-seconds", type=float, default=12.0, help="漂移校准窗口4..60秒")
    multicam.add_argument("--drift-anchors", type=int, default=9, help="漂移校准窗口数3..31")
    multicam.add_argument("--allow-clock-extrapolation", action="store_true", help="显式允许在已观察的校准范围外外推机位时钟，保留警告")
    multicam.add_argument("--output", default=None, help="项目内多机位同步报告路径")
    multicam.add_argument("--apply", action="store_true", help="创建快照并把切换计划写入目标视频轨道")
    multicam.add_argument("--replace-track", action="store_true", help="应用前清空目标视频轨道已有片段")
    smart_cut = _leaf_common(ms.add_parser("smart-cut", help="基于本地静音检测生成或应用智能剪口播计划"))
    smart_cut.add_argument("--project", required=True)
    smart_cut.add_argument("--sequence-id", default=None)
    smart_cut.add_argument("--clip-id", required=True, help="目标视频片段 ID")
    smart_cut.add_argument("--track-id", required=True, help="目标视频轨道 ID")
    smart_cut.add_argument("--linked-track-id", action="append", default=[], help="可重复：按同一 clip-id 联动裁切音频轨道")
    smart_cut.add_argument("--linked-clip-id", action="append", default=[], help="可重复：与 --linked-track-id 一一对应的音频片段 ID；省略时复用目标 clip-id")
    smart_cut.add_argument("--min-silence-seconds", type=float, default=0.6)
    smart_cut.add_argument("--keep-padding-seconds", type=float, default=0.12)
    smart_cut.add_argument("--min-segment-seconds", type=float, default=0.2)
    smart_cut.add_argument("--silence-db", type=float, default=-35.0)
    smart_cut.add_argument("--transcript", default=None, help="项目内 SRT/VTT/ASS/SSA/TTML 字幕，用于显式短语裁切")
    smart_cut.add_argument("--remove-phrase", action="append", default=[], help="可重复：从本地字幕 cue 中匹配并移除该短语所在时间段")
    smart_cut.add_argument("--output", default=None, help="项目内智能剪口播报告路径")
    smart_cut.add_argument("--apply", action="store_true", help="创建快照并将计划写回目标轨道")
    relink = _leaf_common(ms.add_parser("relink", help="按内容哈希重链接丢失素材"))
    relink.add_argument("--project", required=True)
    relink.add_argument("--search-root", required=True, help="本地素材搜索目录")
    relink.add_argument("--match-by-name", action="store_true", help="哈希无匹配时允许唯一文件名近似匹配")
    visual_adapter = _leaf_common(ms.add_parser("adapter", help="注册或检查本地视觉模型适配器"))
    vas = visual_adapter.add_subparsers(dest="adapter_action", required=True)
    visual_adapter_register = _leaf_common(vas.add_parser("register", help="登记本地视觉模型/执行器路径与哈希"))
    visual_adapter_register.add_argument("--project", required=True)
    visual_adapter_register.add_argument("--adapter-id", required=True)
    visual_adapter_register.add_argument("--engine", required=True, help="本地视觉适配器 engine")
    visual_adapter_register.add_argument("--model-path", required=True)
    visual_adapter_register.add_argument("--executable", required=True, help="command-json-tracking-v1 的本地执行器")
    visual_adapter_register.add_argument("--threads", type=int, default=4, help="原生 ONNX CPU 线程数")
    visual_adapter_register.add_argument("--device", choices=['cpu', 'cuda'], default='cpu', help="SAM2/LaMa 显式设备；VACE 要求 cuda，无自动回退")
    visual_adapter_register.add_argument('--text-gpu-budget-mib', type=int, default=None, help='VACE 文本权重 GPU 分配预算，默认 7168 MiB')
    visual_adapter_register.add_argument('--text-cpu-budget-mib', type=int, default=None, help='VACE 文本权重 CPU 分配预算，默认 8192 MiB')
    visual_adapter_register.add_argument("--downsample-ratio", type=float, default=None, help="RVM 内部降采样比例；默认输出长边缩至 512")
    visual_adapter_register.add_argument("--confidence", type=float, default=0.35)
    visual_adapter_register.add_argument("--low-confidence", type=float, default=0.10)
    visual_adapter_register.add_argument("--match-iou", type=float, default=0.10)
    visual_adapter_register.add_argument("--max-gap-seconds", type=float, default=0.8)
    visual_adapter_register.add_argument("--class-id", type=int, action="append", default=None, help="YOLO COCO 类别；默认 person=0")
    visual_adapter_register.add_argument("--license-spdx", default="LicenseRef-UNVERIFIED")
    visual_adapter_register.add_argument("--license-url", default="")
    visual_adapter_register.add_argument("--permitted-use", action="append", default=["internal"])
    visual_adapter_register.add_argument("--verification-status", choices=("unverified", "verified", "restricted"), default="unverified")
    visual_adapter_register.add_argument("--evidence", default="")
    visual_adapter_register.add_argument("--creator", default="unknown")
    visual_adapter_list = _leaf_common(vas.add_parser("list", help="列出项目内已登记视觉适配器"))
    visual_adapter_list.add_argument("--project", required=True)
    visual_adapter_inspect = _leaf_common(vas.add_parser("inspect", help="检查视觉适配器路径与哈希"))
    visual_adapter_inspect.add_argument("--project", required=True)
    visual_adapter_inspect.add_argument("--adapter-id", required=True)
    matting = _leaf_common(ms.add_parser("matting", help="本地人物抠像或提示式对象分割与透明视频"))
    matting.add_argument("--project", required=True)
    matting.add_argument("--asset-id", required=True)
    matting.add_argument("--adapter-id", required=True)
    matting.add_argument("--derived-asset-id", required=True)
    matting.add_argument("--prompts", default=None, help="SAM2 本地提示 JSON，归一化输出坐标及输出帧号")
    matting.add_argument("--object-id", type=int, action='append', default=None, help="SAM2 对象 ID，可重复；默认联合全部对象")
    matting.add_argument("--mask-mode", choices=['binary', 'probability'], default='binary')
    matting.add_argument("--logit-threshold", type=float, default=0.)
    matting.add_argument("--output", default=None)
    matting.add_argument("--start-seconds", type=float, default=0.)
    matting.add_argument("--end-seconds", type=float, default=None)
    matting.add_argument("--fps", default=None, help="显式 CFR，如 25 或 30000/1001")
    matting.add_argument("--max-edge", type=int, default=0, help="0 保留显示尺寸；否则仅缩小")
    matting.add_argument("--max-frames", type=int, default=18000)
    matting.add_argument("--timeout-seconds", type=float, default=3600.)
    matting.add_argument("--cancel-file", default=None)
    matting.add_argument("--no-audio", action="store_true")
    matting.add_argument("--sequence-id", default=None)
    matting.add_argument("--track-id", default=None)
    matting.add_argument("--audio-track-id", default=None, help="入轨时将保留的原声同步写入指定 audio 轨道")
    matting.add_argument("--timeline-start-seconds", type=float, default=0.)
    matting.add_argument("--apply", action="store_true")
    matting.add_argument("--replace-track", action="store_true")
    maskedit = _leaf_common(ms.add_parser('mask-edit', help='用本地笔刷/形状/关键帧修正已编码蒙版'))
    maskedit.add_argument('--project', required=True)
    maskedit.add_argument('--asset-id', required=True)
    maskedit.add_argument('--derived-asset-id', required=True)
    edit_source = maskedit.add_mutually_exclusive_group(required=True)
    edit_source.add_argument('--edits')
    edit_source.add_argument('--edits-from-asset', help='复用已登记蒙版保存的完整编辑计划，仍校验原输入绑定')
    maskedit.add_argument('--channel', choices=['alpha', 'luma'], default='alpha')
    maskedit.add_argument('--fps', default=None)
    maskedit.add_argument('--max-frames', type=int, default=4096)
    maskedit.add_argument('--storage-budget-mib', type=int, default=512)
    maskedit.add_argument('--buffer-budget-mib', type=int, default=256)
    maskedit.add_argument('--work-budget-million', type=int, default=200)
    maskedit.add_argument('--timeout-seconds', type=float, default=1800.)
    maskedit.add_argument('--cancel-file')
    maskedit.add_argument('--output')

    for action in ('inpaint', 'outpaint'):
        inpaint = _leaf_common(ms.add_parser(action, help='使用显式本地 LaMa/VACE 扩图并保护原画面' if action == 'outpaint' else '使用显式本地 LaMa/VACE 和蒙版修复视频区域'))
        inpaint.add_argument('--project', required=True)
        inpaint.add_argument('--asset-id', required=True)
        inpaint.add_argument('--adapter-id', required=True)
        inpaint.add_argument('--derived-asset-id', required=True)
        if action == 'inpaint':
            inpaint.add_argument('--mask-asset-id', required=True)
            inpaint.add_argument('--mask-channel', choices=['alpha', 'luma'], default='alpha')
            inpaint.add_argument('--mask-start-seconds', type=float, default=0.)
            inpaint.add_argument('--mask-resize', choices=['reject', 'nearest'], default='reject')
            inpaint.add_argument('--mask-threshold', type=float, default=.5)
            inpaint.add_argument('--mask-grow', type=int, default=4)
            inpaint.add_argument('--mask-feather', type=float, default=0.)
        else:
            inpaint.add_argument('--width', type=int, required=True)
            inpaint.add_argument('--height', type=int, required=True)
            inpaint.add_argument('--offset-x', type=int)
            inpaint.add_argument('--offset-y', type=int)
            inpaint.set_defaults(mask_asset_id=None, mask_channel='alpha', mask_start_seconds=0., mask_resize='reject', mask_threshold=.5, mask_grow=0, mask_feather=0.)
        inpaint.add_argument('--context-pixels', type=int, default=64)
        inpaint.add_argument('--model-max-edge', type=int, default=1024)
        inpaint.add_argument('--repair-blend', choices=['direct', 'harmonic'], default='direct', help='显式区域色差融合；默认直接合成')
        inpaint.add_argument('--blend-max-iterations', type=int, default=None)
        inpaint.add_argument('--blend-tolerance', type=float, default=None)
        inpaint.add_argument('--output', default=None)
        inpaint.add_argument('--start-seconds', type=float, default=0.)
        inpaint.add_argument('--end-seconds', type=float, default=None)
        inpaint.add_argument('--fps', default=None)
        inpaint.add_argument('--max-edge', type=int, default=0)
        inpaint.add_argument('--max-frames', type=int, default=18000)
        inpaint.add_argument('--timeout-seconds', type=float, default=3600.)
        inpaint.add_argument('--cancel-file', default=None)
        inpaint.add_argument('--no-audio', action='store_true')
        inpaint.add_argument('--sequence-id', default=None)
        inpaint.add_argument('--track-id', default=None)
        inpaint.add_argument('--audio-track-id', default=None)
        inpaint.add_argument('--timeline-start-seconds', type=float, default=0.)
        inpaint.add_argument('--apply', action='store_true')
        inpaint.add_argument('--replace-track', action='store_true')
        inpaint.add_argument('--prompt', default=None, help='VACE 的原文编辑提示词；不扩写、不截断')
        inpaint.add_argument('--negative-prompt', default=None)
        inpaint.add_argument('--seed', type=int, default=None)
        inpaint.add_argument('--inference-steps', type=int, default=None)
        inpaint.add_argument('--flow-shift', type=float, default=None, help='VACE flow-matching 时间偏移，默认 3；显式采样配置')
        inpaint.add_argument('--model-input-scale', type=int, choices=[1,2,4], default=None, help='VACE 受限 ROI 栅格的 1/2/4 倍模型输入；输出画布不变')
        inpaint.add_argument('--guidance-scale', type=float, default=None)
        inpaint.add_argument('--conditioning-scale', type=float, default=None)
        inpaint.add_argument('--window-frames', type=int, default=None)
        inpaint.add_argument('--window-overlap', type=int, default=None)
        inpaint.add_argument('--temporal-context', choices=['none','previous'], default=None, help='VACE 使用前窗已输出的生成前缀作为后窗条件；默认 none')
        inpaint.add_argument('--prompt-max-tokens', type=int, default=None)
        inpaint.add_argument('--scene-cut-frame', type=int, action='append', default=None)
    audio = subs.add_parser("audio", help="本地音频处理")
    aus = audio.add_subparsers(dest="action", required=True)
    extract = _leaf_common(aus.add_parser("extract", help="从本地视频或音频资产提取无损 WAV"))
    extract.add_argument("--project", required=True)
    extract_source = extract.add_mutually_exclusive_group(required=True)
    extract_source.add_argument("--asset-id", default=None, help="项目内视频/音频资产 ID")
    extract_source.add_argument("--input", default=None, help="本地视频或音频路径")
    extract.add_argument("--derived-asset-id", default=None, help="生成的派生音频资产 ID")
    extract.add_argument("--output", default=None, help="项目内 WAV 输出路径")
    extract.add_argument("--sample-rate", type=int, default=None)
    extract.add_argument("--channels", type=int, choices=(1, 2), default=None)
    extract.add_argument("--sequence-id", default=None)
    extract.add_argument("--track-id", default=None, help="可选：将提取的音频片段写入目标音频轨道")
    extract.add_argument("--timeline-start-seconds", type=float, default=0.0)
    extract.add_argument("--apply", action="store_true", help="创建快照并将提取音频片段写入目标音频轨道")
    extract.add_argument("--replace-track", action="store_true", help="应用前清空目标音频轨道已有片段")
    extract.add_argument("--license-spdx", default="LicenseRef-UNVERIFIED")
    extract.add_argument("--license-url", default="")
    extract.add_argument("--permitted-use", action="append", default=["internal"])
    extract.add_argument("--verification-status", choices=("unverified", "verified", "restricted"), default="unverified")
    extract.add_argument("--evidence", default="")
    extract.add_argument("--creator", default="unknown")
    separate = _leaf_common(aus.add_parser("separate", help="本地 HDemucs 人声/伴奏或显式 mid/side 近似"))
    separate.add_argument("--project", required=True)
    separate_source = separate.add_mutually_exclusive_group(required=True)
    separate_source.add_argument("--asset-id", default=None, help="项目内视频/音频资产 ID")
    separate_source.add_argument("--input", default=None, help="本地视频或音频路径")
    separate.add_argument("--center-asset-id", "--vocals-asset-id", dest="center_asset_id", default=None)
    separate.add_argument("--side-asset-id", "--accompaniment-asset-id", dest="side_asset_id", default=None)
    separate.add_argument("--center-output", "--vocals-output", dest="center_output", default=None)
    separate.add_argument("--side-output", "--accompaniment-output", dest="side_output", default=None)
    separate.add_argument("--adapter-id", default=None, help="可选：项目内已注册的离线音频分离适配器")
    separate.add_argument("--sample-rate", type=int, default=None)
    separate.add_argument("--sequence-id", default=None)
    separate.add_argument("--track-id", default=None, help="--apply 时写入目标音频轨道")
    separate.add_argument("--stem", choices=("center", "side", "vocals", "accompaniment"), default=None, help="模型选 vocals/accompaniment；相位近似选 center/side")
    separate.add_argument("--timeline-start-seconds", type=float, default=0.0)
    separate.add_argument("--apply", action="store_true", help="创建快照并将一个 stem 写入目标音频轨道")
    separate.add_argument("--replace-track", action="store_true", help="应用前清空目标音频轨道已有片段")
    separate.add_argument("--license-spdx", default="LicenseRef-UNVERIFIED")
    separate.add_argument("--license-url", default="")
    separate.add_argument("--permitted-use", action="append", default=["internal"])
    separate.add_argument("--verification-status", choices=("unverified", "verified", "restricted"), default="unverified")
    separate.add_argument("--evidence", default="")
    separate.add_argument("--creator", default="unknown")
    from .stem_separation_cli import add_parser as add_stem_parser
    add_stem_parser(aus, _leaf_common)
    from .enhancement_cli import add_parser as add_enhancement_parser
    add_enhancement_parser(aus, _leaf_common)
    adapter = _leaf_common(aus.add_parser("adapter", help="注册或检查本地音频模型适配器"))
    aas = adapter.add_subparsers(dest="adapter_action", required=True)
    adapter_register = _leaf_common(aas.add_parser("register", help="登记本地模型/执行器路径与哈希"))
    adapter_register.add_argument("--project", required=True)
    adapter_register.add_argument("--adapter-id", required=True)
    adapter_register.add_argument("--engine", required=True, help="本地适配器 engine；未知模型只登记，不会被隐式执行")
    adapter_register.add_argument("--model-path", default=None)
    adapter_register.add_argument("--executable", default=None, help="command-json-v1 的本地执行器")
    adapter_register.add_argument("--license-spdx", default="LicenseRef-UNVERIFIED")
    adapter_register.add_argument("--license-url", default="")
    adapter_register.add_argument("--permitted-use", action="append", default=["internal"])
    adapter_register.add_argument("--verification-status", choices=("unverified", "verified", "restricted"), default="unverified")
    adapter_register.add_argument("--evidence", default="")
    adapter_register.add_argument("--creator", default="unknown")
    adapter_register.add_argument("--device", choices=("auto", "cpu", "cuda"), default=None, help="双轨默认 cpu；四轨默认 auto，优先 GPU；显式 cuda 无回退")
    adapter_register.add_argument("--threads", type=int, default=4)
    adapter_register.add_argument("--segment-seconds", type=float, default=6.0)
    adapter_register.add_argument("--overlap", type=float, default=0.25)
    adapter_list = _leaf_common(aas.add_parser("list", help="列出项目内已登记适配器"))
    adapter_list.add_argument("--project", required=True)
    adapter_inspect = _leaf_common(aas.add_parser("inspect", help="检查适配器路径与哈希"))
    adapter_inspect.add_argument("--project", required=True)
    adapter_inspect.add_argument("--adapter-id", required=True)
    track = _leaf_common(ms.add_parser("track", help="本地对象跟踪并生成关键帧"))
    track.add_argument("--project", required=True)
    track.add_argument("--asset-id", default=None, help="项目内视频资产 ID，与 --input 二选一")
    track.add_argument("--input", default=None, help="本地视频路径，与 --asset-id 二选一")
    track.add_argument("--roi", default=None, help="模板/模型跟踪需要的归一化 ROI：x,y,width,height；蒙版模式不使用")
    track.add_argument("--start-seconds", type=float, default=0.0)
    track.add_argument("--end-seconds", type=float, default=None)
    track.add_argument("--step-frames", type=int, default=4)
    track.add_argument("--search-radius", type=int, default=48)
    track.add_argument("--max-width", type=int, default=640)
    track.add_argument("--max-samples", type=int, default=600, help="最大采样帧数，超过预算时降低采样频率并写入报告")
    track.add_argument("--adapter-id", default=None, help="可选：项目内已注册的离线视觉跟踪适配器")
    track.add_argument("--object-id", default=None, help="多目标视觉 runner 中选择要应用的 object_id")
    track.add_argument("--all-objects", action="store_true", help="多目标视觉 runner 返回所有对象；仅用于报告，不可与 --clip-id 联用")
    track.add_argument("--output", default=None, help="项目内跟踪报告 JSON 路径")
    track.add_argument("--clip-id", default=None, help="可选：将位置关键帧应用到片段")
    track.add_argument("--track-id", default=None, help="与 --clip-id 联用以限定轨道")
    track.add_argument("--sequence-id", default=None, help="与 --clip-id 联用，默认主序列")
    track_bind = _leaf_common(ms.add_parser("track-bind", help="将本地对象跟踪关键帧绑定到文字/贴纸/效果片段"))
    track_bind.add_argument("--project", required=True)
    track_bind.add_argument("--asset-id", default=None, help="项目内视频资产 ID，与 --input 二选一")
    track_bind.add_argument("--input", default=None, help="本地视频路径，与 --asset-id 二选一")
    track_bind.add_argument("--roi", default=None, help="模板/模型跟踪需要的归一化 ROI；与蒙版模式互斥")
    track_bind.add_argument("--target-clip-id", required=True, help="被绑定的文字/贴纸/效果片段 ID")
    track_bind.add_argument("--target-track-id", required=True, help="被绑定片段所在轨道 ID")
    track_bind.add_argument("--sequence-id", default=None, help="目标序列 ID，默认主序列")
    track_bind.add_argument("--source-clip-id", default=None, help="将源视频片段的裁切、变换和源时钟映射到目标画布")
    track_bind.add_argument("--source-track-id", default=None, help="与 --source-clip-id 配套的源轨道")
    track_bind.add_argument("--rotation-mode", choices=("none", "source"), default="none", help="画布绑定时可跟随源层相对旋转")
    track_bind.add_argument("--start-seconds", type=float, default=0.0)
    track_bind.add_argument("--end-seconds", type=float, default=None)
    track_bind.add_argument("--step-frames", type=int, default=4)
    track_bind.add_argument("--search-radius", type=int, default=48)
    track_bind.add_argument("--max-width", type=int, default=640)
    track_bind.add_argument("--max-samples", type=int, default=600)
    track_bind.add_argument("--adapter-id", default=None, help="可选：项目内已注册的离线视觉跟踪适配器")
    track_bind.add_argument("--object-id", default=None, help="多目标视觉 runner 中要绑定的 object_id")
    track_bind.add_argument("--offset-x", type=float, default=0.0, help="绑定位置的归一化 X 偏移")
    track_bind.add_argument("--offset-y", type=float, default=0.0, help="绑定位置的归一化 Y 偏移")
    track_bind.add_argument("--scale-mode", choices=("none", "roi"), default="none", help="是否按跟踪 ROI 宽度变化同步 transform.scale")
    track_bind.add_argument("--scale-multiplier", type=float, default=1.0)
    track_bind.add_argument("--output", default=None, help="项目内跟踪绑定报告 JSON 路径")
    track_bind.add_argument("--apply", action="store_true", help="创建快照并将绑定关键帧写回目标片段")
    reframe = _leaf_common(ms.add_parser("reframe", help="将本地对象跟踪转换为目标画幅动态裁切"))
    reframe.add_argument("--project", required=True)
    reframe.add_argument("--asset-id", default=None, help="项目内视频资产 ID，与 --input 二选一")
    reframe.add_argument("--input", default=None, help="本地视频路径，与 --asset-id 二选一")
    reframe.add_argument("--roi", default=None, help="模板/模型跟踪需要的归一化 ROI；与蒙版模式互斥")
    reframe.add_argument("--clip-id", required=True, help="要写入动态裁切的直接媒体片段 ID")
    reframe.add_argument("--track-id", required=True, help="目标视频轨道 ID")
    reframe.add_argument("--sequence-id", default=None, help="目标序列 ID，默认主序列")
    reframe.add_argument("--target-width", type=int, default=None, help="目标画布宽度；省略时读取项目画布")
    reframe.add_argument("--target-height", type=int, default=None, help="目标画布高度；省略时读取项目画布")
    reframe.add_argument("--target-aspect", type=float, default=None, help="目标宽高比；省略时由目标画布计算")
    reframe.add_argument("--margin", type=float, default=0.12, help="跟踪主体安全边距，范围 0..0.75")
    reframe.add_argument("--fit", choices=("fit", "fill", "stretch"), default="fill")
    reframe.add_argument("--start-seconds", type=float, default=None)
    reframe.add_argument("--end-seconds", type=float, default=None)
    reframe.add_argument("--step-frames", type=int, default=4)
    reframe.add_argument("--search-radius", type=int, default=48)
    reframe.add_argument("--max-width", type=int, default=640)
    reframe.add_argument("--max-samples", type=int, default=600)
    reframe.add_argument("--adapter-id", default=None, help="可选：项目内已注册的离线视觉跟踪适配器")
    reframe.add_argument("--object-id", default=None, help="多目标视觉 runner 中要重构图的 object_id")
    reframe.add_argument("--output", default=None, help="项目内自动重构图报告 JSON 路径")
    reframe.add_argument("--apply", action="store_true", help="创建快照并将动态裁切写回片段")
    for tracker in (track, track_bind, reframe):
        tracker.add_argument('--mask-asset-id', default=None, help='显式已选对象蒙版视频，与 ROI/adapter/object-id 互斥')
        tracker.add_argument('--mask-channel', choices=('alpha', 'luma'), default='alpha')
        tracker.add_argument('--mask-threshold', type=int, default=127)
        tracker.add_argument('--mask-source-start-seconds', type=float, default=0.)
        tracker.add_argument('--mask-max-edge', type=int, default=1280)
        tracker.add_argument('--mask-max-frames', type=int, default=4096)
        tracker.add_argument('--mask-budget-mib', type=int, default=256)
        tracker.add_argument('--mask-expectations', default=None)
        tracker.add_argument('--mask-scene-cut-frame', type=int, action='append', default=[])

    ad = subs.add_parser("ad", help="本地广告结构规划")
    ads = ad.add_subparsers(dest="action", required=True)
    ad_plan = _leaf_common(ads.add_parser("plan", help="从 JSON brief 生成广告节拍与时间线标记"))
    ad_plan.add_argument("--project", required=True)
    ad_plan.add_argument("--input", required=True, help="广告 brief JSON")
    ad_plan.add_argument("--analysis", default=None, help="可选本地素材理解/高光报告 JSON")
    ad_plan.add_argument("--output", default=None)
    ad_apply = _leaf_common(ads.add_parser("apply", help="将本地广告计划写入序列标记和时长"))
    ad_apply.add_argument("--project", required=True)
    ad_apply.add_argument("--input", required=True, help="ad plan 输出 JSON 或 plan 对象")
    ad_apply.add_argument("--sequence-id", default=None)
    ad_apply.add_argument("--replace-markers", action="store_true", help="替换计划中同 ID 的既有标记")
    ad_apply.add_argument("--preserve-duration", action="store_true", help="不把序列时长设置为计划时长")
    from .ad_storyboard_cli import add_parsers as add_storyboard_parsers
    add_storyboard_parsers(ads, _leaf_common)

    subtitle = subs.add_parser("subtitle", help="字幕解析、验证与规范化")
    ss = subtitle.add_subparsers(dest="action", required=True)
    subtitle_validate = _leaf_common(ss.add_parser("validate", help="验证 SRT/VTT/ASS/SSA/TTML 字幕"))
    subtitle_validate.add_argument("--input", required=True)
    subtitle_validate.add_argument("--project", default=None)
    subtitle_validate.add_argument("--duration", type=float, default=None)
    subtitle_validate.add_argument("--allow-overlap", action="store_true")
    subtitle_validate.add_argument("--report", default=None)
    subtitle_normalize = _leaf_common(ss.add_parser("normalize", help="将字幕规范化为 SRT"))
    subtitle_normalize.add_argument("--input", required=True)
    subtitle_normalize.add_argument("--output", required=True)
    subtitle_normalize.add_argument("--project", default=None)
    subtitle_normalize.add_argument("--allow-overlap", action="store_true")
    subtitle_segment = _leaf_common(ss.add_parser("segment", help="本地分句、双语分段和带摘要的局部回写"))
    subtitle_segment.add_argument("--project", required=True)
    subtitle_segment.add_argument("--input", required=True, help="本地字幕、ASR 报告或 agent-subtitle-source-v1 JSON")
    subtitle_segment.add_argument("--output", required=True, help="新的项目内分段 JSON")
    subtitle_segment.add_argument("--srt", default=None, help="新的项目内 SRT；默认与输出 JSON 同名")
    subtitle_segment.add_argument("--rules", default=None, help="本地分段规则 JSON")
    subtitle_segment.add_argument("--corrections", default=None, help="绑定输入 SHA-256 的局部纠正 JSON")
    subtitle_segment.add_argument("--expected-input-sha256", default=None)
    subtitle_segment.add_argument("--mode", choices=("original", "translation", "bilingual"), default="original")
    subtitle_segment.add_argument("--source-asset-id", action="append", default=[], help="可重复声明来源权利依赖")
    subtitle_segment.add_argument("--sequence-id", default=None)
    subtitle_segment.add_argument("--track-id", default=None)
    subtitle_segment.add_argument("--font-asset-id", default=None)
    subtitle_segment.add_argument("--timeline-start-tick", type=int, default=0)
    subtitle_segment.add_argument("--apply", action="store_true")
    subtitle_segment.add_argument("--replace-track", action="store_true")
    subtitle_align = _leaf_common(ss.add_parser('align', help='用已登记的离线 CTC 模型将原文对齐为字符/词时间'))
    for name in ('project', 'asset-id', 'transcript', 'adapter-id', 'output'):
        subtitle_align.add_argument('--' + name, required=True)
    subtitle_align.add_argument('--case', choices=('upper', 'lower', 'preserve'), default='upper')
    subtitle_align.add_argument('--granularity', choices=('character', 'whitespace'), default='character')
    subtitle_align.add_argument('--boundary-mode', choices=('ctc', 'activity'), default='ctc',
                                help='ctc 保留原字符峰；activity 用 PCM 活动估计孤立词边界并保留原时间，须 whitespace')
    subtitle_align.add_argument('--window-seconds', type=float, default=30.0)
    subtitle_align.add_argument('--context-seconds', type=float, default=.5)
    subtitle_align.add_argument('--timeout', type=float, default=3600)
    subtitle_align.add_argument('--cancel-file', default=None)
    subtitle_align.add_argument('--apply', action='store_true')
    subtitle_align.add_argument('--track-id', default=None)
    subtitle_align.add_argument('--sequence-id', default=None)
    subtitle_align.add_argument('--font-asset-id', default=None)
    subtitle_align.add_argument('--replace-track', action='store_true')
    subtitle_align.add_argument('--timeline-start-tick', type=int, default=0)
    subtitle_transcribe = _leaf_common(ss.add_parser("transcribe", help="使用本地 ASR 生成带时间戳字幕，并可应用到字幕轨道"))
    subtitle_transcribe.add_argument("--project", required=True)
    subtitle_source = subtitle_transcribe.add_mutually_exclusive_group(required=True)
    subtitle_source.add_argument("--asset-id", default=None, help="项目内本地音频/视频资产；应用时用于继承权利")
    subtitle_source.add_argument("--input", default=None, help="本地音频/视频路径")
    subtitle_model = subtitle_transcribe.add_mutually_exclusive_group(required=True)
    subtitle_model.add_argument("--model-path", default=None, help="本地 Transformers 模型目录或 whisper.cpp 模型文件")
    subtitle_model.add_argument("--adapter-id", default=None, help="已登记的本地 Whisper 模型")
    subtitle_transcribe.add_argument("--transcribe-engine", choices=("transformers", "ffmpeg-whisper"), default="transformers")
    subtitle_transcribe.add_argument("--language", default=None)
    subtitle_transcribe.add_argument("--use-gpu", action="store_true", help="ffmpeg-whisper 允许使用本地 GPU；默认 CPU")
    subtitle_transcribe.add_argument("--output", default=None, help="项目内 SRT 输出路径")
    subtitle_transcribe.add_argument("--sequence-id", default=None)
    subtitle_transcribe.add_argument("--track-id", default=None, help="应用时目标 subtitle 轨道 ID")
    subtitle_transcribe.add_argument("--timeline-start-seconds", type=float, default=0.0)
    subtitle_transcribe.add_argument("--apply", action="store_true", help="写入字幕轨道并登记生成的字幕资产")
    subtitle_transcribe.add_argument("--replace-track", action="store_true", help="应用前清空目标字幕轨道")
    subtitle_transcribe.add_argument("--font-asset-id", default=None, help="可选本地字体资产 ID，写入字幕样式")

    subtitle_evaluate = _leaf_common(ss.add_parser("evaluate", help="比较本地逐字稿或字幕，生成字符错误率 CER 报告"))
    subtitle_evaluate.add_argument("--project", default=None)
    subtitle_evaluate.add_argument("--input", required=True)
    subtitle_evaluate.add_argument("--reference", required=True)
    subtitle_evaluate.add_argument("--normalization", choices=("raw", "nfkc-text"), default="nfkc-text")
    subtitle_evaluate.add_argument("--max-cer", type=float, default=None)
    subtitle_evaluate.add_argument("--report", default=None)

    asr = subs.add_parser("asr", help="登记与核验显式本地 Whisper/CTC 模型")
    asr_sub = asr.add_subparsers(dest="action", required=True)
    asr_adapter = asr_sub.add_parser("adapter")
    asr_actions = asr_adapter.add_subparsers(dest="registration_action", required=True)
    for action in ("register", "list", "inspect"):
        leaf = _leaf_common(asr_actions.add_parser(action))
        leaf.add_argument("--project", required=True)
        if action != "list":
            leaf.add_argument("--adapter-id", required=True)
        if action == "register":
            leaf.add_argument('--engine', choices=(ASR_ENGINE, CTC_ENGINE), default=ASR_ENGINE)
            leaf.add_argument("--python-executable", required=True)
            leaf.add_argument("--model-path", required=True)
            leaf.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
            leaf.add_argument("--threads", type=int, default=4)
            leaf.add_argument("--evidence", required=True)
            leaf.add_argument("--license-spdx", default="LicenseRef-UNVERIFIED")
            leaf.add_argument("--creator", default="unknown")
            leaf.add_argument("--verification-status", choices=("unverified", "verified", "restricted"), default="unverified")
            leaf.add_argument("--permitted-use", action="append", default=None)

    from .ocr_cli import add_parser as add_ocr_parser
    add_ocr_parser(subs, _leaf_common)
    from .face_cli import add_parser as add_face_parser
    add_face_parser(subs, _leaf_common)

    tts = subs.add_parser("tts", help="本地离线文本转语音")
    tts_sub = tts.add_subparsers(dest="action", required=True)
    tts_synthesize = _leaf_common(tts_sub.add_parser("synthesize", help="使用本地 flite 或显式登记的 SoulX 生成 WAV"))
    tts_synthesize.add_argument("--project", required=True)
    tts_text = tts_synthesize.add_mutually_exclusive_group(required=True)
    tts_text.add_argument("--text", default=None, help="配音文本；默认 flite 只接受 ASCII/英文")
    tts_text.add_argument("--input", default=None, help="本地 UTF-8 文本文件")
    tts_synthesize.add_argument("--output", default=None, help="项目内 WAV 输出路径")
    tts_synthesize.add_argument("--voice", default="kal", help="FFmpeg flite voice，例如 kal、slt、rms")
    tts_synthesize.add_argument("--sample-rate", type=int, default=48_000)
    tts_synthesize.add_argument("--channels", type=int, choices=(1, 2), default=2)
    tts_synthesize.add_argument("--adapter-id", default=None, help="已登记的本地 SoulX 模型")
    tts_synthesize.add_argument("--voice-id", default=None, help="已登记的参考声；与 adapter-id 一起使用")
    tts_synthesize.add_argument("--seed", type=int, default=20261015)
    tts_synthesize.add_argument("--asset-id", default=None, help="生成音频资产 ID")
    tts_synthesize.add_argument("--apply", action="store_true", help="将生成音频加入音频轨道")
    tts_synthesize.add_argument("--sequence-id", default=None)
    tts_synthesize.add_argument("--track-id", default=None)
    tts_synthesize.add_argument("--timeline-start-seconds", type=float, default=0.0)
    for registration_kind in ("adapter", "voice"):
        group = tts_sub.add_parser(registration_kind, help="登记/检查显式本地模型或参考声")
        actions = group.add_subparsers(dest="registration_action", required=True)
        for registration_action in ("register", "list", "inspect"):
            leaf = _leaf_common(actions.add_parser(registration_action))
            leaf.add_argument("--project", required=True)
            if registration_action != "list":
                leaf.add_argument(f"--{registration_kind}-id", required=True)
            if registration_action != "register":
                continue
            leaf.add_argument("--evidence", required=True, help="本地模型许可或参考声来源/授权证据文件")
            leaf.add_argument("--license-spdx", default="LicenseRef-UNVERIFIED")
            leaf.add_argument("--creator", default="unknown")
            leaf.add_argument("--verification-status", choices=("unverified", "verified", "restricted"), default="unverified")
            leaf.add_argument("--permitted-use", action="append", default=None)
            if registration_kind == "adapter":
                leaf.add_argument("--python-executable", required=True)
                leaf.add_argument("--source-root", required=True)
                leaf.add_argument("--package-root", required=True)
                leaf.add_argument("--model-path", required=True)
                leaf.add_argument("--tokenizer-path", required=True)
            else:
                leaf.add_argument("--asset-id", required=True, help="已导入的单人参考声音频资产")
                transcript = leaf.add_mutually_exclusive_group(required=True)
                transcript.add_argument("--prompt-text", default=None, help="参考音频原样逐字稿")
                transcript.add_argument("--prompt-input", default=None, help="本地 UTF-8 逐字稿文件")

    effects = subs.add_parser("effects", help="查询本地 FFmpeg 效果目录")
    effects_sub = effects.add_subparsers(dest="action", required=True)
    effects_list = _leaf_common(effects_sub.add_parser("list", help="列出可用效果及参数契约"))
    effects_list.add_argument("--query", default=None, help="按 ID、别名、类别或后端筛选")
    effects_list.add_argument("--keyframable-only", action="store_true", help="只列出支持逐帧参数关键帧的效果")
    effects_inspect = _leaf_common(effects_sub.add_parser("inspect", help="查看单个效果的详细契约"))
    effects_inspect.add_argument("--name", required=True, help="效果 ID 或别名")

    motion = subs.add_parser("motion", help="查询和应用本地关键帧运镜预设")
    motion_sub = motion.add_subparsers(dest="action", required=True)
    from .motion_pack_cli import add_parser as add_motion_pack_parser
    add_motion_pack_parser(motion_sub, _leaf_common)
    motion_list = _leaf_common(motion_sub.add_parser("list", help="列出可用运镜预设及参数契约"))
    motion_list.add_argument("--query", default=None, help="按 ID、别名、类别或说明筛选")
    motion_inspect = _leaf_common(motion_sub.add_parser("inspect", help="查看单个运镜预设的详细契约"))
    motion_inspect.add_argument("--name", required=True, help="预设 ID 或别名")
    motion_apply = _leaf_common(motion_sub.add_parser("apply", help="将运镜预设应用到已有片段"))
    motion_apply.add_argument("--project", required=True)
    motion_apply.add_argument("--clip-id", required=True)
    motion_apply.add_argument("--track-id", default=None, help="可选轨道 ID，用于消除重复片段 ID")
    motion_apply.add_argument("--sequence-id", default=None, help="默认主序列")
    motion_apply.add_argument("--preset", required=True, help="预设 ID 或别名")
    motion_apply.add_argument("--amount", type=float, default=None, help="缩放/位移/抖动强度；默认使用目录值")
    motion_apply.add_argument("--degrees", type=float, default=None, help="旋转角度；默认使用目录值")
    motion_apply.add_argument("--points", type=int, default=None, help="shake 关键帧点数；默认使用目录值")
    motion_apply.add_argument("--start-tick", type=int, default=None, help="片段内起始 tick；默认 0")
    motion_apply.add_argument("--end-tick", type=int, default=None, help="片段内结束 tick；默认片段时长")

    html_register = _leaf_common(motion_sub.add_parser('html-register', help='固定已有本地 Node/Playwright/Chromium 工具链'))
    html_register.add_argument('--project', required=True)
    html_register.add_argument('--input', required=True)
    html_source = _leaf_common(motion_sub.add_parser('html-source', help='封装可编辑离线 HTML 动效源码与已登记资源'))
    html_source.add_argument('--project', required=True)
    html_source.add_argument('--input', required=True)
    html_source.add_argument('--asset-id', required=True)
    html_source.add_argument('--creator', default='unknown')
    html_source.add_argument('--license-spdx', default='LicenseRef-UNVERIFIED')
    stroke_source = _leaf_common(motion_sub.add_parser('stroke-source', help='从显式笔画和字符时间生成离线逐笔描线源'))
    stroke_source.add_argument('--project', required=True)
    stroke_source.add_argument('--input', required=True)
    stroke_source.add_argument('--asset-id', required=True)
    stroke_source.add_argument('--creator', default='unknown')
    stroke_source.add_argument('--license-spdx', default='LicenseRef-UNVERIFIED')
    html_inspect = _leaf_common(motion_sub.add_parser('html-inspect', help='校验并查看动效源码清单'))
    html_inspect.add_argument('--project', required=True)
    html_inspect.add_argument('--source-asset-id', required=True)
    html_fields = _leaf_common(motion_sub.add_parser('html-fields', help='发现组件字段、稳定 ID、当前取值及可写 JSON Schema；不执行浏览器'))
    html_fields.add_argument('--project', required=True)
    fields_source = html_fields.add_mutually_exclusive_group(required=True)
    fields_source.add_argument('--source-asset-id')
    fields_source.add_argument('--from-asset-id')
    html_fields.add_argument('--component-fields')
    html_fields.add_argument('--component-values')
    html_fields.add_argument('--reset-components', action='store_true')
    html_controls = _leaf_common(motion_sub.add_parser('html-controls', help='在两个新上下文实际检查一帧的 CSS、文字和图片控件'))
    html_controls.add_argument('--project', required=True)
    controls_source=html_controls.add_mutually_exclusive_group(required=True)
    controls_source.add_argument('--source-asset-id')
    controls_source.add_argument('--from-asset-id')
    html_controls.add_argument('--params')
    html_controls.add_argument('--overrides')
    html_controls.add_argument('--frame-index', type=int, default=0)
    html_controls.add_argument('--timeout-seconds', type=float, default=120)
    html_controls.add_argument('--cancel-file')
    html_quality = _leaf_common(motion_sub.add_parser('html-quality',help='逐帧核验文字裁切、出框与实际本地字体覆盖'))
    html_quality.add_argument('--project',required=True)
    quality_source=html_quality.add_mutually_exclusive_group(required=True)
    quality_source.add_argument('--source-asset-id')
    quality_source.add_argument('--from-asset-id')
    html_quality.add_argument('--params')
    html_quality.add_argument('--overrides')
    html_quality.add_argument('--timeout-seconds',type=float,default=600)
    html_quality.add_argument('--cancel-file')
    html_render = _leaf_common(motion_sub.add_parser('html-render', help='离线逐帧生成透明动效并验证全帧乱序重绘'))
    html_render.add_argument('--project', required=True)
    html_input = html_render.add_mutually_exclusive_group(required=True)
    html_input.add_argument('--source-asset-id')
    html_input.add_argument('--from-asset-id')
    html_render.add_argument('--asset-id', required=True)
    html_render.add_argument('--params')
    html_render.add_argument('--overrides', help='本地 CSS 变量、文字、已登记图片替换；null 恢复页面值')
    html_render.add_argument('--layout-check',choices=('off','strict'),help='strict 在编码前核验全帧布局/字体；省略继承配方，旧配方默认 off')
    html_render.add_argument('--shutter-samples',type=int,help='每输出帧 1..16 次真实 HTML 绘制；省略继承配方，旧配方默认 1')
    html_render.add_argument('--shutter-fraction',type=float,help='0..1 帧曝光宽度，默认 0.5；0 走单帧路径')
    shutter_cuts=html_render.add_mutually_exclusive_group()
    shutter_cuts.add_argument('--shutter-cut-tick',type=int,action='append',help='重复指定严格递增的源内部切点；采样不跨切点')
    shutter_cuts.add_argument('--shutter-clear-cuts',action='store_true',help='明确清空继承的快门切点')
    html_apply = html_render.add_mutually_exclusive_group()
    html_apply.add_argument('--apply', action='store_true')
    html_apply.add_argument('--replace-clip-id', help='仅替换指定片段的 from-asset-id 引用，保留作者剪口与处理')
    html_render.add_argument('--track-id')
    html_render.add_argument('--sequence-id')
    html_render.add_argument('--timeline-start-tick', type=int, default=0)
    html_render.add_argument('--expected-project-sha256')
    html_render.add_argument('--timeout-seconds', type=float, default=600)
    html_render.add_argument('--cancel-file')
    for parser_with_components in (html_controls, html_quality, html_render):
        parser_with_components.add_argument('--component-fields', help='完整替换组件定义快照；保留相同稳定 ID 的值')
        parser_with_components.add_argument('--component-values', help='本地 JSON：稳定字段 ID 到有类型值；null 重置')
        parser_with_components.add_argument('--reset-components', action='store_true', help='先清空组件取值；保留普通模板覆盖')

    timeline = subs.add_parser("timeline", help="时间线编排")
    ts = timeline.add_subparsers(dest="action", required=True)
    compose = _leaf_common(ts.add_parser("compose", help="应用 JSON 变更集"))
    compose.add_argument("--project", required=True)
    compose.add_argument("--input", required=True)
    compose.add_argument("--sequence-id", default=None)
    edit = _leaf_common(ts.add_parser("edit", help="按整数 tick 规划关联、同步锁、主轨联动、插入/覆盖、范围删除与双边剪口编辑"))
    edit.add_argument("--project", required=True)
    edit.add_argument("--input", required=True, help="本地编辑请求 JSON；先用 --dry-run 查看影响")
    edit.add_argument("--sequence-id", default=None)
    edit.add_argument("--expected-project-sha256", default=None, help="可选：只应用于 dry-run 返回的项目摘要")
    transition = _leaf_common(ts.add_parser('transition', help='添加、调长、移除真实源句柄转场；保持剪口和总时长'))
    transition.add_argument('--project', required=True)
    transition.add_argument('--input', required=True)
    transition.add_argument('--sequence-id', default=None)
    transition.add_argument('--expected-project-sha256', default=None)

    validate = _leaf_common(subs.add_parser("validate", help="验证项目"))
    validate.add_argument("--project", required=True)
    validate.add_argument("--target", default="commercial_ad")
    validate.add_argument("--strict-rights", action="store_true")
    validate.add_argument("--report", default=None)

    rights = subs.add_parser("rights", help="权利门禁")
    rs = rights.add_subparsers(dest="action", required=True)
    check = _leaf_common(rs.add_parser("check", help="检查发布资格"))
    check.add_argument("--project", required=True)
    check.add_argument("--target", default="commercial_ad")
    rights_list = _leaf_common(rs.add_parser("list", help="列出当前有效权利记录"))
    rights_list.add_argument("--project", required=True)
    rights_list.add_argument("--status", choices=tuple(sorted(VALID_STATUSES)), default=None)
    rights_history = _leaf_common(rs.add_parser("history", help="查看资产权利修订和审计历史"))
    rights_history.add_argument("--project", required=True)
    rights_history.add_argument("--asset-id", required=True)
    rights_update = _leaf_common(rs.add_parser("update", help="创建权利记录不可变修订"))
    rights_update.add_argument("--project", required=True)
    rights_update.add_argument("--asset-id", required=True)
    rights_update.add_argument("--status", choices=tuple(sorted(VALID_STATUSES)), default=None)
    rights_update.add_argument("--patch", default=None, help="本地 JSON 修订对象")
    rights_update.add_argument("--reason", required=True)
    rights_update.add_argument("--actor", default="ai-ad-editor")
    rights_update.add_argument("--reopen", action="store_true", help="恢复争议/过期/撤下/阻断记录")
    rights_update.add_argument("--source-url", default=None)
    rights_update.add_argument("--source-version", default=None)
    rights_update.add_argument("--retrieved-at", default=None)
    rights_update.add_argument("--creator", default=None)
    rights_update.add_argument("--license-spdx", default=None)
    rights_update.add_argument("--license-url", default=None)
    rights_update.add_argument("--attribution", default=None)
    rights_update.add_argument("--evidence", action="append", default=None)
    rights_update.add_argument("--expires-at", default=None)
    rights_update.add_argument("--takedown-status", choices=("clear", "notice", "blocked"), default=None)
    rights_update.add_argument("--permitted-use", action="append", default=None)
    rights_update.add_argument("--permitted-channel", action="append", default=None)
    rights_update.add_argument("--restriction", action="append", default=None)
    rights_export = _leaf_common(rs.add_parser("export", help="生成本地发布权利清单"))
    rights_export.add_argument("--project", required=True)
    rights_export.add_argument("--output", required=True, help="项目内 JSON 输出路径")
    rights_export.add_argument("--target", default="commercial_ad")
    rights_batch = _leaf_common(rs.add_parser("batch-update", help="原子批量创建权利记录修订"))
    rights_batch.add_argument("--project", required=True)
    rights_batch.add_argument("--input", required=True, help="本地 JSON：{updates:[{asset_id,patch,reason,actor,reopen}]} ")
    rights_impact = _leaf_common(rs.add_parser("impact", help="查找资产影响的本地历史产物"))
    rights_impact.add_argument("--project", required=True)
    rights_impact.add_argument("--asset-id", required=True)
    rights_retract = _leaf_common(rs.add_parser("retract", help="撤下资产并生成历史影响报告"))
    rights_retract.add_argument("--project", required=True)
    rights_retract.add_argument("--asset-id", required=True)
    rights_retract.add_argument("--status", choices=("takedown", "disputed", "blocked"), default="takedown")
    rights_retract.add_argument("--reason", required=True)
    rights_retract.add_argument("--actor", default="ai-ad-editor")
    rights_decide = _leaf_common(rs.add_parser("decide", help="记录历史成片替换/删除/保留决策"))
    rights_decide.add_argument("--project", required=True)
    rights_decide.add_argument("--asset-id", required=True)
    rights_decide.add_argument("--action", dest="disposition_action", choices=("replace", "delete", "retain"), required=True)
    rights_decide.add_argument("--status", choices=("proposed", "approved", "cancelled"), default="proposed")
    rights_decide.add_argument("--replacement-asset-id", default=None)
    rights_decide.add_argument("--supersedes-decision-id", default=None)
    rights_decide.add_argument("--target", default="commercial_ad")
    rights_decide.add_argument("--reason", required=True)
    rights_decide.add_argument("--actor", default="ai-ad-editor")
    rights_apply = _leaf_common(rs.add_parser("apply", help="执行已批准历史处置并更新当前项目"))
    rights_apply.add_argument("--project", required=True)
    rights_apply.add_argument("--decision-id", required=True)

    preview = subs.add_parser('preview', help='工程时间线帧/区间预览与内容缓存')
    preview_actions = preview.add_subparsers(dest='action', required=True)
    for action in ('frame', 'range'):
        item = _leaf_common(preview_actions.add_parser(action))
        item.add_argument('--project', required=True)
        item.add_argument('--sequence-id', default=None)
        if action == 'frame':
            item.add_argument('--frame', type=int, required=True, help='从 0 开始的输出显示帧号')
        else:
            item.add_argument('--start-frame', type=int, default=0)
            item.add_argument('--end-frame', type=int, required=True, help='不包含此输出帧')
        item.add_argument('--height', type=int, default=360, help='合成后缩小的最大高度，不放大')
        item.add_argument('--budget-mib', type=int, default=512)
        item.add_argument('--output', default=None, help='可选项目内新目录；省略返回缓存路径')
        item.add_argument('--cancel-file', default=None)
    preview_list = _leaf_common(preview_actions.add_parser('cache-list'))
    preview_list.add_argument('--project', required=True)
    preview_prune = _leaf_common(preview_actions.add_parser('cache-prune'))
    preview_prune.add_argument('--project', required=True)
    preview_prune.add_argument('--keep-mib', type=int, default=0)

    cache = subs.add_parser('cache',help='本地派生媒体缓存盘点与显式清理')
    cache_actions=cache.add_subparsers(dest='action',required=True)
    for action in ('list','prune'):
        item=_leaf_common(cache_actions.add_parser(action))
        item.add_argument('--project',required=True)
        item.add_argument('--kind',choices=['reverse-video','native-video-index','native-audio-clock'],default='reverse-video')
        if action=='prune':
            item.add_argument('--keep-mib',type=int,default=0)
            item.add_argument('--key',default=None,help='仅清理指定缓存；不能同时设置保留配额')

    render = _leaf_common(subs.add_parser("render", help="本地 FFmpeg 渲染"))
    render.add_argument("--project", required=True)
    render.add_argument("--sequence-id", default=None)
    render.add_argument("--output", default=None)
    render.add_argument("--publish", action="store_true")
    render.add_argument("--profile", choices=tuple(OUTPUT_PROFILES) + ("custom",), default=None, help="输出画布档案")
    render.add_argument("--width", type=int, default=None, help="自定义输出宽度；必须与 --height 一起使用")
    render.add_argument("--height", type=int, default=None, help="自定义输出高度；必须与 --width 一起使用")
    render.add_argument("--cancel-file", default=None, help="存在该文件时取消渲染并清理临时产物")
    render.add_argument("--resume", default=None, help="从此前失败/取消且依赖未变化的 render 操作重建")
    render.add_argument("--container", choices=tuple(OUTPUT_CONTAINERS), default=None, help="输出容器：mp4、webm 或 mkv")
    render.add_argument("--video-codec", choices=("libx264", "libx265", "libvpx-vp9", "libvpx", "libaom-av1"), default=None)
    render.add_argument("--audio-codec", choices=("aac", "libopus", "opus", "pcm_s16le", "pcm_s24le", "pcm_s32le", "pcm_f32le"), default=None)
    render.add_argument("--crf", type=int, default=None, help="视频 CRF，范围 0..63")
    render.add_argument("--video-bitrate", default=None, help="可选视频码率，例如 8M")
    render.add_argument("--audio-bitrate", default=None, help="音频码率，例如 192k")
    render.add_argument("--pixel-format", choices=OUTPUT_PIXEL_FORMATS, default=None)
    render.add_argument('--hardware-encode', choices=('off', 'prefer', 'require'), default=None)
    render.add_argument('--hardware-decode', choices=('off', 'prefer', 'require'), default=None)
    render.add_argument('--hardware-encoder', choices=('auto', 'nvenc', 'qsv', 'amf', 'mf'), default=None)
    render.add_argument('--hardware-decoder', choices=('auto', 'd3d11va', 'cuda'), default=None)
    render.add_argument('--hardware-probe-mib', type=int, default=None, help='四帧像素工作量预算 1..1024 MiB，不是全部显存上限')

    surface = subs.add_parser('surface', help='原生帧时钟与浮点像素包，供Agent后续编辑')
    surface_sub=surface.add_subparsers(dest='action',required=True)
    surface_export=_leaf_common(surface_sub.add_parser('export',help='从已登记源提取浮点帧，保留原PTS/alpha'))
    surface_export.add_argument('--project',required=True)
    surface_export.add_argument('--asset-id',required=True)
    surface_export.add_argument('--output',required=True,help='工程内新目录，包含Float32像素、int64帧时钟与JSON清单')
    surface_export.add_argument('--source-primaries',required=True,choices=('bt709','display-p3','bt2020','prophoto-rgb','aces-ap1'))
    surface_export.add_argument('--source-transfer',required=True,choices=('linear','srgb','bt709-oetf','gamma22','gamma24','prophoto-rgb'))
    surface_export.add_argument('--working-primaries',default='bt709',choices=('bt709','display-p3','bt2020','prophoto-rgb','aces-ap1'))
    surface_export.add_argument('--working-transfer',default='linear',choices=('linear','srgb','bt709-oetf','gamma22','gamma24','prophoto-rgb'))
    surface_export.add_argument('--source-white-xy',type=float,nargs=2,metavar=('X','Y'),help='明确RGB参考白点CIE1931 xy；默认随基色配置')
    surface_export.add_argument('--working-white-xy',type=float,nargs=2,metavar=('X','Y'),help='明确工作RGB参考白点；D65交付限制不适用于中间浮点包')
    surface_export.add_argument('--pixel-family',default='rgb',choices=('rgb','yuv'))
    surface_export.add_argument('--yuv-matrix',choices=('bt709','bt470bg','smpte170m','bt2020nc'))
    surface_export.add_argument('--yuv-range',choices=('full','limited'))
    surface_export.add_argument('--chroma-location',choices=('left','center','topleft','top','bottomleft','bottom'))
    surface_export.add_argument('--scan',choices=('progressive',),help='YCbCr须明确声明逐行采样语义')
    surface_export.add_argument('--alpha-association',default='straight',choices=('straight','premultiplied'))
    surface_export.add_argument('--start-frame',type=int,default=0)
    surface_export.add_argument('--stop-frame',type=int,help='原生源帧的半开区间末帧；不是输出CFR帧号')
    surface_export.add_argument('--transform-json',help='本地JSON：width/height/inverse(2×3逆仿射)')
    surface_export.add_argument('--max-output-mib',type=int,default=2048,help='1..2048 MiB浮点像素/时钟/清单预算，不是峰值RSS')
    surface_export.add_argument('--cancel-file')
    surface_inspect=_leaf_common(surface_sub.add_parser('inspect',help='只读核验浮点包的像素与原生时钟字节'))
    surface_inspect.add_argument('--project',required=True)
    surface_inspect.add_argument('--input',required=True)

    queue = subs.add_parser("queue", help="项目内持久化渲染队列")
    queue_sub = queue.add_subparsers(dest="action", required=True)
    queue_enqueue = _leaf_common(queue_sub.add_parser("enqueue", help="写入一个或多个本地渲染作业"))
    queue_enqueue.add_argument("--project", required=True)
    queue_enqueue.add_argument("--input", required=True, help="作业 JSON；可为单个作业对象或 {jobs:[...]} 文件")
    queue_list = _leaf_common(queue_sub.add_parser("list", help="列出队列作业"))
    queue_list.add_argument("--project", required=True)
    queue_list.add_argument("--status", choices=tuple(sorted(JOB_STATUSES)), default=None)
    queue_inspect = _leaf_common(queue_sub.add_parser("inspect", help="检查单个队列作业"))
    queue_inspect.add_argument("--project", required=True)
    queue_inspect.add_argument("--job-id", required=True)
    queue_run = _leaf_common(queue_sub.add_parser("run", help="执行本地渲染作业；可用受控 worker 并发"))
    queue_run.add_argument("--project", required=True)
    queue_run.add_argument("--job-id", default=None, help="只执行指定作业；失败或取消作业可显式重试")
    queue_run.add_argument("--max-jobs", type=int, default=None, help="本次最多执行的待处理作业数")
    queue_run.add_argument("--continue-on-error", action="store_true", help="单个作业失败后继续执行后续作业")
    queue_run.add_argument("--workers", type=int, default=1, help="本次最多并发的本地 FFmpeg worker 数；默认 1，超过 1 时必须同时使用 --continue-on-error")
    queue_run.add_argument('--reuse-identical', action='store_true', help='显式复用同次串行调用内相同内容的成功产物；要求完整本地依赖和新输出路径')
    queue_cancel = _leaf_common(queue_sub.add_parser("cancel", help="请求取消或取消尚未启动的作业"))
    queue_cancel.add_argument("--project", required=True)
    queue_cancel.add_argument("--job-id", required=True)

    quality = subs.add_parser("quality", help="输出质量检查")
    qs = quality.add_subparsers(dest="action", required=True)
    qmask = _leaf_common(qs.add_parser("mask", help="逐帧核对本地蒙版范围与明确正负检查点"))
    qmask.add_argument("--project", required=True)
    qmask.add_argument("--asset-id", required=True)
    qmask.add_argument("--channel", choices=("alpha", "luma"), default="alpha")
    qmask.add_argument("--threshold", type=int, default=127)
    qmask.add_argument("--fps", default=None)
    qmask.add_argument("--max-edge", type=int, default=1280)
    qmask.add_argument("--max-frames", type=int, default=4096)
    qmask.add_argument("--budget-mib", type=int, default=256)
    qmask.add_argument("--expectations", default=None)
    qmask.add_argument("--scene-cut-frame", type=int, action="append", default=[])
    qmask.add_argument("--report", default=None)
    qcheck = _leaf_common(qs.add_parser("check", help="检查已渲染媒体"))
    qcheck.add_argument("--project", required=True)
    qcheck.add_argument("--input", required=True)
    qcheck.add_argument("--sequence-id", default=None)
    qcheck.add_argument("--report", default=None)
    qcheck.add_argument("--require-audio", action="store_true")
    qcheck.add_argument("--expensive", action="store_true", help="运行黑帧和响度扫描")
    qcheck.add_argument("--max-av-sync-ms", type=float, default=80.0, help="允许的视频/音频时长差，默认 80ms")
    qcheck.add_argument("--target-lufs", type=float, default=None, help="可选目标 integrated LUFS；需配合 --expensive")
    qcheck.add_argument("--lufs-tolerance", type=float, default=2.0)
    qcheck.add_argument("--fail-on-black", action="store_true", help="检测到黑帧区间时将质量检查判失败")
    qcheck.add_argument("--max-true-peak-dbfs", type=float, default=None, help="可选 true peak 上限，常用 -1 dBFS")
    qcheck.add_argument("--profile", choices=tuple(OUTPUT_PROFILES) + ("custom",), default=None, help="按输出画布档案检查")
    qcheck.add_argument("--width", type=int, default=None)
    qcheck.add_argument("--height", type=int, default=None)
    qscopes = _leaf_common(qs.add_parser("scopes", help="生成本地 waveform/vectorscope/histogram 色彩审查图"))
    qscopes.add_argument("--project", required=True)
    qscopes.add_argument("--input", required=True)
    qscopes.add_argument("--at-seconds", type=float, default=0.0)
    qscopes.add_argument("--output-dir", default=None, help="项目内 scope 输出目录；默认 cache/scopes/<scope_id>")
    qgolden = _leaf_common(qs.add_parser("golden", help="捕获或验证固定本地质量 golden 清单"))
    qgolden.add_argument("--project", required=True)
    qgolden.add_argument("--input", required=True, help="待捕获或验证的本地媒体")
    qgolden.add_argument("--mode", choices=("capture", "verify"), default="verify")
    qgolden.add_argument("--manifest", default=None, help="项目内 golden JSON；默认 validation/golden-quality.json")
    qgolden.add_argument("--sequence-id", default=None)
    qgolden.add_argument("--require-audio", action=argparse.BooleanOptionalAction, default=None)
    qgolden.add_argument("--expensive", action=argparse.BooleanOptionalAction, default=None, help="运行黑帧和响度扫描；verify 默认沿用清单")
    qgolden.add_argument("--max-av-sync-ms", type=float, default=None)
    qgolden.add_argument("--target-lufs", type=float, default=None)
    qgolden.add_argument("--lufs-tolerance", type=float, default=None)
    qgolden.add_argument("--fail-on-black", action=argparse.BooleanOptionalAction, default=None)
    qgolden.add_argument("--max-true-peak-dbfs", type=float, default=None)
    qgolden.add_argument("--profile", choices=tuple(OUTPUT_PROFILES) + ("custom",), default=None)
    qgolden.add_argument("--width", type=int, default=None)
    qgolden.add_argument("--height", type=int, default=None)

    for output_parser in (render, qcheck, qgolden):
        output_parser.add_argument('--projection-acceleration',choices=('off','prefer','require'),default=None,
                                   help='动态裁切/仿射/子序列投影的OpenCL策略，独立于硬件编码')
        output_parser.add_argument('--projection-device',default=None,help='原生OpenCL platform.device索引，例如0.0')
        output_parser.add_argument('--projection-memory-mib',type=int,default=None,
                                   help='GPU投影工作栅格准入配额MiB，1..65536；不是总VRAM上界')
        output_parser.add_argument('--sequence-sampling', choices=('bilinear','area'), default=None,
                                   help='本次输出的序列容器投影采样，不改写作者工程')
        output_parser.add_argument('--sequence-memory-mib', type=int, default=None,
                                   help='序列投影工作配额 MiB，1..65536；不是进程总内存上界')

    convert = subs.add_parser("convert", help="项目/交换格式互操作")
    cs = convert.add_subparsers(dest="action", required=True)
    cimport = _leaf_common(cs.add_parser("import", help="导入 Agent JSON、项目包、OTIO、MLT 或本地明文草稿 JSON"))
    cimport.add_argument("--input", required=True)
    cimport.add_argument("--output", required=True, help="新项目目录")
    cimport.add_argument("--strict", action="store_true", help="明文草稿适配器遇到近似/不支持/失败时拒绝写入")
    cexport = _leaf_common(cs.add_parser("export", help="导出 Agent Project、项目包或本地交换格式"))
    cexport.add_argument("--project", required=True)
    cexport.add_argument("--output", required=True)
    cexport.add_argument("--target-format", choices=("agent-json", "package", "otio", "kdenlive-xml", "jianying-draft-json"), default="agent-json")
    cexport.add_argument("--strict", action="store_true", help="明文草稿适配器遇到近似/不支持/失败时拒绝写入")
    cexport.add_argument("--bake-tracking", action="store_true", help="agent-json/package导出为普通跟踪关键帧并保留源绑定旁车；原生工程逐帧Float32核验")

    template = subs.add_parser("template", help="模板实例化")
    ts2 = template.add_subparsers(dest="action", required=True)
    apply_template = _leaf_common(ts2.add_parser("apply", help="应用本地模板 JSON"))
    apply_template.add_argument("--project", required=True)
    apply_template.add_argument("--input", required=True)
    apply_template.add_argument("--variables", default=None, help="变量 JSON 文件")
    batch_template = _leaf_common(ts2.add_parser("batch", help="批量实例化并本地渲染模板"))
    batch_template.add_argument("--project", required=True)
    batch_template.add_argument("--input", required=True, help="模板 JSON 文件")
    batch_template.add_argument("--variables", required=True, help="variants JSON 文件")
    batch_template.add_argument("--output", required=True, help="项目内批量输出目录")
    batch_template.add_argument("--publish", action="store_true")
    batch_template.add_argument("--continue-on-error", action="store_true")

    library = subs.add_parser("library", help="本地素材与模板资产索引")
    ls = library.add_subparsers(dest="action", required=True)
    lindex = _leaf_common(ls.add_parser("index", help="索引本地媒体/字幕/字体"))
    lindex.add_argument("--root", required=True)
    lindex.add_argument("--output", required=True)
    lindex.add_argument("--max-files", type=int, default=5000)
    lindex.add_argument("--license-spdx", default="LicenseRef-UNVERIFIED")
    lindex.add_argument("--verification-status", choices=("unverified", "verified", "restricted"), default="unverified")
    lindex.add_argument("--previous", default=None, help="上一版本地目录 JSON，用于增量刷新")
    lindex.add_argument("--incremental", action="store_true", help="按文件 stat 与字幕侧车签名复用未变化记录")
    lindex.add_argument("--visual-hash", action="store_true", help="通过本地 FFmpeg 生成候选感知哈希样本")
    lsearch = _leaf_common(ls.add_parser("search", help="查询本地资产索引"))
    lsearch.add_argument("--catalog", required=True)
    lsearch.add_argument("--query", default="")
    lsearch.add_argument("--kind", default=None)
    lsearch.add_argument("--verification-status", default=None)
    lsearch.add_argument("--min-duration", type=float, default=None)
    lsearch.add_argument("--max-duration", type=float, default=None)
    lsearch.add_argument("--min-width", type=int, default=None)
    lsearch.add_argument("--min-height", type=int, default=None)
    lsearch.add_argument("--has-audio", action=argparse.BooleanOptionalAction, default=None, help="按是否含音频流过滤")
    lsearch.add_argument("--duplicate-only", action="store_true", help="只返回精确内容重复组中的记录")
    lsearch.add_argument("--limit", type=int, default=50)
    lduplicates = _leaf_common(ls.add_parser("duplicates", help="按 SHA-256 列出精确重复素材组"))
    lduplicates.add_argument("--catalog", required=True)
    lduplicates.add_argument("--include-unique", action="store_true", help="同时返回只有一个成员的哈希组")
    lsimilar = _leaf_common(ls.add_parser("similar", help="按可选 FFmpeg 感知哈希列出相似画面候选组"))
    lsimilar.add_argument("--catalog", required=True)
    lsimilar.add_argument("--max-distance", type=int, default=12, help="平均哈希汉明距离上限")

    fragment = subs.add_parser('fragment', help='离线可复用已编辑片段组')
    fragments_sub = fragment.add_subparsers(dest='action', required=True)
    for action in ('save', 'apply', 'list', 'inspect'):
        leaf = _leaf_common(fragments_sub.add_parser(action))
        leaf.add_argument('--library', required=True)
        if action in {'save', 'apply'}:
            leaf.add_argument('--project', required=True)
            leaf.add_argument('--input', required=True, help='本地保存/插入请求 JSON')
            leaf.add_argument('--expected-project-sha256', default=None)
            leaf.add_argument('--expected-fragment-sha256', default=None)
        if action == 'inspect':
            leaf.add_argument('--id', required=True)
            leaf.add_argument('--version', required=True, type=int)
        if action == 'list':
            leaf.add_argument('--query', default='')
        else:
            leaf.add_argument('--max-bytes', type=int, default=fragments.DEFAULT_MAX_BYTES)

    lut = subs.add_parser("lut", help="项目内本地 LUT 资产库")
    luts = lut.add_subparsers(dest="action", required=True)
    lut_register = _leaf_common(luts.add_parser("register", help="登记并复制本地 LUT 到项目资产库"))
    lut_register.add_argument("--project", required=True)
    lut_register.add_argument("--input", required=True, help="本地 .cube/.3dl/.csp/.dat 文件")
    lut_register.add_argument("--lut-id", default=None, help="稳定 LUT ID；默认由 SHA-256 派生")
    lut_register.add_argument("--name", default=None)
    lut_register.add_argument("--license-spdx", default="LicenseRef-UNVERIFIED")
    lut_register.add_argument("--license-url", default="")
    lut_register.add_argument("--permitted-use", action="append", default=["internal"])
    lut_register.add_argument("--verification-status", choices=("unverified", "verified", "restricted"), default="unverified")
    lut_register.add_argument("--evidence", default="")
    lut_register.add_argument("--creator", default="unknown")
    lut_list = _leaf_common(luts.add_parser("list", help="列出项目内已登记 LUT"))
    lut_list.add_argument("--project", required=True)
    lut_list.add_argument("--query", default=None)
    lut_inspect = _leaf_common(luts.add_parser("inspect", help="检查 LUT 文件、哈希和元数据"))
    lut_inspect.add_argument("--project", required=True)
    lut_inspect.add_argument("--lut-id", required=True)

    look = subs.add_parser('look', help='500 个离线开源风格预设（含逐项说明与许可）')
    look_sub = look.add_subparsers(dest='action', required=True)
    look_list = _leaf_common(look_sub.add_parser('list', help='按中文/英文/类别搜索风格'))
    look_list.add_argument('--query', default='')
    look_list.add_argument('--category', default=None)
    look_inspect = _leaf_common(look_sub.add_parser('inspect', help='检查来源、许可及完整性'))
    look_inspect.add_argument('--id', required=True)
    look_preview = _leaf_common(look_sub.add_parser('preview', help='用本地图片或内置测试卡实际渲染 PNG'))
    look_preview.add_argument('--id', required=True)
    look_preview.add_argument('--input', default=None)
    look_preview.add_argument('--output', required=True)
    look_preview.add_argument('--strength', type=float, default=1.)
    look_apply = _leaf_common(look_sub.add_parser('apply', help='复制 LUT/许可到项目并应用预设'))
    look_apply.add_argument('--project', required=True)
    look_apply.add_argument('--id', required=True)
    look_target = look_apply.add_mutually_exclusive_group(required=True)
    look_target.add_argument('--clip-id')
    look_target.add_argument('--global', dest='global_scope', action='store_true', help='应用到项目全局调整链')
    look_apply.add_argument('--sequence-id', default='seq_main')
    look_apply.add_argument('--strength', type=float, default=1.)
    look_apply.add_argument('--append', action='store_true', help='保留并叠加既有内置风格；默认替换内置风格')

    schema = subs.add_parser('schema',help='查看/原字节导出随包固定的 Agent Project 合同')
    schema_sub = schema.add_subparsers(dest='action',required=True)
    _leaf_common(schema_sub.add_parser('show',help='读取随包合同及实际摘要'))
    schema_export = _leaf_common(schema_sub.add_parser('export',help='向新本地文件导出原字节合同'))
    schema_export.add_argument('--output',required=True)
    doctor = _leaf_common(subs.add_parser("doctor", help="检查本机依赖"))
    doctor.add_argument("--project", default=None)
    operation = _leaf_common(subs.add_parser("operation", help="查看操作状态"))
    osub = operation.add_subparsers(dest="action", required=True)
    opinspect = _leaf_common(osub.add_parser("inspect", help="读取操作记录"))
    opinspect.add_argument("--project", required=True)
    opinspect.add_argument("--operation-id", required=True)
    _leaf_common(subs.add_parser("version", help="版本信息"))
    _leaf_common(subs.add_parser("capabilities", help="输出本地 Agent 能力清单"))
    policy = subs.add_parser("policy", help="本地运行策略")
    policy_sub = policy.add_subparsers(dest="action", required=True)
    policy_audit = _leaf_common(policy_sub.add_parser("audit", help="审计项目产物中的远程/闭源引用"))
    policy_audit.add_argument("--project", required=True)
    from .community_cli import add_parser as add_community_parser
    add_community_parser(subs, _leaf_common)
    from .capture import add_parser as add_capture_parser
    add_capture_parser(subs, _leaf_common)
    from .semantic_cli import add_parser as add_semantic_parser
    add_semantic_parser(subs, _leaf_common)
    from .dubbing_cli import add_parser as add_dubbing_parser
    add_dubbing_parser(subs, _leaf_common)
    return parser


def _envelope(command: str, args: argparse.Namespace, *, data: Any = None, status: str = "succeeded", warnings: list[Any] | None = None, errors: list[Any] | None = None, operation_id: str | None = None) -> dict[str, Any]:
    return {
        "ok": status == "succeeded" or status == "planned",
        "command": command,
        "request_id": args.request_id or new_id("req"),
        "operation_id": operation_id,
        "status": status,
        "data": data if data is not None else {},
        "artifacts": [],
        "warnings": warnings or [],
        "errors": errors or [],
        "provenance": {"cli_version": VERSION, "schema_version": SCHEMA_VERSION, "engine_version": ENGINE_ID, "started_at": now_iso(), "finished_at": now_iso(), "network": "disabled"},
    }


def _print(value: dict[str, Any], fmt: str = "json") -> None:
    if fmt == "text":
        print(json.dumps(value, ensure_ascii=False, indent=2))
    else:
        print(json.dumps(value, ensure_ascii=False, separators=(",", ":")))


def _command_name(args: argparse.Namespace) -> str:
    action = getattr(args, "action", None)
    return f"{args.domain}.{action}" if action else str(args.domain)


def _operation(root: Path, operation_id: str, payload: dict[str, Any]) -> None:
    atomic_write_json(root / "operations" / f"{operation_id}.json", payload)


def _progress(args: argparse.Namespace, operation_id: str, event_type: str, stage: str, percent: float | None, message: str, *, error: Any = None) -> None:
    if getattr(args, "progress", "none") != "jsonl":
        return
    event = {"event_id": new_id("event"), "operation_id": operation_id, "type": event_type, "at": now_iso(), "stage": stage, "percent": percent, "message": message, "artifacts": []}
    if error is not None:
        event["error"] = error
    print(json.dumps(event, ensure_ascii=False, separators=(",", ":")), file=sys.stderr)


def _load_changes(path: str) -> dict[str, Any]:
    value = load_json(Path(path))
    if not isinstance(value, dict):
        raise argument_error("变更集必须是 JSON 对象")
    return value


def command_project_init(args: argparse.Namespace) -> dict[str, Any]:
    if args.dry_run:
        root = Path(args.path).expanduser().resolve()
        return _envelope("project.init", args, status="planned", data={"root": str(root), "name": args.name or root.name, "project_id": args.project_id or "generated-at-apply"})
    root, project = create_project(args.path, args.name, args.project_id)
    return _envelope("project.init", args, data={"project": str(project_file(root)), "root": str(root), "project_id": project["project"]["id"]})


def command_project_inspect(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    report = validate_project(root, project, strict_rights=False)
    return _envelope("project.inspect", args, data={"root": str(root), "project": project["project"], "assets": len(project.get("assets", [])), "sequences": len(project.get("sequences", [])), "validation": report})


def command_project_snapshot(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    if args.dry_run:
        return _envelope("project.snapshot", args, status="planned", data={"project": str(root), "label": args.label, "history": str(history_dir(root))})
    snapshot = create_snapshot(root, project, label=args.label)
    operation_id = new_id("op")
    _operation(root, operation_id, {"operation_id": operation_id, "command": "project.snapshot", "status": "succeeded", **snapshot})
    return _envelope("project.snapshot", args, data=snapshot, operation_id=operation_id)


def command_project_restore(args: argparse.Namespace) -> dict[str, Any]:
    root, current = load_project(args.project)
    requested = Path(args.snapshot).expanduser()
    if not requested.is_absolute() and requested.suffix.lower() == ".json":
        project_relative = (root / requested).resolve()
        history_relative = (history_dir(root) / requested.name).resolve()
        if project_relative.exists():
            requested = project_relative
        elif history_relative.exists():
            requested = history_relative
    if requested.suffix.lower() == ".json" and requested.exists():
        try:
            requested.resolve().relative_to(history_dir(root).resolve())
        except ValueError as exc:
            raise argument_error("快照路径必须位于项目 history 目录内", str(requested)) from exc
        snapshot_id = requested.stem
    else:
        snapshot_id = str(args.snapshot)
    payload = load_snapshot(root, snapshot_id)
    candidate = payload.get("project")
    if not isinstance(candidate, dict):
        raise AppError("SNAPSHOT_INVALID", "快照 project 字段无效", exit_code=2, path=f"{snapshot_id}.project")
    validation = validate_project(root, candidate, strict_rights=False)
    if not validation["ok"]:
        raise AppError("SNAPSHOT_PROJECT_INVALID", "快照恢复前校验失败，拒绝覆盖当前项目", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    if args.dry_run:
        return _envelope("project.restore", args, status="planned", data={"snapshot_id": snapshot_id, "project_id": candidate.get("project", {}).get("id"), "validation": validation})
    backup = create_snapshot(root, current, label="before-restore")
    restored = restore_snapshot(root, payload)
    operation_id = new_id("op")
    _operation(root, operation_id, {"operation_id": operation_id, "command": "project.restore", "status": "succeeded", "snapshot_id": snapshot_id, "backup_snapshot_id": backup["snapshot_id"], "created_at": now_iso()})
    return _envelope("project.restore", args, data={"snapshot_id": snapshot_id, "backup": backup, **restored, "validation": validation}, operation_id=operation_id)


def command_project_migrate(args: argparse.Namespace) -> dict[str, Any]:
    root, current = load_project(args.project)
    if not isinstance(current.get("schema_version"), str) or current["schema_version"] not in SUPPORTED_SOURCE_VERSIONS:
        raise AppError("SCHEMA_VERSION_UNSUPPORTED", "迁移仅支持本项目 schema 0.0.0 和 0.1.0；未知格式须使用显式转换器", exit_code=2, path="schema_version")
    if args.report:
        requested_report = Path(args.report).expanduser()
        report_path = (root / "validation" / requested_report if not requested_report.is_absolute() else requested_report).resolve()
    else:
        report_path = root / "validation" / f"migration_{new_id('report')}.json"
    ensure_inside(root / "validation", report_path)
    if report_path.suffix.lower() != ".json":
        raise argument_error("迁移报告必须使用 validation 目录内的 JSON 文件", str(report_path))
    metadata: dict[str, dict[str, Any]] = {}
    for asset in current.get("assets", []):
        if not isinstance(asset, dict):
            continue
        if asset.get("sha256") and "probe" in asset:
            continue
        uri = asset.get("uri")
        if not isinstance(uri, str) or not uri or "://" in uri:
            raise AppError("MIGRATION_ASSET_URI_MISSING", "迁移资产必须包含本地文件 uri", exit_code=2, path="assets[].uri")
        source = Path(uri)
        if not source.is_absolute():
            source = root / source
        extensions = asset.get("extensions") if isinstance(asset.get("extensions"), dict) else {}
        source = ensure_inside(root, source, allow_external=bool(extensions.get("external_authorized")))
        if not source.is_file():
            raise AppError("MIGRATION_ASSET_HASH_MISSING", "资产缺少元数据且本地文件不存在，拒绝猜测内容指纹", exit_code=3, path=str(source))
        supplied: dict[str, Any] = {}
        if not asset.get("sha256"):
            supplied["sha256"] = f"sha256:{sha256_file(source)}"
        if "probe" not in asset:
            supplied["probe"] = probe_media(source)
        metadata[str(asset.get("id"))] = supplied
    candidate, migration = migrate_project_payload(current, timestamp=now_iso(), asset_metadata=metadata)
    validation = validate_project(root, candidate, strict_rights=False)
    if not validation["ok"]:
        raise AppError(
            "MIGRATION_PROJECT_INVALID",
            "迁移候选项目校验失败，拒绝覆盖原项目",
            exit_code=2,
            path=str(project_file(root)),
            cause=json.dumps(validation, ensure_ascii=False),
        )
    if args.dry_run:
        return _envelope("project.migrate", args, status="planned", data={"project": str(root), "migration": migration, "validation": validation})
    backup: dict[str, Any] | None = None
    operation_id = new_id("op")
    if migration["changed"]:
        backup = create_snapshot(root, current, label="before-migrate")
        save_project(root, candidate)
    report_payload = {
        **migration,
        "created_at": now_iso(),
        "project_id": candidate.get("project", {}).get("id"),
        "operation_id": operation_id,
        "backup_snapshot_id": backup.get("snapshot_id") if backup else None,
        "validation": validation,
    }
    atomic_write_json(report_path, report_payload)
    status = "succeeded"
    _operation(root, operation_id, {"operation_id": operation_id, "command": "project.migrate", "status": status, "changed": migration["changed"], "report": str(report_path), "backup_snapshot_id": report_payload["backup_snapshot_id"], "created_at": now_iso()})
    return _envelope("project.migrate", args, data={"migration": migration, "report": str(report_path), "backup": backup, "validation": validation}, operation_id=operation_id)


def command_project_recover(args: argparse.Namespace) -> dict[str, Any]:
    from .utils import project_root
    from .job_workspaces import recover_workspaces
    root = project_root(args.project)
    journal = root / "operations" / "project-transaction.json"
    if not (root / 'project.json').exists() and not journal.exists():
        raise AppError('PROJECT_NOT_FOUND', '项目或待恢复事务不存在', exit_code=3, path=str(root))
    if args.dry_run:
        data = {"project": str(root), "journal": str(journal), "pending": journal.exists()}
        if args.cleanup_jobs:
            data['job_recovery'] = recover_workspaces(root, dry_run=True)
            data['job_recovery']['metadata_rollback_pending'] = journal.exists()
        return _envelope("project.recover", args, status="planned", data=data)
    recovery = recover_pending_transaction(root)
    load_project(root)  # Verify the recovered project before interpreting asset references.
    jobs = recover_workspaces(root) if args.cleanup_jobs else None
    operation_id = new_id("op")
    _operation(root, operation_id, {"operation_id": operation_id, "command": "project.recover", "status": "succeeded", "recovery": recovery, "job_recovery": jobs, "created_at": now_iso()})
    data = {"project": str(root), "recovery": recovery}
    if jobs is not None: data['job_recovery'] = jobs
    return _envelope("project.recover", args, data=data, operation_id=operation_id)


def command_media_ingest(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    source = Path(args.input).expanduser().resolve()
    if source.as_uri().startswith("http") or not source.exists() or not source.is_file():
        raise argument_error("--input 必须是存在的本地文件", str(source))
    asset_id = args.asset_id or new_id("asset")
    if asset_id in asset_map(project):
        raise argument_error(f"资产 ID 已存在: {asset_id}", "--asset-id")
    probe = probe_media(source)
    kind = classify_path(source, probe)
    destination = root / "assets" / f"{asset_id}_{safe_filename(source.name)}"
    if not args.dry_run:
        shutil.copy2(source, destination)
    digest = sha256_file(source)
    uri = str(destination.relative_to(root)).replace("\\", "/")
    source_reference = require_local_reference(args.source_url or f"local://{source}", field="--source-url")
    license_reference = require_local_reference(args.license_url, field="--license-url") if args.license_url else ""
    evidence_reference = require_local_reference(args.evidence, field="--evidence") if args.evidence else ("" if args.verification_status == "unverified" else f"local://{source}")
    asset = {"id": asset_id, "kind": kind, "uri": uri, "sha256": f"sha256:{digest}", "probe": probe, "rights_ref": asset_id, "source": {"source_url": source_reference, "retrieved_at": now_iso(), "original_name": source.name}}
    record = {"asset_id": asset_id, "kind": kind, "sha256": f"sha256:{digest}", "source_url": source_reference, "source_version": "local", "retrieved_at": now_iso(), "creator": args.creator, "license_spdx": args.license_spdx, "license_url": license_reference, "attribution": "", "permitted_uses": list(dict.fromkeys(args.permitted_use)), "restrictions": [], "evidence": evidence_reference, "verification_status": args.verification_status, "verified_by": "ai-ad-editor" if args.verification_status == "verified" else "", "takedown_status": "clear", "notes": "Imported by local CLI"}
    if args.dry_run:
        return _envelope("media.ingest", args, status="planned", data={"asset": asset, "rights_record": record})
    project.setdefault("assets", []).append(asset)
    ledger = load_ledger(root)
    add_record(ledger, record)
    operation_id = new_id("op")
    _progress(args, operation_id, "started", "media.ingest", 0, "开始导入本地素材")
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.ingest", "asset_id": asset_id, "at": now_iso()})
    save_project(root, project)
    save_ledger(root, ledger)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "media.ingest", "status": "succeeded", "asset_id": asset_id, "sha256": digest, "created_at": now_iso()})
    _progress(args, operation_id, "completed", "media.ingest", 100, "素材导入完成")
    return _envelope("media.ingest", args, data={"asset": asset, "rights": record, "path": str(destination)}, operation_id=operation_id)


def command_audio_extract(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    if args.timeline_start_seconds < 0:
        raise argument_error("timeline_start_seconds 不能为负数", "timeline_start_seconds")
    if args.apply and not args.track_id:
        raise argument_error("--apply 必须提供 --track-id", "track_id")
    if args.replace_track and not args.apply:
        raise argument_error("--replace-track 必须与 --apply 一起使用", "replace_track")
    source_asset: dict[str, Any] | None = None
    parent_rights_ref: str | None = None
    if args.asset_id:
        source_asset = asset_map(project).get(str(args.asset_id))
        if not source_asset:
            raise argument_error(f"找不到音频提取源资产: {args.asset_id}", "asset_id")
        source = Path(str(source_asset.get("uri", "")))
        if not source.is_absolute():
            source = root / source
        parent_rights_ref = str(source_asset.get("rights_ref") or source_asset.get("id"))
    else:
        raw_input = str(args.input or "").strip()
        if raw_input.lower().startswith(("http://", "https://")):
            raise argument_error("--input 只接受本地视频或音频文件", "input")
        source = Path(raw_input).expanduser().resolve()
    source = source.resolve()
    input_probe = inspect_audio_source(source)
    derived_id = str(args.derived_asset_id or new_id("asset_audio"))
    if derived_id in asset_map(project):
        raise argument_error(f"派生音频资产 ID 已存在: {derived_id}", "derived_asset_id")
    output = Path(args.output).expanduser() if args.output else Path("assets") / "derived" / f"audio_{safe_filename(derived_id)}.wav"
    if not output.is_absolute():
        output = root / output
    output = output.resolve()
    ensure_inside(root, output)
    if output.exists():
        raise argument_error("音频提取输出已存在，为避免覆盖请指定新的 --output", str(output))
    if args.dry_run:
        return _envelope(
            "audio.extract",
            args,
            status="planned",
            data={
                "source": str(source),
                "source_asset_id": args.asset_id,
                "source_sha256": f"sha256:{sha256_file(source)}",
                "input_probe": input_probe,
                "derived_asset_id": derived_id,
                "output": str(output),
                "sample_rate": args.sample_rate,
                "channels": args.channels,
                "track_id": args.track_id,
                "timeline_start_seconds": args.timeline_start_seconds,
                "engine": "ffmpeg-local-audio-extract-v1",
                "network": "disabled",
            },
        )
    before_project = copy.deepcopy(project)
    snapshot = create_snapshot(root, before_project, label="before-audio-extract")
    operation_id = new_id("op")
    extraction = extract_audio(source, output, sample_rate=args.sample_rate, channels=args.channels)
    output_probe = extraction["output_probe"]
    timeline_tps = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", TICKS_PER_SECOND))
    duration_tick = max(1, int(round(float(extraction["duration_seconds"]) * timeline_tps)))
    if source_asset is not None:
        ledger = load_ledger(root)
        records = {str(item.get("asset_id")): item for item in active_records(ledger)}
        parent_record = records.get(parent_rights_ref or "")
        if parent_record is None:
            raise AppError("RIGHTS_RECORD_MISSING", "源资产缺少可继承的 Rights Ledger 记录", exit_code=7, path=parent_rights_ref)
        rights_source_url = f"local://{output}"
        record = {
            "asset_id": derived_id,
            "kind": "audio",
            "sha256": extraction["output_sha256"],
            "source_url": rights_source_url,
            "source_version": "derived-audio-extract",
            "retrieved_at": now_iso(),
            "creator": parent_record.get("creator", "unknown"),
            "license_spdx": parent_record.get("license_spdx", "LicenseRef-UNVERIFIED"),
            "license_url": parent_record.get("license_url", ""),
            "attribution": parent_record.get("attribution", ""),
            "permitted_uses": list(parent_record.get("permitted_uses", ["internal"])),
            "permitted_channels": list(parent_record.get("permitted_channels", [])),
            "restrictions": list(parent_record.get("restrictions", [])),
            "derived_from": [parent_rights_ref],
            "evidence": parent_record.get("evidence", ""),
            "verification_status": parent_record.get("verification_status", "unverified"),
            "verified_by": parent_record.get("verified_by", ""),
            "takedown_status": parent_record.get("takedown_status", "clear"),
            "notes": "Derived by local FFmpeg audio extraction; inherits source rights",
        }
    else:
        rights_source_url = f"local://{source}"
        record = {
            "asset_id": derived_id,
            "kind": "audio",
            "sha256": extraction["output_sha256"],
            "source_url": rights_source_url,
            "source_version": "derived-audio-extract",
            "retrieved_at": now_iso(),
            "creator": args.creator,
            "license_spdx": args.license_spdx,
            "license_url": require_local_reference(args.license_url, field="--license-url") if args.license_url else "",
            "attribution": "",
            "permitted_uses": list(dict.fromkeys(args.permitted_use)),
            "permitted_channels": [],
            "restrictions": [],
            "derived_from": [],
            "evidence": require_local_reference(args.evidence, field="--evidence") if args.evidence else ("" if args.verification_status == "unverified" else rights_source_url),
            "verification_status": args.verification_status,
            "verified_by": "ai-ad-editor" if args.verification_status == "verified" else "",
            "takedown_status": "clear",
            "notes": "Derived by local FFmpeg audio extraction",
        }
    asset = {
        "id": derived_id,
        "kind": "audio",
        "uri": str(output.relative_to(root)).replace("\\", "/"),
        "sha256": extraction["output_sha256"],
        "probe": output_probe,
        "rights_ref": derived_id,
        "source": {"source_url": rights_source_url, "retrieved_at": now_iso(), "original_name": output.name, "derived_from": [source_asset.get("id")] if source_asset else []},
    }
    project.setdefault("assets", []).append(asset)
    sequence = None
    generated_clip = None
    if args.apply:
        sequence = find_sequence(project, args.sequence_id)
        target_track = find_track(sequence, args.track_id, None)
        if str(target_track.get("kind")) != "audio":
            raise argument_error("音频提取应用目标必须是 audio 轨道", "track_id")
        if args.replace_track:
            target_track["clips"] = []
        timeline_start_tick = int(round(float(args.timeline_start_seconds) * timeline_tps))
        generated_clip = {
            "id": new_id("clip_audio_extract"),
            "asset_id": derived_id,
            "timeline_start_tick": timeline_start_tick,
            "duration_tick": duration_tick,
            "source_in_tick": 0,
            "source_out_tick": duration_tick,
        }
        target_track.setdefault("clips", []).append(generated_clip)
        _recompute_sequence_duration(sequence)
    ledger = load_ledger(root)
    add_record(ledger, record)
    validation = validate_project(root, project, strict_rights=False)
    if not validation["ok"]:
        raise AppError("AUDIO_EXTRACT_APPLY_INVALID", "音频提取写入后项目校验失败", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    report_path = root / "validation" / f"audio_extract_{safe_filename(operation_id)}.json"
    report = {
        "report_version": AUDIO_EXTRACT_VERSION,
        "created_at": now_iso(),
        "operation_id": operation_id,
        "snapshot_id": snapshot["snapshot_id"],
        "asset": asset,
        "rights": record,
        "extraction": extraction,
        "generated_clip": generated_clip,
        "validation": validation,
    }
    atomic_write_json(report_path, report)
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "audio.extract", "asset_id": derived_id, "source_asset_id": source_asset.get("id") if source_asset else None, "snapshot_id": snapshot["snapshot_id"], "report": str(report_path), "clip_id": generated_clip.get("id") if generated_clip else None, "at": now_iso()})
    save_project(root, project)
    save_ledger(root, ledger)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "audio.extract", "status": "succeeded", "asset_id": derived_id, "source_asset_id": source_asset.get("id") if source_asset else None, "snapshot_id": snapshot["snapshot_id"], "report": str(report_path), "created_at": now_iso()})
    return _envelope("audio.extract", args, data={"asset": asset, "rights": record, "snapshot": snapshot, "report": str(report_path), "extraction": extraction, "generated_clip": generated_clip, "validation": validation}, operation_id=operation_id)


def command_audio_separate(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    if args.timeline_start_seconds < 0:
        raise argument_error("timeline_start_seconds 不能为负数", "timeline_start_seconds")
    if args.apply and (not args.track_id or not args.stem):
        raise argument_error("--apply 必须同时提供 --track-id 和 --stem", "track_id")
    if args.replace_track and not args.apply:
        raise argument_error("--replace-track 必须与 --apply 一起使用", "replace_track")
    adapter_record = None
    adapter_verification = None
    if args.adapter_id:
        registry = load_model_registry(root)
        adapter_record = adapter_for(registry, args.adapter_id)
        if adapter_record is None:
            raise AppError("MODEL_ADAPTER_NOT_FOUND", f"找不到已注册音频适配器: {args.adapter_id}", exit_code=3, path=str(registry_path(root)))
        adapter_verification = verify_audio_adapter(adapter_record)
        if not adapter_verification["ok"]:
            raise AppError("MODEL_ADAPTER_HASH_INVALID", "本地音频适配器路径或哈希校验失败", exit_code=10, path=str(registry_path(root)), cause=json.dumps(adapter_verification, ensure_ascii=False))
        if adapter_record.get("engine") not in {AUDIO_SEPARATION_ENGINE, "command-json-v1", DEMUCS_ENGINE}:
            raise AppError("AUDIO_SEPARATION_ADAPTER_UNAVAILABLE", f"适配器已登记但当前没有对应本地 runner: {adapter_record.get('engine')}", exit_code=10, path=str(args.adapter_id), hint="可执行引擎为 ffmpeg-local-mid-side-v1、command-json-v1 和 torchaudio-hdemucs-local-v1；未知模型不会被隐式 fallback")
    native = bool(adapter_record and adapter_record.get('engine') == DEMUCS_ENGINE)
    roles = ('vocals','accompaniment') if native else ('center','side')
    if args.stem is not None and args.stem not in roles:
        raise argument_error('当前引擎可应用的 stem: '+', '.join(roles),'stem')
    if native and args.apply and not args.asset_id:
        raise argument_error('模型分离入轨要求已摄取的 --asset-id','asset_id')
    if args.apply:
        preflight_track = find_track(find_sequence(project,args.sequence_id),args.track_id,None)
        if preflight_track.get('kind') != 'audio':
            raise argument_error('音频分离应用目标必须是 audio 轨道','track_id')
    source_asset: dict[str, Any] | None = None
    parent_rights_ref: str | None = None
    if args.asset_id:
        source_asset = asset_map(project).get(str(args.asset_id))
        if not source_asset:
            raise argument_error(f"找不到音频分离源资产: {args.asset_id}", "asset_id")
        source = resolve_local_path(root,str(source_asset.get('uri','')),field='asset.uri')
        parent_rights_ref = str(source_asset.get("rights_ref") or source_asset.get("id"))
    else:
        source = resolve_local_path(root,str(args.input or ''),field='input')
    source = source.resolve()
    input_probe = inspect_audio_source(source)
    if native and source_asset and source_asset.get('sha256') != 'sha256:'+sha256_file(source):
        raise AppError('SEPARATION_SOURCE_HASH_MISMATCH','分离源素材与已登记摘要不匹配',exit_code=10)
    from .audio_separation import _validate_sample_rate
    _validate_sample_rate(args.sample_rate)
    center_id = str(args.center_asset_id or new_id('asset_'+roles[0]))
    side_id = str(args.side_asset_id or new_id('asset_'+roles[1]))
    assert_id(center_id,'derived_asset_id');assert_id(side_id,'derived_asset_id')
    existing = asset_map(project)
    if center_id == side_id:
        raise argument_error("center 和 side 派生资产 ID 必须不同", "center_asset_id")
    if center_id in existing or side_id in existing:
        raise argument_error("音频分离派生资产 ID 已存在", "center_asset_id")
    center_output = Path(args.center_output).expanduser() if args.center_output else Path("assets") / "derived" / f"{safe_filename(center_id)}.wav"
    side_output = Path(args.side_output).expanduser() if args.side_output else Path("assets") / "derived" / f"{safe_filename(side_id)}.wav"
    if not center_output.is_absolute():
        center_output = root / center_output
    if not side_output.is_absolute():
        side_output = root / side_output
    center_output = ensure_inside(root, center_output)
    side_output = ensure_inside(root, side_output)
    if center_output == side_output:
        raise argument_error("center 和 side 输出必须是不同文件", "output")
    if any(p.exists() or p.suffix.lower() != '.wav' for p in (center_output,side_output)):
        raise argument_error('分离需要尚不存在的 .wav 输出','output')
    if args.dry_run:
        dry_engine = adapter_record.get("engine") if adapter_record else AUDIO_SEPARATION_ENGINE
        dry_method = 'hdemucs' if native else "command-json" if dry_engine == "command-json-v1" else "mid-side"
        dry_warnings = ([{'code':'AUDIO_SEPARATION_MODEL_REVIEW','message':'HDemucs 将以显式本地权重执行；仍需复核分离质量和许可'}] if native else [{"code": "AUDIO_SEPARATION_LOCAL_RUNNER_REVIEW", "message": "command-json-v1 将由已登记的本地 runner 执行；正式运行前仍需检查 runner 协议与质量 golden"}] if dry_method == "command-json" else [{"code": "AUDIO_SEPARATION_APPROXIMATE", "message": "mid/side 仅按声道相位生成 center/side，不能替代本地 AI 源分离模型"}])
        return _envelope(
            "audio.separate",
            args,
            status="planned",
            data={
                "source": str(source),
                "source_asset_id": args.asset_id,
                "source_sha256": f"sha256:{sha256_file(source)}",
                "input_probe": input_probe,
                "method": dry_method,
                "engine": dry_engine,
                "adapter": adapter_record,
                "adapter_verification": adapter_verification,
                roles[0]: {"asset_id": center_id, "output": str(center_output)},
                roles[1]: {"asset_id": side_id, "output": str(side_output)},
                "track_id": args.track_id,
                "stem": args.stem,
                "timeline_start_seconds": args.timeline_start_seconds,
                "network": "disabled",
            },
            warnings=dry_warnings,
        )
    try:
        before_project = copy.deepcopy(project)
        snapshot = create_snapshot(root, before_project, label="before-audio-separate")
        operation_id = new_id("op")
        if native:
            separation = separate_native(root,source,center_output,side_output,adapter=adapter_record,sample_rate=args.sample_rate)
        elif adapter_record and adapter_record.get("engine") == "command-json-v1":
            model_path = Path(str(adapter_record.get("model_path") or "")).expanduser().resolve()
            executable = Path(str(adapter_record.get("executable") or "")).expanduser().resolve()
            separation = separate_command_json(
                source,
                center_output,
                side_output,
                adapter_id=str(args.adapter_id),
                model_path=model_path,
                executable=executable,
                sample_rate=args.sample_rate,
            )
        else:
            separation = separate_mid_side(source, center_output, side_output, sample_rate=args.sample_rate)
        separation["adapter_id"] = args.adapter_id
        ledger = load_ledger(root)
        parent_record = None
        if source_asset is not None:
            records = {str(item.get("asset_id")): item for item in active_records(ledger)}
            parent_record = records.get(parent_rights_ref or "")
            if parent_record is None:
                center_output.unlink(missing_ok=True)
                side_output.unlink(missing_ok=True)
                raise AppError("RIGHTS_RECORD_MISSING", "源资产缺少可继承的 Rights Ledger 记录", exit_code=7, path=parent_rights_ref)

        derived_version = f"derived-audio-{separation.get('method', 'mid-side')}"

        def make_rights_record(asset_id: str, stem: str, details: dict[str, Any]) -> dict[str, Any]:
            source_url = f"local://{details['output']}"
            if parent_record is not None:
                return {
                    "asset_id": asset_id,
                    "kind": "audio",
                    "sha256": details["sha256"],
                    "source_url": source_url,
                    "source_version": derived_version,
                    "retrieved_at": now_iso(),
                    "creator": parent_record.get("creator", "unknown"),
                    "license_spdx": parent_record.get("license_spdx", "LicenseRef-UNVERIFIED"),
                    "license_url": parent_record.get("license_url", ""),
                    "attribution": parent_record.get("attribution", ""),
                    "permitted_uses": list(parent_record.get("permitted_uses", ["internal"])),
                    "permitted_channels": list(parent_record.get("permitted_channels", [])),
                    "restrictions": list(parent_record.get("restrictions", [])),
                    "derived_from": [parent_rights_ref],
                    "evidence": parent_record.get("evidence", ""),
                    "verification_status": parent_record.get("verification_status", "unverified"),
                    "verified_by": parent_record.get("verified_by", ""),
                    "takedown_status": parent_record.get("takedown_status", "clear"),
                    "notes": f"Derived by local {separation.get('engine', AUDIO_SEPARATION_ENGINE)} {stem} split; inherits source rights",
                }
            return {
                "asset_id": asset_id,
                "kind": "audio",
                "sha256": details["sha256"],
                "source_url": source_url,
                "source_version": derived_version,
                "retrieved_at": now_iso(),
                "creator": args.creator,
                "license_spdx": args.license_spdx,
                "license_url": require_local_reference(args.license_url, field="--license-url") if args.license_url else "",
                "attribution": "",
                "permitted_uses": list(dict.fromkeys(args.permitted_use)),
                "permitted_channels": [],
                "restrictions": [],
                "derived_from": [],
                "evidence": require_local_reference(args.evidence, field="--evidence") if args.evidence else ("" if args.verification_status == "unverified" else source_url),
                "verification_status": args.verification_status,
                "verified_by": "ai-ad-editor" if args.verification_status == "verified" else "",
                "takedown_status": "clear",
                "notes": f"Derived by local {separation.get('engine', AUDIO_SEPARATION_ENGINE)} {stem} split",
            }

        stems = separation["stems"]
        center_details = stems["center"]
        side_details = stems["side"]
        if native:
            separation['stems'] = {roles[0]:center_details,roles[1]:side_details}
        center_asset = {
            "id": center_id,
            "kind": "audio",
            "uri": str(center_output.relative_to(root)).replace("\\", "/"),
            "sha256": center_details["sha256"],
            "probe": center_details["probe"],
            "rights_ref": center_id,
            "source": {"source_url": f"local://{center_output}", "retrieved_at": now_iso(), "original_name": center_output.name, "derived_from": [source_asset.get("id")] if source_asset else []},
        }
        side_asset = {
            "id": side_id,
            "kind": "audio",
            "uri": str(side_output.relative_to(root)).replace("\\", "/"),
            "sha256": side_details["sha256"],
            "probe": side_details["probe"],
            "rights_ref": side_id,
            "source": {"source_url": f"local://{side_output}", "retrieved_at": now_iso(), "original_name": side_output.name, "derived_from": [source_asset.get("id")] if source_asset else []},
        }
        center_rights = make_rights_record(center_id, roles[0], center_details)
        side_rights = make_rights_record(side_id, roles[1], side_details)
        if adapter_record:
            model_rights = str(adapter_record.get('rights_ref') or f'adapter:{args.adapter_id}')
            for record in (center_rights,side_rights):
                record['derived_from'] = list(dict.fromkeys([*record.get('derived_from',[]),model_rights]))
        project.setdefault("assets", []).extend([center_asset, side_asset])
        generated_clip = None
        if args.apply:
            sequence = find_sequence(project, args.sequence_id)
            target_track = find_track(sequence, args.track_id, None)
            if str(target_track.get("kind")) != "audio":
                raise argument_error("音频分离应用目标必须是 audio 轨道", "track_id")
            if args.replace_track:
                target_track["clips"] = []
            selected_asset = center_asset if args.stem == roles[0] else side_asset
            selected_probe = selected_asset["probe"].get("audio", {})
            duration_seconds = float(selected_probe.get("duration_seconds", 0.0) or 0.0)
            timeline_tps = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", TICKS_PER_SECOND))
            duration_tick = max(1, int(round(duration_seconds * timeline_tps)))
            timeline_start_tick = int(round(float(args.timeline_start_seconds) * timeline_tps))
            generated_clip = {
                "id": new_id(f"clip_audio_{args.stem}"),
                "asset_id": selected_asset["id"],
                "timeline_start_tick": timeline_start_tick,
                "duration_tick": duration_tick,
                "source_in_tick": 0,
                "source_out_tick": duration_tick,
            }
            target_track.setdefault("clips", []).append(generated_clip)
            _recompute_sequence_duration(sequence)
        add_record(ledger, center_rights)
        add_record(ledger, side_rights)
        save_ledger(root,ledger)
        validation = validate_project(root, project, strict_rights=False)
        if not validation["ok"]:
            center_output.unlink(missing_ok=True)
            side_output.unlink(missing_ok=True)
            raise AppError("AUDIO_SEPARATION_APPLY_INVALID", "音频分离写入后项目校验失败", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
        report_path = root / "validation" / f"audio_separate_{safe_filename(operation_id)}.json"
        report = {
            "report_version": AUDIO_SEPARATION_VERSION,
            "created_at": now_iso(),
            "operation_id": operation_id,
            "snapshot_id": snapshot["snapshot_id"],
            "method": separation.get("method", "mid-side"),
            "engine": separation.get("engine", AUDIO_SEPARATION_ENGINE),
            "adapter": adapter_record,
            "source_asset_id": args.asset_id,
            "assets": {roles[0]: center_asset, roles[1]: side_asset},
            "rights": {roles[0]: center_rights, roles[1]: side_rights},
            "separation": separation,
            "generated_clip": generated_clip,
            "validation": validation,
        }
        atomic_write_json(report_path, report)
        project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "audio.separate", "method": separation.get("method", "mid-side"), "engine": separation.get("engine", AUDIO_SEPARATION_ENGINE), "asset_ids": [center_id, side_id], "source_asset_id": args.asset_id, "snapshot_id": snapshot["snapshot_id"], "report": str(report_path), "clip_id": generated_clip.get("id") if generated_clip else None, "at": now_iso()})
        save_project(root, project)
        save_ledger(root, ledger)
        _operation(root, operation_id, {"operation_id": operation_id, "command": "audio.separate", "status": "succeeded", "method": separation.get("method", "mid-side"), "engine": separation.get("engine", AUDIO_SEPARATION_ENGINE), "asset_ids": [center_id, side_id], "snapshot_id": snapshot["snapshot_id"], "report": str(report_path), "created_at": now_iso()})
        return _envelope("audio.separate", args, data={"assets": {roles[0]: center_asset, roles[1]: side_asset}, "rights": {roles[0]: center_rights, roles[1]: side_rights}, "snapshot": snapshot, "report": str(report_path), "separation": separation, "adapter": adapter_record, "generated_clip": generated_clip, "validation": validation}, warnings=separation.get("warnings"), operation_id=operation_id)
    except BaseException:
        center_output.unlink(missing_ok=True)
        side_output.unlink(missing_ok=True)
        raise


def command_audio_adapter_register(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    license_url = require_local_reference(args.license_url, field="--license-url") if args.license_url else ""
    evidence = require_local_reference(args.evidence, field="--evidence") if args.evidence else ""
    registry = load_model_registry(root)
    if adapter_for(registry, args.adapter_id) is not None:
        raise AppError("MODEL_ADAPTER_EXISTS", f"本地音频适配器已存在: {args.adapter_id}", exit_code=2, path=str(registry_path(root)))
    adapter_record, rights_record = prepare_audio_adapter(
        adapter_id=args.adapter_id,
        engine=args.engine,
        model_path=args.model_path,
        executable=args.executable,
        creator=args.creator,
        license_spdx=args.license_spdx,
        license_url=license_url,
        permitted_uses=list(dict.fromkeys(args.permitted_use)),
        verification_status=args.verification_status,
        evidence=evidence,
        root=root,
        native_options={'device':args.device or ('auto' if args.engine == FOUR_STEM_ENGINE else 'cpu'),'threads':args.threads,'segment_seconds':args.segment_seconds,'overlap':args.overlap} if args.engine in {DEMUCS_ENGINE, FOUR_STEM_ENGINE} else None,
    )
    if args.dry_run:
        return _envelope("audio.adapter.register", args, status="planned", data={"registry": str(registry_path(root)), "adapter": adapter_record, "rights": rights_record})
    ledger = load_ledger(root)
    before_project = copy.deepcopy(project)
    snapshot = create_snapshot(root, before_project, label="before-audio-adapter-register")
    registry.setdefault("adapters", []).append(adapter_record)
    add_record(ledger, rights_record)
    operation_id = new_id("op")
    project.setdefault("provenance", {}).setdefault("local_adapters", []).append({"adapter_id": args.adapter_id, "engine": args.engine, "model_sha256": adapter_record.get("model_sha256"), "registered_at": adapter_record["registered_at"]})
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "audio.adapter.register", "adapter_id": args.adapter_id, "engine": args.engine, "snapshot_id": snapshot["snapshot_id"], "registry": str(registry_path(root)), "at": now_iso()})
    save_model_registry(root, registry)
    save_project(root, project)
    save_ledger(root, ledger)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "audio.adapter.register", "status": "succeeded", "adapter_id": args.adapter_id, "engine": args.engine, "snapshot_id": snapshot["snapshot_id"], "registry": str(registry_path(root)), "created_at": now_iso()})
    return _envelope("audio.adapter.register", args, data={"registry": str(registry_path(root)), "adapter": adapter_record, "rights": rights_record, "snapshot": snapshot}, operation_id=operation_id)


def command_audio_adapter_list(args: argparse.Namespace) -> dict[str, Any]:
    root, _ = load_project(args.project)
    registry = load_model_registry(root)
    adapters = []
    for adapter in registry.get("adapters", []):
        if not isinstance(adapter, dict):
            continue
        adapters.append({"adapter": adapter, "verification": verify_audio_adapter(adapter)})
    return _envelope("audio.adapter.list", args, data={"registry": str(registry_path(root)), "schema_version": MODEL_REGISTRY_VERSION, "count": len(adapters), "adapters": adapters, "network": "disabled"})


def command_audio_adapter_inspect(args: argparse.Namespace) -> dict[str, Any]:
    root, _ = load_project(args.project)
    registry = load_model_registry(root)
    adapter = adapter_for(registry, args.adapter_id)
    if adapter is None:
        raise AppError("MODEL_ADAPTER_NOT_FOUND", f"找不到已注册音频适配器: {args.adapter_id}", exit_code=3, path=str(registry_path(root)))
    return _envelope("audio.adapter.inspect", args, data={"registry": str(registry_path(root)), "adapter": adapter, "verification": verify_audio_adapter(adapter), "network": "disabled"})


def command_audio_adapter(args: argparse.Namespace) -> dict[str, Any]:
    handlers = {
        "register": command_audio_adapter_register,
        "list": command_audio_adapter_list,
        "inspect": command_audio_adapter_inspect,
    }
    try:
        return handlers[args.adapter_action](args)
    except KeyError as exc:
        raise argument_error(f"不支持的 audio adapter 操作: {args.adapter_action}", "adapter_action") from exc


def command_media_adapter_register(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    if args.engine not in {INTERPOLATION_ENGINE, LIPSYNC_ENGINE, SEGMENTATION_ENGINE, INPAINT_ENGINE, VACE_ENGINE} and args.device != 'cpu' or args.engine != MATTING_ENGINE and args.downsample_ratio is not None:
        raise argument_error('device=cuda 只适用于 MuseTalk/SAM2/LaMa/VACE；downsample-ratio 只适用于 RVM', 'device/downsample_ratio')
    if args.engine != VACE_ENGINE and (args.text_gpu_budget_mib is not None or args.text_cpu_budget_mib is not None):
        raise argument_error('text 权重预算只适用于 VACE', 'text_gpu_budget_mib/text_cpu_budget_mib')
    license_url = require_local_reference(args.license_url, field="--license-url") if args.license_url else ""
    evidence = require_local_reference(args.evidence, field="--evidence") if args.evidence else ""
    registry = load_visual_model_registry(root)
    if visual_adapter_for(registry, args.adapter_id) is not None:
        raise AppError("VISUAL_MODEL_ADAPTER_EXISTS", f"本地视觉适配器已存在: {args.adapter_id}", exit_code=2, path=str(visual_registry_path(root)))
    adapter_record, rights_record = prepare_visual_adapter(
        adapter_id=args.adapter_id,
        engine=args.engine,
        model_path=args.model_path,
        executable=args.executable,
        creator=args.creator,
        license_spdx=args.license_spdx,
        license_url=license_url,
        permitted_uses=list(dict.fromkeys(args.permitted_use)),
        verification_status=args.verification_status,
        evidence=evidence,
        root=root,
        native_options=({'threads':args.threads,'device':args.device} if args.engine in {INTERPOLATION_ENGINE,LIPSYNC_ENGINE} else {'threads':args.threads,'device':args.device,'text_gpu_budget_mib':7168 if args.text_gpu_budget_mib is None else args.text_gpu_budget_mib,'text_cpu_budget_mib':8192 if args.text_cpu_budget_mib is None else args.text_cpu_budget_mib} if args.engine == VACE_ENGINE else {'threads': args.threads, 'device': args.device} if args.engine in {SEGMENTATION_ENGINE, INPAINT_ENGINE} else {'threads': args.threads, 'downsample_ratio': args.downsample_ratio} if args.engine == MATTING_ENGINE else {'threads':args.threads, 'confidence':args.confidence, 'low_confidence':args.low_confidence, 'match_iou':args.match_iou, 'max_gap_seconds':args.max_gap_seconds, 'class_ids':args.class_id}),
    )
    if args.dry_run:
        return _envelope("media.adapter.register", args, status="planned", data={"registry": str(visual_registry_path(root)), "adapter": adapter_record, "rights": rights_record})
    ledger = load_ledger(root)
    before_project = copy.deepcopy(project)
    snapshot = create_snapshot(root, before_project, label="before-media-adapter-register")
    registry.setdefault("adapters", []).append(adapter_record)
    add_record(ledger, rights_record)
    operation_id = new_id("op")
    project.setdefault("provenance", {}).setdefault("local_adapters", []).append({"adapter_id": args.adapter_id, "kind": adapter_record['kind'], "engine": args.engine, "model_sha256": adapter_record.get("model_sha256"), "registered_at": adapter_record["registered_at"]})
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.adapter.register", "adapter_id": args.adapter_id, "engine": args.engine, "snapshot_id": snapshot["snapshot_id"], "registry": str(visual_registry_path(root)), "at": now_iso()})
    try:
        save_visual_model_registry(root, registry)
        save_project(root, project)
        save_ledger(root, ledger)
        _operation(root, operation_id, {"operation_id": operation_id, "command": "media.adapter.register", "status": "succeeded", "adapter_id": args.adapter_id, "engine": args.engine, "snapshot_id": snapshot["snapshot_id"], "registry": str(visual_registry_path(root)), "created_at": now_iso()})
    except OSError as exc:
        raise AppError('MODEL_REGISTRATION_WRITE_FAILED', '视觉模型登记写入失败，元数据事务将回滚', exit_code=6, cause=str(exc)) from exc
    return _envelope("media.adapter.register", args, data={"registry": str(visual_registry_path(root)), "adapter": adapter_record, "rights": rights_record, "snapshot": snapshot}, operation_id=operation_id)


def command_media_adapter_list(args: argparse.Namespace) -> dict[str, Any]:
    root, _ = load_project(args.project)
    registry = load_visual_model_registry(root)
    adapters = []
    for adapter in registry.get("adapters", []):
        if isinstance(adapter, dict):
            adapters.append({"adapter": adapter, "verification": verify_visual_adapter(adapter)})
    return _envelope("media.adapter.list", args, data={"registry": str(visual_registry_path(root)), "schema_version": MODEL_REGISTRY_VERSION, "count": len(adapters), "adapters": adapters, "network": "disabled"})


def command_media_adapter_inspect(args: argparse.Namespace) -> dict[str, Any]:
    root, _ = load_project(args.project)
    registry = load_visual_model_registry(root)
    adapter = visual_adapter_for(registry, args.adapter_id)
    if adapter is None:
        raise AppError("VISUAL_MODEL_ADAPTER_NOT_FOUND", f"找不到已注册视觉适配器: {args.adapter_id}", exit_code=3, path=str(visual_registry_path(root)))
    return _envelope("media.adapter.inspect", args, data={"registry": str(visual_registry_path(root)), "adapter": adapter, "verification": verify_visual_adapter(adapter), "network": "disabled"})


def command_media_adapter(args: argparse.Namespace) -> dict[str, Any]:
    handlers = {
        "register": command_media_adapter_register,
        "list": command_media_adapter_list,
        "inspect": command_media_adapter_inspect,
    }
    try:
        return handlers[args.adapter_action](args)
    except KeyError as exc:
        raise argument_error(f"不支持的 media adapter 操作: {args.adapter_action}", "adapter_action") from exc


def command_media_mask_edit(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    asset = asset_map(project).get(args.asset_id)
    if not asset or asset.get('kind') not in {'image', 'video'}:
        raise argument_error('蒙版编辑要求已登记 image/video 资产', 'asset-id')
    assert_id(args.derived_asset_id, 'derived-asset-id')
    ledger = load_ledger(root)
    records = {r['asset_id']: r for r in active_records(ledger)}
    parent_ref = asset.get('rights_ref') or asset['id']
    parent = records.get(parent_ref)
    if not parent or parent.get('sha256') != asset.get('sha256'):
        raise AppError('MASK_EDIT_RIGHTS_MISSING', '输入蒙版缺少摘要匹配的权利记录', exit_code=7)
    if args.derived_asset_id in asset_map(project) or args.derived_asset_id in records:
        raise argument_error('派生资产或权利 ID 已存在', 'derived-asset-id')
    dependencies = [parent_ref]
    embedded = None
    if args.edits_from_asset:
        previous = asset_map(project).get(args.edits_from_asset)
        authored = previous.get('source', {}).get('mask_edit', {}) if previous else {}
        embedded = authored.get('plan')
        if (previous is None or previous.get('kind') not in {'image', 'video'} or authored.get('engine') != mask_edit.ENGINE
                or not isinstance(embedded, dict) or mask_edit.plan_digest(embedded) != authored.get('plan_sha256')):
            raise argument_error('复用源没有有效的蒙版编辑计划摘要', 'edits-from-asset')
        reference = previous.get('rights_ref') or previous['id']
        if reference not in records or records[reference].get('sha256') != previous.get('sha256'):
            raise AppError('MASK_EDIT_RIGHTS_MISSING', '复用计划缺少摘要匹配的权利记录', exit_code=7)
        dependencies = list(dict.fromkeys([*dependencies, reference]))
    if not math.isfinite(args.timeout_seconds) or not 0 < args.timeout_seconds <= 604800:
        raise argument_error('timeout-seconds 必须为 0..604800 的有限正数', 'timeout-seconds')
    plan = mask_edit.prepare(root, asset, edits_path=args.edits, embedded=embedded, channel=args.channel, fps=args.fps,
        max_frames=args.max_frames, storage_budget_mib=args.storage_budget_mib,
        buffer_budget_mib=args.buffer_budget_mib, work_budget_million=args.work_budget_million)
    suffix = '.png' if asset['kind'] == 'image' else '.mov'
    output = ensure_inside(root, resolve_local_path(root, args.output or f'assets/derived/{args.derived_asset_id}{suffix}', field='output'))
    if output.exists() or output.suffix.lower() != suffix:
        raise argument_error('输出须为项目内全新的 .png 图像或 .mov 视频', 'output')
    cancel = resolve_local_path(root, args.cancel_file, field='cancel-file') if args.cancel_file else None
    if args.dry_run:
        return _envelope('media.mask-edit', args, status='planned', data={'plan': mask_edit.public_plan(plan),
            'derived_asset_id': args.derived_asset_id, 'output': str(output), 'rights_dependencies': dependencies}, warnings=plan['warnings'])
    snapshot = create_snapshot(root, copy.deepcopy(project), label='before-media-mask-edit')
    operation_id = new_id('op')
    report_path = root/'validation'/f'mask-edit_{operation_id}.json'
    published = False
    try:
        _progress(args, operation_id, 'started', 'media.mask-edit', 0, '开始本地蒙版笔刷/关键帧修正')
        def progress(frame, total):
            _progress(args, operation_id, 'progress', 'media.mask-edit', round(90*frame/total), f'蒙版修正 {frame}/{total} 帧')
        result = mask_edit.execute(root, plan, output, timeout=args.timeout_seconds, cancel_file=cancel, progress=progress)
        published = True
        derived = {'id': args.derived_asset_id, 'kind': asset['kind'], 'uri': output.relative_to(root).as_posix(),
            'sha256': result['sha256'], 'probe': result['probe'], 'rights_ref': args.derived_asset_id,
            'source': {'source_url': f'local://{output}', 'retrieved_at': now_iso(), 'original_name': output.name,
                'derived_from': [asset['id']], 'mask_edit': {'engine': mask_edit.ENGINE,
                    'plan': plan['editable_plan'], 'plan_sha256': plan['plan_sha256']}}}
        rights = {k: copy.deepcopy(parent.get(k, default)) for k, default in [('creator', 'unknown'),
            ('license_spdx', 'LicenseRef-UNVERIFIED'), ('license_url', ''), ('attribution', ''), ('permitted_uses', ['internal']),
            ('permitted_channels', []), ('restrictions', []), ('evidence', ''), ('verification_status', 'unverified'),
            ('verified_by', ''), ('takedown_status', 'clear')]}
        rights.update(asset_id=args.derived_asset_id, kind=asset['kind'], sha256=result['sha256'],
            source_url=f'local://{output}', source_version='derived-local-mask-edit', retrieved_at=now_iso(),
            derived_from=dependencies, notes='Explicit local mask geometry; original mask and reused authored-plan rights remain dependencies')
        project.setdefault('assets', []).append(derived)
        add_record(ledger, rights)
        save_ledger(root, ledger)
        validation = validate_project(root, project, strict_rights=False)
        if not validation['ok']:
            raise AppError('MASK_EDIT_PROJECT_INVALID', '蒙版派生项目校验失败，事务回滚', exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
        report = {'version': '0.1.0', 'operation_id': operation_id, 'created_at': now_iso(),
            'snapshot_id': snapshot['snapshot_id'], 'source_asset_id': asset['id'], 'asset': derived,
            'rights': rights, 'mask_edit': result, 'validation': validation}
        atomic_write_json(report_path, report)
        project.setdefault('provenance', {}).setdefault('change_log', []).append({'operation_id': operation_id,
            'command': 'media.mask-edit', 'asset_id': args.derived_asset_id, 'source_asset_id': asset['id'],
            'snapshot_id': snapshot['snapshot_id'], 'report': str(report_path), 'at': now_iso()})
        save_project(root, project)
        _operation(root, operation_id, {'operation_id': operation_id, 'command': 'media.mask-edit', 'status': 'succeeded',
            'asset_id': args.derived_asset_id, 'snapshot_id': snapshot['snapshot_id'], 'report': str(report_path), 'created_at': now_iso()})
        _progress(args, operation_id, 'completed', 'media.mask-edit', 100, '蒙版编码 RGBA 与精确帧时钟验证完成')
        return _envelope('media.mask-edit', args, data=report, warnings=result['warnings'], operation_id=operation_id)
    except BaseException as exc:
        if published:
            output.unlink(missing_ok=True)
        report_path.unlink(missing_ok=True)
        if isinstance(exc, OSError):
            raise AppError('MASK_EDIT_WRITE_FAILED', '蒙版产物或项目写入失败，事务将回滚', exit_code=6, cause=str(exc)) from exc
        raise


def command_media_matting(args: argparse.Namespace) -> dict[str, Any]:
    from .artifact_locks import verification_scope
    with verification_scope():
        return _command_media_matting(args)


def _command_media_matting(args: argparse.Namespace) -> dict[str, Any]:
    outpainting = args.action == 'outpaint'
    inpainting = args.action in {'inpaint', 'outpaint'}
    command = 'media.' + args.action
    result_key = 'outpainting' if outpainting else 'inpainting' if inpainting else 'matting'
    root, project = load_project(args.project)
    if not math.isfinite(args.timeline_start_seconds) or args.timeline_start_seconds < 0 or not math.isfinite(args.timeout_seconds) or not 0 < args.timeout_seconds <= 604800:
        raise argument_error('需要非负有限时间线起点及 0..604800 的超时预算', 'timeline_start_seconds/timeout_seconds')
    if args.apply and not args.track_id or args.replace_track and not args.apply:
        raise argument_error('--apply 要求 --track-id；--replace-track 要求 --apply', 'track_id/apply')
    if args.audio_track_id and (not args.apply or args.no_audio):
        raise argument_error('--audio-track-id 要求 --apply 且不能与 --no-audio 同用', 'audio_track_id')
    source_asset = asset_map(project).get(args.asset_id)
    if not source_asset or source_asset.get('kind') != 'video':
        raise argument_error('抠像要求已摄取的 video 资产', 'asset_id')
    source = resolve_local_path(root, source_asset['uri'], field='asset.uri')
    if 'sha256:' + sha256_file(source) != source_asset.get('sha256'):
        raise AppError('MATTING_SOURCE_HASH_MISMATCH', '抠像源与已登记摘要不符', exit_code=10)
    adapter = visual_adapter_for(load_visual_model_registry(root), args.adapter_id)
    if adapter is None or adapter.get('engine') not in ({INPAINT_ENGINE, VACE_ENGINE} if inpainting else {MATTING_ENGINE, SEGMENTATION_ENGINE}):
        raise AppError('MATTING_ADAPTER_UNAVAILABLE', '要求已登记且用途匹配的本地 LaMa/VACE 修复或 RVM/SAM2 抠像适配器', exit_code=10)
    segmentation = adapter['engine'] == SEGMENTATION_ENGINE
    joint = adapter['engine'] == VACE_ENGINE
    if segmentation and not args.prompts:
        raise argument_error('SAM2 要求显式本地 --prompts JSON', 'prompts')
    if not segmentation and not inpainting and (args.prompts or args.object_id is not None or args.mask_mode != 'binary' or args.logit_threshold != 0):
        raise argument_error('RVM 不接受 SAM2 提示或掩模参数', 'prompts/object_id/mask_mode')
    ledger = load_ledger(root)
    records = {r['asset_id']: r for r in active_records(ledger)}
    parent_ref = source_asset.get('rights_ref') or args.asset_id
    model_ref = adapter['rights_ref']
    parent = records.get(parent_ref)
    if parent is None or model_ref not in records or records[model_ref].get('sha256') != adapter['sha256']:
        raise AppError('MATTING_RIGHTS_DEPENDENCY_MISSING', '源素材或模型缺少匹配的权利记录', exit_code=7)
    if outpainting and parent.get('sha256') != source_asset.get('sha256'):
        raise AppError('OUTPAINT_RIGHTS_DEPENDENCY_MISMATCH', '扩图源与权利记录的内容摘要不符', exit_code=7)
    rights_dependencies = [parent_ref, model_ref]
    derived_from_assets = [args.asset_id]
    mask_asset = None
    if inpainting and not outpainting:
        mask_asset = asset_map(project).get(args.mask_asset_id)
        if mask_asset is None or mask_asset.get('kind') not in {'image', 'video'}:
            raise argument_error('区域修复需要已摄取的 image/video 蒙版资产', 'mask_asset_id')
        mask_ref = mask_asset.get('rights_ref') or args.mask_asset_id
        if records.get(mask_ref, {}).get('sha256') != mask_asset.get('sha256') or parent.get('sha256') != source_asset.get('sha256'):
            raise AppError('INPAINT_RIGHTS_DEPENDENCY_MISSING', '源或蒙版缺少匹配的权利记录', exit_code=7)
        rights_dependencies = list(dict.fromkeys([parent_ref, mask_ref, model_ref]))
        derived_from_assets = list(dict.fromkeys([args.asset_id, args.mask_asset_id]))
    derived_id = str(args.derived_asset_id)
    assert_id(derived_id, 'derived_asset_id')
    if derived_id in asset_map(project) or derived_id in records:
        raise argument_error('派生资产 ID 或权利 ID 已存在', 'derived_asset_id')
    output = ensure_inside(root, resolve_local_path(root, args.output or f'assets/derived/{derived_id}.mov', field='output'))
    if output.exists() or output.suffix.lower() != '.mov':
        raise argument_error('抠像输出须为项目内尚不存在的 .mov', 'output')
    cancel_file = resolve_local_path(root, args.cancel_file, field='cancel_file') if args.cancel_file else None
    plan = prepare_matting_plan(source, adapter, start_seconds=args.start_seconds, end_seconds=args.end_seconds, fps=args.fps,
                                max_edge=args.max_edge, max_frames=args.max_frames, preserve_audio=not args.no_audio)
    if segmentation:
        plan['prompt_plan'], plan['prompt_source'] = load_segmentation_prompts(root, args.prompts, frames=plan['video']['frames'], object_ids=args.object_id, mask_mode=args.mask_mode, threshold=args.logit_threshold)
        plan['video'].pop('downsample_ratio', None)
    if outpainting:
        from .local_outpainting import extend_plan
        extend_plan(plan, width=args.width, height=args.height, offset_x=args.offset_x, offset_y=args.offset_y)
    if inpainting:
        if not outpainting:
            plan['mask'] = prepare_inpaint_mask(root, mask_asset['uri'], kind=mask_asset['kind'], video=plan['video'], channel=args.mask_channel, start_seconds=args.mask_start_seconds, resize=args.mask_resize)
        if not outpainting and plan['mask']['sha256'] != mask_asset.get('sha256'):
            raise AppError('INPAINT_MASK_HASH_MISMATCH', '蒙版文件与已登记摘要不符', exit_code=10)
        if args.repair_blend == 'direct' and (args.blend_max_iterations is not None or args.blend_tolerance is not None):
            raise argument_error('求解参数要求显式 --repair-blend harmonic', 'repair_blend')
        plan['inpainting'] = inpaint_options(threshold=args.mask_threshold, grow=args.mask_grow, feather=args.mask_feather, context=args.context_pixels, model_max_edge=args.model_max_edge,
            blend_mode=args.repair_blend, blend_max_iterations=2000 if args.blend_max_iterations is None else args.blend_max_iterations, blend_tolerance=1e-6 if args.blend_tolerance is None else args.blend_tolerance)
        generation_args = {'prompt':args.prompt,'negative_prompt':args.negative_prompt,'seed':args.seed,'inference_steps':args.inference_steps,
                           'guidance_scale':args.guidance_scale,'conditioning_scale':args.conditioning_scale,'window_frames':args.window_frames,
                           'window_overlap':args.window_overlap,'prompt_max_tokens':args.prompt_max_tokens,'scene_cut_frames':args.scene_cut_frame,
                           'flow_shift':args.flow_shift,'model_input_scale':args.model_input_scale,'temporal_context':args.temporal_context}
        if joint:
            plan['generation'] = vace_options(**generation_args, frames=plan['video']['frames'])
            plan['windows'] = vace_windows(plan['video']['frames'],plan['generation'])
            from .repair_blend import joint_blend_overhead
            plan['owned_array_budget_bytes'] = vace_buffer_budget(plan['video']['width'],plan['video']['height'],plan['generation'],plan['inpainting']['model_max_edge'])+joint_blend_overhead(plan['video']['width'],plan['video']['height'],plan['inpainting'])
            if plan['owned_array_budget_bytes'] > adapter['settings']['state_budget_bytes']:
                raise AppError('VACE_WINDOW_BUFFER_BUDGET_EXCEEDED','窗口自有数组超预算；显式减小 max-edge/model-max-edge、model-input-scale、window-frames 或 window-overlap',exit_code=2)
        elif any(v is not None for v in generation_args.values()):
            raise argument_error('提示词、seed 和窗口参数只适用于 VACE；LaMa 不接受这些选项','prompt/generation')
        from .repair_blend import blend_budget_plan
        plan['blend_budget'] = blend_budget_plan(plan['video']['width'], plan['video']['height'], plan['inpainting'], adapter['settings']['state_budget_bytes'], plan.get('owned_array_budget_bytes'))
        if args.repair_blend == 'harmonic':
            plan['warnings'].append({'code':'REPAIR_HARMONIZE_REVIEW_REQUIRED','message':'逐帧空间色差修正；结构、纹理、残影、时序和背景真值须独立复核'})
        plan['video'].pop('downsample_ratio', None)
        if not outpainting: plan['warnings'].append({'code': 'INPAINT_MASK_CLOCK', 'message': '蒙版按自身显示起点加 mask-start-seconds 取样；缩放及 CFR 取样见计划，不推断源时钟或裁切关系'})
    tps = int(project.get('settings', {}).get('timebase', {}).get('ticks_per_second', TICKS_PER_SECOND))
    start_tick = round(args.timeline_start_seconds * tps)
    duration_tick = max(1, round(plan['video']['duration_seconds'] * tps))
    sequence = track = audio_track = None
    if args.apply:
        sequence = find_sequence(project, args.sequence_id)
        track = find_track(sequence, args.track_id, None)
        if track.get('kind') != 'video':
            raise argument_error('抠像应用目标须为 video 轨道', 'track_id')
        if not args.replace_track and any(int(c.get('timeline_start_tick', 0)) < start_tick + duration_tick and int(c.get('timeline_start_tick', 0)) + int(c.get('duration_tick', 0)) > start_tick for c in track.get('clips', [])):
            raise argument_error('目标时间范围已有片段；指定新轨道或显式 --replace-track', 'track_id')
        if args.audio_track_id:
            audio_track = find_track(sequence, args.audio_track_id, None)
            if not plan['audio']['preserve'] or audio_track.get('kind') != 'audio':
                raise argument_error('原声入轨要求源有音频且目标为 audio 轨道', 'audio_track_id')
            if not args.replace_track and any(int(c.get('timeline_start_tick', 0)) < start_tick + duration_tick and int(c.get('timeline_start_tick', 0)) + int(c.get('duration_tick', 0)) > start_tick for c in audio_track.get('clips', [])):
                raise argument_error('原声目标范围已有片段；指定新轨道或显式 --replace-track', 'audio_track_id')
    if args.dry_run:
        return _envelope(command, args, status='planned', data={'plan': plan, 'adapter': adapter, 'derived_asset_id': derived_id, 'output': str(output),
                         'source_asset_id': args.asset_id, 'track_id': args.track_id, 'audio_track_id': args.audio_track_id, 'rights_dependencies': rights_dependencies}, warnings=plan['warnings'])
    snapshot = create_snapshot(root, copy.deepcopy(project), label='before-media-' + args.action)
    operation_id = new_id('op')
    report_path = root / 'validation' / f'{result_key}_{safe_filename(operation_id)}.json'
    published = False
    try:
        _progress(args, operation_id, 'started', command, 0, '开始本地 VACE 联合视频编辑' if joint else '开始本地 LaMa 区域修复' if inpainting else '开始本地对象分割' if segmentation else '开始本地 RVM 时序抠像')
        def progress(frame, total):
            _progress(args, operation_id, 'progress', command + '.inference', round(90 * frame / total), f'{"区域修复" if inpainting else "对象分割" if segmentation else "人物抠像"} {frame}/{total} 帧')
        result = matte_native(root, output, adapter=adapter, plan=plan, timeout=args.timeout_seconds, cancel_file=cancel_file, progress=progress, operation_id=operation_id)
        published = True
        asset = {'id': derived_id, 'kind': 'video', 'uri': output.relative_to(root).as_posix(), 'sha256': result['sha256'], 'probe': result['probe'], 'rights_ref': derived_id,
                 'source': {'source_url': f'local://{output}', 'retrieved_at': now_iso(), 'original_name': output.name, 'derived_from': derived_from_assets}}
        if outpainting:
            from .local_outpainting import recipe
            asset['source']['outpainting'] = recipe(plan, adapter, args.asset_id)
        elif joint:
            asset['source']['vace_generation'] = copy.deepcopy(plan['generation'])
        rights = {key: copy.deepcopy(parent.get(key, default)) for key, default in [('creator', 'unknown'), ('license_spdx', 'LicenseRef-UNVERIFIED'), ('license_url', ''),
                  ('attribution', ''), ('permitted_uses', ['internal']), ('permitted_channels', []), ('restrictions', []), ('evidence', ''), ('verification_status', 'unverified'), ('verified_by', ''), ('takedown_status', 'clear')]}
        rights.update(asset_id=derived_id, kind='video', sha256=result['sha256'], source_url=f'local://{output}', source_version='derived-video-outpainting' if outpainting else 'derived-video-vace-editing' if joint else 'derived-video-lama-inpainting' if inpainting else 'derived-video-sam2-segmentation' if segmentation else 'derived-video-rvm-matting', retrieved_at=now_iso(),
                      derived_from=rights_dependencies, notes='Local prompted joint video windows; source, mask and model rights required' if joint else 'Local framewise masked repair; source, mask and model rights required' if inpainting else 'Local prompted object segmentation; source and model rights both required' if segmentation else 'Local recurrent human matting; source and model rights both required')
        project.setdefault('assets', []).append(asset)
        add_record(ledger, rights)
        clip = audio_clip = None
        if args.apply:
            if args.replace_track:
                track['clips'] = []
            clip = {'id': new_id('clip_matting'), 'asset_id': derived_id, 'timeline_start_tick': start_tick, 'duration_tick': duration_tick, 'source_in_tick': 0, 'source_out_tick': duration_tick}
            track.setdefault('clips', []).append(clip)
            if audio_track is not None:
                if args.replace_track:
                    audio_track['clips'] = []
                audio_clip = {**clip, 'id': new_id('clip_matting_audio')}
                audio_track.setdefault('clips', []).append(audio_clip)
            _recompute_sequence_duration(sequence)
        save_ledger(root, ledger)
        validation = validate_project(root, project, strict_rights=False)
        if not validation['ok']:
            raise AppError('MATTING_APPLY_INVALID', '抠像项目校验失败', exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
        report = {'version': '0.1.0', 'created_at': now_iso(), 'operation_id': operation_id, 'snapshot_id': snapshot['snapshot_id'], 'source_asset_id': args.asset_id,
                  'asset': asset, 'rights': rights, 'generated_clip': clip, 'generated_audio_clip': audio_clip, result_key: result, 'validation': validation}
        if inpainting and not outpainting: report['mask_asset_id'] = args.mask_asset_id
        atomic_write_json(report_path, report)
        project.setdefault('provenance', {}).setdefault('change_log', []).append({'operation_id': operation_id, 'command': command, 'engine': adapter['engine'],
            'asset_id': derived_id, 'source_asset_id': args.asset_id, 'snapshot_id': snapshot['snapshot_id'], 'report': str(report_path), 'at': now_iso()})
        save_project(root, project)
        _operation(root, operation_id, {'operation_id': operation_id, 'command': command, 'status': 'succeeded', 'asset_id': derived_id,
                   'snapshot_id': snapshot['snapshot_id'], 'report': str(report_path), 'created_at': now_iso()})
        _progress(args, operation_id, 'completed', command, 100, '派生素材及 RGBA 编码往返校验完成')
        return _envelope(command, args, data=report, warnings=result['warnings'], operation_id=operation_id)
    except BaseException as exc:
        if published:
            output.unlink(missing_ok=True)
        report_path.unlink(missing_ok=True)
        if isinstance(exc, AppError):
            exc.operation_id = operation_id
        if isinstance(exc, OSError):
            raise AppError('MATTING_WRITE_FAILED', '抠像输出或元数据写入失败，事务将回滚', exit_code=6, cause=str(exc),
                operation_id=operation_id, diagnostics=getattr(exc, 'diagnostics', None)) from exc
        raise


def command_media_stabilize(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    if bool(args.asset_id) == bool(args.input):
        raise argument_error("必须且只能提供 --asset-id 或 --input")
    source_asset: dict[str, Any] | None = None
    parent_rights_ref: str | None = None
    if args.asset_id:
        source_asset = asset_map(project).get(str(args.asset_id))
        if not source_asset:
            raise argument_error(f"找不到资产: {args.asset_id}", "--asset-id")
        source = Path(str(source_asset.get("uri", "")))
        if not source.is_absolute():
            source = root / source
        parent_rights_ref = str(source_asset.get("rights_ref") or source_asset.get("id"))
    else:
        raw_input = str(args.input or "").strip()
        if raw_input.lower().startswith(("http://", "https://")):
            raise argument_error("--input 只接受本地视频文件", "--input")
        source = Path(raw_input).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise argument_error("防抖输入不存在", str(source))
    derived_id = str(args.derived_asset_id or new_id("asset_stabilized"))
    if derived_id in asset_map(project):
        raise argument_error(f"派生资产 ID 已存在: {derived_id}", "--derived-asset-id")
    output = Path(args.output).expanduser() if args.output else Path("assets") / "derived" / f"stabilized_{safe_filename(derived_id)}.mp4"
    if not output.is_absolute():
        output = root / output
    output = output.resolve()
    ensure_inside(root, output)
    if output.exists():
        raise argument_error("防抖输出已存在，为避免覆盖请指定新的 --output", str(output))
    parameters = {
        "shakiness": args.shakiness, "accuracy": args.accuracy, "stepsize": args.stepsize,
        "mincontrast": args.mincontrast, "smoothing": args.smoothing, "maxshift": args.maxshift,
        "maxangle": args.maxangle, "crop": args.crop, "optzoom": args.optzoom,
        "zoom": args.zoom, "interpol": args.interpol,
    }
    transform_dir = root / "cache" / "stabilization" / safe_filename(derived_id)
    if args.dry_run:
        return _envelope(
            "media.stabilize",
            args,
            status="planned",
            data={"input": str(source), "asset_id": args.asset_id, "derived_asset_id": derived_id, "output": str(output), "transform_dir": str(transform_dir), "parameters": parameters, "engine": "ffmpeg-local:vidstabdetect+vidstabtransform"},
        )
    snapshot = create_snapshot(root, project, label="before-stabilize")
    operation_id = new_id("op")
    _progress(args, operation_id, "started", "media.stabilize.detect", 0, "开始本地 vidstabdetect 分析")
    try:
        stabilization = stabilize_media(source, output, transform_dir, **parameters)
        _progress(args, operation_id, "progress", "media.stabilize.transform", 70, "完成运动轨迹分析，开始 vidstabtransform 输出")
        digest = str(stabilization["output_sha256"])
        if source_asset is not None:
            ledger = load_ledger(root)
            parent_records = {str(item.get("asset_id")): item for item in active_records(ledger)}
            parent_record = parent_records.get(parent_rights_ref or "")
            if parent_record is None:
                raise AppError("RIGHTS_RECORD_MISSING", "源资产缺少可继承的 Rights Ledger 记录", exit_code=7, path=parent_rights_ref)
            rights_source_url = f"local://{output}"
            record = {
                "asset_id": derived_id, "kind": "video", "sha256": digest, "source_url": rights_source_url,
                "source_version": "derived:vidstab", "retrieved_at": now_iso(), "creator": parent_record.get("creator", "unknown"),
                "license_spdx": parent_record.get("license_spdx", "LicenseRef-UNVERIFIED"), "license_url": parent_record.get("license_url", ""),
                "attribution": parent_record.get("attribution", ""), "permitted_uses": list(parent_record.get("permitted_uses", ["internal"])),
                "permitted_channels": list(parent_record.get("permitted_channels", [])), "restrictions": list(parent_record.get("restrictions", [])),
                "derived_from": [parent_rights_ref], "evidence": parent_record.get("evidence", ""),
                "verification_status": parent_record.get("verification_status", "unverified"), "verified_by": parent_record.get("verified_by", ""),
                "takedown_status": parent_record.get("takedown_status", "clear"), "notes": "Derived by local FFmpeg vidstab; inherits source rights",
            }
        else:
            rights_source_url = require_local_reference(args.source_url or f"local://{source}", field="--source-url")
            evidence_reference = require_local_reference(args.evidence, field="--evidence") if args.evidence else ("" if args.verification_status == "unverified" else f"local://{output}")
            record = {
                "asset_id": derived_id, "kind": "video", "sha256": digest, "source_url": rights_source_url,
                "source_version": "derived:vidstab", "retrieved_at": now_iso(), "creator": args.creator,
                "license_spdx": args.license_spdx, "license_url": require_local_reference(args.license_url, field="--license-url") if args.license_url else "",
                "attribution": "", "permitted_uses": list(dict.fromkeys(args.permitted_use)), "permitted_channels": [],
                "restrictions": [], "derived_from": [], "evidence": evidence_reference, "verification_status": args.verification_status,
                "verified_by": "ai-ad-editor" if args.verification_status == "verified" else "", "takedown_status": "clear",
                "notes": "Derived by local FFmpeg vidstab",
            }
        asset = {
            "id": derived_id, "kind": "video", "uri": str(output.relative_to(root)).replace("\\", "/"),
            "sha256": digest, "probe": stabilization["probe"], "rights_ref": derived_id,
            "source": {"source_url": rights_source_url, "retrieved_at": now_iso(), "original_name": output.name, "derived_from": [source_asset.get("id")] if source_asset else []},
        }
        report_path = root / "validation" / f"stabilization_{safe_filename(operation_id)}.json"
        report = {"report_version": "0.1.0", "created_at": now_iso(), "project_id": project["project"]["id"], "operation_id": operation_id, "snapshot_id": snapshot["snapshot_id"], "asset_id": derived_id, "parent_asset_id": source_asset.get("id") if source_asset else None, "stabilization": stabilization, "rights_dependency": parent_rights_ref}
        atomic_write_json(report_path, report)
        project.setdefault("assets", []).append(asset)
        ledger = load_ledger(root)
        add_record(ledger, record)
        project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.stabilize", "asset_id": derived_id, "source_asset_id": source_asset.get("id") if source_asset else None, "snapshot_id": snapshot["snapshot_id"], "report": str(report_path), "at": now_iso()})
        save_project(root, project)
        save_ledger(root, ledger)
        _operation(root, operation_id, {"operation_id": operation_id, "command": "media.stabilize", "status": "succeeded", "asset_id": derived_id, "source_asset_id": source_asset.get("id") if source_asset else None, "snapshot_id": snapshot["snapshot_id"], "report": str(report_path), "created_at": now_iso()})
        _progress(args, operation_id, "completed", "media.stabilize", 100, "本地防抖派生素材完成")
        return _envelope("media.stabilize", args, data={"asset": asset, "rights": record, "snapshot": snapshot, "report": str(report_path), "stabilization": stabilization}, operation_id=operation_id)
    except Exception:
        if output.exists():
            try:
                output.unlink()
            except OSError:
                pass
        raise


def command_media_relink(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    search_root = Path(args.search_root).expanduser().resolve()
    if args.dry_run:
        return _envelope("media.relink", args, status="planned", data={"project": str(root), "search_root": str(search_root), "match_by_name": bool(args.match_by_name)})
    result = relink_missing_assets(root, project, search_root, match_by_name=args.match_by_name)
    report_path = root / "validation" / f"relink_{new_id('report')}.json"
    atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), "project_id": project["project"]["id"], **result})
    if result["relinked"]:
        ledger = load_ledger(root)
        by_asset = {str(record.get("asset_id")): record for record in ledger.get("records", [])}
        for entry in result["entries"]:
            if entry.get("status") in {"Exact", "Approximate"} and entry.get("asset_id") in by_asset:
                record = by_asset[str(entry["asset_id"])]
                record["sha256"] = entry.get("sha256")
        save_ledger(root, ledger)
        project.setdefault("provenance", {}).setdefault("change_log", []).append({"command": "media.relink", "report": str(report_path), "at": now_iso(), "relinked": result["relinked"]})
        save_project(root, project)
    operation_id = new_id("op")
    status = "succeeded" if not any(item.get("status") == "Failed" for item in result["entries"]) else "failed"
    _operation(root, operation_id, {"operation_id": operation_id, "command": "media.relink", "status": status, "report": str(report_path), "relinked": result["relinked"], "created_at": now_iso()})
    return _envelope("media.relink", args, data={**result, "report": str(report_path)}, status=status, errors=[item for item in result["entries"] if item.get("status") == "Failed"], operation_id=operation_id)


def _record_tracking_dependency(clip: dict[str, Any], adapter: dict[str, Any] | None) -> None:
    from .local_vision import YOLO_ENGINE
    if adapter and adapter.get('engine') == YOLO_ENGINE:
        dependency = {'rights_ref':adapter['rights_ref'], 'sha256':adapter['sha256']}
        values = clip.setdefault('rights_dependencies', [])
        if dependency not in values:
            values.append(dependency)


def _protect_tracking_report(path: Path, adapter: dict[str, Any] | None) -> None:
    from .local_vision import YOLO_ENGINE
    if adapter and adapter.get('engine') == YOLO_ENGINE and path.exists():
        raise AppError('OUTPUT_EXISTS', 'YOLO 报告已存在，请指定新的项目内输出路径', exit_code=2, path=str(path))


def _check_native_tracking_source(adapter: dict[str, Any] | None, asset_id: str | None, applying: bool) -> None:
    if adapter and adapter.get('engine') == 'yolov10-onnx-cpu-tracking-v1' and applying and not asset_id:
        raise AppError('VISION_SOURCE_RIGHTS_REQUIRED', '模型轨迹应用要求先摄取源素材并使用 --asset-id，以保留源权利依赖', exit_code=2)


def _resolve_visual_tracking_adapter(root: Path, adapter_id: str | None) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not adapter_id:
        return None, None
    registry = load_visual_model_registry(root)
    adapter = visual_adapter_for(registry, adapter_id)
    if adapter is None:
        raise AppError("VISUAL_MODEL_ADAPTER_NOT_FOUND", f"找不到已注册视觉适配器: {adapter_id}", exit_code=3, path=str(visual_registry_path(root)))
    verification = verify_visual_adapter(adapter)
    if not verification["ok"]:
        raise AppError("MODEL_ADAPTER_HASH_INVALID", "本地视觉适配器路径或哈希校验失败", exit_code=10, path=str(visual_registry_path(root)), cause=json.dumps(verification, ensure_ascii=False))
    if adapter.get("engine") not in {OBJECT_TRACKING_ENGINE, *MULTI_OBJECT_TRACKING_ENGINES}:
        raise AppError(
            "TRACKING_ADAPTER_UNAVAILABLE",
            f"适配器已登记但当前没有对应本地 runner: {adapter.get('engine')}",
            exit_code=10,
            path=str(adapter_id),
            hint="请登记已支持的 command-json 或 yolov10-onnx-cpu-tracking-v1 引擎；未知模型不会被隐式 fallback",
        )
    return adapter, verification


def _validate_mask_tracking_mode(args: argparse.Namespace) -> None:
    if not args.mask_asset_id:
        nondefault = (args.mask_channel != 'alpha' or args.mask_threshold != 127 or args.mask_source_start_seconds != 0 or
                      args.mask_max_edge != 1280 or args.mask_max_frames != 4096 or args.mask_budget_mib != 256 or
                      args.mask_expectations is not None or args.mask_scene_cut_frame)
        if nondefault:
            raise argument_error('蒙版参数需要 mask-asset-id', 'mask-asset-id')
        if args.roi is None:
            raise argument_error('模板/模型跟踪需要 roi，或显式 mask-asset-id', 'roi')
        return
    if args.roi is not None or args.adapter_id or args.object_id or getattr(args, 'all_objects', False) or not args.asset_id or args.input:
        raise argument_error('蒙版模式需要已登记 asset-id，不能混用 roi/adapter-id/object-id/all-objects/input', 'mask-asset-id')
    if args.search_radius != 48 or args.max_width != 640:
        raise argument_error('蒙版模式使用 mask-max-edge，不使用模板 search-radius/max-width', 'mask-max-edge')


def _mask_tracking_setup(root: Path, project: dict, args: argparse.Namespace, *, start: float, end: float | None, report: Path) -> dict | None:
    _validate_mask_tracking_mode(args)
    if not args.mask_asset_id:
        return None
    source_asset = asset_map(project).get(args.asset_id)
    mask_asset = asset_map(project).get(args.mask_asset_id)
    if source_asset is None or mask_asset is None:
        raise argument_error('源或蒙版资产未登记', 'asset-id/mask-asset-id')
    try:
        report.resolve().relative_to((root / 'validation').resolve())
    except ValueError as exc:
        raise argument_error('蒙版跟踪报告必须位于项目 validation 目录', 'output') from exc
    if report.suffix.lower() != '.json' or args.mask_expectations and report == resolve_local_path(root, args.mask_expectations, field='mask-expectations'):
        raise argument_error('蒙版跟踪报告须为 JSON 且不能覆盖期望文件', 'output')
    ledger = active_records(load_ledger(root))
    for asset in (source_asset, mask_asset):
        if not any(r.get('asset_id') == asset.get('rights_ref') and r.get('sha256') == asset.get('sha256') for r in ledger):
            raise AppError('RIGHTS_RECORD_MISSING', '源/蒙版缺少匹配权利记录', exit_code=7)
    plan = prepare_mask_tracking(root, source_asset, mask_asset, start_seconds=start, end_seconds=end,
        source_start_seconds=args.mask_source_start_seconds, channel=args.mask_channel, threshold=args.mask_threshold,
        max_edge=args.mask_max_edge, max_frames=args.mask_max_frames, budget_mib=args.mask_budget_mib,
        expectations=args.mask_expectations, scene_cuts=args.mask_scene_cut_frame, step_frames=args.step_frames,
        max_samples=args.max_samples, ticks_per_second=int(project['settings']['timebase']['ticks_per_second']))
    raw = source_asset['probe']['video']; display = plan['source_display']
    if raw['width'] != plan['source_coded']['width'] or raw['height'] != plan['source_coded']['height']:
        raise AppError('MASK_TRACK_SOURCE_PROBE_CHANGED', '源登记尺寸与实际编码不同，请重新摄取', exit_code=6)
    if (display['width'] != raw['width'] or display['height'] != raw['height']) and (getattr(args, 'source_clip_id', None) or args.action == 'reframe' and args.apply):
        raise AppError('MASK_TRACK_RENDER_GEOMETRY_UNSUPPORTED', '该源的固有旋转/SAR 需要先烘焙显示几何，再使用画布绑定或重构图应用', exit_code=2)
    return plan


def _record_mask_tracking_dependency(clip: dict, tracking: dict) -> None:
    if tracking.get('engine') == MASK_TRACKING_ENGINE:
        records = clip.setdefault('rights_dependencies', [])
        for dependency in tracking['rights_dependencies']:
            if dependency not in records:
                records.append(copy.deepcopy(dependency))


def _mask_tracking_warnings() -> list[dict]:
    return [{'code': 'MASK_TRACK_REVIEW_REQUIRED', 'message': '轨迹来自所供蒙版框；confidence 仅表示非空，仍须复核对象身份、范围、插值和裁切'}]


def command_media_track(args: argparse.Namespace) -> dict[str, Any]:
    _validate_mask_tracking_mode(args)
    root, project = load_project(args.project)
    if bool(args.asset_id) == bool(args.input):
        raise argument_error("必须且只能提供 --asset-id 或 --input")
    source: Path
    asset_id = args.asset_id
    if asset_id:
        asset = asset_map(project).get(str(asset_id))
        if not asset:
            raise argument_error(f"找不到资产: {asset_id}", "--asset-id")
        source = Path(str(asset.get("uri", "")))
        if not source.is_absolute():
            source = root / source
    else:
        source = Path(str(args.input)).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise argument_error("跟踪输入不存在", str(source))
    visual_adapter, adapter_verification = _resolve_visual_tracking_adapter(root, args.adapter_id)
    _check_native_tracking_source(visual_adapter, asset_id, bool(args.clip_id))
    if args.object_id and args.all_objects:
        raise argument_error("--object-id 与 --all-objects 不能同时使用", "object_id")
    if args.all_objects and args.clip_id:
        raise AppError("TRACK_MULTI_APPLY_SELECTION_REQUIRED", "--all-objects 只生成多目标报告，不能与 --clip-id 联用", exit_code=2, path="clip_id")
    if args.object_id or args.all_objects:
        if not visual_adapter or visual_adapter.get("engine") not in MULTI_OBJECT_TRACKING_ENGINES:
            raise AppError("TRACK_OBJECT_SELECTION_UNSUPPORTED", "object_id/all_objects 只适用于多目标视觉适配器", exit_code=2, path="adapter_id")
    if visual_adapter and visual_adapter.get("engine") in MULTI_OBJECT_TRACKING_ENGINES and not (args.object_id or args.all_objects):
        raise AppError("TRACK_OBJECT_SELECTION_REQUIRED", "多目标视觉 runner 需要 --object-id 或 --all-objects", exit_code=2, path="object_id")
    sequence_id = args.sequence_id
    if args.clip_id:
        sequence = find_sequence(project, sequence_id)
        _find_clip(sequence, str(args.clip_id), args.track_id)
    report_path = resolve_local_path(root, args.output, field='output') if args.output else root / 'validation' / f"tracking_{new_id('run')}.json"
    mask_plan = _mask_tracking_setup(root, project, args, start=args.start_seconds, end=args.end_seconds, report=report_path)
    if args.dry_run:
        return _envelope(
            "media.track",
            args,
            status="planned",
            data={
                "input": str(source),
                "asset_id": asset_id,
                "roi": args.roi,
                "clip_id": args.clip_id,
                "sequence_id": sequence_id,
                "step_frames": args.step_frames,
                "adapter_id": args.adapter_id,
                "object_id": args.object_id,
                "all_objects": bool(args.all_objects),
                "adapter": visual_adapter,
                "adapter_verification": adapter_verification,
                "engine": MASK_TRACKING_ENGINE if mask_plan else visual_adapter.get("engine") if visual_adapter else "local-template-matching",
                "mask_plan": public_mask_tracking_plan(mask_plan) if mask_plan else None,
            },
        )
    if mask_plan:
        report = execute_mask_tracking(root, mask_plan, failure_report=report_path)
    elif visual_adapter and visual_adapter.get("engine") in MULTI_OBJECT_TRACKING_ENGINES:
        report = track_command_json_multi(
            source,
            args.roi,
            adapter_id=str(visual_adapter["adapter_id"]),
            model_path=str(visual_adapter["model_path"]),
            executable=str(visual_adapter["executable"]),
            model_sha256=str(visual_adapter.get("model_sha256") or ""),
            executable_sha256=str(visual_adapter.get("executable_sha256") or ""),
            object_id=args.object_id,
            start_seconds=args.start_seconds,
            end_seconds=args.end_seconds,
            step_frames=args.step_frames,
            max_width=args.max_width,
            max_samples=args.max_samples,
            ticks_per_second=int(project["settings"]["timebase"]["ticks_per_second"]),
            native_adapter=visual_adapter if visual_adapter.get("engine") == "yolov10-onnx-cpu-tracking-v1" else None,
        )
    elif visual_adapter:
        report = track_command_json(
            source,
            args.roi,
            adapter_id=str(visual_adapter["adapter_id"]),
            model_path=str(visual_adapter["model_path"]),
            executable=str(visual_adapter["executable"]),
            model_sha256=str(visual_adapter.get("model_sha256") or ""),
            executable_sha256=str(visual_adapter.get("executable_sha256") or ""),
            start_seconds=args.start_seconds,
            end_seconds=args.end_seconds,
            step_frames=args.step_frames,
            max_width=args.max_width,
            max_samples=args.max_samples,
            ticks_per_second=int(project["settings"]["timebase"]["ticks_per_second"]),
        )
    else:
        report = track_media(
            source,
            args.roi,
            start_seconds=args.start_seconds,
            end_seconds=args.end_seconds,
            step_frames=args.step_frames,
            search_radius=args.search_radius,
            max_width=args.max_width,
            max_samples=args.max_samples,
            ticks_per_second=int(project["settings"]["timebase"]["ticks_per_second"]),
        )
    report["source_sha256"] = f"sha256:{sha256_file(source)}"
    report["asset_id"] = asset_id
    report["clip_id"] = args.clip_id
    report["sequence_id"] = sequence_id
    report["adapter_id"] = args.adapter_id
    report["object_id"] = args.object_id
    report["all_objects"] = bool(args.all_objects)
    try:
        report_path.relative_to(root)
    except ValueError as exc:
        raise argument_error("跟踪报告必须位于项目目录内", str(report_path)) from exc
    _protect_tracking_report(report_path, visual_adapter)
    before_snapshot: dict[str, Any] | None = None
    operation_id = new_id("op")
    applied_properties: list[str] = []
    if args.clip_id:
        target_sequence = find_sequence(project, sequence_id)
        _, clip = _find_clip(target_sequence, str(args.clip_id), args.track_id)
        before_snapshot = create_snapshot(root, project, label="before-track-apply")
        for item in report.get("keyframes", []):
            if not isinstance(item, dict) or not isinstance(item.get("keyframes"), list):
                continue
            values: list[tuple[int, float, str]] = []
            for point in item["keyframes"]:
                if not isinstance(point, dict):
                    continue
                try:
                    values.append((int(point.get("at_tick", 0)), float(point.get("value", 0.0)), str(point.get("interpolation", "linear"))))
                except (TypeError, ValueError):
                    continue
            if values:
                _set_keyframe_track(clip, str(item.get("property")), values)
                applied_properties.append(str(item.get("property")))
        _clamp_clip_keyframes(clip)
        _record_tracking_dependency(clip, visual_adapter)
        _record_mask_tracking_dependency(clip, report)
        validation = validate_project(root, project, strict_rights=False)
        if not validation["ok"]:
            raise AppError("TRACK_APPLY_INVALID", "对象跟踪关键帧应用后项目校验失败", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
        project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.track", "asset_id": asset_id, "clip_id": args.clip_id, "report": str(report_path), "at": now_iso()})
    atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), "project_id": project["project"]["id"], **report})
    if args.clip_id:
        save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "media.track", "status": "succeeded", "report": str(report_path), "asset_id": asset_id, "clip_id": args.clip_id, "engine": report.get("engine"), "adapter_id": args.adapter_id, "object_id": args.object_id, "all_objects": bool(args.all_objects), "applied_properties": applied_properties, "before_snapshot": before_snapshot, "created_at": now_iso()})
    if mask_plan:
        warnings = _mask_tracking_warnings()
    elif visual_adapter and visual_adapter.get("engine") in MULTI_OBJECT_TRACKING_ENGINES:
        warnings = [{"code": "TRACKING_MULTI_OBJECT_REVIEW", "message": "多目标 runner 输出已通过协议校验，但仍需检查对象身份连续性、遮挡、镜头切换和轨迹稳定性"}]
    elif visual_adapter:
        warnings = [{"code": "TRACKING_EXTERNAL_REVIEW", "message": "本地视觉 runner 输出已通过协议校验，但仍需用质量报告检查遮挡、镜头切换和轨迹稳定性"}]
    else:
        warnings = [{"code": "TRACKING_APPROXIMATE", "message": "本地模板匹配可能在遮挡、缩放或镜头切换时漂移；请检查 confidence 和关键帧"}]
    return _envelope("media.track", args, data={"report": str(report_path), "result": report, "adapter": visual_adapter, "adapter_verification": adapter_verification, "applied_properties": applied_properties, "before_snapshot": before_snapshot}, warnings=warnings, operation_id=operation_id)


def command_media_track_bind(args: argparse.Namespace) -> dict[str, Any]:
    """Bind local tracking output to an independent visual clip.

    The target may be a text generator, sticker-like media clip, or any other
    visual clip that accepts ordinary transform keyframes.  Source tracking is
    sampled in its own local clock and mapped deterministically onto the target
    clip duration, so a short overlay can follow a longer source range without
    changing the source media or generating a hidden dependency.
    """
    _validate_mask_tracking_mode(args)
    root, project = load_project(args.project)
    if bool(args.asset_id) == bool(args.input):
        raise argument_error("必须且只能提供 --asset-id 或 --input")
    if not -1.0 <= float(args.offset_x) <= 1.0 or not -1.0 <= float(args.offset_y) <= 1.0:
        raise argument_error("offset-x/offset-y 必须位于 -1..1", "offset")
    if float(args.scale_multiplier) <= 0 or float(args.scale_multiplier) > 20:
        raise argument_error("scale-multiplier 必须位于 (0,20]", "scale_multiplier")
    asset_id = args.asset_id
    if asset_id:
        asset = asset_map(project).get(str(asset_id))
        if not asset:
            raise argument_error(f"找不到跟踪源资产: {asset_id}", "asset_id")
        source = Path(str(asset.get("uri", "")))
        if not source.is_absolute():
            source = root / source
    else:
        raw_input = str(args.input or "").strip()
        if raw_input.lower().startswith(("http://", "https://")):
            raise argument_error("跟踪绑定只接受本地输入", "input")
        source = Path(raw_input).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise argument_error("跟踪绑定输入不存在", str(source))
    visual_adapter, adapter_verification = _resolve_visual_tracking_adapter(root, args.adapter_id)
    _check_native_tracking_source(visual_adapter, asset_id, bool(args.apply))
    if args.object_id and (not visual_adapter or visual_adapter.get("engine") not in MULTI_OBJECT_TRACKING_ENGINES):
        raise AppError("TRACK_OBJECT_SELECTION_UNSUPPORTED", "object_id 只适用于多目标视觉适配器", exit_code=2, path="adapter_id")
    if visual_adapter and visual_adapter.get("engine") in MULTI_OBJECT_TRACKING_ENGINES and not args.object_id:
        raise AppError("TRACK_OBJECT_SELECTION_REQUIRED", "多目标视觉 runner 需要 --object-id 才能绑定到目标片段", exit_code=2, path="object_id")
    sequence = find_sequence(project, args.sequence_id)
    target_track, target_clip = _find_clip(sequence, str(args.target_clip_id), args.target_track_id)
    if str(target_track.get("kind", "video")) == "audio":
        raise AppError("TRACK_BIND_TARGET_AUDIO", "对象跟踪不能绑定到音频片段", exit_code=2, path="target_track_id")
    if target_clip.get("sequence_id"):
        raise AppError("TRACK_BIND_NESTED_UNSUPPORTED", "对象跟踪绑定当前不支持嵌套序列片段", exit_code=2, path="target_clip_id")
    source_track = source_clip = None
    if bool(args.source_clip_id) != bool(args.source_track_id):
        raise argument_error('source-clip-id 与 source-track-id 必须同时提供', 'source_clip_id')
    if args.source_clip_id:
        if not asset_id:
            raise argument_error('画布绑定需要已摄取的 --asset-id', 'asset_id')
        source_track,source_clip = _find_clip(sequence,args.source_clip_id,args.source_track_id)
        if source_clip.get('asset_id') != asset_id or source_clip.get('sequence_id') or source_clip.get('id') == target_clip.get('id') or source_track.get('kind') not in {'video','overlay'}:
            raise argument_error('画布绑定源必须是相同 asset-id 的独立直接视频片段', 'source_clip_id')
        if asset_map(project)[asset_id].get('sha256') != 'sha256:'+sha256_file(source):
            raise AppError('TRACK_BIND_SOURCE_CHANGED', '源媒体已偏离摄取摘要，请重新摄取后跟踪', exit_code=6)
    elif args.rotation_mode != 'none':
        raise argument_error('rotation-mode=source 需要明确源片段', 'source_clip_id')
    target_duration = max(1, int(target_clip.get("duration_tick", 1)))
    if float(args.start_seconds) < 0:
        raise argument_error("start-seconds 不能为负数", "start_seconds")
    if args.end_seconds is not None and float(args.end_seconds) <= float(args.start_seconds):
        raise argument_error("end-seconds 必须大于 start-seconds", "end_seconds")
    report_path = resolve_local_path(root, args.output, field='output') if args.output else root / "validation" / f"track_bind_{safe_filename(str(args.target_clip_id))}.json"
    ensure_inside(root, report_path)
    _protect_tracking_report(report_path, visual_adapter)
    mask_plan = _mask_tracking_setup(root, project, args, start=args.start_seconds, end=args.end_seconds, report=report_path)
    if args.dry_run:
        return _envelope(
            "media.track-bind",
            args,
            status="planned",
            data={
                "input": str(source),
                "asset_id": asset_id,
                "roi": args.roi,
                "target_clip_id": args.target_clip_id,
                "target_track_id": args.target_track_id,
                "sequence_id": sequence.get("id"),
                "target_duration_tick": target_duration,
                "coordinate_space": "timeline-canvas-v1" if source_clip else "source-normalized",
                "source_clip_id": args.source_clip_id,
                "source_track_id": args.source_track_id,
                "rotation_mode": args.rotation_mode,
                "scale_mode": args.scale_mode,
                "scale_multiplier": args.scale_multiplier,
                "offset": {"x": args.offset_x, "y": args.offset_y},
                "apply": bool(args.apply),
                "adapter_id": args.adapter_id,
                "object_id": args.object_id,
                "adapter": visual_adapter,
                "adapter_verification": adapter_verification,
                "engine": MASK_TRACKING_ENGINE if mask_plan else visual_adapter.get("engine") if visual_adapter else "local-template-matching",
                "network": "disabled",
                "mask_plan": public_mask_tracking_plan(mask_plan) if mask_plan else None,
            },
        )
    if mask_plan:
        tracking = execute_mask_tracking(root, mask_plan, failure_report=report_path)
    elif visual_adapter and visual_adapter.get("engine") in MULTI_OBJECT_TRACKING_ENGINES:
        tracking = track_command_json_multi(
            source,
            args.roi,
            adapter_id=str(visual_adapter["adapter_id"]),
            model_path=str(visual_adapter["model_path"]),
            executable=str(visual_adapter["executable"]),
            model_sha256=str(visual_adapter.get("model_sha256") or ""),
            executable_sha256=str(visual_adapter.get("executable_sha256") or ""),
            object_id=args.object_id,
            start_seconds=float(args.start_seconds),
            end_seconds=args.end_seconds,
            step_frames=args.step_frames,
            max_width=args.max_width,
            max_samples=args.max_samples,
            ticks_per_second=int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", TICKS_PER_SECOND)),
            native_adapter=visual_adapter if visual_adapter.get("engine") == "yolov10-onnx-cpu-tracking-v1" else None,
        )
    elif visual_adapter:
        tracking = track_command_json(
            source,
            args.roi,
            adapter_id=str(visual_adapter["adapter_id"]),
            model_path=str(visual_adapter["model_path"]),
            executable=str(visual_adapter["executable"]),
            model_sha256=str(visual_adapter.get("model_sha256") or ""),
            executable_sha256=str(visual_adapter.get("executable_sha256") or ""),
            start_seconds=float(args.start_seconds),
            end_seconds=args.end_seconds,
            step_frames=args.step_frames,
            max_width=args.max_width,
            max_samples=args.max_samples,
            ticks_per_second=int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", TICKS_PER_SECOND)),
        )
    else:
        tracking = track_media(
            source,
            args.roi,
            start_seconds=float(args.start_seconds),
            end_seconds=args.end_seconds,
            step_frames=args.step_frames,
            search_radius=args.search_radius,
            max_width=args.max_width,
            max_samples=args.max_samples,
            ticks_per_second=int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", TICKS_PER_SECOND)),
        )
    frames = [item for item in tracking.get("frames", []) if isinstance(item, dict)]
    if not frames:
        raise AppError("TRACK_BIND_EMPTY", "跟踪没有返回可绑定的帧", exit_code=6, path="frames")
    source_span_tick = max(1, max(int(item.get("at_tick", 0)) for item in frames))
    if tracking.get('engine') in {'yolov10-onnx-cpu-tracking-v1', MASK_TRACKING_ENGINE}:
        source_span_tick = max(1, round((tracking['range']['end_seconds']-tracking['range']['start_seconds'])*int(project['settings']['timebase']['ticks_per_second'])))
    first_width = max(1e-6, float(frames[0].get("width", 0.0) or 0.0))
    base_scale = float(target_clip.get("transform", {}).get("scale", 1.0) if isinstance(target_clip.get("transform"), dict) else 1.0)
    if base_scale <= 0:
        base_scale = 1.0
    position_x: list[tuple[int, float, str]] = []
    position_y: list[tuple[int, float, str]] = []
    scale_values: list[tuple[int, float, str]] = []
    for item in frames:
        try:
            local_tick = min(target_duration, max(0, int(round(int(item.get("at_tick", 0)) / source_span_tick * target_duration))))
            x = min(1.0, max(0.0, float(item.get("x", 0.5)) + float(args.offset_x)))
            y = min(1.0, max(0.0, float(item.get("y", 0.5)) + float(args.offset_y)))
            width = max(1e-6, float(item.get("width", first_width) or first_width))
        except (TypeError, ValueError):
            continue
        position_x.append((local_tick, x, "linear"))
        position_y.append((local_tick, y, "linear"))
        if args.scale_mode == "roi":
            scale_values.append((local_tick, max(0.01, min(20.0, base_scale * float(args.scale_multiplier) * width / first_width)), "linear"))
    if not position_x:
        raise AppError("TRACK_BIND_EMPTY", "跟踪帧没有可用的绑定关键帧", exit_code=6, path="frames")
    plan: dict[str, Any] = {
        "binding_version": "0.1.0",
        "engine": tracking.get("engine", "local-template-matching"),
        "method": tracking.get("method", "template-matching"),
        "adapter_id": args.adapter_id,
        "object_id": args.object_id,
        "source": str(source),
        "source_sha256": f"sha256:{sha256_file(source)}",
        "asset_id": asset_id,
        "sequence_id": sequence.get("id"),
        "target_track_id": target_track.get("id"),
        "target_clip_id": target_clip.get("id"),
        "target_duration_tick": target_duration,
        "roi": args.roi,
        "scale_mode": args.scale_mode,
        "scale_multiplier": float(args.scale_multiplier),
        "offset": {"x": float(args.offset_x), "y": float(args.offset_y)},
        "keyframes": [
            {"property": "transform.position.x", "keyframes": [{"at_tick": at, "value": value, "interpolation": interpolation} for at, value, interpolation in position_x]},
            {"property": "transform.position.y", "keyframes": [{"at_tick": at, "value": value, "interpolation": interpolation} for at, value, interpolation in position_y]},
        ],
        "tracking": tracking,
        "warnings": (["multi_object_identity_requires_quality_review", "tracking_clock_mapped_to_target_clip_duration"] if visual_adapter and visual_adapter.get("engine") in MULTI_OBJECT_TRACKING_ENGINES else ["external_local_runner_requires_quality_review", "tracking_clock_mapped_to_target_clip_duration"] if visual_adapter else ["template_matching_can_drift_on_occlusion_or_large_scale_change", "tracking_clock_mapped_to_target_clip_duration"]),
    }
    if args.scale_mode == "roi":
        plan["keyframes"].append({"property": "transform.scale", "keyframes": [{"at_tick": at, "value": value, "interpolation": interpolation} for at, value, interpolation in scale_values]})
    if mask_plan:
        plan['warnings'] = tracking['warnings'] + ['tracking_clock_mapped_to_target_clip_duration']
    if source_clip is not None:
        from .bindings import make_binding,compile_binding
        tracking['source_sha256'] = plan['source_sha256']
        if tracking['range'].get('end_seconds') is None:
            tracking['range']['end_seconds'] = float(asset_map(project)[asset_id]['probe']['duration_seconds'])
        binding = make_binding(project,sequence,source_track,source_clip,target_track,target_clip,tracking,offset_x=float(args.offset_x),offset_y=float(args.offset_y),scale_mode=args.scale_mode,scale_multiplier=float(args.scale_multiplier),rotation_mode=args.rotation_mode)
        from .bindings import native_clock_project
        if native_clock_project(project):
            from .float_tracking import binding_plan
            geometry = binding_plan(project,sequence,target_track,{**target_clip,'tracking_binding':binding})
        else:
            geometry = compile_binding(project,sequence,target_track,{**target_clip,'tracking_binding':binding})
        model_warnings = [w for w in plan['warnings'] if w != 'tracking_clock_mapped_to_target_clip_duration']
        plan.update({'binding_version':'0.2.0','tracking_binding':binding,**geometry})
        plan['warnings'] = model_warnings+plan['warnings']
    if not args.apply:
        atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), "applied": False, "plan": plan})
        warnings = _mask_tracking_warnings() if mask_plan else ([{"code": "TRACKING_MULTI_OBJECT_REVIEW", "message": "多目标 runner 输出已通过协议校验，但仍需检查对象身份连续性、目标文字/贴纸边界和轨迹稳定性"}] if visual_adapter and visual_adapter.get("engine") in MULTI_OBJECT_TRACKING_ENGINES else [{"code": "TRACKING_EXTERNAL_REVIEW", "message": "本地视觉 runner 输出已通过协议校验，但仍需检查目标文字/贴纸边界和轨迹稳定性"}] if visual_adapter else [{"code": "TRACKING_APPROXIMATE", "message": "本地模板匹配绑定可能在遮挡、缩放或镜头切换时漂移；请检查 confidence 和目标文字/贴纸边界"}])
        return _envelope("media.track-bind", args, status="planned", data={"report": str(report_path), "plan": plan, "adapter": visual_adapter, "adapter_verification": adapter_verification, "applied": False}, warnings=warnings)
    before_project = copy.deepcopy(project)
    before_snapshot = create_snapshot(root, before_project, label="before-track-bind")
    if source_clip is not None:
        from .bindings import apply_compiled_binding
        target_clip['tracking_binding'] = copy.deepcopy(plan['tracking_binding'])
        apply_compiled_binding(target_clip,plan)
    else:
        target_clip.pop('tracking_binding',None)
    for item in plan["keyframes"]:
        values = [(int(point["at_tick"]), float(point["value"]), str(point.get("interpolation", "linear"))) for point in item["keyframes"]]
        _set_keyframe_track(target_clip, str(item["property"]), values)
    _clamp_clip_keyframes(target_clip)
    _record_tracking_dependency(target_clip, visual_adapter)
    _record_mask_tracking_dependency(target_clip, tracking)
    validation = validate_project(root, project, strict_rights=False)
    if not validation["ok"]:
        raise AppError("TRACK_BIND_APPLY_INVALID", "对象跟踪绑定后项目校验失败", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    operation_id = new_id("op")
    atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), "applied": True, "operation_id": operation_id, "before_snapshot_id": before_snapshot["snapshot_id"], "plan": plan, "validation": validation})
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.track-bind", "asset_id": asset_id, "target_clip_id": target_clip.get("id"), "target_track_id": target_track.get("id"), "report": str(report_path), "before_snapshot_id": before_snapshot["snapshot_id"], "at": now_iso()})
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "media.track-bind", "status": "succeeded", "report": str(report_path), "asset_id": asset_id, "object_id": args.object_id, "target_clip_id": target_clip.get("id"), "target_track_id": target_track.get("id"), "before_snapshot_id": before_snapshot["snapshot_id"], "created_at": now_iso()})
    warnings = _mask_tracking_warnings() if mask_plan else ([{"code": "TRACKING_MULTI_OBJECT_REVIEW", "message": "多目标 runner 输出已通过协议校验，但仍需检查对象身份连续性、目标文字/贴纸边界和轨迹稳定性"}] if visual_adapter and visual_adapter.get("engine") in MULTI_OBJECT_TRACKING_ENGINES else [{"code": "TRACKING_EXTERNAL_REVIEW", "message": "本地视觉 runner 输出已通过协议校验，但仍需检查目标文字/贴纸边界和轨迹稳定性"}] if visual_adapter else [{"code": "TRACKING_APPROXIMATE", "message": "本地模板匹配绑定可能在遮挡、缩放或镜头切换时漂移；请检查 confidence 和目标文字/贴纸边界"}])
    return _envelope("media.track-bind", args, data={"report": str(report_path), "plan": plan, "adapter": visual_adapter, "adapter_verification": adapter_verification, "target_clip_id": target_clip.get("id"), "target_track_id": target_track.get("id"), "before_snapshot": before_snapshot, "validation": validation, "applied": True}, warnings=warnings, operation_id=operation_id)


def command_media_reframe(args: argparse.Namespace) -> dict[str, Any]:
    _validate_mask_tracking_mode(args)
    root, project = load_project(args.project)
    if bool(args.asset_id) == bool(args.input):
        raise argument_error("必须且只能提供 --asset-id 或 --input")
    sequence = find_sequence(project, args.sequence_id)
    _, clip = _find_clip(sequence, str(args.clip_id), args.track_id)
    if clip.get('presentation_window') is not None:
        raise AppError('REFRAME_PRESENTATION_WINDOW_UNSUPPORTED','请先在完整作者片段上重构图，再裁切输出窗口',exit_code=2,path='clip.presentation_window')
    if clip.get("sequence_id"):
        raise AppError("REFRAME_NESTED_UNSUPPORTED", "自动重构图当前只支持直接媒体片段", exit_code=2, path="clip_id")
    try:
        speed = float(clip.get("speed", 1.0))
    except (TypeError, ValueError) as exc:
        raise AppError("REFRAME_SPEED_UNSUPPORTED", "自动重构图无法解析片段 speed", exit_code=2, path="clip.speed") from exc
    if abs(speed - 1.0) > 1e-6 or bool(clip.get("reverse")) or clip.get("speed_curve") is not None:
        raise AppError("REFRAME_TIME_MAPPING_UNSUPPORTED", "自动重构图当前要求常速正向片段，请先烘焙变速或倒放", exit_code=2, path="clip.speed")
    asset_id = args.asset_id
    if asset_id:
        asset = asset_map(project).get(str(asset_id))
        if not asset:
            raise argument_error(f"找不到资产: {asset_id}", "--asset-id")
        source = Path(str(asset.get("uri", "")))
        if not source.is_absolute():
            source = root / source
    else:
        source = Path(str(args.input)).expanduser().resolve()
        asset = None
    if not source.exists() or not source.is_file():
        raise argument_error("自动重构图输入不存在", str(source))
    visual_adapter, adapter_verification = _resolve_visual_tracking_adapter(root, args.adapter_id)
    _check_native_tracking_source(visual_adapter, asset_id, bool(args.apply))
    if args.object_id and (not visual_adapter or visual_adapter.get("engine") not in MULTI_OBJECT_TRACKING_ENGINES):
        raise AppError("TRACK_OBJECT_SELECTION_UNSUPPORTED", "object_id 只适用于多目标视觉适配器", exit_code=2, path="adapter_id")
    if visual_adapter and visual_adapter.get("engine") in MULTI_OBJECT_TRACKING_ENGINES and not args.object_id:
        raise AppError("TRACK_OBJECT_SELECTION_REQUIRED", "多目标视觉 runner 需要 --object-id 才能生成自动重构图", exit_code=2, path="object_id")
    tps = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", 90_000))
    clip_source_in = int(clip.get("source_in_tick", 0))
    clip_source_out = int(clip.get("source_out_tick", clip_source_in + int(clip.get("duration_tick", 1))))
    start_seconds = clip_source_in / max(1, tps) if args.start_seconds is None else (float(args.start_seconds) if args.mask_asset_id else max(0.0, float(args.start_seconds)))
    end_seconds = clip_source_out / max(1, tps) if args.end_seconds is None else args.end_seconds
    if end_seconds is not None and end_seconds <= start_seconds:
        raise argument_error("自动重构图 end_seconds 必须大于 start_seconds", "--end-seconds")
    probe = probe_media(source)
    video = probe.get("video") if isinstance(probe.get("video"), dict) else {}
    source_width = int(video.get("width", 0) or 0)
    source_height = int(video.get("height", 0) or 0)
    if source_width <= 0 or source_height <= 0:
        raise AppError("REFRAME_VIDEO_MISSING", "自动重构图需要视频流", exit_code=4, path="input")
    canvas = project.get("settings", {}).get("canvas") if isinstance(project.get("settings", {}).get("canvas"), dict) else {}
    target_width = int(args.target_width or canvas.get("width", 1080))
    target_height = int(args.target_height or canvas.get("height", 1920))
    target_aspect = float(args.target_aspect or (target_width / max(1, target_height)))
    if target_width <= 0 or target_height <= 0:
        raise argument_error("目标画布尺寸必须大于 0", "target_width")
    report_path = resolve_local_path(root, args.output, field='output') if args.output else root / 'validation' / f"reframe_{safe_filename(str(args.clip_id))}.json"
    mask_plan = _mask_tracking_setup(root, project, args, start=start_seconds, end=end_seconds, report=report_path)
    if mask_plan and clip.get('asset_id') != asset_id:
        raise argument_error('蒙版重构图的目标片段必须使用同一 asset-id', 'clip-id')
    if args.dry_run:
        return _envelope("media.reframe", args, status="planned", data={"input": str(source), "asset_id": asset_id, "clip_id": args.clip_id, "track_id": args.track_id, "sequence_id": sequence.get("id"), "target_width": target_width, "target_height": target_height, "target_aspect": target_aspect, "margin": args.margin, "fit": args.fit, "start_seconds": start_seconds, "end_seconds": end_seconds, "adapter_id": args.adapter_id, "object_id": args.object_id, "adapter": visual_adapter, "adapter_verification": adapter_verification, "mask_plan": public_mask_tracking_plan(mask_plan) if mask_plan else None, "engine": MASK_TRACKING_ENGINE if mask_plan else visual_adapter.get("engine") if visual_adapter else "local-template-matching"})
    if mask_plan:
        tracking = execute_mask_tracking(root, mask_plan, failure_report=report_path)
        source_width, source_height = (mask_plan['source_display'][k] for k in ('width', 'height'))
    elif visual_adapter and visual_adapter.get("engine") in MULTI_OBJECT_TRACKING_ENGINES:
        tracking = track_command_json_multi(
            source,
            args.roi,
            adapter_id=str(visual_adapter["adapter_id"]),
            model_path=str(visual_adapter["model_path"]),
            executable=str(visual_adapter["executable"]),
            model_sha256=str(visual_adapter.get("model_sha256") or ""),
            executable_sha256=str(visual_adapter.get("executable_sha256") or ""),
            object_id=args.object_id,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            step_frames=args.step_frames,
            max_width=args.max_width,
            max_samples=args.max_samples,
            ticks_per_second=tps,
            native_adapter=visual_adapter if visual_adapter.get("engine") == "yolov10-onnx-cpu-tracking-v1" else None,
        )
    elif visual_adapter:
        tracking = track_command_json(
            source,
            args.roi,
            adapter_id=str(visual_adapter["adapter_id"]),
            model_path=str(visual_adapter["model_path"]),
            executable=str(visual_adapter["executable"]),
            model_sha256=str(visual_adapter.get("model_sha256") or ""),
            executable_sha256=str(visual_adapter.get("executable_sha256") or ""),
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            step_frames=args.step_frames,
            max_width=args.max_width,
            max_samples=args.max_samples,
            ticks_per_second=tps,
        )
    else:
        tracking = track_media(
            source,
            args.roi,
            start_seconds=start_seconds,
            end_seconds=end_seconds,
            step_frames=args.step_frames,
            search_radius=args.search_radius,
            max_width=args.max_width,
            max_samples=args.max_samples,
            ticks_per_second=tps,
        )
    plan = build_reframe_plan(
        tracking.get("frames", []),
        source_aspect=source_width / source_height,
        target_aspect=target_aspect,
        margin=args.margin,
        fit=args.fit,
    )
    if mask_plan:
        plan['engine'] = 'local-reframe-from-mask-bbox-v1'
        plan['warnings'] = [w for w in plan['warnings'] if not w.startswith('local_template_')] + tracking['warnings']
    plan.update({"project_id": project.get("project", {}).get("id"), "sequence_id": sequence.get("id"), "asset_id": asset_id, "clip_id": args.clip_id, "track_id": args.track_id, "source": str(source), "source_sha256": f"sha256:{sha256_file(source)}", "source_range": {"start_seconds": start_seconds, "end_seconds": end_seconds}, "adapter_id": args.adapter_id, "object_id": args.object_id, "tracking": tracking})
    ensure_inside(root, report_path)
    _protect_tracking_report(report_path, visual_adapter)
    if not args.apply:
        atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), "applied": False, "plan": plan})
        warnings = _mask_tracking_warnings() if mask_plan else ([{"code": "TRACKING_MULTI_OBJECT_REVIEW", "message": "多目标 runner 输出已通过协议校验，但仍需检查对象身份连续性、主体边界和动态裁切稳定性"}] if visual_adapter and visual_adapter.get("engine") in MULTI_OBJECT_TRACKING_ENGINES else [{"code": "TRACKING_EXTERNAL_REVIEW", "message": "本地视觉 runner 输出已通过协议校验，但仍需检查主体边界和动态裁切稳定性"}] if visual_adapter else [{"code": "REFRAME_APPROXIMATE", "message": "自动重构图使用本地模板跟踪；请检查 confidence 和裁切范围"}])
        return _envelope("media.reframe", args, status="planned", data={"report": str(report_path), "plan": plan, "adapter": visual_adapter, "adapter_verification": adapter_verification, "applied": False}, warnings=warnings)
    before_project = copy.deepcopy(project)
    before_snapshot = create_snapshot(root, before_project, label="before-reframe")
    clip["crop"] = copy.deepcopy(plan["crop"])
    _record_tracking_dependency(clip, visual_adapter)
    _record_mask_tracking_dependency(clip, tracking)
    for track in plan["keyframes"]:
        values = [(int(item["at_tick"]), float(item["value"]), str(item.get("interpolation", "linear"))) for item in track["keyframes"]]
        _set_keyframe_track(clip, str(track["property"]), values)
    _clamp_clip_keyframes(clip)
    validation = validate_project(root, project, strict_rights=False)
    if not validation["ok"]:
        raise AppError("REFRAME_APPLY_INVALID", "自动重构图应用后项目校验失败", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    operation_id = new_id("op")
    plan["applied_properties"] = [str(item["property"]) for item in plan["keyframes"]]
    atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), "applied": True, "operation_id": operation_id, "before_snapshot_id": before_snapshot["snapshot_id"], "plan": plan, "validation": validation})
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.reframe", "clip_id": args.clip_id, "track_id": args.track_id, "report": str(report_path), "before_snapshot_id": before_snapshot["snapshot_id"], "at": now_iso()})
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "media.reframe", "status": "succeeded", "clip_id": args.clip_id, "track_id": args.track_id, "object_id": args.object_id, "report": str(report_path), "before_snapshot_id": before_snapshot["snapshot_id"], "created_at": now_iso()})
    warnings = _mask_tracking_warnings() if mask_plan else ([{"code": "TRACKING_MULTI_OBJECT_REVIEW", "message": "多目标 runner 输出已通过协议校验，但仍需检查对象身份连续性、主体边界和动态裁切稳定性"}] if visual_adapter and visual_adapter.get("engine") in MULTI_OBJECT_TRACKING_ENGINES else [{"code": "TRACKING_EXTERNAL_REVIEW", "message": "本地视觉 runner 输出已通过协议校验，但仍需检查主体边界和动态裁切稳定性"}] if visual_adapter else [{"code": "REFRAME_APPROXIMATE", "message": "自动重构图使用本地模板跟踪；请检查 confidence、主体边界和裁切警告"}])
    return _envelope("media.reframe", args, data={"report": str(report_path), "plan": plan, "adapter": visual_adapter, "adapter_verification": adapter_verification, "before_snapshot": before_snapshot, "validation": validation}, warnings=warnings, operation_id=operation_id)


def command_asr_adapter(args: argparse.Namespace) -> dict[str, Any]:
    from .artifact_locks import verification_scope
    with verification_scope():
        return _command_asr_adapter_locked(args)


def _command_asr_adapter_locked(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    command = f"asr.adapter.{args.registration_action}"
    if args.registration_action in {"list", "inspect"}:
        values = asr_registry(project).get("adapters", []) if args.registration_action == "list" else [asr_registry_item(project, args.adapter_id)]
        checked = [{"adapter": item, "verification": verify_asr_adapter(item)} for item in values]
        data: dict[str, Any] = {"adapters": checked, "network": "disabled"}
        if args.registration_action == "inspect":
            data.update(checked[0])
        return _envelope(command, args, data=data)
    if any(item.get("adapter_id") == args.adapter_id for item in asr_registry(project).get("adapters", [])):
        raise AppError("ASR_REGISTRATION_EXISTS", "ASR 模型登记已存在，请使用新的 ID", exit_code=2)
    record, rights = prepare_asr_adapter(root, adapter_id=args.adapter_id, python_executable=args.python_executable, model_path=args.model_path, device=args.device, threads=args.threads, evidence=args.evidence, license_spdx=args.license_spdx, creator=args.creator, status=args.verification_status, uses=args.permitted_use or ["internal"], engine=args.engine)
    if args.dry_run:
        return _envelope(command, args, status="planned", data={"adapter": record, "rights": rights, "network": "disabled"})
    snapshot = create_snapshot(root, project, label="before-asr-adapter-register")
    registry = project.setdefault("extensions", {}).setdefault("local_asr", {"schema_version": "0.1.0", "adapters": []})
    registry["adapters"].append(record)
    registry["updated_at"] = now_iso()
    ledger, operation_id = load_ledger(root), new_id("op")
    add_record(ledger, rights)
    change = {"operation_id": operation_id, "command": command, "adapter_id": args.adapter_id, "sha256": record["sha256"], "snapshot_id": snapshot["snapshot_id"], "at": now_iso()}
    project.setdefault("provenance", {}).setdefault("change_log", []).append(change)
    save_project(root, project)
    save_ledger(root, ledger)
    _operation(root, operation_id, {**change, "status": "succeeded"})
    return _envelope(command, args, data={"adapter": record, "rights": rights, "snapshot": snapshot, "network": "disabled"}, operation_id=operation_id)


def _selected_asr_adapter(root: Path, project: dict[str, Any], args: argparse.Namespace) -> dict[str, Any] | None:
    if not args.adapter_id:
        return None
    if args.transcribe_engine != "transformers" or args.use_gpu:
        raise argument_error("登记模型的引擎与设备由登记项确定，不能混用 --transcribe-engine ffmpeg-whisper 或 --use-gpu", "adapter_id")
    adapter = asr_registry_item(project, args.adapter_id)
    if adapter.get('engine') != ASR_ENGINE:
        raise argument_error('CTC 模型用于 subtitle align，不能用作 Whisper 转写', 'adapter_id')
    verification = verify_asr_adapter(adapter)
    if not verification["ok"]:
        raise AppError("ASR_INTEGRITY_FAILED", "ASR 模型完整性核验失败", exit_code=10, cause=json.dumps(verification, ensure_ascii=False))
    record = next((item for item in active_records(load_ledger(root)) if item.get("asset_id") == adapter["rights_ref"]), None)
    if not record or record.get("sha256") != adapter["sha256"]:
        raise AppError("RIGHTS_RECORD_MISSING", "ASR 模型缺少匹配的权利记录", exit_code=7)
    return adapter


def command_subtitle_evaluate(args: argparse.Namespace) -> dict[str, Any]:
    root = load_project(args.project)[0] if args.project else Path.cwd().resolve()
    source = resolve_local_path(root, args.input, field="input")
    reference = resolve_local_path(root, args.reference, field="reference")
    if not source.is_file() or not reference.is_file():
        raise argument_error("转写和参考逐字稿必须为现有本地文件", "input/reference")
    if args.max_cer is not None and (not math.isfinite(args.max_cer) or args.max_cer < 0):
        raise argument_error("max-cer 必须为非负有限数", "max_cer")
    output = resolve_local_path(root, args.report, field="report") if args.report else (root / "validation" / f"asr_evaluation_{new_id('cer')}.json" if args.project else None)
    if output:
        if args.project:
            ensure_inside(root, output)
        if output.exists():
            raise argument_error("CER 报告已存在，请使用新路径", "report")
    if args.dry_run:
        return _envelope("subtitle.evaluate", args, status="planned", data={"input": str(source), "reference": str(reference), "report": str(output) if output else None})
    report = evaluate_transcripts(reference, source, normalization=args.normalization)
    report.update({"created_at": now_iso(), "max_cer": args.max_cer, "ok": args.max_cer is None or report["cer"] <= args.max_cer, "network": "disabled"})
    if output:
        atomic_write_json(output, report)
    if not report["ok"]:
        raise AppError("ASR_CER_THRESHOLD_EXCEEDED", "字符错误率超过指定门禁", exit_code=6, path=str(output) if output else None, cause=json.dumps({"cer": report["cer"], "max_cer": args.max_cer, "report": str(output) if output else None}, ensure_ascii=False))
    return _envelope("subtitle.evaluate", args, data={"report": str(output) if output else None, "result": report})


def _transcribe_with_local_engine(
    root: Path,
    source: Path,
    *,
    engine: str,
    model_path: str | Path | None,
    language: str | None,
    output_srt: Path,
    use_gpu: bool = False,
    adapter: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run one of the explicitly local ASR adapters and persist SRT evidence."""
    output_srt = ensure_inside(root, output_srt)
    if output_srt.exists():
        raise argument_error("字幕输出已存在，请使用新路径", "output")
    if adapter:
        transcription = transcribe_registered(root, source, adapter=adapter, language=language)
        write_srt(transcription, output_srt)
        transcription["srt"] = str(output_srt)
        return transcription
    if engine == "ffmpeg-whisper":
        return transcribe_local_ffmpeg_whisper(
            source,
            model_path=model_path,
            output_srt=output_srt,
            language=language,
            use_gpu=use_gpu,
        )
    transcription = transcribe_local(source, model_path=model_path, language=language)
    write_srt(transcription, output_srt)
    transcription["srt"] = str(output_srt)
    return transcription


def command_media_understand(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    if args.adapter_id and not args.transcribe:
        raise argument_error("ASR --adapter-id 必须与 --transcribe 一起使用", "adapter_id")
    adapter = _selected_asr_adapter(root, project, args)
    source: Path | None = None
    asset_id = args.asset_id
    if asset_id:
        asset = asset_map(project).get(asset_id)
        if not asset:
            raise argument_error(f"找不到资产: {asset_id}", "--asset-id")
        source = Path(str(asset["uri"]))
        if not source.is_absolute():
            source = root / source
    elif args.input:
        source = Path(args.input).expanduser().resolve()
    else:
        raise argument_error("必须提供 --asset-id 或 --input")
    assert source is not None
    if not source.exists():
        raise argument_error("分析输入不存在", str(source))
    if args.dry_run:
        return _envelope("media.understand", args, status="planned", data={"input": str(source), "scene_threshold": args.scene_threshold})
    analysis = understand_media(source, scene_threshold=args.scene_threshold, include_beats=args.beats)
    if args.transcribe:
        if adapter or args.transcribe_engine == "ffmpeg-whisper" or args.srt:
            srt_path = Path(args.srt).expanduser() if args.srt else root / "cache" / f"understand_{new_id('asr')}.srt"
            if not srt_path.is_absolute():
                srt_path = root / srt_path
            srt_path = srt_path.resolve()
            ensure_inside(root, srt_path)
            analysis["transcription"] = _transcribe_with_local_engine(
                root,
                source,
                engine=args.transcribe_engine,
                model_path=args.model_path,
                language=args.language,
                output_srt=srt_path,
                use_gpu=bool(args.use_gpu),
                **({"adapter": adapter} if adapter else {}),
            )
            if not args.srt:
                srt_path.unlink(missing_ok=True)
                analysis["transcription"].pop("srt", None)
        else:
            analysis["transcription"] = transcribe_local(source, model_path=args.model_path, language=args.language)
    analysis["source_sha256"] = f"sha256:{sha256_file(source)}"
    analysis["asset_id"] = asset_id
    path = root / "validation" / f"understand_{asset_id or new_id('asset')}.json"
    atomic_write_json(path, analysis)
    return _envelope("media.understand", args, data={"analysis": str(path), "result": analysis})


def command_media_contact_sheet(args: argparse.Namespace) -> dict[str, Any]:
    from .contact_sheet import plan_contact_sheet, execute_contact_sheet, number
    from .policy import resolve_local_path
    root, project = load_project(args.project)
    asset = asset_map(project).get(args.asset_id) if args.asset_id else None
    if args.asset_id and asset is None:
        raise argument_error('找不到联系表资产', '--asset-id')
    source = resolve_local_path(root, asset['uri'] if asset else args.input, field='input')
    output = resolve_local_path(root, args.output, field='output'); ensure_inside(root, output)
    if output == root or output.exists():
        raise argument_error('联系表输出必须为项目内新目录', '--output')
    if not .1 <= number(args.timeout, 'timeout') <= 3600:
        raise argument_error('联系表 timeout 为 0.1..3600 秒', '--timeout')
    if any(parent.exists() and not parent.is_dir() for parent in output.parents):
        raise argument_error('联系表父路径包含文件', '--output')
    cancel = resolve_local_path(root, args.cancel_file, field='cancel_file') if args.cancel_file else None
    if cancel is not None:
        ensure_inside(root, cancel)
        if cancel.is_relative_to(output):
            raise argument_error('取消标记不能位于联系表输出中', '--cancel-file')
    plan = plan_contact_sheet(source, times=args.at_seconds, count=args.count,
        start=args.start_seconds, end=args.end_seconds, width=args.width, height=args.height,
        columns=args.columns, views=args.view, cancel_file=cancel)
    if args.dry_run:
        return _envelope('media.contact-sheet', args, status='planned', data={'output':str(output), 'plan':plan})
    operation_id = new_id('contact')
    result = execute_contact_sheet(plan, output, timeout=args.timeout, cancel_file=cancel)
    data = {'asset_id':args.asset_id, 'output':str(output), 'contact':str(output/'contact.png'),
            'manifest':str(output/'manifest.json'), 'frames':len(result['frames']),
            'manifest_sha256':'sha256:'+sha256_file(output/'manifest.json'), 'quality_accepted':False}
    try:
        _operation(root, operation_id, {'operation_id':operation_id, 'command':'media.contact-sheet',
            'status':'succeeded', 'artifacts':data, 'source_sha256':plan['source']['sha256'], 'created_at':now_iso()})
    except BaseException:
        shutil.rmtree(output)
        raise
    return _envelope('media.contact-sheet', args, data=data, operation_id=operation_id)


def command_media_prepare(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    asset_id = args.asset_id
    source: Path | None = None
    asset: dict[str, Any] | None = None
    if asset_id:
        asset = asset_map(project).get(asset_id)
        if not asset:
            raise argument_error(f"找不到资产: {asset_id}", "--asset-id")
        source = Path(str(asset["uri"]))
        if not source.is_absolute():
            source = root / source
    elif args.input:
        source = Path(args.input).expanduser().resolve()
    else:
        raise argument_error("必须提供 --asset-id 或 --input")
    assert source is not None
    if not source.exists() or not source.is_file():
        raise argument_error("准备输入不存在", str(source))
    if asset is None:
        asset = {"id": source.stem, "kind": classify_path(source), "uri": str(source)}
    kind = str(asset.get("kind", classify_path(source)))
    proxy_width = int(args.proxy_width or 0)
    make_thumbnail = bool(args.thumbnail)
    make_waveform = bool(args.waveform)
    if not proxy_width and not make_thumbnail and not make_waveform:
        proxy_width = 720 if kind == "video" else 0
        make_thumbnail = kind in {"video", "image"}
        make_waveform = kind in {"video", "audio"}
    if args.dry_run:
        return _envelope("media.prepare", args, status="planned", data={"asset_id": asset_id, "input": str(source), "proxy_width": proxy_width, "thumbnail": make_thumbnail, "waveform": make_waveform})
    artifacts: dict[str, Any] = {"asset_id": asset_id, "input": str(source)}
    if proxy_width:
        proxy_path = root / "cache" / "proxies" / f"{asset.get('id', source.stem)}_{proxy_width}.mp4"
        generate_proxy(source, proxy_path, width=proxy_width)
        artifacts["proxy"] = str(proxy_path)
        if asset_id:
            asset["proxy"] = {"uri": str(proxy_path.relative_to(root)).replace("\\", "/"), "width": proxy_width, "sha256": f"sha256:{sha256_file(proxy_path)}"}
    if make_thumbnail:
        thumbnail_path = root / "cache" / "thumbnails" / f"{asset.get('id', source.stem)}.jpg"
        generate_thumbnail(source, thumbnail_path, at_seconds=args.at_seconds)
        artifacts["thumbnail"] = str(thumbnail_path)
        if asset_id:
            asset["thumbnail"] = {"uri": str(thumbnail_path.relative_to(root)).replace("\\", "/"), "sha256": f"sha256:{sha256_file(thumbnail_path)}", "at_seconds": max(0.0, args.at_seconds)}
    if make_waveform:
        waveform_path = root / "cache" / "waveforms" / f"{asset.get('id', source.stem)}.png"
        generate_waveform(source, waveform_path)
        artifacts["waveform"] = str(waveform_path)
        if asset_id:
            asset["waveform"] = {"uri": str(waveform_path.relative_to(root)).replace("\\", "/"), "sha256": f"sha256:{sha256_file(waveform_path)}"}
    operation_id = new_id("op")
    if asset_id:
        project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.prepare", "asset_id": asset_id, "artifacts": artifacts, "at": now_iso()})
        save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "media.prepare", "status": "succeeded", "artifacts": artifacts, "created_at": now_iso()})
    return _envelope("media.prepare", args, data=artifacts, operation_id=operation_id)


def command_media_highlights(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    asset_id = args.asset_id
    if asset_id:
        asset = asset_map(project).get(asset_id)
        if not asset:
            raise argument_error(f"找不到资产: {asset_id}", "--asset-id")
        source = Path(str(asset["uri"]))
        if not source.is_absolute():
            source = root / source
    elif args.input:
        source = Path(args.input).expanduser().resolve()
    else:
        raise argument_error("必须提供 --asset-id 或 --input")
    if not source.exists() or not source.is_file():
        raise argument_error("高光分析输入不存在", str(source))

    sequence = None
    target_track = None
    if args.apply:
        if not asset_id:
            raise argument_error("--apply 必须提供项目内 --asset-id，不能把未登记输入直接写入时间线", "asset_id")
        if not args.track_id:
            raise argument_error("--apply 必须提供 --track-id", "track_id")
        if args.timeline_start_seconds < 0:
            raise argument_error("timeline_start_seconds 不能为负数", "timeline_start_seconds")
        sequence = find_sequence(project, args.sequence_id)
        target_track = find_track(sequence, args.track_id, None)
        if str(target_track.get("kind", "video")) != "video":
            raise argument_error("高光粗剪应用目标必须是 video 轨道", "track_id")
        if target_track.get("locked"):
            raise AppError("TRACK_LOCKED", "高光粗剪目标轨道已锁定", exit_code=2, path="track_id")

    if args.dry_run:
        return _envelope(
            "media.highlights",
            args,
            status="planned",
            data={
                "input": str(source),
                "asset_id": asset_id,
                "top_k": args.top_k,
                "min_duration": args.min_duration,
                "max_duration": args.max_duration,
                "beats": bool(args.beats),
                "apply": bool(args.apply),
                "replace_track": bool(args.replace_track),
                "sequence_id": sequence.get("id") if sequence else args.sequence_id,
                "track_id": target_track.get("id") if target_track else args.track_id,
                "timeline_start_seconds": args.timeline_start_seconds,
                "engine": "ffmpeg-local-highlight-heuristic-v1",
            },
        )

    analysis = understand_media(source, include_beats=args.beats)
    recommendation = recommend_highlights(analysis, top_k=args.top_k, min_duration=args.min_duration, max_duration=args.max_duration)
    recommendation.update({
        "asset_id": asset_id,
        "source": str(source),
        "source_sha256": f"sha256:{sha256_file(source)}",
        "analysis": analysis,
        "pipeline_engine": "ffmpeg-local-highlight-heuristic-v1",
        "apply": bool(args.apply),
        "replace_track": bool(args.replace_track),
        "network": "disabled",
    })
    output: Path
    if args.output:
        output = Path(args.output).expanduser().resolve()
        try:
            output.relative_to(root)
        except ValueError as exc:
            raise argument_error("高光报告必须位于项目目录内", str(output)) from exc
    else:
        output = root / "validation" / f"highlights_{asset_id or new_id('asset')}.json"

    warnings = [{
        "code": "HIGHLIGHTS_HEURISTIC",
        "message": "高光排序只使用本地镜头、静音和可选节拍证据；不等同语义理解或剪映智能导演。",
    }]
    if not args.apply:
        atomic_write_json(output, recommendation)
        return _envelope("media.highlights", args, data={"report": str(output), "recommendation": recommendation}, warnings=warnings)

    assert sequence is not None and target_track is not None
    timeline_tps = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", TICKS_PER_SECOND))
    timeline_cursor = int(round(float(args.timeline_start_seconds) * timeline_tps))
    run_id = new_id("highlights")
    selected = sorted(
        [item for item in recommendation.get("candidates", []) if isinstance(item, dict)],
        key=lambda item: (float(item.get("start_seconds", 0.0)), str(item.get("id", ""))),
    )
    generated_plan: list[dict[str, Any]] = []
    for index, item in enumerate(selected, start=1):
        try:
            source_in = max(0, int(round(float(item["start_seconds"]) * timeline_tps)))
            source_out = max(source_in + 1, int(round(float(item["end_seconds"]) * timeline_tps)))
        except (KeyError, TypeError, ValueError) as exc:
            raise AppError("HIGHLIGHTS_PLAN_INVALID", "高光候选缺少合法的源时间范围", exit_code=6, path="candidates") from exc
        duration_tick = source_out - source_in
        generated_plan.append({
            "id": f"{run_id}_{index:03d}",
            "asset_id": str(asset_id),
            "timeline_start_tick": timeline_cursor,
            "duration_tick": duration_tick,
            "source_in_tick": source_in,
            "source_out_tick": source_out,
            "source_start_seconds": round(source_in / timeline_tps, 6),
            "source_end_seconds": round(source_out / timeline_tps, 6),
            "score": item.get("score"),
            "candidate_id": item.get("id"),
        })
        timeline_cursor += duration_tick
    if not generated_plan:
        raise AppError("HIGHLIGHTS_EMPTY", "本地高光分析没有生成可应用的候选片段", exit_code=6, path="candidates")

    recommendation.update({
        "project_id": project.get("project", {}).get("id"),
        "sequence_id": sequence.get("id"),
        "track_id": target_track.get("id"),
        "timeline_start_seconds": round(float(args.timeline_start_seconds), 6),
        "generated_plan": generated_plan,
    })
    existing_clips = list(target_track.get("clips", []))
    if not args.replace_track:
        for generated in generated_plan:
            generated_start = int(generated["timeline_start_tick"])
            generated_end = generated_start + int(generated["duration_tick"])
            for existing in existing_clips:
                existing_start = int(existing.get("timeline_start_tick", 0))
                existing_end = existing_start + int(existing.get("duration_tick", 0))
                if max(generated_start, existing_start) < min(generated_end, existing_end):
                    raise AppError("HIGHLIGHTS_TRACK_OVERLAP", "高光粗剪会覆盖目标轨道已有片段，请使用 --replace-track 或调整时间线起点", exit_code=2, path="track_id")
    before_project = copy.deepcopy(project)
    if args.replace_track:
        target_track["clips"] = []
    generated_clips: list[dict[str, Any]] = []
    for item in generated_plan:
        clip = {key: item[key] for key in ("id", "asset_id", "timeline_start_tick", "duration_tick", "source_in_tick", "source_out_tick")}
        target_track.setdefault("clips", []).append(clip)
        generated_clips.append(clip)
    _recompute_sequence_duration(sequence)
    validation = validate_project(root, project, strict_rights=False)
    if not validation["ok"]:
        raise AppError("HIGHLIGHTS_APPLY_INVALID", "高光粗剪应用后项目校验失败", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    snapshot = create_snapshot(root, before_project, label="before-highlights")
    operation_id = new_id("op")
    recommendation["generated_clips"] = generated_clips
    report_payload = {
        "report_version": "0.2.0",
        "created_at": now_iso(),
        "applied": True,
        "operation_id": operation_id,
        "before_snapshot_id": snapshot["snapshot_id"],
        "recommendation": recommendation,
        "validation": validation,
    }
    atomic_write_json(output, report_payload)
    project.setdefault("provenance", {}).setdefault("change_log", []).append({
        "operation_id": operation_id,
        "command": "media.highlights",
        "asset_id": asset_id,
        "sequence_id": sequence.get("id"),
        "track_id": target_track.get("id"),
        "clip_ids": [clip["id"] for clip in generated_clips],
        "report": str(output),
        "before_snapshot_id": snapshot["snapshot_id"],
        "at": now_iso(),
    })
    save_project(root, project)
    _operation(root, operation_id, {
        "operation_id": operation_id,
        "command": "media.highlights",
        "status": "succeeded",
        "asset_id": asset_id,
        "sequence_id": sequence.get("id"),
        "track_id": target_track.get("id"),
        "clip_ids": [clip["id"] for clip in generated_clips],
        "report": str(output),
        "before_snapshot_id": snapshot["snapshot_id"],
        "created_at": now_iso(),
    })
    warnings.append({"code": "HIGHLIGHTS_REVIEW_REQUIRED", "message": "高光候选已写入时间线；发布前必须检查镜头语义、连续性、音画同步和转场。"})
    return _envelope(
        "media.highlights",
        args,
        data={"report": str(output), "recommendation": recommendation, "generated_clips": generated_clips, "before_snapshot": snapshot, "validation": validation},
        warnings=warnings,
        operation_id=operation_id,
    )

def command_media_beat_cut(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    sequence = find_sequence(project, getattr(args, "sequence_id", None))
    target_track = find_track(sequence, args.track_id, None)
    if str(target_track.get("kind")) != "video":
        raise argument_error("按节拍剪辑目标轨道必须是 video 轨道", "track_id")
    if args.timeline_start_seconds < 0:
        raise argument_error("timeline_start_seconds 不能为负数", "timeline_start_seconds")
    assets = asset_map(project)
    source_assets: list[dict[str, Any]] = []
    for asset_id in args.source_asset_id:
        asset = assets.get(str(asset_id))
        if not asset:
            raise argument_error(f"找不到源视频资产: {asset_id}", "source_asset_id")
        if str(asset.get("kind", "")).lower() != "video":
            raise argument_error(f"按节拍剪辑源素材必须是 video 资产: {asset_id}", "source_asset_id")
        source_assets.append(asset)

    audio_asset_id = args.audio_asset_id
    if audio_asset_id:
        audio_asset = assets.get(str(audio_asset_id))
        if not audio_asset:
            raise argument_error(f"找不到节拍分析资产: {audio_asset_id}", "audio_asset_id")
        source = Path(str(audio_asset.get("uri", "")))
        if not source.is_absolute():
            source = root / source
    else:
        raw_input = str(args.input or "").strip()
        if raw_input.lower().startswith(("http://", "https://")):
            raise argument_error("--input 只接受本地音频或视频文件", "input")
        source = Path(raw_input).expanduser().resolve()
        audio_asset = None
    if not source.exists() or not source.is_file():
        raise argument_error("节拍分析输入不存在", str(source))

    timeline_tps = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", 90_000))
    run_id = new_id("beatcut")
    report_path = Path(args.output).expanduser().resolve() if args.output else root / "validation" / f"beat_cut_{safe_filename(run_id)}.json"
    ensure_inside(root, report_path)
    if args.dry_run:
        return _envelope(
            "media.beat-cut",
            args,
            status="planned",
            data={
                "input": str(source),
                "audio_asset_id": audio_asset_id,
                "source_asset_ids": [str(asset["id"]) for asset in source_assets],
                "sequence_id": sequence.get("id"),
                "track_id": target_track.get("id"),
                "parameters": {
                    "start_seconds": args.start_seconds,
                    "end_seconds": args.end_seconds,
                    "timeline_start_seconds": args.timeline_start_seconds,
                    "min_segment_seconds": args.min_segment_seconds,
                    "max_clips": args.max_clips,
                    "source_mode": args.source_mode,
                    "apply": bool(args.apply),
                    "replace_track": bool(args.replace_track),
                },
                "engine": "ffmpeg-local-energy-beat-v1",
            },
        )

    probe = probe_media(source)
    beat_anchors = detect_beats(source)
    analysis = {
        "analysis_version": "0.1.0",
        "source": str(source),
        "source_sha256": f"sha256:{sha256_file(source)}",
        "probe": probe,
        "beat_anchors": beat_anchors,
        "network": "disabled",
    }
    plan = build_beat_cut_plan(
        analysis,
        source_assets,
        ticks_per_second=timeline_tps,
        start_seconds=args.start_seconds,
        end_seconds=args.end_seconds,
        min_segment_seconds=args.min_segment_seconds,
        max_clips=args.max_clips,
        source_mode=args.source_mode,
    )
    timeline_offset = int(round(float(args.timeline_start_seconds) * timeline_tps))
    for clip in plan["clips"]:
        clip["id"] = f"{run_id}_{int(clip['index']):03d}"
        clip["timeline_start_tick"] = int(clip["timeline_start_tick"]) + timeline_offset
    plan.update(
        {
            "project_id": project.get("project", {}).get("id"),
            "sequence_id": sequence.get("id"),
            "track_id": target_track.get("id"),
            "audio_asset_id": audio_asset_id,
            "source": str(source),
            "source_sha256": analysis["source_sha256"],
            "timeline_start_seconds": round(float(args.timeline_start_seconds), 6),
            "replace_track": bool(args.replace_track),
        }
    )
    if not args.apply:
        atomic_write_json(report_path, {"report_version": BEAT_CUT_VERSION, "created_at": now_iso(), "applied": False, "plan": plan})
        return _envelope("media.beat-cut", args, status="planned", data={"report": str(report_path), "plan": plan, "applied": False}, warnings=plan.get("warnings"))

    existing_clips = list(target_track.get("clips", []))
    if not args.replace_track:
        for generated in plan["clips"]:
            generated_start = int(generated["timeline_start_tick"])
            generated_end = generated_start + int(generated["duration_tick"])
            for existing in existing_clips:
                existing_start = int(existing.get("timeline_start_tick", 0))
                existing_end = existing_start + int(existing.get("duration_tick", 0))
                if max(generated_start, existing_start) < min(generated_end, existing_end):
                    raise AppError("BEAT_CUT_TRACK_OVERLAP", "按节拍剪辑会覆盖目标轨道已有片段，请使用 --replace-track 或调整时间线起点", exit_code=2, path="track_id")
    before_project = copy.deepcopy(project)
    if args.replace_track:
        target_track["clips"] = []
    generated_clips: list[dict[str, Any]] = []
    for item in plan["clips"]:
        clip = {
            "id": item["id"],
            "asset_id": item["asset_id"],
            "timeline_start_tick": int(item["timeline_start_tick"]),
            "duration_tick": int(item["duration_tick"]),
            "source_in_tick": int(item["source_in_tick"]),
            "source_out_tick": int(item["source_out_tick"]),
        }
        if float(item.get("speed", 1.0)) != 1.0:
            clip["speed"] = float(item["speed"])
        target_track.setdefault("clips", []).append(clip)
        generated_clips.append(clip)
    _recompute_sequence_duration(sequence)
    validation = validate_project(root, project, strict_rights=False)
    if not validation["ok"]:
        raise AppError("BEAT_CUT_APPLY_INVALID", "按节拍剪辑应用后项目校验失败", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    snapshot = create_snapshot(root, before_project, label="before-beat-cut")
    operation_id = new_id("op")
    plan["generated_clips"] = generated_clips
    payload = {
        "report_version": BEAT_CUT_VERSION,
        "created_at": now_iso(),
        "applied": True,
        "operation_id": operation_id,
        "before_snapshot_id": snapshot["snapshot_id"],
        "plan": plan,
        "validation": validation,
    }
    atomic_write_json(report_path, payload)
    project.setdefault("provenance", {}).setdefault("change_log", []).append(
        {
            "operation_id": operation_id,
            "command": "media.beat-cut",
            "at": now_iso(),
            "report": str(report_path),
            "before_snapshot_id": snapshot["snapshot_id"],
            "sequence_id": sequence.get("id"),
            "track_id": target_track.get("id"),
            "clip_ids": [clip["id"] for clip in generated_clips],
        }
    )
    save_project(root, project)
    _operation(
        root,
        operation_id,
        {
            "operation_id": operation_id,
            "command": "media.beat-cut",
            "status": "succeeded",
            "report": str(report_path),
            "before_snapshot_id": snapshot["snapshot_id"],
            "clip_ids": [clip["id"] for clip in generated_clips],
            "created_at": now_iso(),
        },
    )
    return _envelope(
        "media.beat-cut",
        args,
        data={"report": str(report_path), "plan": plan, "generated_clips": generated_clips, "before_snapshot": snapshot, "validation": validation},
        warnings=plan.get("warnings"),
        operation_id=operation_id,
    )


def command_media_multicam(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    sequence = find_sequence(project, getattr(args, "sequence_id", None))
    if args.timeline_start_seconds < 0:
        raise argument_error("timeline_start_seconds 不能为负数", "timeline_start_seconds")
    if args.apply and not args.track_id:
        raise argument_error("--apply 必须提供 --track-id", "track_id")
    if args.apply:
        target_track = find_track(sequence, args.track_id, None)
        if str(target_track.get("kind")) != "video":
            raise argument_error("多机位切换目标轨道必须是 video 轨道", "track_id")
        if target_track.get("locked", False):
            raise AppError("TRACK_LOCKED", "多机位切换目标轨道已锁定", exit_code=2, path="track_id")
    assets = asset_map(project)
    sources: list[dict[str, Any]] = []
    for asset_id in args.source_asset_id:
        asset = assets.get(str(asset_id))
        if not asset:
            raise argument_error(f"找不到多机位源素材: {asset_id}", "source_asset_id")
        if str(asset.get("kind", "")).lower() != "video":
            raise argument_error(f"多机位源素材必须是 video 资产: {asset_id}", "source_asset_id")
        source = Path(str(asset.get("uri", "")))
        if not source.is_absolute():
            source = root / source
        sources.append({"asset_id": str(asset_id), "path": source.resolve()})
    switch_plan_payload: list[dict[str, Any]] | None = None
    if args.switch_plan:
        switch_path = Path(args.switch_plan).expanduser().resolve()
        ensure_inside(root, switch_path)
        try:
            with switch_path.open('r', encoding='utf-8-sig') as stream:
                raw = json.load(stream)
        except FileNotFoundError as exc:
            raise AppError('FILE_NOT_FOUND', f'文件不存在: {switch_path}', exit_code=3, path=str(switch_path)) from exc
        except (json.JSONDecodeError, UnicodeError) as exc:
            raise AppError('JSON_INVALID', f'JSON 无法解析: {switch_path}: {exc}', exit_code=2, path=str(switch_path)) from exc
        if isinstance(raw, dict):
            raw = raw.get("segments")
        if not isinstance(raw, list):
            raise argument_error("--switch-plan 必须是数组或包含 segments 数组的 JSON", "switch_plan")
        switch_plan_payload = raw
    if args.switch_seconds is not None and switch_plan_payload is not None:
        raise argument_error("--switch-seconds 与 --switch-plan 只能提供一个", "switch_plan")
    run_id = new_id("multicam")
    report_path = Path(args.output).expanduser().resolve() if args.output else root / "validation" / f"multicam_{safe_filename(run_id)}.json"
    ensure_inside(root, report_path)
    sync = synchronize_multicam_sources(
        sources,
        reference_asset_id=args.reference_asset_id,
        sample_rate=args.sample_rate,
        analysis_seconds=args.analysis_seconds,
        max_offset_seconds=args.max_offset_seconds,
        clock_model=getattr(args, "clock_model", "offset"),
        max_drift_ppm=getattr(args, "max_drift_ppm", 5000.0),
        drift_window_seconds=getattr(args, "drift_window_seconds", 12.0),
        drift_anchors=getattr(args, "drift_anchors", 9),
        project_root=root,
    )
    segments, switch_warnings = build_switch_segments(
        sync,
        switch_seconds=args.switch_seconds,
        switch_plan=switch_plan_payload,
        start_seconds=args.start_seconds,
        end_seconds=args.end_seconds,
        timeline_start_seconds=args.timeline_start_seconds,
        source_shortfall=args.source_shortfall,
        allow_clock_extrapolation=getattr(args, "allow_clock_extrapolation", False),
    )
    tps = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", TICKS_PER_SECOND))
    for index, item in enumerate(segments):
        item["id"] = new_multicam_clip_id(index)
        item["timeline_start_tick"] = int(round(float(item["timeline_start_seconds"]) * tps))
        item["duration_tick"] = int(round(float(item["duration_seconds"]) * tps))
        item["source_in_tick"] = max(0, int(round(float(item["source_in_seconds"]) * tps)))
        item["source_out_tick"] = int(round(float(item["source_out_seconds"]) * tps))
        if item["duration_tick"] <= 0 or item["source_out_tick"] <= item["source_in_tick"]:
            raise AppError("MULTICAM_SEGMENT_TOO_SHORT", "多机位切换段小于项目时间基精度", exit_code=2, path=f"switch_plan[{index}]")
    reference = next(row for row in sync["offsets"] if row["asset_id"] == sync["reference_asset_id"])
    window_end = float(args.end_seconds) if args.end_seconds is not None else float(reference["evidence"]["duration_seconds"])
    output_end = float(args.timeline_start_seconds) + window_end - float(args.start_seconds)
    plan = {
        "multicam_version": MULTICAM_SYNC_VERSION,
        "project_id": project.get("project", {}).get("id"),
        "sequence_id": sequence.get("id"),
        "track_id": args.track_id,
        "run_id": run_id,
        "sync": sync,
        "parameters": {
            "start_seconds": round(float(args.start_seconds), 6),
            "end_seconds": args.end_seconds,
            "timeline_start_seconds": round(float(args.timeline_start_seconds), 6),
            "source_shortfall": args.source_shortfall,
            "allow_clock_extrapolation": bool(getattr(args, "allow_clock_extrapolation", False)),
            "output_window_end_seconds": round(output_end, 6),
            "switch_seconds": args.switch_seconds,
            "switch_plan": str(args.switch_plan) if args.switch_plan else None,
            "apply": bool(args.apply),
            "replace_track": bool(args.replace_track),
        },
        "segments": segments,
        "warnings": [*sync.get("warnings", []), *switch_warnings],
        "changed": bool(segments),
    }
    warnings = plan["warnings"]
    if args.dry_run:
        return _envelope(
            "media.multicam",
            args,
            status="planned",
            data={"report": None, "plan": plan, "applied": False},
            warnings=warnings,
        )
    if not args.apply:
        atomic_write_json(report_path, {"report_version": MULTICAM_SYNC_VERSION, "created_at": now_iso(), "applied": False, "plan": plan})
        return _envelope("media.multicam", args, status="planned", data={"report": str(report_path), "plan": plan, "applied": False}, warnings=warnings)
    if not segments:
        raise AppError("MULTICAM_SWITCH_PLAN_REQUIRED", "--apply 需要 switch_seconds 或非空 switch_plan", exit_code=2, path="switch_plan")
    existing_clips = list(target_track.get("clips", []))
    if not args.replace_track:
        for generated in segments:
            generated_start = int(generated["timeline_start_tick"])
            generated_end = generated_start + int(generated["duration_tick"])
            for existing in existing_clips:
                existing_start = int(existing.get("timeline_start_tick", 0))
                existing_end = existing_start + int(existing.get("duration_tick", 0))
                if max(generated_start, existing_start) < min(generated_end, existing_end):
                    raise AppError("MULTICAM_TRACK_OVERLAP", "多机位切换会覆盖目标轨道已有片段，请使用 --replace-track 或调整时间线起点", exit_code=2, path="track_id")
    before_project = copy.deepcopy(project)
    if args.replace_track:
        target_track["clips"] = []
    generated_clips: list[dict[str, Any]] = []
    for item in segments:
        clip = {
            "id": item["id"],
            "asset_id": item["camera_asset_id"],
            "timeline_start_tick": int(item["timeline_start_tick"]),
            "duration_tick": int(item["duration_tick"]),
            "source_in_tick": int(item["source_in_tick"]),
            "source_out_tick": int(item["source_out_tick"]),
        }
        if float(item.get("speed", 1.0)) != 1.0:
            clip["speed"] = float(item["speed"])
        target_track.setdefault("clips", []).append(clip)
        generated_clips.append(clip)
    authored_duration = int(sequence.get("duration_tick", 1))
    _recompute_sequence_duration(sequence)
    sequence["duration_tick"] = max(sequence["duration_tick"], authored_duration, int(round(output_end * tps)))
    validation = validate_project(root, project, strict_rights=False)
    if not validation["ok"]:
        raise AppError("MULTICAM_APPLY_INVALID", "多机位切换应用后项目校验失败", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    snapshot = create_snapshot(root, before_project, label="before-multicam")
    operation_id = new_id("op")
    plan["generated_clips"] = generated_clips
    payload = {"report_version": MULTICAM_SYNC_VERSION, "created_at": now_iso(), "applied": True, "operation_id": operation_id, "before_snapshot_id": snapshot["snapshot_id"], "plan": plan, "validation": validation}
    atomic_write_json(report_path, payload)
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.multicam", "at": now_iso(), "report": str(report_path), "before_snapshot_id": snapshot["snapshot_id"], "sequence_id": sequence.get("id"), "track_id": target_track.get("id"), "clip_ids": [clip["id"] for clip in generated_clips]})
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "media.multicam", "status": "succeeded", "report": str(report_path), "before_snapshot_id": snapshot["snapshot_id"], "clip_ids": [clip["id"] for clip in generated_clips], "created_at": now_iso()})
    return _envelope("media.multicam", args, data={"report": str(report_path), "plan": plan, "generated_clips": generated_clips, "before_snapshot": snapshot, "validation": validation}, warnings=warnings, operation_id=operation_id)


def command_media_smart_cut(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    sequence = find_sequence(project, getattr(args, "sequence_id", None))
    target_track, clip = _find_clip(sequence, args.clip_id, args.track_id)
    if clip.get('presentation_window') is not None:
        raise AppError('SMART_CUT_PRESENTATION_WINDOW_UNSUPPORTED','源分析尚未映射到输出窗口；请分析完整作者片段后再裁切',exit_code=2,path='clip.presentation_window')
    asset = asset_map(project).get(str(clip.get("asset_id")))
    if not asset:
        raise argument_error("智能剪口播目标必须引用项目内媒体资产", "clip_id")
    source = Path(str(asset.get("uri", "")))
    if not source.is_absolute():
        source = root / source
    if not source.exists() or not source.is_file():
        raise argument_error("智能剪口播输入素材不存在", str(source))
    if str(clip.get("sequence_id", "")):
        raise argument_error("智能剪口播当前只支持直接媒体片段", "clip_id")
    analysis = understand_media(source, silence_db=args.silence_db)
    analysis["source_sha256"] = f"sha256:{sha256_file(source)}"
    duration_seconds = int(clip.get("duration_tick", 0)) / max(1, int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", 90000)))
    semantic_evidence: dict[str, Any] = {"phrases": [], "ranges": [], "matches": [], "unmatched_phrases": []}
    semantic_ranges: list[tuple[float, float]] = []
    transcript_path: Path | None = None
    if args.transcript and not args.remove_phrase:
        raise argument_error("--transcript 需要至少一个 --remove-phrase 才会参与语义裁切", "transcript")
    if args.remove_phrase:
        if not args.transcript:
            raise argument_error("使用 --remove-phrase 时必须提供项目内 --transcript", "transcript")
        transcript_path = Path(args.transcript).expanduser().resolve()
        ensure_inside(root, transcript_path)
        try:
            transcript_cues = parse_caption_file(transcript_path)
        except AppError as exc:
            raise AppError("SMART_CUT_TRANSCRIPT_INVALID", "本地字幕无法用于语义剪口播", exit_code=2, path=str(transcript_path), cause=str(exc)) from exc
        transcript_validation = validate_cues(transcript_cues, duration=duration_seconds)
        if not transcript_validation["ok"]:
            raise AppError("SMART_CUT_TRANSCRIPT_INVALID", "本地字幕时间轴不在目标片段范围内或存在重叠", exit_code=2, path=str(transcript_path), cause=json.dumps(transcript_validation, ensure_ascii=False))
        semantic_evidence = match_transcript_phrases(transcript_cues, [str(value) for value in args.remove_phrase], duration_seconds=duration_seconds)
        semantic_evidence["path"] = str(transcript_path)
        semantic_evidence["sha256"] = f"sha256:{sha256_file(transcript_path)}"
        semantic_evidence["validation"] = transcript_validation
        semantic_ranges = [
            (float(item["start_seconds"]), float(item["end_seconds"]))
            for item in semantic_evidence.get("ranges", [])
            if isinstance(item, dict)
        ]
    plan = build_smart_cut_plan(
        analysis,
        duration_seconds=duration_seconds,
        min_silence_seconds=args.min_silence_seconds,
        keep_padding_seconds=args.keep_padding_seconds,
        min_segment_seconds=args.min_segment_seconds,
        semantic_ranges=semantic_ranges,
        semantic_evidence=semantic_evidence,
    )
    linked_track_ids = [str(value) for value in args.linked_track_id]
    linked_clip_ids = [str(value) for value in args.linked_clip_id]
    if linked_clip_ids and len(linked_clip_ids) not in {1, len(linked_track_ids)}:
        raise argument_error("--linked-clip-id 必须提供一个值或与 --linked-track-id 数量相同", "linked_clip_id")
    linked_pairs = [
        {"track_id": track_id, "clip_id": linked_clip_ids[0] if len(linked_clip_ids) == 1 else linked_clip_ids[index] if linked_clip_ids else str(args.clip_id)}
        for index, track_id in enumerate(linked_track_ids)
    ]
    plan.update({
        "project_id": project.get("project", {}).get("id"),
        "sequence_id": sequence.get("id"),
        "asset_id": asset.get("id"),
        "clip_id": clip.get("id"),
        "track_id": target_track.get("id"),
        "linked_track_ids": linked_track_ids,
        "linked_clips": linked_pairs,
        "source": str(source),
        "source_sha256": analysis["source_sha256"],
        "transcript": semantic_evidence,
    })
    if args.dry_run:
        return _envelope("media.smart-cut", args, status="planned", data={"plan": plan, "apply": bool(args.apply)}, warnings=plan.get("warnings"))
    output = Path(args.output).expanduser().resolve() if args.output else root / "validation" / f"smart_cut_{safe_filename(str(args.clip_id))}.json"
    ensure_inside(root, output)
    if not args.apply or not plan.get("changed"):
        payload = {"report_version": SMART_CUT_VERSION, "created_at": now_iso(), "plan": plan, "applied": False}
        atomic_write_json(output, payload)
        return _envelope("media.smart-cut", args, status="planned", data={"report": str(output), "plan": plan, "applied": False}, warnings=plan.get("warnings"))
    before_project = copy.deepcopy(project)
    ticks_per_second = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", 90000))
    targets = [(str(args.track_id), str(args.clip_id)), *[(item["track_id"], item["clip_id"]) for item in linked_pairs if item["track_id"] != str(args.track_id)]]
    replacements: list[dict[str, Any]] = []
    try:
        for track_id, clip_id in targets:
            track = find_track(sequence, track_id, None)
            pieces = replace_clip_with_smart_cut(track, clip_id, plan, ticks_per_second=ticks_per_second)
            replacements.append({"track_id": track_id, "clip_id": clip_id, "piece_ids": [item["id"] for item in pieces], "duration_tick": sum(int(item["duration_tick"]) for item in pieces)})
    except AppError:
        raise
    _recompute_sequence_duration(sequence)
    validation = validate_project(root, project, strict_rights=False)
    if not validation["ok"]:
        raise AppError("PROJECT_INVALID", "智能剪口播生成的项目未通过校验", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    snapshot = create_snapshot(root, before_project, label="before-smart-cut")
    operation_id = new_id("op")
    plan["replacements"] = replacements
    payload = {"report_version": SMART_CUT_VERSION, "created_at": now_iso(), "plan": plan, "applied": True, "operation_id": operation_id, "before_snapshot_id": snapshot["snapshot_id"], "validation": validation}
    atomic_write_json(output, payload)
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "media.smart-cut", "at": now_iso(), "report": str(output), "before_snapshot_id": snapshot["snapshot_id"], "replacements": replacements})
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "media.smart-cut", "status": "succeeded", "report": str(output), "before_snapshot_id": snapshot["snapshot_id"], "replacements": replacements, "created_at": now_iso()})
    return _envelope("media.smart-cut", args, data={"report": str(output), "plan": plan, "replacements": replacements, "before_snapshot": snapshot, "validation": validation}, warnings=plan.get("warnings"), operation_id=operation_id)


def command_ad_plan(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    brief = load_json(Path(args.input).expanduser().resolve())
    analysis = load_json(Path(args.analysis).expanduser().resolve()) if args.analysis else None
    plan = build_ad_plan(brief, analysis=analysis)
    output = Path(args.output).expanduser().resolve() if args.output else root / "validation" / f"ad_plan_{new_id('run')}.json"
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise argument_error("广告规划输出必须位于项目目录内", str(output)) from exc
    if args.dry_run:
        return _envelope("ad.plan", args, status="planned", data={"output": str(output), "plan": plan})
    atomic_write_json(output, {"report_version": "0.1.0", "created_at": now_iso(), "project_id": project["project"]["id"], "brief": brief, "plan": plan})
    operation_id = new_id("op")
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "ad.plan", "output": str(output), "plan_version": plan["plan_version"], "at": now_iso()})
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "ad.plan", "status": "succeeded", "output": str(output), "created_at": now_iso()})
    return _envelope("ad.plan", args, data={"output": str(output), "plan": plan}, operation_id=operation_id)


def command_ad_apply(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    payload = load_json(Path(args.input).expanduser().resolve())
    plan = payload.get("plan") if isinstance(payload, dict) and isinstance(payload.get("plan"), dict) else payload
    if not isinstance(plan, dict):
        raise argument_error("广告计划必须是 JSON 对象", "input")
    operations = plan.get("timeline_operations")
    if not isinstance(operations, list) or not operations:
        raise argument_error("广告计划缺少非空 timeline_operations", "timeline_operations")
    sequence = find_sequence(project, args.sequence_id)
    duration_tick = plan.get("duration_tick")
    if duration_tick is not None:
        try:
            duration_tick = int(duration_tick)
        except (TypeError, ValueError) as exc:
            raise argument_error("广告计划 duration_tick 必须是整数", "duration_tick") from exc
        if duration_tick <= 0:
            raise argument_error("广告计划 duration_tick 必须大于 0", "duration_tick")
    before_project = copy.deepcopy(project)
    applied: list[dict[str, Any]] = []
    existing_ids = {str(marker.get("id")) for marker in sequence.get("markers", [])}
    for item in operations:
        if not isinstance(item, dict) or str(item.get("op", "")) != "add_marker":
            raise argument_error("ad apply 目前只接受 add_marker 计划操作", "timeline_operations")
        marker_id = str(item.get("id") or "")
        if not marker_id:
            raise argument_error("广告计划标记缺少 id", "timeline_operations[].id")
        try:
            at_tick = int(item.get("at_tick", 0))
        except (TypeError, ValueError) as exc:
            raise argument_error("广告计划标记 at_tick 必须是整数", "timeline_operations[].at_tick") from exc
        if at_tick < 0:
            raise argument_error("广告计划标记 at_tick 不能为负", "timeline_operations[].at_tick")
        if marker_id in existing_ids:
            if not args.replace_markers:
                raise argument_error(f"序列标记 ID 已存在: {marker_id}; 需要 --replace-markers", "timeline_operations[].id")
            sequence["markers"] = [marker for marker in sequence.get("markers", []) if str(marker.get("id")) != marker_id]
        marker = {"id": marker_id, "at_tick": at_tick, "label": str(item.get("label", ""))}
        sequence.setdefault("markers", []).append(marker)
        existing_ids.add(marker_id)
        applied.append({"op": "add_marker", "marker": marker})
    if duration_tick is not None and not args.preserve_duration:
        max_end = max((int(clip.get("timeline_start_tick", 0)) + int(clip.get("duration_tick", 0)) for track in sequence.get("tracks", []) for clip in track.get("clips", [])), default=0)
        if duration_tick < max_end:
            raise argument_error("计划时长短于已有片段末尾", "duration_tick")
        sequence["duration_tick"] = duration_tick
        applied.append({"op": "set_sequence_duration", "sequence_id": sequence["id"], "duration_tick": duration_tick})
    if args.dry_run:
        return _envelope("ad.apply", args, status="planned", data={"sequence_id": sequence["id"], "applied": applied, "plan_version": plan.get("plan_version")})
    validation = validate_project(root, project, strict_rights=False)
    if not validation["ok"]:
        raise AppError("PROJECT_INVALID", "广告计划应用会生成无效项目", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    snapshot = create_snapshot(root, before_project, label="before-ad-plan-apply")
    operation_id = new_id("op")
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "ad.apply", "input": str(Path(args.input).expanduser().resolve()), "plan_version": plan.get("plan_version"), "applied": applied, "before_snapshot_id": snapshot["snapshot_id"], "at": now_iso()})
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "ad.apply", "status": "succeeded", "applied": applied, "before_snapshot_id": snapshot["snapshot_id"], "created_at": now_iso()})
    return _envelope("ad.apply", args, data={"sequence_id": sequence["id"], "applied": applied, "validation": validation, "before_snapshot": snapshot}, operation_id=operation_id)


def command_subtitle_validate(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.input).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise argument_error("字幕输入不存在", str(source))
    try:
        cues = parse_caption_file(source)
    except AppError:
        raise
    duration = args.duration
    root = None
    if args.project:
        root, project = load_project(args.project)
        if duration is None:
            sequence = find_sequence(project, None)
            sequence_duration_tick = int(sequence.get("duration_tick", 1))
            # A freshly initialized sequence uses one placeholder tick. Do not
            # reject a standalone subtitle file against that sentinel duration.
            if sequence_duration_tick > 1:
                duration = sequence_duration_tick / int(project["settings"]["timebase"]["ticks_per_second"])
    report = validate_cues(cues, duration, allow_overlap=args.allow_overlap)
    report["input"] = str(source)
    report["format"] = source.suffix.lower().lstrip(".")
    report_path = None
    if args.report:
        report_path = Path(args.report).expanduser().resolve()
    elif root:
        report_path = root / "validation" / f"subtitle_{new_id('run')}.json"
    if report_path:
        atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), **report})
        report["report"] = str(report_path)
    status = "succeeded" if report["ok"] else "failed"
    return _envelope("subtitle.validate", args, data=report, status=status, errors=report["errors"])


def command_subtitle_normalize(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.input).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise argument_error("字幕输入不存在", str(source))
    root = None
    if args.project:
        root, _ = load_project(args.project)
        try:
            output.relative_to(root)
        except ValueError as exc:
            raise argument_error("字幕输出必须位于项目目录内", str(output)) from exc
    cues = parse_caption_file(source)
    report = validate_cues(cues, allow_overlap=args.allow_overlap)
    if not report["ok"]:
        return _envelope("subtitle.normalize", args, data={"input": str(source), "output": str(output), "validation": report}, status="failed", errors=report["errors"])
    if args.dry_run:
        return _envelope("subtitle.normalize", args, status="planned", data={"input": str(source), "output": str(output), "cue_count": len(cues)})
    write_srt_file(output, cues)
    return _envelope("subtitle.normalize", args, data={"input": str(source), "output": str(output), "cue_count": len(cues), "validation": report})


def command_subtitle_segment(args: argparse.Namespace) -> dict[str, Any]:
    from .artifact_locks import verification_scope
    with verification_scope():
        return _command_subtitle_segment_locked(args)


def _command_subtitle_segment_locked(args: argparse.Namespace) -> dict[str, Any]:
    from .artifact_locks import artifact_entry
    root, project = load_project(args.project)
    tps = int(project['settings']['timebase']['ticks_per_second'])
    source_path = resolve_local_path(root, args.input, field='input')
    input_digest = artifact_entry(source_path, 'subtitle-input')['sha256']
    source, inherited_rules = load_segment_source(source_path, tps)
    if args.expected_input_sha256 is not None and args.expected_input_sha256 != input_digest:
        raise AppError('SUBTITLE_SEGMENT_STALE_INPUT', '输入摘要与预览不一致', exit_code=2)
    def config(path_value: str | None) -> dict[str, Any] | None:
        if not path_value:
            return None
        path = resolve_local_path(root, path_value, field='configuration')
        if not path.is_file() or path.stat().st_size > 8 * 1024 * 1024:
            raise argument_error('配置文件不存在或超过 8 MiB', str(path))
        artifact_entry(path, 'subtitle-configuration')
        return load_json(path)
    overrides = config(args.rules)
    rules = {**inherited_rules, **(overrides or {})}
    for group in ('weight', 'cost'):
        if overrides and group in overrides:
            rules[group] = {**inherited_rules.get(group, {}), **overrides[group]} if isinstance(overrides[group], dict) else overrides[group]
    rules = checked_segment_rules(rules)
    edits = checked_segment_corrections(config(args.corrections), input_digest, source)
    output = resolve_local_path(root, args.output, field='output')
    srt = resolve_local_path(root, args.srt, field='srt') if args.srt else output.with_suffix('.srt')
    for path in (output, srt):
        ensure_inside(root / 'assets', path)
        if path.exists():
            raise argument_error('字幕输出已经存在，必须指定新文件', str(path))
    if output.suffix.lower() != '.json' or srt.suffix.lower() != '.srt' or output == srt:
        raise argument_error('分段输出必须为 assets 内新的 JSON 和 SRT', 'output')
    if args.timeline_start_tick < 0 or args.timeline_start_tick > 2**63 - 1:
        raise argument_error('timeline-start-tick 必须是非负整数', 'timeline_start_tick')
    if not args.apply and (args.track_id or args.sequence_id or args.font_asset_id or args.replace_track or args.timeline_start_tick):
        raise argument_error('入轨选项需要 --apply', 'apply')
    ledger = load_ledger(root)
    records = {str(r['asset_id']): r for r in active_records(ledger)}
    assets = asset_map(project)
    parent_ids = list(dict.fromkeys(args.source_asset_id + [a['id'] for a in assets.values()
        if resolve_local_path(root, a.get('uri', ''), field='asset.uri') == source_path]))
    parents = []
    for aid in parent_ids:
        asset = assets.get(aid)
        if not asset:
            raise argument_error('字幕来源资产不存在', aid)
        path = resolve_local_path(root, asset.get('uri', ''), field='source_asset_id')
        digest = artifact_entry(path, 'subtitle-parent')['sha256'] if path.is_file() else None
        ref = str(asset.get('rights_ref') or aid)
        if digest != asset.get('sha256') or ref not in records or records[ref].get('sha256') != digest:
            raise AppError('SUBTITLE_SEGMENT_SOURCE_INVALID', '字幕来源文件或权利摘要不匹配', exit_code=7, path=aid)
        parents.append(ref)
    sequence = find_sequence(project, args.sequence_id) if args.apply else None
    track = find_track(sequence, args.track_id, None) if args.apply and args.track_id else None
    if args.apply and (track is None or track.get('kind') != 'subtitle'):
        raise argument_error('应用需要 subtitle 目标轨道', 'track_id')
    if track and track.get('locked'):
        raise AppError('SUBTITLE_SEGMENT_TRACK_LOCKED', '字幕目标轨道已锁定', exit_code=2)
    if args.font_asset_id:
        font = assets.get(args.font_asset_id)
        if not font or font.get('kind') != 'font':
            raise argument_error('font-asset-id 必须是已登记字体', 'font_asset_id')
    result = segment_source(source, rules=rules, edits=edits)
    cues = segment_display_cues(result, args.mode)
    for cue in cues:
        cue['start_tick'] += args.timeline_start_tick
        cue['end_tick'] += args.timeline_start_tick
        if cue['end_tick'] > 2**63 - 1:
            raise argument_error('字幕偏移超过 tick 范围', 'timeline_start_tick')
    text = segmented_srt_text(cues, tps)
    if track and not args.replace_track:
        for cue in cues:
            for existing in track.get('clips', []):
                a = int(existing.get('timeline_start_tick', 0))
                b = a + int(existing.get('duration_tick', 0))
                if max(a, cue['start_tick']) < min(b, cue['end_tick']):
                    raise AppError('SUBTITLE_SEGMENT_TRACK_OVERLAP', '分段字幕与既有片段重叠；需要显式 --replace-track', exit_code=2)
    result.update({'input': str(source_path), 'input_sha256': input_digest, 'mode': args.mode,
                   'display_cues': cues, 'timeline_start_tick': args.timeline_start_tick,
                   'parent_rights_refs': parents})
    data = {'output': str(output), 'srt': str(srt), 'plan': result, 'applied': bool(args.apply)}
    if args.dry_run:
        return _envelope('subtitle.segment', args, data=data, status='planned', warnings=result['warnings'])
    created: list[Path] = []
    def write_new(path: Path, value: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            created.append(path)
            stream.write(value.encode('utf-8'))
            stream.flush()
            os.fsync(stream.fileno())
    try:
        snapshot = create_snapshot(root, project, label='before-subtitle-segment')
        operation_id = new_id('op')
        result['operation_id'] = operation_id
        write_new(output, json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
        write_new(srt, text)
        registered = []
        for path, kind in ((output, 'generated'), (srt, 'subtitle')):
            aid = new_id('subtitle_segments' if kind == 'generated' else 'subtitle_asset')
            digest = 'sha256:' + sha256_file(path)
            dependencies = parents if kind == 'generated' else [registered[0]['rights_ref']]
            asset = {'id': aid, 'kind': kind, 'uri': path.relative_to(root).as_posix(), 'sha256': digest,
                     'rights_ref': aid, 'probe': {'duration_tick': max(c['end_tick'] for c in cues), 'subtitle_cues': len(cues)},
                     'source': {'source_url': f'local://{path}', 'original_name': path.name, 'retrieved_at': now_iso()}}
            record = {'asset_id': aid, 'kind': kind, 'sha256': digest, 'source_url': f'local://{path}',
                      'source_version': 'derived-openfilm-subtitle-segments', 'retrieved_at': now_iso(),
                      'creator': 'unknown', 'license_spdx': 'LicenseRef-UNVERIFIED', 'license_url': '',
                      'attribution': '', 'permitted_uses': ['internal'], 'permitted_channels': [], 'restrictions': [],
                      'derived_from': list(dependencies), 'evidence': f'local://{output}',
                      'verification_status': 'unverified', 'verified_by': '', 'takedown_status': 'clear',
                      'notes': 'Local subtitle text/translation requires rights review; algorithm MIT does not license transcript content'}
            project.setdefault('assets', []).append(asset)
            add_record(ledger, record)
            registered.append(asset)
        generated = []
        if track:
            style = {'fontsize': 52, 'fontcolor': 'white', 'borderw': 3, 'bordercolor': 'black',
                     'x': '(w-text_w)/2', 'y': 'h-text_h-40'}
            if args.font_asset_id:
                style['font_asset_id'] = args.font_asset_id
            for i, cue in enumerate(cues):
                duration = cue['end_tick'] - cue['start_tick']
                generated.append({'id': new_id('subtitle_piece'), 'timeline_start_tick': cue['start_tick'],
                    'duration_tick': duration, 'source_in_tick': 0, 'source_out_tick': duration,
                    'generator': {'type': 'text'}, 'subtitle': {'text': cue['text'], 'style': copy.deepcopy(style)},
                    'rights_dependencies': [{'rights_ref': registered[-1]['rights_ref'], 'sha256': registered[-1]['sha256']}],
                    'extensions': {'subtitle_segment': {'source_asset_id': registered[0]['id'], 'line_id': cue['line_id'], 'parts': cue['parts']}}})
            if args.replace_track:
                track['clips'] = []
            track.setdefault('clips', []).extend(generated)
            sequence['duration_tick'] = max(int(sequence.get('duration_tick', 1)), max(c['end_tick'] for c in cues))
        save_ledger(root, ledger)
        validation = validate_project(root, project, strict_rights=False)
        if not validation['ok']:
            raise AppError('SUBTITLE_SEGMENT_APPLY_INVALID', '字幕资产/应用未通过项目验证', exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
        project.setdefault('provenance', {}).setdefault('change_log', []).append({
            'operation_id': operation_id, 'command': 'subtitle.segment', 'input_sha256': input_digest,
            'report': output.relative_to(root).as_posix(), 'mode': args.mode,
            'before_snapshot_id': snapshot['snapshot_id'], 'at': now_iso()})
        save_project(root, project)
        _operation(root, operation_id, {'operation_id': operation_id, 'command': 'subtitle.segment', 'status': 'succeeded',
            'assets': [a['id'] for a in registered], 'clip_ids': [c['id'] for c in generated],
            'before_snapshot_id': snapshot['snapshot_id'], 'created_at': now_iso()})
        data.update({'registered_assets': registered, 'generated_clips': generated, 'validation': validation, 'before_snapshot': snapshot})
        return _envelope('subtitle.segment', args, data=data, operation_id=operation_id, warnings=result['warnings'])
    except Exception as exc:
        for path in reversed(created):
            path.unlink(missing_ok=True)
        if isinstance(exc, OSError):
            raise AppError('SUBTITLE_SEGMENT_IO_FAILED', '字幕写入失败；本轮新文件已清理，项目由原事务恢复', exit_code=9, cause=str(exc)) from exc
        raise


def command_subtitle_transcribe(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    adapter = _selected_asr_adapter(root, project, args)
    source_asset: dict[str, Any] | None = None
    if args.asset_id:
        source_asset = asset_map(project).get(str(args.asset_id))
        if not source_asset:
            raise argument_error(f"找不到 ASR 源资产: {args.asset_id}", "asset_id")
        source = resolve_local_path(root, source_asset.get("uri", ""), field="asset_id")
    else:
        raw_input = str(args.input or "").strip()
        if raw_input.lower().startswith(("http://", "https://")):
            raise argument_error("字幕转写只接受本地音频或视频路径", "input")
        source = resolve_local_path(root, raw_input, field="input")
    if not source.exists() or not source.is_file():
        raise argument_error("字幕转写输入不存在", str(source))
    if not math.isfinite(args.timeline_start_seconds) or args.timeline_start_seconds < 0:
        raise argument_error("timeline-start-seconds 不能为负数", "timeline_start_seconds")
    if args.apply and not args.asset_id:
        raise AppError("SUBTITLE_APPLY_SOURCE_ASSET_REQUIRED", "应用自动字幕前必须使用 --asset-id，以便继承源素材的 Rights Ledger 记录", exit_code=7, path="asset_id")
    run_id = new_id("subtitle")
    output = resolve_local_path(root, args.output, field="output") if args.output else root / "assets" / "subtitles" / f"{run_id}.srt"
    ensure_inside(root, output)
    if output.suffix.lower() != ".srt":
        raise argument_error("转写输出必须为新的 SRT 文件", "output")
    if source_asset and source_asset.get("sha256") != "sha256:" + sha256_file(source):
        raise AppError("ASR_SOURCE_HASH_MISMATCH", "ASR 源资产已变化，请重新登记", exit_code=10)
    if args.apply and not any(record.get("asset_id") == str(source_asset.get("rights_ref") or source_asset.get("id")) for record in active_records(load_ledger(root))):
        raise AppError("RIGHTS_RECORD_MISSING", "ASR 源资产缺少权利记录", exit_code=7)
    sequence = find_sequence(project, args.sequence_id) if args.apply else None
    target_track = None
    if args.apply:
        if not args.track_id:
            raise argument_error("--apply 必须提供 --track-id", "track_id")
        target_track = find_track(sequence, args.track_id, None)
        if str(target_track.get("kind")) != "subtitle":
            raise argument_error("自动字幕只能应用到 subtitle 轨道", "track_id")
        if args.font_asset_id:
            font_asset = asset_map(project).get(str(args.font_asset_id))
            if not font_asset or str(font_asset.get("kind", "")).lower() != "font":
                raise argument_error("font-asset-id 必须引用项目内 font 资产", "font_asset_id")
    if args.dry_run:
        return _envelope(
            "subtitle.transcribe",
            args,
            status="planned",
            data={
                "input": str(source),
                "asset_id": args.asset_id,
                "output": str(output),
                "engine": ASR_ENGINE if adapter else args.transcribe_engine,
                "model_path": adapter["model_path"] if adapter else str(Path(args.model_path).expanduser().resolve()),
                "adapter_id": args.adapter_id,
                "model_sha256": adapter["sha256"] if adapter else None,
                "language": args.language,
                "apply": bool(args.apply),
                "sequence_id": sequence.get("id") if sequence else None,
                "track_id": target_track.get("id") if target_track else None,
                "timeline_start_seconds": args.timeline_start_seconds,
                "network": "disabled",
            },
        )

    if output.exists():
        raise argument_error("字幕输出已存在，为避免覆盖请指定新的 --output", str(output))
    report_path = None
    try:
        transcription = _transcribe_with_local_engine(
            root,
            source,
            engine=args.transcribe_engine,
            model_path=args.model_path,
            language=args.language,
            output_srt=output,
            use_gpu=bool(args.use_gpu),
            **({"adapter": adapter} if adapter else {}),
        )
        cues = list(transcription.get("segments") or [])
        source_duration = 0.0
        try:
            source_probe = probe_media(source)
            source_duration = float(source_probe.get("duration_seconds", 0.0) or 0.0)
        except AppError:
            source_probe = {}
        cue_validation = validate_cues(cues, duration=source_duration if source_duration > 0 else None)
        if not cue_validation["ok"]:
            output.unlink(missing_ok=True)
            raise AppError("SUBTITLE_TRANSCRIPTION_INVALID", "本地 ASR 返回的字幕时间轴未通过校验", exit_code=6, path=str(output), cause=json.dumps(cue_validation["errors"], ensure_ascii=False))
        report_path = root / "validation" / f"subtitle_transcribe_{safe_filename(run_id)}.json"
        base_report: dict[str, Any] = {
            "report_version": "0.1.0",
            "created_at": now_iso(),
            "operation_id": None,
            "applied": False,
            "project_id": project.get("project", {}).get("id"),
            "source": str(source),
            "source_asset_id": args.asset_id,
            "source_sha256": f"sha256:{sha256_file(source)}",
            "engine": ASR_ENGINE if adapter else args.transcribe_engine,
            "transcription": transcription,
            "cue_validation": cue_validation,
            "output": str(output),
            "network": "disabled",
        }
        if not args.apply:
            atomic_write_json(report_path, base_report)
            return _envelope("subtitle.transcribe", args, data={"report": str(report_path), "output": str(output), "transcription": transcription, "cue_validation": cue_validation, "applied": False})

        assert sequence is not None and target_track is not None and source_asset is not None
        timeline_tps = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", TICKS_PER_SECOND))
        timeline_offset = int(round(float(args.timeline_start_seconds) * timeline_tps))
        generated_clips: list[dict[str, Any]] = []
        style: dict[str, Any] = {
            "fontsize": 52,
            "fontcolor": "white",
            "borderw": 4,
            "bordercolor": "black",
            "shadowx": 2,
            "shadowy": 2,
            "shadowcolor": "black@0.7",
            "box": False,
            "x": "(w-text_w)/2",
            "y": "h-text_h-120",
        }
        if args.font_asset_id:
            style["font_asset_id"] = str(args.font_asset_id)
        for index, cue in enumerate(cues):
            start_tick = timeline_offset + int(round(float(cue.get("start", 0.0)) * timeline_tps))
            end_tick = timeline_offset + int(round(float(cue.get("end", 0.0)) * timeline_tps))
            duration_tick = max(1, end_tick - start_tick)
            generated_clips.append(
                {
                    "id": f"{run_id}_{index:03d}",
                    "timeline_start_tick": start_tick,
                    "duration_tick": duration_tick,
                    "source_in_tick": 0,
                    "source_out_tick": duration_tick,
                    "generator": {"type": "text"},
                    "subtitle": {"text": str(cue.get("text", "")).strip(), "style": copy.deepcopy(style)},
                }
            )
        existing_clips = list(target_track.get("clips", []))
        if not args.replace_track:
            for generated in generated_clips:
                generated_start = int(generated["timeline_start_tick"])
                generated_end = generated_start + int(generated["duration_tick"])
                for existing in existing_clips:
                    existing_start = int(existing.get("timeline_start_tick", 0))
                    existing_end = existing_start + int(existing.get("duration_tick", 0))
                    if max(generated_start, existing_start) < min(generated_end, existing_end):
                        output.unlink(missing_ok=True)
                        raise AppError("SUBTITLE_TRANSCRIBE_TRACK_OVERLAP", "自动字幕会覆盖目标字幕轨道已有片段，请使用 --replace-track 或调整时间线起点", exit_code=2, path="track_id")
        before_project = copy.deepcopy(project)
        snapshot = create_snapshot(root, before_project, label="before-subtitle-transcribe")
        operation_id = new_id("op")
        subtitle_asset_id = new_id("subtitle_asset")
        source_rights_ref = str(source_asset.get("rights_ref") or source_asset.get("id"))
        ledger = load_ledger(root)
        parent_record = next((record for record in active_records(ledger) if str(record.get("asset_id")) == source_rights_ref), None)
        if parent_record is None:
            output.unlink(missing_ok=True)
            raise AppError("RIGHTS_RECORD_MISSING", "ASR 源资产缺少可继承的 Rights Ledger 记录", exit_code=7, path=source_rights_ref)
        output_digest = sha256_file(output)
        subtitle_asset = {
            "id": subtitle_asset_id,
            "kind": "subtitle",
            "uri": str(output.relative_to(root)).replace("\\", "/"),
            "sha256": f"sha256:{output_digest}",
            "probe": {"duration_seconds": source_duration, "duration_tick": int(round(source_duration * timeline_tps)) if source_duration > 0 else max((int(item["timeline_start_tick"]) + int(item["duration_tick"]) for item in generated_clips), default=1), "subtitle_cues": len(cues)},
            "rights_ref": subtitle_asset_id,
            "source": {"source_url": f"local://{output}", "retrieved_at": now_iso(), "original_name": output.name, "derived_from": [source_asset.get("id")]},
        }
        subtitle_record = {
            "asset_id": subtitle_asset_id,
            "kind": "subtitle",
            "sha256": f"sha256:{output_digest}",
            "source_url": f"local://{output}",
            "source_version": f"derived-{ASR_ENGINE if adapter else args.transcribe_engine}",
            "retrieved_at": now_iso(),
            "creator": parent_record.get("creator", "unknown"),
            "license_spdx": parent_record.get("license_spdx", "LicenseRef-UNVERIFIED"),
            "license_url": parent_record.get("license_url", ""),
            "attribution": parent_record.get("attribution", ""),
            "permitted_uses": list(parent_record.get("permitted_uses", ["internal"])),
            "permitted_channels": list(parent_record.get("permitted_channels", [])),
            "restrictions": list(parent_record.get("restrictions", [])),
            "derived_from": list(dict.fromkeys([source_rights_ref] + ([adapter["rights_ref"]] if adapter else []))),
            "evidence": parent_record.get("evidence", ""),
            "verification_status": parent_record.get("verification_status", "unverified"),
            "verified_by": parent_record.get("verified_by", ""),
            "takedown_status": parent_record.get("takedown_status", "clear"),
            "notes": "Generated by local offline ASR; inherits source rights",
        }
        if args.replace_track:
            target_track["clips"] = []
        target_track.setdefault("clips", []).extend(generated_clips)
        project.setdefault("assets", []).append(subtitle_asset)
        add_record(ledger, subtitle_record)
        _recompute_sequence_duration(sequence)
        save_ledger(root, ledger)  # validation must see the candidate dependency record
        validation = validate_project(root, project, strict_rights=False)
        if not validation["ok"]:
            output.unlink(missing_ok=True)
            raise AppError("SUBTITLE_TRANSCRIBE_APPLY_INVALID", "自动字幕应用后项目校验失败", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
        base_report.update({
            "applied": True,
            "operation_id": operation_id,
            "before_snapshot_id": snapshot["snapshot_id"],
            "sequence_id": sequence.get("id"),
            "track_id": target_track.get("id"),
            "subtitle_asset": subtitle_asset,
            "rights": subtitle_record,
            "generated_clips": generated_clips,
            "timeline_start_seconds": round(float(args.timeline_start_seconds), 6),
            "replace_track": bool(args.replace_track),
            "validation": validation,
        })
        atomic_write_json(report_path, base_report)
        project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "subtitle.transcribe", "asset_id": subtitle_asset_id, "source_asset_id": source_asset.get("id"), "sequence_id": sequence.get("id"), "track_id": target_track.get("id"), "report": str(report_path), "before_snapshot_id": snapshot["snapshot_id"], "at": now_iso()})
        save_project(root, project)
        _operation(root, operation_id, {"operation_id": operation_id, "command": "subtitle.transcribe", "status": "succeeded", "asset_id": subtitle_asset_id, "source_asset_id": source_asset.get("id"), "report": str(report_path), "before_snapshot_id": snapshot["snapshot_id"], "clip_ids": [clip["id"] for clip in generated_clips], "created_at": now_iso()})
        return _envelope("subtitle.transcribe", args, data={"report": str(report_path), "output": str(output), "transcription": transcription, "subtitle_asset": subtitle_asset, "rights": subtitle_record, "generated_clips": generated_clips, "before_snapshot": snapshot, "validation": validation, "applied": True}, operation_id=operation_id)

    except OSError as exc:
        output.unlink(missing_ok=True)
        if report_path:
            report_path.unlink(missing_ok=True)
        raise AppError("SUBTITLE_TRANSCRIBE_IO_FAILED", "字幕落盘失败，已恢复项目元数据并清理本轮输出", exit_code=9, cause=str(exc)) from exc
    except Exception:
        output.unlink(missing_ok=True)
        if report_path:
            report_path.unlink(missing_ok=True)
        raise


def _tts_text_file(root: Path, value: str) -> tuple[str, dict[str, Any]]:
    path = tts_local_path(root, value, "input")
    try:
        text = path.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        raise argument_error("配音文本/逐字稿必须是 UTF-8", str(path)) from exc
    return text, {"kind": "file", "path": str(path), "sha256": f"sha256:{sha256_file(path)}"}


def command_tts_registration(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    kind = "adapters" if args.action == "adapter" else "voices"
    command = f"tts.{args.action}.{args.registration_action}"
    if args.registration_action in {"list", "inspect"}:
        items = tts_registry(project).get(kind, []) if args.registration_action == "list" else [tts_registry_item(project, kind, getattr(args, f"{args.action}_id"))]
        checked = [{args.action: item, "verification": verify_tts_adapter(item) if kind == "adapters" else verify_tts_voice(root, project, item)} for item in items]
        data = {"count": len(checked), "items": checked, "network": "disabled"}
        if args.registration_action == "inspect":
            data.update(checked[0])
        return _envelope(command, args, data=data)
    item_id = getattr(args, f"{args.action}_id")
    if any(item.get(f"{args.action}_id") == item_id for item in tts_registry(project).get(kind, [])):
        raise AppError("TTS_REGISTRATION_EXISTS", f"TTS 登记已存在: {item_id}", exit_code=2)
    common = {"evidence": args.evidence, "license_spdx": args.license_spdx, "creator": args.creator, "status": args.verification_status, "uses": args.permitted_use or ["internal"]}
    if kind == "adapters":
        record, rights = prepare_tts_adapter(root, adapter_id=args.adapter_id, python_executable=args.python_executable, source_root=args.source_root, package_root=args.package_root, model_path=args.model_path, tokenizer_path=args.tokenizer_path, **common)
    else:
        prompt = args.prompt_text if args.prompt_text is not None else _tts_text_file(root, args.prompt_input)[0]
        record, rights = prepare_tts_voice(root, project, voice_id=args.voice_id, asset_id=args.asset_id, prompt_text=prompt, **common)
        if not any(item.get("asset_id") == rights["derived_from"][0] for item in active_records(load_ledger(root))):
            raise AppError("RIGHTS_RECORD_MISSING", "参考声缺少源权利记录", exit_code=7)
    if args.dry_run:
        return _envelope(command, args, status="planned", data={args.action: record, "rights": rights, "network": "disabled"})
    snapshot = create_snapshot(root, project, label=f"before-tts-{args.action}-register")
    ledger, operation_id = load_ledger(root), new_id("op")
    add_tts_registration(project, kind, record)
    add_record(ledger, rights)
    change = {"operation_id": operation_id, "command": command, f"{args.action}_id": item_id, "snapshot_id": snapshot["snapshot_id"], "sha256": record["sha256"], "at": now_iso()}
    project.setdefault("provenance", {}).setdefault("change_log", []).append(change)
    save_project(root, project)
    save_ledger(root, ledger)
    _operation(root, operation_id, {**change, "status": "succeeded"})
    return _envelope(command, args, data={args.action: record, "rights": rights, "snapshot": snapshot, "network": "disabled"}, operation_id=operation_id)


def command_tts_synthesize(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    text, source = (str(args.text), {"kind": "inline", "path": None}) if args.text is not None else _tts_text_file(root, args.input)
    if bool(args.adapter_id) != bool(args.voice_id):
        raise argument_error("--adapter-id 与 --voice-id 必须一起提供", "adapter_id/voice_id")
    if not math.isfinite(args.timeline_start_seconds) or args.timeline_start_seconds < 0:
        raise argument_error("时间线起点必须为非负有限秒数", "timeline_start_seconds")
    if not 0 <= args.seed < 2 ** 32:
        raise argument_error("seed 必须在 0–4294967295 之间", "seed")
    if args.apply and not args.track_id:
        raise argument_error("--apply 必须提供 --track-id", "track_id")
    sequence = find_sequence(project, args.sequence_id) if args.apply else None
    track = find_track(sequence, args.track_id, None) if sequence else None
    if track is not None and track.get("kind") != "audio":
        raise argument_error("配音应用目标必须为 audio 轨道", "track_id")
    operation_id, asset_id = new_id("op"), args.asset_id or new_id("asset_tts")
    assert_id(asset_id, "asset_id")
    if asset_id in asset_map(project):
        raise argument_error("生成音频资产 ID 已存在", "asset_id")
    output = Path(args.output).expanduser() if args.output else Path("assets") / "tts" / f"{asset_id}.wav"
    output = ensure_inside(root, output if output.is_absolute() else root / output)
    ensure_inside(root / "assets", output)
    validate_tts_output(args.sample_rate, args.channels, output)
    adapter = voice = None
    checks = None
    parents: list[str] = []
    if args.adapter_id:
        text = validate_tts_text(text)
        adapter = tts_registry_item(project, "adapters", args.adapter_id)
        voice = tts_registry_item(project, "voices", args.voice_id)
        checks = verify_tts_inputs(root, project, adapter, voice)
        parents = [adapter["rights_ref"], voice["rights_ref"]]
        records = {item["asset_id"]: item for item in active_records(load_ledger(root))}
        if any(parent not in records for parent in parents):
            raise AppError("RIGHTS_RECORD_MISSING", "配音模型或声线缺少权利记录", exit_code=7)
        if any(records[parent].get("sha256") != item["sha256"] for parent, item in zip(parents, [adapter, voice])):
            raise AppError("TTS_RIGHTS_HASH_MISMATCH", "模型或声线登记与权利记录不一致", exit_code=7)
    else:
        text = validate_flite_text(text)
        validate_flite_voice(args.voice)
    if args.dry_run:
        return _envelope("tts.synthesize", args, status="planned", data={"output": str(output), "asset_id": asset_id, "voice": args.voice, "adapter_id": args.adapter_id, "voice_id": args.voice_id, "engine": SOULX_ENGINE if adapter else "ffmpeg-flite-local", "sample_rate": args.sample_rate, "channels": args.channels, "source": source, "checks": checks, "apply": args.apply, "track_id": args.track_id, "timeline_start_seconds": args.timeline_start_seconds, "network": "disabled"}, operation_id=operation_id)
    if adapter is None and not flite_available():
        raise dependency_error("当前 FFmpeg 没有 flite 音频滤镜", "安装原生 FFmpeg；不会自动下载或调用线上 TTS")
    snapshot = create_snapshot(root, project, label="before-tts-synthesize")
    created_output = False
    try:
        if adapter and voice:
            result = synthesize_soulx(root, text, output, adapter=adapter, voice=voice, audio=Path(checks[1]["audio"]), operation_id=operation_id, sample_rate=args.sample_rate, channels=args.channels, seed=args.seed)
        else:
            result = synthesize_local_tts(root, text, output, operation_id=operation_id, voice=args.voice, sample_rate=args.sample_rate, channels=args.channels)
        created_output = True
        tps = int(project.get("settings", {}).get("timebase", {}).get("ticks_per_second", TICKS_PER_SECOND))
        duration = float(result["probe"].get("duration_seconds") or 0)
        if not math.isfinite(duration) or duration <= 0:
            raise AppError("TTS_OUTPUT_INVALID", "配音时长必须为正数", exit_code=6)
        digest = f"sha256:{sha256_file(output)}"
        asset = {"id": asset_id, "kind": "audio", "uri": output.relative_to(root).as_posix(), "sha256": digest, "duration_tick": max(1, round(duration * tps)), "timebase": {"ticks_per_second": tps}, "probe": result["probe"], "rights_ref": asset_id, "source": {"source_url": f"local://tts/{operation_id}", "retrieved_at": now_iso(), "original_name": output.name, "derived_from": parents, "generation": {"engine": result["engine"], "text": text, "text_sha256": result["text_sha256"], "adapter_id": args.adapter_id, "voice_id": args.voice_id, "seed": args.seed if adapter else None}}}
        project.setdefault("assets", []).append(asset)
        generated_clip = None
        if track is not None:
            generated_clip = {"id": new_id("clip_tts"), "asset_id": asset_id, "timeline_start_tick": round(args.timeline_start_seconds * tps), "source_in_tick": 0, "source_out_tick": asset["duration_tick"], "duration_tick": asset["duration_tick"], "enabled": True}
            track.setdefault("clips", []).append(generated_clip)
            _recompute_sequence_duration(sequence)
        report_path = root / "validation" / f"tts_{operation_id}.json"
        rights = {"asset_id": asset_id, "kind": "audio", "sha256": digest, "source_url": f"local://tts/{operation_id}", "source_version": result["engine"], "retrieved_at": now_iso(), "creator": "local-tts", "license_spdx": "LicenseRef-UNVERIFIED", "license_url": "", "attribution": "", "permitted_uses": ["internal"], "permitted_channels": [], "restrictions": [], "derived_from": parents, "evidence": str(report_path), "verification_status": "unverified", "verified_by": "", "takedown_status": "clear", "notes": "Generated speech needs output, model, reference voice and text rights review before publication"}
        ledger = load_ledger(root)
        add_record(ledger, rights)
        # validate_project reads the on-disk ledger. The enclosing metadata
        # transaction rolls this candidate back if validation or commit fails.
        save_ledger(root, ledger)
        validation = validate_project(root, project, strict_rights=False)
        if not validation["ok"]:
            raise AppError("TTS_APPLY_INVALID", "配音资产或音频轨道校验失败", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
        atomic_write_json(report_path, {"report_version": "0.1.0", "operation_id": operation_id, "source": source, "synthesis": result, "asset": asset, "rights": rights, "generated_clip": generated_clip, "snapshot_id": snapshot["snapshot_id"], "validation": validation})
        change = {"operation_id": operation_id, "command": "tts.synthesize", "asset_id": asset_id, "output": str(output), "engine": result["engine"], "text_sha256": result["text_sha256"], "snapshot_id": snapshot["snapshot_id"], "report": str(report_path), "at": now_iso()}
        project.setdefault("provenance", {}).setdefault("change_log", []).append(change)
        save_project(root, project)
        save_ledger(root, ledger)
        _operation(root, operation_id, {**change, "status": "succeeded", "duration_seconds": duration})
        envelope = _envelope("tts.synthesize", args, data={**result, "source": source, "asset": asset, "rights": rights, "snapshot": snapshot, "generated_clip": generated_clip, "report": str(report_path), "validation": validation}, operation_id=operation_id)
        envelope.setdefault("warnings", []).append({"code": "TTS_REVIEW_REQUIRED", "message": "配音保留自然时长；发布前需复核错读、断尾、声线与模型/声源/文本权利"})
        return envelope
    except BaseException:
        if created_output:
            output.unlink(missing_ok=True)
        _operation(root, operation_id, {"operation_id": operation_id, "command": "tts.synthesize", "status": "failed", "created_at": now_iso(), "output": str(output)})
        raise


def command_effects_list(args: argparse.Namespace) -> dict[str, Any]:
    effects = list_effects(args.query, keyframable_only=bool(args.keyframable_only))
    return _envelope(
        "effects.list",
        args,
        data={
            "catalog_version": EFFECT_CATALOG_VERSION,
            "source": "native-and-ffmpeg-local",
            "network": "disabled",
            "count": len(effects),
            "effects": effects,
        },
    )


def command_effects_inspect(args: argparse.Namespace) -> dict[str, Any]:
    effect = get_effect(args.name)
    if effect is None:
        raise argument_error(f"本地效果目录中不存在: {args.name}", "name")
    return _envelope(
        "effects.inspect",
        args,
        data={
            "catalog_version": EFFECT_CATALOG_VERSION,
            "source": effect.get("source", "ffmpeg-local"),
            "network": "disabled",
            "effect": effect,
        },
    )


def command_html_register(args: argparse.Namespace) -> dict[str, Any]:
    root, _ = load_project(args.project)
    path = resolve_local_path(root, args.input, field='input')
    record = html_motion.prepare_runtime(root, load_json(path))
    if not args.dry_run:
        atomic_write_json(root / 'config/html-motion-runtime.json', record)
    return _envelope('motion.html-register', args, status='planned' if args.dry_run else 'succeeded',
                     data={'runtime': record, 'automatic_downloads': False})


def _html_rights(asset: dict, parents: list[str], *, creator='unknown', license_spdx='LicenseRef-UNVERIFIED') -> dict:
    return {'asset_id': asset['id'], 'kind': asset['kind'], 'sha256': asset['sha256'],
        'source_url': asset['uri'], 'source_version': html_motion.ENGINE,
        'retrieved_at': now_iso(), 'creator': creator, 'license_spdx': license_spdx, 'license_url': '',
        'attribution': '', 'permitted_uses': ['internal'], 'restrictions': [], 'derived_from': parents,
        'evidence': asset['uri'], 'verification_status': 'unverified', 'verified_by': '',
        'takedown_status': 'clear', 'notes': 'Local editable HTML motion; template, image and font rights require separate review'}


def command_html_source(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    assert_id(args.asset_id, 'asset_id')
    if args.asset_id in asset_map(project):
        raise argument_error('源码资产 ID 已存在', 'asset_id')
    command = 'motion.' + args.action
    if args.action == 'stroke-source':
        from .stroke_motion import build_source
        content, plan = build_source(root, project, args.input)
    else:
        content, plan = html_motion.build_source(root, project, args.input)
    output = ensure_inside(root, root / 'assets/html-motion' / (html_motion.digest(args.asset_id.encode())[7:39] + '.zip'))
    if output.exists():
        raise argument_error('源码包路径已存在，必须使用新的 ID', str(output))
    asset = {'id': args.asset_id, 'kind': 'generated', 'uri': output.relative_to(root).as_posix(),
        'sha256': html_motion.digest(content), 'rights_ref': args.asset_id, 'probe': {'format': 'agent-html-motion-source'},
        'source': {'source_url': output.relative_to(root).as_posix(), 'retrieved_at': now_iso(), 'original_name': output.name},
        'html_source': {'engine': html_motion.ENGINE, 'version': html_motion.VERSION,
            'ticks_per_second': project['settings']['timebase']['ticks_per_second'], 'resources': plan['resources']}}
    if 'component_fields' in plan:
        asset['html_source']['component_fields'] = plan['component_fields']
    parents = list(dict.fromkeys(asset_map(project)[r['asset_id']]['rights_ref'] for r in plan['resources']))
    record = _html_rights(asset, parents, creator=args.creator, license_spdx=args.license_spdx)
    if args.dry_run:
        return _envelope(command, args, status='planned', data={'asset': asset, 'rights': record, 'plan': plan})
    snapshot = create_snapshot(root, project, label='before-html-source')
    created = False
    try:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open('xb') as stream:
            created = True
            stream.write(content)
        ledger = load_ledger(root)
        add_record(ledger, record)
        project['assets'].append(asset)
        operation_id = new_id('op')
        project['provenance'].setdefault('change_log', []).append({'command': command,
            'operation_id': operation_id, 'asset_id': asset['id'], 'snapshot_id': snapshot['snapshot_id'], 'at': now_iso()})
        save_project(root, project)
        save_ledger(root, ledger)
        _operation(root, operation_id, {'command': command, 'status': 'succeeded',
                   'asset_id': asset['id'], 'created_at': now_iso()})
        return _envelope(command, args, data={'asset': asset, 'rights': record, 'plan': plan,
                         'snapshot': snapshot}, operation_id=operation_id)
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise


def command_html_inspect(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    source = html_motion.inspect_source(root, project, args.source_asset_id)
    source.pop('data')
    return _envelope('motion.html-inspect', args, data=source)


def command_html_fields(args: argparse.Namespace) -> dict[str, Any]:
    from .html_components import configure, discover
    from .html_template import merge_overrides
    root, project = load_project(args.project)
    previous = {}
    source_id = args.source_asset_id
    if args.from_asset_id:
        previous = asset_map(project).get(args.from_asset_id, {}).get('html_motion', {})
        if not previous:
            raise AppError('HTML_RECIPE_MISSING', '已有输出没有可重建源码配方', exit_code=2)
        source_id = previous['source_asset_id']
    source = html_motion.inspect_source(root, project, source_id)
    fields, values, _ = configure(root, source, previous, args)
    result = discover(root, project, source, fields, values, merge_overrides(previous.get('template_overrides')))
    result['source_asset_id'] = source_id
    return _envelope('motion.html-fields', args, data=result)


def command_html_controls(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    inspection_args = copy.copy(args)
    inspection_args.asset_id = new_id('inspect_html')
    inspection_args.apply = False
    inspection_args.track_id = None
    inspection_args.timeline_start_tick = 0
    inspection_args.expected_project_sha256 = None
    plan = html_motion.prepare_render(root, project, inspection_args)
    html_motion._integer(args.frame_index, 'frame_index', 0, plan['frame_count']-1)
    public = html_motion.public_plan(plan)
    public.update(inspection_only=True, sample_frame_index=args.frame_index,
                  all_frames_checked_in_two_fresh_context_orders=False, output=None)
    if args.dry_run:
        return _envelope('motion.html-controls', args, status='planned', data={'plan': public})
    cancel = resolve_local_path(root, args.cancel_file, field='cancel_file') if args.cancel_file else None
    report_path = root / 'validation' / f'html-controls-{new_id("inspect")}.json'
    result = html_motion.inspect_controls(root, plan, report_path, frame_index=args.frame_index,
                                         timeout=args.timeout_seconds, cancel_file=cancel)
    return _envelope('motion.html-controls', args, data={'inspection': result, 'report': str(report_path)})


def command_html_quality(args: argparse.Namespace) -> dict[str, Any]:
    root,project=load_project(args.project)
    inspection_args=copy.copy(args)
    inspection_args.asset_id=new_id('quality_html');inspection_args.apply=False
    inspection_args.track_id=None;inspection_args.timeline_start_tick=0;inspection_args.expected_project_sha256=None
    plan=html_motion.prepare_render(root,project,inspection_args)
    if args.dry_run:
        return _envelope('motion.html-quality',args,status='planned',data={'plan':html_motion.public_quality_plan(plan)})
    cancel=resolve_local_path(root,args.cancel_file,field='cancel_file') if args.cancel_file else None
    report_path=root/'validation'/f'html-quality-{new_id("inspect")}.json'
    result=html_motion.inspect_layout(root,plan,report_path,timeout=args.timeout_seconds,cancel_file=cancel)
    return _envelope('motion.html-quality',args,data={'quality':result,'report':str(report_path)})


def command_html_render(args: argparse.Namespace) -> dict[str, Any]:
    from time import monotonic
    started=monotonic()
    root, project = load_project(args.project)
    plan = html_motion.prepare_render(root, project, args)
    public = html_motion.public_plan(plan)
    if args.dry_run:
        return _envelope('motion.html-render', args, status='planned', data={'plan': public})
    output = ensure_inside(root, root / 'assets/html-motion' / (html_motion.digest(args.asset_id.encode())[7:39] + '.nut'))
    if output.exists():
        raise argument_error('动效输出已存在，必须使用新的 ID', str(output))
    cancel = resolve_local_path(root, args.cancel_file, field='cancel_file') if args.cancel_file else None
    layout_result=None;layout_path=None
    if plan['layout_check']=='strict':
        layout_path=root/'validation'/f'html-quality-{new_id("gate")}.json'
        layout_result=html_motion.inspect_layout(root,plan,layout_path,timeout=args.timeout_seconds,cancel_file=cancel)
    remaining=args.timeout_seconds-(monotonic()-started)
    operation_id = new_id('op')
    report_path = root / 'validation' / f'html-motion-{operation_id}.json'
    cancelled=cancel is not None and cancel.exists()
    if cancelled or remaining<=0:
        error=AppError('CANCELLED' if cancelled else 'HTML_TIMEOUT',
            'HTML 动效已取消' if cancelled else 'HTML 布局预检与渲染共用的总期限已到',
            exit_code=8 if cancelled else 6)
        html_motion.record_unstarted_render_failure(plan,report_path,error,
            layout_report=layout_path,layout_result=layout_result)
        raise error
    snapshot = create_snapshot(root, project, label='before-html-render')
    created = False
    try:
        result = html_motion.render_frames(root, plan, output, report_path, timeout=remaining, cancel_file=cancel)
        created = True
        asset = {'id': args.asset_id, 'kind': 'video', 'uri': output.relative_to(root).as_posix(),
            'sha256': result['output_sha256'], 'rights_ref': args.asset_id, 'probe': result['probe'],
            'source': {'source_url': output.relative_to(root).as_posix(), 'retrieved_at': now_iso(), 'original_name': output.name},
            'html_motion': {'engine': html_motion.ENGINE, 'source_asset_id': plan['source_asset_id'],
                'parameters': plan['parameters'], 'spec': plan['spec'], 'frame_count': plan['frame_count'],
                'template_overrides': plan['template_overrides'], 'override_resources': plan['override_resources'],
                'layout_check':plan['layout_check'],'shutter':plan['shutter']['config']}}
        if 'component_fields' in plan:
            asset['html_motion'].update(component_fields=plan['component_fields'], component_values=plan['component_values'])
        if layout_result is not None:
            asset['html_motion']['layout_evidence']={'report_sha256':'sha256:'+sha256_file(layout_path),
                'frame_count':layout_result['frame_count'],'quality_passed':True,'all_frame_orders_equal':True,
                'sampling_scope':'actual_shutter_subframes' if plan['shutter']['enabled'] else 'output_frame_anchors'}
        record = _html_rights(asset, list(dict.fromkeys([plan['asset']['rights_ref'],*[r['rights_ref'] for r in plan['override_resources']]])))
        project['assets'].append(asset)
        ledger = load_ledger(root)
        add_record(ledger, record)
        clip = None
        if plan.get('replacement_clip') is not None:
            clip = plan['replacement_clip']
            clip['asset_id'] = asset['id']
        elif plan['track'] is not None:
            clip = {'id': new_id('clip_html'), 'asset_id': asset['id'], 'timeline_start_tick': args.timeline_start_tick,
                'duration_tick': plan['spec']['duration_tick'], 'source_in_tick': 0, 'source_out_tick': plan['spec']['duration_tick']}
            plan['track']['clips'].append(clip)
            _recompute_sequence_duration(find_sequence(project, args.sequence_id))
        save_ledger(root, ledger)  # validation sees the same candidate rights; transaction protects rollback
        validation = validate_project(root, project, strict_rights=False)
        if not validation['ok']:
            raise AppError('HTML_APPLY_INVALID', '动效写入后项目校验失败', exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
        project['provenance'].setdefault('change_log', []).append({'command': 'motion.html-render', 'operation_id': operation_id,
            'asset_id': asset['id'], 'source_asset_id': plan['source_asset_id'], 'snapshot_id': snapshot['snapshot_id'], 'at': now_iso()})
        save_project(root, project)
        save_ledger(root, ledger)
        _operation(root, operation_id, {'command': 'motion.html-render', 'status': 'succeeded', 'asset_id': asset['id'],
                   'report': str(report_path), 'created_at': now_iso()})
        return _envelope('motion.html-render', args, data={'plan': public, 'asset': asset, 'rights': record,
                         'generated_clip': clip, 'snapshot': snapshot, 'report': str(report_path), 'validation': validation,
                         'layout_report':str(layout_path) if layout_path else None}, operation_id=operation_id)
    except BaseException as exc:
        if created:
            output.unlink(missing_ok=True)
        if report_path.is_file():
            try:
                failed = load_json(report_path)
                failed['render_status'] = failed['status']
                failed['status'] = 'failed'
                failed['application_error'] = exc.as_dict() if isinstance(exc, AppError) else {'message': str(exc)}
                atomic_write_json(report_path, failed)
                if isinstance(exc, AppError):
                    exc.path = str(report_path)
            except (OSError, ValueError):
                pass
        raise


def command_motion_list(args: argparse.Namespace) -> dict[str, Any]:
    presets = list_motion_presets(args.query)
    return _envelope(
        "motion.list",
        args,
        data={
            "catalog_version": MOTION_PRESET_CATALOG_VERSION,
            "source": "local-catalog",
            "engine": "timeline-keyframes",
            "network": "disabled",
            "count": len(presets),
            "presets": presets,
        },
    )


def command_motion_inspect(args: argparse.Namespace) -> dict[str, Any]:
    preset = get_motion_preset(args.name)
    if preset is None:
        raise argument_error(f"本地运镜目录中不存在: {args.name}", "name")
    return _envelope(
        "motion.inspect",
        args,
        data={
            "catalog_version": MOTION_PRESET_CATALOG_VERSION,
            "source": "local-catalog",
            "engine": "timeline-keyframes",
            "network": "disabled",
            "preset": preset,
        },
    )


def _clip_from_change(change: dict[str, Any], track: dict[str, Any]) -> dict[str, Any]:
    for field in ("source_in_tick", "source_out_tick"):
        if field not in change:
            raise argument_error(f"append_clip 缺少字段: {field}", field)
    asset_id = change.get("asset_id")
    sequence_id = change.get("nested_sequence_id")
    generator = change.get("generator")
    text_generator = isinstance(generator, dict) and str(generator.get("type", "")).lower() == "text" and isinstance(change.get("subtitle"), dict)
    particle_generator = isinstance(generator,dict) and generator.get('type')=='particles'
    if not asset_id and not sequence_id and not text_generator and not particle_generator:
        raise argument_error("append_clip 必须提供 asset_id、nested_sequence_id 或有效的 text/particles generator")
    source_in = int(change["source_in_tick"])
    source_out = int(change["source_out_tick"])
    duration = int(change.get("duration_tick", source_out - source_in))
    if duration <= 0 or source_out <= source_in:
        raise argument_error("片段 source/duration 时间范围无效")
    start = change.get("timeline_start_tick")
    if start is None:
        start = max((int(item.get("timeline_start_tick", 0)) + int(item.get("duration_tick", 0)) for item in track.get("clips", [])), default=0)
    clip = {"id": change.get("id") or new_id("clip"), "timeline_start_tick": int(start), "duration_tick": duration, "source_in_tick": source_in, "source_out_tick": source_out}
    if asset_id:
        clip["asset_id"] = asset_id
    if sequence_id:
        clip["sequence_id"] = sequence_id
    if text_generator:
        clip["generator"] = copy.deepcopy(generator)
    for field in ("speed", "speed_curve", "reverse", "freeze", "crop", "transform", "keyframes", "effects", "transition_in", "transition_out", "subtitle", "generator", "audio", "blend", "mask", "tracking_binding", "link_id"):
        if field in change:
            clip[field] = change[field]
    return clip


def _find_clip(sequence: dict[str, Any], clip_id: str, track_id: str | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    if not clip_id:
        raise argument_error("操作必须提供 clip_id", "clip_id")
    tracks = sequence.get("tracks", [])
    if track_id:
        tracks = [track for track in tracks if track.get("id") == track_id]
    for track in tracks:
        for clip in track.get("clips", []):
            if clip.get("id") == clip_id:
                return track, clip
    raise argument_error(f"找不到片段: {clip_id}", "clip_id")


def _recompute_sequence_duration(sequence: dict[str, Any]) -> None:
    end = max(
        (int(clip.get("timeline_start_tick", 0)) + int(clip.get("duration_tick", 0))
         for track in sequence.get("tracks", [])
         for clip in track.get("clips", [])),
        default=0,
    )
    sequence["duration_tick"] = max(1, end)


def _add_track(sequence: dict[str, Any], change: dict[str, Any]) -> dict[str, Any]:
    track_id = str(change.get("track_id") or change.get("id") or new_id("track"))
    if any(track.get("id") == track_id for track in sequence.get("tracks", [])):
        raise argument_error(f"轨道 ID 已存在: {track_id}", "track_id")
    kind = str(change.get("kind") or change.get("track_kind") or "video")
    if kind not in {"video", "audio", "subtitle", "data"}:
        raise argument_error(f"轨道 kind 无效: {kind}", "kind")
    order = int(change.get("order", max((int(track.get("order", 0)) for track in sequence.get("tracks", [])), default=-1) + 1))
    track = {
        "id": track_id,
        "kind": kind,
        "order": order,
        "muted": bool(change.get("muted", False)),
        "locked": bool(change.get("locked", False)),
        "clips": [],
    }
    if "overlap_policy" in change:
        track["overlap_policy"] = change["overlap_policy"]
    if 'sync_lock' in change:
        track['sync_lock'] = change['sync_lock']
    if isinstance(change.get("audio"), dict):
        track["audio"] = copy.deepcopy(change["audio"])
    sequence.setdefault("tracks", []).append(track)
    return track


def _set_keyframe_track(clip: dict[str, Any], property_name: str, values: list[tuple[int, float, str]]) -> None:
    tracks = clip.setdefault("keyframes", [])
    track = next((item for item in tracks if item.get("property") == property_name), None)
    payload = {"property": property_name, "keyframes": [{"at_tick": int(at), "value": float(value), "interpolation": interpolation} for at, value, interpolation in values]}
    if track is None:
        tracks.append(payload)
    else:
        track.clear()
        track.update(payload)


def _clamp_clip_keyframes(clip: dict[str, Any]) -> None:
    duration = max(1, int((clip.get('presentation_window') or {}).get('authored_duration_tick', clip.get('duration_tick', 1))))
    retained: list[dict[str, Any]] = []
    for track in clip.get("keyframes", []):
        if not isinstance(track, dict):
            continue
        points = track.get("keyframes", [])
        if not isinstance(points, list):
            continue
        normalized: list[dict[str, Any]] = []
        for point in points:
            if not isinstance(point, dict):
                continue
            copy_point = dict(point)
            try:
                copy_point["at_tick"] = min(duration, max(0, int(copy_point.get("at_tick", 0))))
            except (TypeError, ValueError):
                continue
            normalized.append(copy_point)
        normalized.sort(key=lambda item: int(item["at_tick"]))
        if normalized:
            track["keyframes"] = normalized
            retained.append(track)
    clip["keyframes"] = retained


def _apply_motion_preset(clip: dict[str, Any], change: dict[str, Any]) -> dict[str, Any]:
    requested = str(change.get("preset") or change.get("motion_preset") or "")
    preset = canonical_motion_preset(requested)
    if not requested:
        raise argument_error("apply_motion_preset 缺少 preset", "preset")
    definition = get_motion_preset(preset or requested)
    if definition is None or preset is None:
        raise argument_error(f"不支持的运动预设: {requested}", "preset")
    duration = max(1, int(clip.get("duration_tick", 1)))
    start_tick = max(0, int(change.get("start_tick", 0)))
    end_tick = min(duration, int(change.get("end_tick", duration)))
    if end_tick <= start_tick:
        raise argument_error("运动预设的时间范围无效", "start_tick/end_tick")
    offset_tick = (clip.get('presentation_window') or {}).get('offset_tick',0)
    start_tick += offset_tick
    end_tick += offset_tick
    parameter_values = definition.get("parameters", {})

    def _number(name: str, *, absolute: bool = False) -> float:
        default = parameter_values.get(name, {}).get("default", 0.0)
        raw = change.get(name, default)
        if isinstance(raw, bool):
            raise argument_error(f"运动预设参数 {name} 必须是数字", name)
        try:
            value = float(raw)
        except (TypeError, ValueError) as exc:
            raise argument_error(f"运动预设参数 {name} 必须是数字", name) from exc
        if not math.isfinite(value):
            raise argument_error(f"运动预设参数 {name} 必须是有限数字", name)
        if absolute:
            value = abs(value)
        spec = parameter_values.get(name, {})
        minimum = spec.get("minimum")
        maximum = spec.get("maximum")
        if (minimum is not None and value < float(minimum)) or (maximum is not None and value > float(maximum)):
            raise argument_error(f"运动预设参数 {name} 超出范围", name)
        return value

    def _integer(name: str) -> int:
        default = parameter_values.get(name, {}).get("default", 0)
        raw = change.get(name, default)
        if isinstance(raw, bool):
            raise argument_error(f"运动预设参数 {name} 必须是整数", name)
        if isinstance(raw, float) and not raw.is_integer():
            raise argument_error(f"运动预设参数 {name} 必须是整数", name)
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise argument_error(f"运动预设参数 {name} 必须是整数", name) from exc
        spec = parameter_values.get(name, {})
        minimum = spec.get("minimum")
        maximum = spec.get("maximum")
        if (minimum is not None and value < int(minimum)) or (maximum is not None and value > int(maximum)):
            raise argument_error(f"运动预设参数 {name} 超出范围", name)
        return value

    amount = _number("amount", absolute=True) if "amount" in parameter_values else 0.0
    transform = clip.get("transform") if isinstance(clip.get("transform"), dict) else {}
    position = transform.get("position") if isinstance(transform.get("position"), dict) else {}
    scale = float(transform.get("scale", 1.0))
    x = float(position.get("x", transform.get("position_x", 0.5)))
    y = float(position.get("y", transform.get("position_y", 0.5)))
    ease = "ease_in_out"
    if preset == "zoom_in":
        _set_keyframe_track(clip, "transform.scale", [(start_tick, scale, ease), (end_tick, scale * (1 + amount), ease)])
    elif preset == "zoom_out":
        _set_keyframe_track(clip, "transform.scale", [(start_tick, scale * (1 + amount), ease), (end_tick, scale, ease)])
    elif preset == "pan_left":
        _set_keyframe_track(clip, "transform.position.x", [(start_tick, x + amount / 2, ease), (end_tick, x - amount / 2, ease)])
    elif preset == "pan_right":
        _set_keyframe_track(clip, "transform.position.x", [(start_tick, x - amount / 2, ease), (end_tick, x + amount / 2, ease)])
    elif preset == "pan_up":
        _set_keyframe_track(clip, "transform.position.y", [(start_tick, y + amount / 2, ease), (end_tick, y - amount / 2, ease)])
    elif preset == "pan_down":
        _set_keyframe_track(clip, "transform.position.y", [(start_tick, y - amount / 2, ease), (end_tick, y + amount / 2, ease)])
    elif preset == "ken_burns":
        _set_keyframe_track(clip, "transform.scale", [(start_tick, scale, ease), (end_tick, scale * (1 + amount), ease)])
        _set_keyframe_track(clip, "transform.position.x", [(start_tick, x - amount / 3, ease), (end_tick, x + amount / 3, ease)])
        _set_keyframe_track(clip, "transform.position.y", [(start_tick, y + amount / 3, ease), (end_tick, y - amount / 3, ease)])
    elif preset == "rotate_in":
        degrees = _number("degrees")
        _set_keyframe_track(clip, "transform.rotation", [(start_tick, degrees, ease), (end_tick, 0.0, ease)])
    elif preset == "rotate_out":
        degrees = _number("degrees")
        _set_keyframe_track(clip, "transform.rotation", [(start_tick, 0.0, ease), (end_tick, degrees, ease)])
    elif preset == "fade_in":
        _set_keyframe_track(clip, "transform.opacity", [(start_tick, 0.0, "linear"), (end_tick, 1.0, ease)])
    elif preset == "fade_out":
        _set_keyframe_track(clip, "transform.opacity", [(start_tick, 1.0, ease), (end_tick, 0.0, "linear")])
    elif preset == "shake":
        points = _integer("points")
        values = []
        for index in range(points):
            progress = index / (points - 1)
            sign = -1 if index % 2 else 1
            values.append((round(start_tick + (end_tick - start_tick) * progress), x + sign * amount / 3, "linear"))
        _set_keyframe_track(clip, "transform.position.x", values)
    return {
        "preset": preset,
        "requested_preset": requested,
        "catalog_version": MOTION_PRESET_CATALOG_VERSION,
        "properties": definition["properties"],
        "start_tick": start_tick,
        "end_tick": end_tick,
        "amount": amount,
        **({"degrees": _number("degrees")} if "degrees" in parameter_values else {}),
        **({"points": _integer("points")} if "points" in parameter_values else {}),
    }


def command_motion_apply(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    sequence = find_sequence(project, args.sequence_id)
    before_project = copy.deepcopy(project)
    working = copy.deepcopy(project) if args.dry_run else project
    target_sequence = find_sequence(working, sequence["id"])
    track, clip = _find_clip(target_sequence, args.clip_id, args.track_id)
    change: dict[str, Any] = {"preset": args.preset}
    for field in ("amount", "degrees", "points", "start_tick", "end_tick"):
        value = getattr(args, field, None)
        if value is not None:
            change[field] = value
    motion = _apply_motion_preset(clip, change)
    validation = validate_project(root, working, strict_rights=False)
    if not validation["ok"]:
        raise AppError("PROJECT_INVALID", "运动预设会生成无效项目", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    if args.dry_run:
        return _envelope(
            "motion.apply",
            args,
            status="planned",
            data={"sequence_id": target_sequence["id"], "track_id": track["id"], "clip_id": clip["id"], "motion": motion, "clip": clip, "validation": validation},
        )
    snapshot = create_snapshot(root, before_project, label="before-motion-apply")
    operation_id = new_id("op")
    working.setdefault("provenance", {}).setdefault("change_log", []).append(
        {
            "operation_id": operation_id,
            "command": "motion.apply",
            "at": now_iso(),
            "sequence_id": target_sequence["id"],
            "track_id": track["id"],
            "clip_id": clip["id"],
            "motion": motion,
            "before_snapshot_id": snapshot["snapshot_id"],
        }
    )
    save_project(root, working)
    _operation(
        root,
        operation_id,
        {
            "operation_id": operation_id,
            "command": "motion.apply",
            "status": "succeeded",
            "project_id": working["project"]["id"],
            "sequence_id": target_sequence["id"],
            "track_id": track["id"],
            "clip_id": clip["id"],
            "motion": motion,
            "before_snapshot_id": snapshot["snapshot_id"],
            "created_at": now_iso(),
        },
    )
    return _envelope(
        "motion.apply",
        args,
        data={"sequence_id": target_sequence["id"], "track_id": track["id"], "clip_id": clip["id"], "motion": motion, "clip": clip, "validation": validation, "before_snapshot": snapshot},
        operation_id=operation_id,
    )


def _split_clip_keyframes(clip: dict[str, Any], split_tick: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    left = copy.deepcopy(clip.get("keyframes", []))
    right = copy.deepcopy(clip.get("keyframes", []))
    for tracks, offset, upper in ((left, 0, split_tick), (right, split_tick, int(clip.get("duration_tick", 0)))):
        for track in tracks:
            points = []
            for point in track.get("keyframes", []):
                at = int(point.get("at_tick", 0))
                if offset == 0 and at <= upper:
                    points.append(point)
                elif offset == split_tick and at >= offset and at <= upper:
                    updated = dict(point)
                    updated["at_tick"] = at - offset
                    points.append(updated)
            track["keyframes"] = points
    return [track for track in left if track.get("keyframes")], [track for track in right if track.get("keyframes")]


def _adjust_source_for_duration(clip: dict[str, Any], new_duration: int) -> None:
    old_duration = max(1, int(clip.get("duration_tick", 1)))
    source_span = max(1, int(clip.get("source_out_tick", 1)) - int(clip.get("source_in_tick", 0)))
    speed = abs(float(clip.get("speed", 1.0) or 1.0))
    source_span = max(1, int(round(new_duration * speed)))
    if bool(clip.get("reverse")):
        clip["source_in_tick"] = max(0, int(clip.get("source_out_tick", source_span)) - source_span)
    else:
        clip["source_out_tick"] = int(clip.get("source_in_tick", 0)) + source_span
    clip["duration_tick"] = max(1, int(new_duration))


def _source_shift(clip: dict[str, Any], delta: int, asset: dict[str, Any]) -> None:
    source_in = int(clip.get("source_in_tick", 0)) + int(delta)
    source_out = int(clip.get("source_out_tick", 0)) + int(delta)
    total = int(asset.get("probe", {}).get("duration_tick", 0) or 0)
    if source_in < 0 or source_out <= source_in or (total and source_out > total):
        raise argument_error("slip_clip 会越过素材边界", "delta_source_tick")
    clip["source_in_tick"] = source_in
    clip["source_out_tick"] = source_out


def command_timeline_edit(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    sequence = find_sequence(project, args.sequence_id)
    expected = args.expected_project_sha256
    actual = edit_project_fingerprint(project)
    if expected is not None and expected != actual:
        raise AppError('EDIT_PROJECT_CHANGED', '项目已偏离已规划的摘要，请重新规划', exit_code=2, path='expected_project_sha256')
    initial_validation = validate_project(root, project, strict_rights=False)
    if not initial_validation['ok']:
        raise AppError('PROJECT_INVALID', '编辑前工程无效', exit_code=2, cause=json.dumps(initial_validation, ensure_ascii=False))
    candidate, plan = build_edit_plan(project, sequence['id'], _load_changes(args.input))
    validation = validate_project(root, candidate, strict_rights=False)
    if not validation['ok']:
        raise AppError('PROJECT_INVALID', '时间线编辑会生成无效项目', exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    warnings = ([{'code': 'EDIT_RIPPLE_SHORTFALL', 'message': '同步轨道空间不足，统一保留未闭合 tick；没有单轨回退',
                  'short_tick': plan['short_tick']}] if plan['short_tick'] else [])
    warnings.extend(plan.get('warnings', []))
    data = {'sequence_id': sequence['id'], 'plan': plan, 'validation': validation}
    if args.dry_run:
        return _envelope('timeline.edit', args, status='planned', data=data, warnings=warnings)
    snapshot = create_snapshot(root, project, label='before-timeline-edit')
    operation_id = new_id('op')
    record = {'operation_id': operation_id, 'command': 'timeline.edit', 'created_at': now_iso(),
              'before_snapshot_id': snapshot['snapshot_id'], 'plan': plan}
    candidate.setdefault('provenance', {}).setdefault('change_log', []).append(copy.deepcopy(record))
    save_project(root, candidate)
    _operation(root, operation_id, {**record, 'status': 'succeeded'})
    return _envelope('timeline.edit', args, data={**data, 'before_snapshot': snapshot},
                     warnings=warnings, operation_id=operation_id)


def command_timeline_transition(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    sequence = find_sequence(project, args.sequence_id)
    if args.expected_project_sha256 is not None and args.expected_project_sha256 != edit_project_fingerprint(project):
        raise AppError('EDIT_PROJECT_CHANGED', '项目已偏离规划摘要，请重新规划', exit_code=2)
    validation = validate_project(root, project, strict_rights=False)
    if not validation['ok']:
        raise AppError('PROJECT_INVALID', '转场编辑前工程无效', exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    candidate, plan = build_source_transition_plan(project, sequence['id'], _load_changes(args.input))
    validation = validate_project(root, candidate, strict_rights=False)
    if not validation['ok']:
        raise AppError('PROJECT_INVALID', '转场编辑后工程无效', exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    data = {'sequence_id': sequence['id'], 'plan': plan, 'validation': validation}
    if args.dry_run:
        return _envelope('timeline.transition', args, status='planned', data=data)
    snapshot = create_snapshot(root, project, label='before-source-transition')
    operation_id = new_id('op')
    record = {'operation_id': operation_id, 'command': 'timeline.transition', 'created_at': now_iso(),
              'before_snapshot_id': snapshot['snapshot_id'], 'plan': plan}
    candidate.setdefault('provenance', {}).setdefault('change_log', []).append(copy.deepcopy(record))
    save_project(root, candidate)
    _operation(root, operation_id, {**record, 'status': 'succeeded'})
    return _envelope('timeline.transition', args, data={**data, 'before_snapshot': snapshot}, operation_id=operation_id)


def command_timeline_compose(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    changes = _load_changes(args.input)
    sequence = find_sequence(project, changes.get("sequence_id") or args.sequence_id)
    before_project = copy.deepcopy(project)
    if args.dry_run:
        working = json.loads(json.dumps(project))
    else:
        working = project
    operations = changes.get("operations")
    if operations is None:
        operations = [{"op": "append_clip", **item} for item in changes.get("clips", [])]
    applied: list[dict[str, Any]] = []
    for change in operations:
        operation = change.get("op", "append_clip")
        if operation in WINDOW_OPERATIONS:
            target_sequence = find_sequence(working, change.get('sequence_id') or sequence['id'])
            from .magnetic_mode import enabled as magnet_enabled, main_track as magnet_main, trim as magnet_trim
            is_main_trim = False
            if operation == 'trim_clip' and magnet_enabled(target_sequence):
                trim_track, trim_clip = _find_clip(target_sequence, change.get('clip_id', change.get('id')), change.get('track_id'))
                is_main_trim = trim_track is magnet_main(target_sequence)
            if is_main_trim:
                working, plan = magnet_trim(working, target_sequence['id'], trim_track, trim_clip, change)
            else:
                working, plan = apply_window_operation(working, target_sequence['id'], change)
            applied.append({'op': operation, 'plan': plan})
        elif operation == 'source_transition':
            target_sequence = find_sequence(working, change.get('sequence_id') or sequence['id'])
            working, plan = build_source_transition_plan(working, target_sequence['id'], change.get('transition'))
            applied.append({'op': operation, 'plan': plan})
        elif operation == 'linked_edit':
            edit_validation = validate_project(root, working, strict_rights=False)
            if not edit_validation['ok']:
                raise AppError('PROJECT_INVALID', '关联编辑前批次工程无效', exit_code=2,
                               cause=json.dumps(edit_validation, ensure_ascii=False))
            target_sequence = find_sequence(working, change.get('sequence_id') or sequence['id'])
            working, plan = build_edit_plan(working, target_sequence['id'], change.get('edit'))
            applied.append({'op': operation, 'plan': plan})
        elif operation == "append_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track = find_track(target_sequence, change.get("track_id"), change.get("track_kind", "video"))
            clip = _clip_from_change(change, track)
            if clip.get("speed_curve") is not None and "duration_tick" not in change:
                source_span = max(1, int(clip.get("source_out_tick", 1)) - int(clip.get("source_in_tick", 0)))
                curve_duration = speed_curve_duration_seconds(clip, source_span, int(working["settings"]["timebase"]["ticks_per_second"]))
                if curve_duration is not None:
                    clip["duration_tick"] = max(1, int(round(curve_duration * int(working["settings"]["timebase"]["ticks_per_second"]))))
            if any(existing.get("id") == clip["id"] for existing in track.get("clips", [])):
                raise argument_error(f"片段 ID 已存在: {clip['id']}")
            preset = change.get("motion_preset") or change.get("preset")
            applied_item = {"op": operation, "track_id": track["id"], "clip": clip}
            if preset:
                applied_item["motion"] = _apply_motion_preset(clip, {**change, "motion_preset": preset})
            from .magnetic_mode import enabled as magnet_enabled, main_track as magnet_main, insert as magnet_insert
            if magnet_enabled(target_sequence) and track is magnet_main(target_sequence):
                working, applied_item['plan'] = magnet_insert(working, target_sequence['id'], track, clip, clip['timeline_start_tick'])
                _, applied_item['clip'] = _find_clip(find_sequence(working, target_sequence['id']), clip['id'], track['id'])
            else:
                track.setdefault("clips", []).append(clip)
                target_sequence["duration_tick"] = max(int(target_sequence.get("duration_tick", 1)), clip["timeline_start_tick"] + clip["duration_tick"])
            applied.append(applied_item)
        elif operation == "add_sequence":
            sequence_id = str(change.get("id") or change.get("sequence_id") or new_id("seq"))
            if any(item.get("id") == sequence_id for item in working.get("sequences", [])):
                raise argument_error(f"序列 ID 已存在: {sequence_id}", "id")
            target = {"id": sequence_id, "name": str(change.get("name") or sequence_id), "duration_tick": max(1, int(change.get("duration_tick", 1))), "tracks": [], "markers": []}
            if 'canvas' in change:
                validate_canvas(change['canvas'])
                target['canvas'] = copy.deepcopy(change['canvas'])
            if 'audio_routing' in change:
                target['audio_routing'] = copy.deepcopy(change['audio_routing'])
            if 'editing' in change:
                target['editing'] = copy.deepcopy(change['editing'])
            for track_kind, track_id, order in (("video", f"{sequence_id}_video_1", 0), ("audio", f"{sequence_id}_audio_1", 0)):
                target["tracks"].append({"id": str(change.get(f"{track_kind}_track_id") or track_id), "kind": track_kind, "order": order, "muted": False, "locked": False, "clips": []})
            working.setdefault("sequences", []).append(target)
            applied.append({"op": operation, "sequence": target})
        elif operation == "update_sequence":
            target = find_sequence(working, change.get('sequence_id') or change.get('id') or sequence['id'])
            patch = change.get('patch')
            if not isinstance(patch, dict) or not patch or set(patch)-{'name', 'duration_tick', 'canvas', 'markers', 'editing', 'audio_routing'}:
                raise argument_error('update_sequence.patch 支持 name/duration_tick/canvas/markers/editing/audio_routing；轨道与片段通过专用操作编辑', 'patch')
            if 'canvas' in patch:
                validate_canvas(patch['canvas'])
            target.update(copy.deepcopy(patch))
            applied.append({'op': operation, 'sequence': copy.deepcopy(target)})
        elif operation == "append_sequence_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track = find_track(target_sequence, change.get("track_id"), change.get("track_kind", "video"))
            nested_change = {**change, "nested_sequence_id": change.get("nested_sequence_id") or change.get("child_sequence_id")}
            clip = _clip_from_change(nested_change, track)
            if not clip.get("sequence_id"):
                raise argument_error("append_sequence_clip 必须提供 nested_sequence_id", "nested_sequence_id")
            if any(existing.get("id") == clip["id"] for existing in track.get("clips", [])):
                raise argument_error(f"片段 ID 已存在: {clip['id']}")
            from .magnetic_mode import enabled as magnet_enabled, main_track as magnet_main, insert as magnet_insert
            item = {"op": operation, "track_id": track["id"], "clip": clip}
            if magnet_enabled(target_sequence) and track is magnet_main(target_sequence):
                working, item['plan'] = magnet_insert(working, target_sequence['id'], track, clip, clip['timeline_start_tick'])
                _, item['clip'] = _find_clip(find_sequence(working, target_sequence['id']), clip['id'], track['id'])
            else:
                track.setdefault("clips", []).append(clip)
                target_sequence["duration_tick"] = max(int(target_sequence.get("duration_tick", 1)), clip["timeline_start_tick"] + clip["duration_tick"])
            applied.append(item)
        elif operation == "slip_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            cid = clip['id']
            working, plan = build_edit_plan(working, target_sequence['id'], {
                'action': 'slip', 'clip_id': cid, 'delta_source_tick': change.get('delta_source_tick', 0),
                'options': {'linked': change.get('linked', False)}})
            updated = find_sequence(working, target_sequence['id'])
            track, clip = _find_clip(updated, cid, track['id'])
            applied.append({"op": operation, "track_id": track["id"], "clip": clip, 'plan': plan})
        elif operation == "slide_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            new_start = int(clip.get("timeline_start_tick", 0)) + int(change.get("delta_tick", 0))
            if new_start < 0:
                raise argument_error("slide_clip 不能移动到负时间", "delta_tick")
            from .magnetic_mode import enabled as magnet_enabled, main_track as magnet_main
            item = {"op": operation, "track_id": track["id"], "clip": clip}
            if magnet_enabled(target_sequence) and track is magnet_main(target_sequence):
                working, item['plan'] = build_edit_plan(working, target_sequence['id'],
                    {'action': 'shift', 'clip_ids': [clip['id']], 'delta_tick': change.get('delta_tick', 0)})
                _, item['clip'] = _find_clip(find_sequence(working, target_sequence['id']), clip['id'], track['id'])
            else:
                clip["timeline_start_tick"] = new_start
                _recompute_sequence_duration(target_sequence)
            applied.append(item)
        elif operation == 'retime_clip':
            target_sequence = find_sequence(working, change.get('sequence_id') or sequence['id'])
            if set(change)-{'op','sequence_id','clip_id','clip_ids','transform','options','sync_content'} or ('clip_id' in change and 'clip_ids' in change):
                raise argument_error('retime_clip 需要 clip_id 或 clip_ids，以及 transform/options/sync_content')
            query = {k:copy.deepcopy(v) for k,v in change.items() if k in {'transform','options','sync_content'}}
            query.update(action='retime',clip_ids=change.get('clip_ids',[change.get('clip_id')]))
            working, plan = build_edit_plan(working,target_sequence['id'],query)
            applied.append({'op':operation,'plan':plan})
        elif operation == "set_clip_speed":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            speed = float(change.get("speed", 1.0))
            if speed <= 0:
                raise argument_error("speed 必须大于 0", "speed")
            window = clip.get('presentation_window')
            if window and (window['offset_tick'] != 0 or window['authored_duration_tick'] != clip['duration_tick']):
                raise AppError('CLIP_WINDOW_AUTHOR_EDIT_REQUIRES_FULL_TAKE', '请在完整作者片段上修改速度后重新裁切；当前选区不会隐式扩展', exit_code=2)
            clip["speed"] = speed
            if str(change.get("duration_mode", "preserve_source")) == "preserve_source":
                source_span = max(1, int(clip.get("source_out_tick", 1)) - int(clip.get("source_in_tick", 0)))
                clip["duration_tick"] = max(1, int(round(source_span / speed)))
            if window:
                window['authored_duration_tick'] = clip['duration_tick']
            _recompute_sequence_duration(target_sequence)
            applied.append({"op": operation, "track_id": track["id"], "clip": clip})
        elif operation == "set_clip_speed_curve":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            window = clip.get('presentation_window')
            if window and (window['offset_tick'] != 0 or window['authored_duration_tick'] != clip['duration_tick']):
                raise AppError('CLIP_WINDOW_AUTHOR_EDIT_REQUIRES_FULL_TAKE', '请在完整作者片段上修改变速曲线后重新裁切',exit_code=2)
            curve = change.get("speed_curve") if isinstance(change.get("speed_curve"), (dict, list)) else {"keyframes": change.get("keyframes", [])}
            if isinstance(curve, dict):
                keyframes = curve.get("keyframes")
            else:
                keyframes = curve
            if not isinstance(keyframes, list) or not keyframes:
                raise argument_error("set_clip_speed_curve 需要非空 keyframes", "speed_curve.keyframes")
            clip["speed_curve"] = curve
            source_span = max(1, int(clip.get("source_out_tick", 1)) - int(clip.get("source_in_tick", 0)))
            curve_duration = speed_curve_duration_seconds(clip, source_span, int(working["settings"]["timebase"]["ticks_per_second"]))
            if curve_duration is not None and str(change.get("duration_mode", "preserve_source")) == "preserve_source":
                clip["duration_tick"] = max(1, int(round(curve_duration * int(working["settings"]["timebase"]["ticks_per_second"]))))
            if window:
                window['authored_duration_tick'] = clip['duration_tick']
            _clamp_clip_keyframes(clip)
            _recompute_sequence_duration(target_sequence)
            applied.append({"op": operation, "track_id": track["id"], "clip": clip, "curve_duration_seconds": curve_duration})
        elif operation == "reverse_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            window = clip.get('presentation_window')
            if window and (window['offset_tick'] != 0 or window['authored_duration_tick'] != clip['duration_tick']):
                raise AppError('CLIP_WINDOW_AUTHOR_EDIT_REQUIRES_FULL_TAKE','请先对完整作者片段倒放，再重新裁切；不隐式重排选区动画或定格',exit_code=2)
            clip["reverse"] = bool(change.get("enabled", not bool(clip.get("reverse", False))))
            applied.append({"op": operation, "track_id": track["id"], "clip_id": clip["id"], "reverse": clip["reverse"]})
        elif operation == "freeze_frame":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            window = clip.get('presentation_window')
            if window and (window['offset_tick'] != 0 or window['authored_duration_tick'] != clip['duration_tick']):
                raise AppError('CLIP_WINDOW_AUTHOR_EDIT_REQUIRES_FULL_TAKE', '请在完整作者片段上添加定格后重新裁切；当前选区不会隐式扩展', exit_code=2)
            freeze_duration = int(change.get("duration_tick", 0))
            if freeze_duration <= 0:
                raise argument_error("freeze_frame 需要正 duration_tick", "duration_tick")
            at_tick = int(change.get("at_tick", int(clip.get("duration_tick", 1))))
            if at_tick < 0 or at_tick > int(clip.get("duration_tick", 1)):
                raise argument_error("freeze_frame 的 at_tick 越过片段", "at_tick")
            audio_mode = str(change.get("audio_mode", "silence")).lower()
            if audio_mode not in {"silence", "continue"}:
                raise argument_error("freeze_frame 的 audio_mode 只支持 silence 或 continue", "audio_mode")
            clip["freeze"] = {"at_tick": at_tick, "duration_tick": freeze_duration, "audio_mode": audio_mode}
            clip["duration_tick"] = int(clip.get("duration_tick", 1)) + freeze_duration
            if window:
                window['authored_duration_tick'] = clip['duration_tick']
            _clamp_clip_keyframes(clip)
            _recompute_sequence_duration(target_sequence)
            applied.append({"op": operation, "track_id": track["id"], "clip": clip})
        elif operation == "add_track":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track = _add_track(target_sequence, change)
            applied.append({"op": operation, "sequence_id": target_sequence["id"], "track": track})
        elif operation == "remove_track":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track_id = str(change.get("track_id") or change.get("id") or "")
            track = find_track(target_sequence, track_id, None)
            if track.get("locked"):
                raise argument_error(f"轨道已锁定，不能删除: {track_id}", "track_id")
            if track.get("clips") and not bool(change.get("force", False)):
                raise argument_error("含片段的轨道需要 force=true 才能删除", "force")
            target_sequence["tracks"] = [item for item in target_sequence.get("tracks", []) if item is not track]
            _recompute_sequence_duration(target_sequence)
            applied.append({"op": operation, "sequence_id": target_sequence["id"], "track_id": track_id})
        elif operation == "update_track":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track = find_track(target_sequence, change.get("track_id"), None)
            patch = change.get("patch") if isinstance(change.get("patch"), dict) else change
            for field in ("muted", "locked", "order", "overlap_policy", "audio", "sync_lock"):
                if field in patch:
                    track[field] = copy.deepcopy(patch[field]) if field == "audio" else patch[field]
            applied.append({"op": operation, "track_id": track["id"], "track": track})
        elif operation == "remove_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            from .magnetic_mode import enabled as magnet_enabled, main_track as magnet_main
            item = {"op": operation, "track_id": track["id"], "clip_id": clip['id']}
            if magnet_enabled(target_sequence) and track is magnet_main(target_sequence):
                working, item['plan'] = build_edit_plan(working, target_sequence['id'],
                    {'action': 'remove', 'clip_ids': [clip['id']]})
            else:
                track["clips"] = [value for value in track.get("clips", []) if value is not clip]
                _recompute_sequence_duration(target_sequence)
            applied.append(item)
        elif operation == "update_clip":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            patch = change.get("patch") if isinstance(change.get("patch"), dict) else change
            if "id" in patch or "clip_id" in patch:
                raise argument_error("update_clip 不允许修改片段 ID", "patch")
            for field in ("asset_id", "sequence_id", "timeline_start_tick", "duration_tick", "source_in_tick", "source_out_tick", "speed", "speed_curve", "reverse", "freeze", "crop", "transform", "keyframes", "effects", "transition_in", "transition_out", "subtitle", "generator", "audio", "blend", "mask", "tracking_binding", "link_id"):
                if field in patch:
                    clip[field] = patch[field]
            _clamp_clip_keyframes(clip)
            _recompute_sequence_duration(target_sequence)
            applied.append({"op": operation, "track_id": track["id"], "clip": clip})
        elif operation == "apply_motion_preset":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            track, clip = _find_clip(target_sequence, str(change.get("clip_id") or change.get("id") or ""), change.get("track_id"))
            motion = _apply_motion_preset(clip, change)
            applied.append({"op": operation, "track_id": track["id"], "clip_id": clip["id"], "motion": motion})
        elif operation == "set_sequence_duration":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            duration_tick = int(change.get("duration_tick", 0))
            if duration_tick <= 0:
                raise argument_error("duration_tick 必须大于 0", "duration_tick")
            max_end = max((int(clip.get("timeline_start_tick", 0)) + int(clip.get("duration_tick", 0)) for track in target_sequence.get("tracks", []) for clip in track.get("clips", [])), default=0)
            if duration_tick < max_end and not bool(change.get("trim", False)):
                raise argument_error("序列时长不能短于片段末尾；需要 trim=true 才能继续", "duration_tick")
            target_sequence["duration_tick"] = duration_tick
            if change.get("trim"):
                for track in target_sequence.get("tracks", []):
                    track["clips"] = [clip for clip in track.get("clips", []) if int(clip.get("timeline_start_tick", 0)) < duration_tick]
                    for clip in track.get("clips", []):
                        end = int(clip.get("timeline_start_tick", 0)) + int(clip.get("duration_tick", 0))
                        if end > duration_tick:
                            clip["duration_tick"] = max(1, duration_tick - int(clip.get("timeline_start_tick", 0)))
                        _clamp_clip_keyframes(clip)
            applied.append({"op": operation, "sequence_id": target_sequence["id"], "duration_tick": target_sequence["duration_tick"]})
        elif operation == "add_marker":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            marker = {"id": change.get("id") or new_id("marker"), "at_tick": int(change.get("at_tick", 0)), "label": change.get("label", "")}
            if any(item.get("id") == marker["id"] for item in target_sequence.get("markers", [])):
                raise argument_error(f"标记 ID 已存在: {marker['id']}", "id")
            target_sequence.setdefault("markers", []).append(marker)
            applied.append({"op": operation, "marker": marker})
        elif operation == "remove_marker":
            target_sequence = find_sequence(working, change.get("sequence_id") or sequence["id"])
            marker_id = str(change.get("marker_id") or change.get("id") or "")
            before = len(target_sequence.get("markers", []))
            target_sequence["markers"] = [item for item in target_sequence.get("markers", []) if item.get("id") != marker_id]
            if len(target_sequence["markers"]) == before:
                raise argument_error(f"找不到标记: {marker_id}", "marker_id")
            applied.append({"op": operation, "sequence_id": target_sequence["id"], "marker_id": marker_id})
        else:
            raise argument_error(f"不支持的时间线操作: {operation}")
    validation = validate_project(root, working, strict_rights=False)
    if not validation["ok"]:
        raise AppError("PROJECT_INVALID", "时间线变更会生成无效项目", exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
    if args.dry_run:
        return _envelope("timeline.compose", args, status="planned", data={"applied": applied, "validation": validation})
    snapshot = create_snapshot(root, before_project, label="before-timeline-compose")
    operation_id = new_id("op")
    working.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "timeline.compose", "input": str(Path(args.input).resolve()), "at": now_iso(), "changes": applied, "before_snapshot_id": snapshot["snapshot_id"]})
    save_project(root, working)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "timeline.compose", "status": "succeeded", "changes": applied, "before_snapshot_id": snapshot["snapshot_id"], "created_at": now_iso()})
    return _envelope("timeline.compose", args, data={"sequence_id": sequence["id"], "applied": applied, "validation": validation, "before_snapshot": snapshot}, operation_id=operation_id)


def command_validate(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    report = validate_project(root, project, strict_rights=args.strict_rights, target=args.target)
    if args.report:
        report_path = Path(args.report).expanduser().resolve()
    else:
        report_path = root / "validation" / f"validation_{new_id('run')}.json"
    atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), "project_id": project["project"]["id"], **report})
    status = "succeeded" if report["ok"] else "failed"
    errors = report.get("errors", [])
    return _envelope("validate", args, data={"report": str(report_path), **report}, status=status, warnings=report.get("warnings", []), errors=errors)


def command_rights_check(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    result = check_project_rights(project, load_ledger(root), args.target, strict=True)
    status = "succeeded" if result["ok"] else "failed"
    return _envelope("rights.check", args, data=result, status=status, errors=result.get("failures", []), warnings=result.get("warnings", []))


def command_rights_list(args: argparse.Namespace) -> dict[str, Any]:
    root, _project = load_project(args.project)
    records = active_records(load_ledger(root))
    if args.status:
        records = [record for record in records if record.get("verification_status") == args.status]
    return _envelope("rights.list", args, data={"records": records, "count": len(records)})


def command_rights_history(args: argparse.Namespace) -> dict[str, Any]:
    root, _project = load_project(args.project)
    ledger = load_ledger(root)
    history = record_history(ledger, args.asset_id)
    events = [event for event in ledger.get("events", []) if str(event.get("asset_id")) == str(args.asset_id)]
    if not history:
        raise AppError("RIGHTS_RECORD_MISSING", f"找不到 Rights Ledger 记录: {args.asset_id}", exit_code=3, path="asset_id")
    return _envelope("rights.history", args, data={"asset_id": args.asset_id, "records": history, "events": events, "decisions": disposition_decisions(ledger, args.asset_id), "effective_decisions": effective_disposition_decisions(ledger, args.asset_id), "count": len(history)})


def command_rights_update(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    ledger = load_ledger(root)
    patch: dict[str, Any] = {}
    if args.patch:
        patch_path = Path(require_local_reference(args.patch, field="--patch")).expanduser().resolve()
        patch_payload = load_json(patch_path)
        if not isinstance(patch_payload, dict):
            raise argument_error("--patch 顶层必须是 JSON 对象", "--patch")
        patch.update(patch_payload)
    flags = {
        "verification_status": args.status,
        "source_url": args.source_url,
        "source_version": args.source_version,
        "retrieved_at": args.retrieved_at,
        "creator": args.creator,
        "license_spdx": args.license_spdx,
        "license_url": args.license_url,
        "attribution": args.attribution,
        "evidence": args.evidence,
        "expires_at": args.expires_at,
        "takedown_status": args.takedown_status,
        "permitted_uses": args.permitted_use,
        "permitted_channels": args.permitted_channel,
        "restrictions": args.restriction,
    }
    patch.update({key: value for key, value in flags.items() if value is not None})
    planned_ledger = copy.deepcopy(ledger)
    result = revise_record(planned_ledger, args.asset_id, patch, reason=args.reason, actor=args.actor, reopen=args.reopen)
    if args.dry_run:
        return _envelope("rights.update", args, status="planned", data={"revision": result, "ledger": str(ledger_file(root))})
    snapshot = create_snapshot(root, project, label=f"rights-{args.asset_id}-revision")
    operation_id = new_id("op")
    committed = revise_record(ledger, args.asset_id, patch, reason=args.reason, actor=args.actor, reopen=args.reopen)
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "rights.update", "asset_id": args.asset_id, "record_id": committed["record"]["record_id"], "record_version": committed["record"]["record_version"], "reason": args.reason, "snapshot_id": snapshot["snapshot_id"], "at": now_iso()})
    save_ledger(root, ledger)
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "rights.update", "status": "succeeded", "asset_id": args.asset_id, "record_id": committed["record"]["record_id"], "record_version": committed["record"]["record_version"], "snapshot_id": snapshot["snapshot_id"], "created_at": now_iso()})
    return _envelope("rights.update", args, data={"revision": committed, "snapshot": snapshot, "ledger": str(ledger_file(root))}, operation_id=operation_id)


def command_rights_export(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    output = ensure_inside(root, Path(args.output))
    manifest = release_manifest(project, load_ledger(root), args.target)
    if args.dry_run:
        return _envelope("rights.export", args, status="planned", data={"manifest": manifest, "output": str(output)})
    atomic_write_json(output, manifest)
    status = "succeeded" if manifest["rights_check"]["ok"] else "failed"
    return _envelope("rights.export", args, data={"manifest": manifest, "output": str(output)}, status=status, errors=manifest["rights_check"].get("failures", []), warnings=manifest["rights_check"].get("warnings", []))


def command_rights_batch_update(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    ledger = load_ledger(root)
    input_path = Path(require_local_reference(args.input, field="--input")).expanduser().resolve()
    payload = load_json(input_path)
    updates = payload.get("updates")
    if not isinstance(updates, list) or not updates:
        raise argument_error("Rights Ledger 批量输入必须包含非空 updates 数组", "--input")

    def apply_updates(target_ledger: dict[str, Any]) -> list[dict[str, Any]]:
        planned: list[dict[str, Any]] = []
        for index, item in enumerate(updates):
            if not isinstance(item, dict):
                raise argument_error(f"批量修订第 {index} 项必须是对象", "updates")
            asset_id = str(item.get("asset_id") or "")
            if not asset_id:
                raise argument_error(f"批量修订第 {index} 项缺少 asset_id", "updates")
            patch = copy.deepcopy(item.get("patch"))
            if patch is None:
                patch = {}
                if item.get("status") is not None:
                    patch["verification_status"] = item["status"]
            if not isinstance(patch, dict):
                raise argument_error(f"批量修订第 {index} 项 patch 必须是对象", "updates")
            reason = str(item.get("reason") or "")
            actor = str(item.get("actor") or "ai-ad-editor")
            revision = revise_record(target_ledger, asset_id, patch, reason=reason, actor=actor, reopen=bool(item.get("reopen", False)))
            planned.append({"asset_id": asset_id, "revision": revision})
        return planned

    planned_ledger = copy.deepcopy(ledger)
    planned = apply_updates(planned_ledger)
    if args.dry_run:
        return _envelope("rights.batch-update", args, status="planned", data={"updates": planned, "count": len(planned), "input": str(input_path)})
    snapshot = create_snapshot(root, project, label="rights-batch-update")
    operation_id = new_id("op")
    committed = apply_updates(ledger)
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "rights.batch-update", "count": len(committed), "snapshot_id": snapshot["snapshot_id"], "input": str(input_path), "at": now_iso()})
    save_ledger(root, ledger)
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "rights.batch-update", "status": "succeeded", "count": len(committed), "snapshot_id": snapshot["snapshot_id"], "created_at": now_iso()})
    return _envelope("rights.batch-update", args, data={"updates": committed, "count": len(committed), "snapshot": snapshot, "ledger": str(ledger_file(root))}, operation_id=operation_id)


def command_rights_impact(args: argparse.Namespace) -> dict[str, Any]:
    root, _project = load_project(args.project)
    artifacts = impacted_artifacts(root, args.asset_id)
    return _envelope("rights.impact", args, data={"asset_id": args.asset_id, "artifacts": artifacts, "count": len(artifacts)})


def command_rights_retract(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    ledger = load_ledger(root)
    before = impacted_artifacts(root, args.asset_id)
    patch = {"verification_status": args.status}
    planned_ledger = copy.deepcopy(ledger)
    revision = revise_record(planned_ledger, args.asset_id, patch, reason=args.reason, actor=args.actor)
    if args.dry_run:
        return _envelope("rights.retract", args, status="planned", data={"revision": revision, "impacted_artifacts": before})
    snapshot = create_snapshot(root, project, label=f"rights-{args.asset_id}-retract")
    operation_id = new_id("op")
    committed = revise_record(ledger, args.asset_id, patch, reason=args.reason, actor=args.actor)
    save_ledger(root, ledger)
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "rights.retract", "asset_id": args.asset_id, "status": args.status, "reason": args.reason, "snapshot_id": snapshot["snapshot_id"], "at": now_iso()})
    save_project(root, project)
    after = impacted_artifacts(root, args.asset_id)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "rights.retract", "status": "succeeded", "asset_id": args.asset_id, "record_id": committed["record"]["record_id"], "snapshot_id": snapshot["snapshot_id"], "impacted_artifacts": after, "created_at": now_iso()})
    return _envelope("rights.retract", args, data={"revision": committed, "snapshot": snapshot, "impacted_artifacts": after, "previous_impact": before}, operation_id=operation_id)


def command_rights_decide(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    ledger = load_ledger(root)
    impacted = impacted_artifacts(root, args.asset_id)
    planned_ledger = copy.deepcopy(ledger)
    decision = create_disposition_decision(planned_ledger, args.asset_id, action=args.disposition_action, status=args.status, reason=args.reason, actor=args.actor, target=args.target, replacement_asset_id=args.replacement_asset_id, impacted=impacted, supersedes_decision_id=args.supersedes_decision_id, project=project)
    impacted = decision["affected_artifacts"]
    if args.dry_run:
        return _envelope("rights.decide", args, status="planned", data={"decision": decision, "impacted_artifacts": impacted, "ledger": str(ledger_file(root))})
    snapshot = create_snapshot(root, project, label=f"rights-{args.asset_id}-disposition")
    operation_id = new_id("op")
    committed = create_disposition_decision(ledger, args.asset_id, action=args.disposition_action, status=args.status, reason=args.reason, actor=args.actor, target=args.target, replacement_asset_id=args.replacement_asset_id, impacted=impacted, supersedes_decision_id=args.supersedes_decision_id, project=project)
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "rights.decide", "asset_id": args.asset_id, "action": args.disposition_action, "status": args.status, "decision_id": committed["decision_id"], "snapshot_id": snapshot["snapshot_id"], "at": now_iso()})
    save_ledger(root, ledger)
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "rights.decide", "status": "succeeded", "asset_id": args.asset_id, "action": args.disposition_action, "decision_status": args.status, "decision_id": committed["decision_id"], "snapshot_id": snapshot["snapshot_id"], "impacted_artifacts": impacted, "created_at": now_iso()})
    return _envelope("rights.decide", args, data={"decision": committed, "snapshot": snapshot, "impacted_artifacts": impacted, "ledger": str(ledger_file(root))}, operation_id=operation_id)


def command_rights_apply(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    ledger = load_ledger(root)
    if any(event.get("event") == "disposition_applied" and event.get("decision_id") == args.decision_id for event in ledger.get("events", [])):
        raise AppError("RIGHTS_DISPOSITION_ALREADY_APPLIED", "该历史处置决策已经 apply", exit_code=2, path="decision_id")
    candidate = copy.deepcopy(project)
    applied = apply_disposition_to_project(candidate, ledger, args.decision_id)
    validation = validate_project(root, candidate, strict_rights=False, target="commercial_ad")
    if not validation["ok"]:
        raise AppError("RIGHTS_DISPOSITION_APPLY_INVALID", "处置后的项目未通过结构或时间线校验", exit_code=2, path="project", cause=json.dumps(validation, ensure_ascii=False))
    rights_validation = check_project_rights(candidate, ledger, str(applied["decision"].get("target") or "commercial_ad"), strict=True)
    if not rights_validation["ok"]:
        raise AppError("RIGHTS_DISPOSITION_APPLY_RIGHTS_BLOCKED", "处置后的当前项目未通过最新权利门禁", exit_code=7, path="project", cause=json.dumps(rights_validation, ensure_ascii=False))
    if args.dry_run:
        return _envelope("rights.apply", args, status="planned", data={"applied": applied, "validation": validation, "rights_check": rights_validation, "project": str(project_file(root)), "ledger": str(ledger_file(root))})
    snapshot = create_snapshot(root, project, label=f"before-rights-{args.decision_id}-apply")
    operation_id = new_id("op")
    applied["operation_id"] = operation_id
    ledger.setdefault("events", []).append({"event_id": new_id("rightsevent"), "event": "disposition_applied", "decision_id": args.decision_id, "asset_id": applied["asset_id"], "action": applied["action"], "replacement_asset_id": applied.get("replacement_asset_id"), "operation_id": operation_id, "snapshot_id": snapshot["snapshot_id"], "changed_clips": copy.deepcopy(applied["changed_clips"]), "removed_clips": copy.deepcopy(applied["removed_clips"]), "at": now_iso()})
    candidate.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "rights.apply", "decision_id": args.decision_id, "asset_id": applied["asset_id"], "action": applied["action"], "snapshot_id": snapshot["snapshot_id"], "at": now_iso()})
    save_project(root, candidate)
    save_ledger(root, ledger)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "rights.apply", "status": "succeeded", "decision_id": args.decision_id, "snapshot_id": snapshot["snapshot_id"], "applied": applied, "rights_check": rights_validation, "created_at": now_iso()})
    return _envelope("rights.apply", args, data={"applied": applied, "snapshot": snapshot, "validation": validation, "rights_check": rights_validation, "project": str(project_file(root)), "ledger": str(ledger_file(root))}, operation_id=operation_id)


def _render_settings_for_args(project: dict[str, Any], args: argparse.Namespace) -> tuple[dict[str, Any], str | None]:
    profile = getattr(args, "profile", None)
    width = getattr(args, "width", None)
    height = getattr(args, "height", None)
    if (width is None) != (height is None):
        raise argument_error("--width 与 --height 必须同时提供")
    if profile and profile != "custom" and (width is not None or height is not None):
        raise argument_error("指定预设 --profile 时不能再传 --width/--height；请使用 --profile custom")
    if profile == "custom" and width is None:
        raise argument_error("--profile custom 必须同时提供 --width 与 --height")
    if profile and profile != "custom":
        width, height = OUTPUT_PROFILES[profile]
    settings = copy.deepcopy(project["settings"])
    from .hardware_acceleration import apply_overrides as acceleration_overrides
    acceleration_overrides(settings, vars(args))
    from .projection_opencl import apply_overrides as projection_overrides
    projection_overrides(settings,vars(args))
    sampling = getattr(args, 'sequence_sampling', None)
    memory_mib = getattr(args, 'sequence_memory_mib', None)
    if sampling is not None or memory_mib is not None:
        sampling_patch = sequence_sampling_configuration(settings.get('sequence_sampling'))
        if sampling is not None:
            sampling_patch['method'] = sampling
        if memory_mib is not None:
            if type(memory_mib) is not int or not 1 <= memory_mib <= 65536:
                raise argument_error('--sequence-memory-mib 必须为 1..65536 的整数', 'sequence_memory_mib')
            sampling_patch['max_working_bytes'] = memory_mib*1024*1024
        settings['sequence_sampling'] = sequence_sampling_configuration(sampling_patch)
    else:
        sequence_sampling_configuration(settings.get('sequence_sampling'))
    selected_sequence = find_sequence(project, getattr(args, 'sequence_id', None))
    settings['canvas'] = {**settings.get('canvas', {}), **sequence_canvas(project, selected_sequence)}
    output_patch: dict[str, Any] = {}
    if getattr(args, "container", None) is not None:
        output_patch["container"] = args.container
    video_patch = {key: value for key, value in (("codec", getattr(args, "video_codec", None)), ("crf", getattr(args, "crf", None)), ("bitrate", getattr(args, "video_bitrate", None)), ("pixel_format", getattr(args, "pixel_format", None))) if value is not None}
    audio_patch = {key: value for key, value in (("codec", getattr(args, "audio_codec", None)), ("bitrate", getattr(args, "audio_bitrate", None))) if value is not None}
    if video_patch:
        output_patch["video"] = video_patch
    if audio_patch:
        output_patch["audio"] = audio_patch
    if output_patch:
        existing_output = settings.get("output") if isinstance(settings.get("output"), dict) else {}
        merged_output = copy.deepcopy(existing_output)
        merged_output.update({key: value for key, value in output_patch.items() if key not in {"video", "audio"}})
        for branch in ("video", "audio"):
            if branch in output_patch:
                existing_branch = merged_output.get(branch) if isinstance(merged_output.get(branch), dict) else {}
                existing_branch.update(output_patch[branch])
                merged_output[branch] = existing_branch
        settings["output"] = merged_output
    if width is None:
        normalized = output_settings(settings)
        settings["output"] = normalized
        validate_output_alignment(settings['canvas'], str(normalized['video']['pixel_format']))
        return settings, None
    width = int(width)
    height = int(height)
    if width < 64 or height < 64 or width > 8192 or height > 8192:
        raise argument_error("输出画布必须在 64 到 8192 像素之间")
    settings["canvas"] = dict(project["settings"].get("canvas", {}))
    settings["canvas"].update({"width": width, "height": height})
    settings["output"] = output_settings(settings)
    validate_output_alignment(settings['canvas'], str(settings['output']['video']['pixel_format']))
    return settings, profile or "custom"


def _load_render_resume(root: Path, project: dict[str, Any], sequence: dict[str, Any], operation_id: str) -> dict[str, Any]:
    path = root / "operations" / f"{operation_id}.json"
    if not path.exists():
        raise AppError("RESUME_OPERATION_NOT_FOUND", f"找不到可续跑的渲染操作: {operation_id}", exit_code=3, path=str(path))
    record = load_json(path)
    if record.get("command") != "render" or record.get("status") not in {"failed", "cancelled"}:
        raise AppError("RESUME_NOT_ALLOWED", "只能从 failed 或 cancelled 的 render 操作重建", exit_code=2, path=str(path))
    plan = record.get("plan") if isinstance(record.get("plan"), dict) else {}
    if not record.get("project_fingerprint") or not record.get("input_hashes") or not plan.get("filter_complex"):
        raise AppError("RESUME_METADATA_MISSING", "原渲染操作缺少经过验证的计划或输入指纹，拒绝盲目续跑", exit_code=2, path=str(path))
    if record.get("project_id") and record.get("project_id") != project.get("project", {}).get("id"):
        raise AppError("RESUME_PROJECT_MISMATCH", "续跑操作不属于当前项目", exit_code=2, path=str(path))
    if record.get("sequence_id") and record.get("sequence_id") != sequence.get("id"):
        raise AppError("RESUME_SEQUENCE_MISMATCH", "续跑操作不属于当前序列", exit_code=2, path=str(path))
    return record


def command_cache(args: argparse.Namespace) -> dict[str, Any]:
    from . import reverse_cache,native_video_index,native_audio_clock
    root,_=load_project(args.project)
    cache={'native-video-index':native_video_index,'native-audio-clock':native_audio_clock,'reverse-video':reverse_cache}[args.kind]
    data=(cache.cache_list(root) if args.action=='list' else
        cache.cache_prune(root,keep_bytes=args.keep_mib*1024*1024,dry_run=args.dry_run,key=args.key))
    return _envelope('cache.'+args.action,args,status='planned' if args.dry_run else 'succeeded',data=data)


def command_preview(args: argparse.Namespace) -> dict[str, Any]:
    from . import preview
    from .policy import require_local_reference, resolve_local_path
    root, project = load_project(args.project)
    if args.action == 'cache-list':
        return _envelope('preview.cache-list', args, data=preview.cache_list(root))
    if args.action == 'cache-prune':
        return _envelope('preview.cache-prune', args, status='planned' if args.dry_run else 'succeeded',
            data=preview.cache_prune(root, keep_bytes=args.keep_mib*1024*1024, dry_run=args.dry_run))
    sequence = find_sequence(project, args.sequence_id)
    report = validate_project(root, project, strict_rights=False, target='commercial_ad')
    if not report['ok']:
        raise AppError('PROJECT_INVALID', '项目验证失败，拒绝预览', exit_code=2, cause=json.dumps(report,ensure_ascii=False))
    first = args.frame if args.action == 'frame' else args.start_frame
    last = first+1 if args.action == 'frame' else args.end_frame
    request = preview.plan(project, sequence, start_frame=first, end_frame=last,
        height=args.height, mode=args.action, budget_mib=args.budget_mib)
    output = None
    if args.output:
        require_local_reference(args.output, field='preview.output')
        raw = Path(args.output).expanduser()
        output = preview.plain(root, raw if raw.is_absolute() else root/raw)
    marker = resolve_local_path(root,args.cancel_file,field='preview.cancel') if args.cancel_file else None
    if marker:
        ensure_inside(root,marker)
        if marker.is_relative_to(preview.cache_root(root)) or (output and marker.is_relative_to(output)):
            raise argument_error('取消标记不能位于预览输出或缓存中', '--cancel-file')
    result = preview.preview_project(root,project,sequence,request=request,output=output,cancel_file=marker,dry_run=args.dry_run)
    operation_id = new_id('preview')
    if not args.dry_run:
        _operation(root,operation_id,{'operation_id':operation_id,'command':'preview.'+args.action,
            'status':'succeeded','result':result,'created_at':now_iso()})
    return _envelope('preview.'+args.action,args,status='planned' if args.dry_run else 'succeeded',
        data=result,operation_id=operation_id,warnings=report.get('warnings',[])+result.get('warnings',[]))


def command_surface(args: argparse.Namespace) -> dict[str, Any]:
    from . import float_bundle
    from .float_hdr import parse_signal
    from .float_yuv import YUVSpec
    root,project=load_project(args.project)
    if args.action=='inspect':
        return _envelope('surface.inspect',args,data=float_bundle.inspect_bundle(root,args.input))
    geometry=_load_changes(args.transform_json) if args.transform_json else None
    supplied=any(value is not None for value in (args.yuv_matrix,args.yuv_range,args.chroma_location))
    spec=YUVSpec(args.yuv_matrix,args.yuv_range,args.chroma_location) if supplied else None
    def signal(primaries,transfer,white):
        value=dict(primaries=primaries,transfer=transfer)
        if white is not None:value['white_xy']=white
        return parse_signal(value)
    plan=float_bundle.prepare(root,project,args.asset_id,args.output,
        source_signal=signal(args.source_primaries,args.source_transfer,args.source_white_xy),
        target_signal=signal(args.working_primaries,args.working_transfer,args.working_white_xy),pixel_family=args.pixel_family,
        yuv_spec=spec,scan=args.scan,alpha_association=args.alpha_association,start_frame=args.start_frame,
        stop_frame=args.stop_frame,geometry=geometry,max_output_bytes=args.max_output_mib*1024**2)
    if args.dry_run:return _envelope('surface.export',args,status='planned',data=plan)
    operation_id=new_id('surface')
    result=float_bundle.export_bundle(root,plan,cancel_file=args.cancel_file,
        progress=lambda done,total:_progress(args,operation_id,'progress','surface.export',done/total*100,'提取并转换原生浮点帧'))
    _operation(root,operation_id,{'operation_id':operation_id,'command':'surface.export','status':'succeeded',
        'created_at':now_iso(),'asset_id':args.asset_id,'output':result['output'],'manifest':result['manifest'],
        'manifest_sha256':result['manifest_sha256'],'recipe_sha256':result['recipe_sha256']})
    return _envelope('surface.export',args,data=result,operation_id=operation_id)


def command_render(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    sequence = find_sequence(project, args.sequence_id)
    resume_record = _load_render_resume(root, project, sequence, args.resume) if args.resume else None
    settings_overridden = any(getattr(args, field, None) is not None for field in ("profile", "width", "height", "container", "video_codec", "audio_codec", "crf", "video_bitrate", "audio_bitrate", "pixel_format", "sequence_sampling", "sequence_memory_mib", 'hardware_encode', 'hardware_decode', 'hardware_encoder', 'hardware_decoder', 'hardware_probe_mib','projection_acceleration','projection_device','projection_memory_mib'))
    if resume_record:
        if args.output is None:
            args.output = resume_record.get("output")
    report = validate_project(root, project, strict_rights=args.publish, target="commercial_ad")
    if not report["ok"]:
        raise AppError("PROJECT_INVALID", "项目验证失败，拒绝渲染", exit_code=7 if args.publish else 2, cause=json.dumps(report, ensure_ascii=False))
    if resume_record and not settings_overridden and isinstance(resume_record.get("settings"), dict):
        render_settings, profile = copy.deepcopy(resume_record["settings"]), resume_record.get("profile")
    else:
        render_settings, profile = _render_settings_for_args(project, args)
    if resume_record:
        current_fingerprints = render_fingerprints(project, sequence, render_settings, root)
        if current_fingerprints.get("project_fingerprint") != resume_record.get("project_fingerprint") or current_fingerprints.get("input_hashes") != resume_record.get("input_hashes"):
            raise AppError("RESUME_INPUT_CHANGED", "项目、素材哈希或输出设置已变化，拒绝续跑", exit_code=2, path=str(root / "operations" / f"{args.resume}.json"), retryable=False)
    container = str(render_settings.get("output", {}).get("container", "mp4")) if isinstance(render_settings.get("output"), dict) else "mp4"
    default_extension = {"mp4": ".mp4", "webm": ".webm", "mkv": ".mkv"}.get(container, ".mp4")
    output = Path(args.output).expanduser().resolve() if args.output else root / "renders" / f"{sequence['id']}_{new_id('render')}{default_extension}"
    try:
        output.relative_to(root)
    except ValueError as exc:
        raise argument_error("输出路径必须位于项目目录内", str(output)) from exc
    cancel_file = Path(args.cancel_file).expanduser().resolve() if args.cancel_file else None
    progress_callback = None
    if getattr(args, "progress", "none") == "jsonl":
        progress_callback = lambda operation_id, event_type, percent, message: _progress(args, operation_id, event_type, "render", percent, message)
    result = render_project(root, project, sequence, output, dry_run=args.dry_run, render_settings=render_settings, profile=profile, cancel_file=cancel_file, progress_callback=progress_callback, resume_of=args.resume)
    if result.get("status") == "planned":
        return _envelope("render", args, status="planned", data=result)
    encoder = render_settings.get("output", {}) if isinstance(render_settings.get("output"), dict) else {}
    project.setdefault("outputs", []).append({"id": new_id("output"), "path": str(output), "container": container, "profile": profile, "canvas": render_settings.get("canvas", {}), "video": encoder.get("video", {}), "audio": encoder.get("audio", {}), "target_platform": "generic"})
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"command": "render", "at": now_iso(), "output": str(output), "manifest": result.get("manifest")})
    save_project(root, project)
    _operation(root, result.get("operation_id", new_id("op")), {"operation_id": result.get("operation_id"), "command": "render", "status": "succeeded", "output": str(output), "manifest": result.get("manifest"), "warnings": result.get("warnings", []), "profile": profile, "settings": render_settings, "project_id": project["project"]["id"], "sequence_id": sequence["id"], "project_fingerprint": result.get("project_fingerprint"), "input_hashes": result.get("input_hashes", {}), "resume_of": args.resume, "created_at": now_iso()})
    return _envelope("render", args, data=result, operation_id=result.get("operation_id"), warnings=report.get("warnings", []) + result.get("warnings", []))


def _queue_counts(queue: dict[str, Any]) -> dict[str, int]:
    counts = {status: 0 for status in sorted(JOB_STATUSES)}
    for job in queue.get("jobs", []):
        if isinstance(job, dict) and job.get("status") in counts:
            counts[str(job["status"])] += 1
    return counts


def _queue_job_args(root: Path, job: dict[str, Any], args: argparse.Namespace) -> argparse.Namespace:
    """Map a persisted job to the render settings contract without shell parsing."""
    return argparse.Namespace(
        profile=job.get("profile"),
        width=job.get("width"),
        height=job.get("height"),
        container=job.get("container"),
        video_codec=job.get("video_codec"),
        audio_codec=job.get("audio_codec"),
        crf=job.get("crf"),
        video_bitrate=job.get("video_bitrate"),
        audio_bitrate=job.get("audio_bitrate"),
        pixel_format=job.get("pixel_format"),
        sequence_sampling=job.get('sequence_sampling'),
        projection_acceleration=job.get('projection_acceleration'),
        projection_device=job.get('projection_device'),
        projection_memory_mib=job.get('projection_memory_mib'),
        sequence_memory_mib=job.get('sequence_memory_mib'),
        hardware_encode=job.get('hardware_encode'),
        hardware_decode=job.get('hardware_decode'),
        hardware_encoder=job.get('hardware_encoder'),
        hardware_decoder=job.get('hardware_decoder'),
        hardware_probe_mib=job.get('hardware_probe_mib'),
        output=str(root / str(job["output"])),
        publish=bool(job.get("publish", False)),
        sequence_id=job.get("sequence_id"),
        cancel_file=str(cancel_path(root, str(job["job_id"]))),
        resume=None,
        dry_run=False,
        progress=getattr(args, "progress", "none"),
    )


def _queue_render_one(root: Path, project: dict[str, Any], job: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    """Render one queue job without mutating queue/project metadata.

    Parallel queue workers are deliberately limited to the FFmpeg/render phase.
    The caller commits project outputs, operation records, and queue state from
    one thread so the existing JSON/transaction semantics remain deterministic.
    """
    job_id = str(job["job_id"])
    marker = cancel_path(root, job_id)
    try:
        sequence = find_sequence(project, job.get("sequence_id"))
        report = validate_project(root, project, strict_rights=bool(job.get("publish", False)), target="commercial_ad")
        if not report["ok"]:
            raise AppError("PROJECT_INVALID", "项目验证失败，拒绝执行队列作业", exit_code=7 if job.get("publish") else 2, cause=json.dumps(report, ensure_ascii=False))
        render_args = _queue_job_args(root, job, args)
        render_settings, profile = _render_settings_for_args(project, render_args)
        output = ensure_inside(root, root / str(job["output"]))
        progress_callback = None
        if getattr(args, "progress", "none") == "jsonl":
            progress_callback = lambda operation_id, event_type, percent, message: _progress(args, operation_id, event_type, "queue.render", percent, message)
        result = render_project(root, project, sequence, output, dry_run=False, render_settings=render_settings, profile=profile, cancel_file=marker, progress_callback=progress_callback)
        return {
            "job_id": job_id,
            "status": "succeeded",
            "sequence": sequence,
            "report": report,
            "render_settings": render_settings,
            "profile": profile,
            "output": output,
            "result": result,
        }
    except AppError as exc:
        return {
            "job_id": job_id,
            "status": "cancelled" if exc.code == "CANCELLED" else "failed",
            "error": exc.as_dict(),
            "operation_id": exc.operation_id,
        }


def _queue_output_conflicts(root: Path, jobs: list[dict[str, Any]]) -> list[str]:
    outputs: dict[str, str] = {}
    conflicts: list[str] = []
    for job in jobs:
        candidate = str(ensure_inside(root, root / str(job["output"])).resolve()).casefold()
        previous = outputs.get(candidate)
        if previous is not None:
            conflicts.append(f"{previous}={job['job_id']}")
        else:
            outputs[candidate] = str(job["job_id"])
    return conflicts


def _queue_run_parallel(
    root: Path,
    project: dict[str, Any],
    queue: dict[str, Any],
    selected: list[dict[str, Any]],
    args: argparse.Namespace,
) -> dict[str, Any]:
    """Run a bounded local worker pool while serializing all metadata commits."""
    conflicts = _queue_output_conflicts(root, selected)
    if conflicts:
        raise AppError("QUEUE_OUTPUT_CONFLICT", "并发队列作业不能共享输出路径", exit_code=2, cause=", ".join(conflicts))

    queue_operation_id = new_id("op")
    summary = {"selected": len(selected), "succeeded": 0, "failed": 0, "cancelled": 0, "skipped": 0}
    errors: list[dict[str, Any]] = []
    job_results: list[dict[str, Any]] = []
    runnable: list[dict[str, Any]] = []

    # Claim all selected jobs in one short queue-channel transaction. FFmpeg is
    # never run while this lock is held; queue.cancel can still create markers.
    with queue_cancel_lock(root, timeout=2.0):
        _, latest_project = load_project(root)
        latest_queue = load_queue(root, project_id=latest_project["project"]["id"])
        for selected_job in selected:
            job_id = str(selected_job["job_id"])
            job = find_job(latest_queue, job_id)
            marker = cancel_path(root, job_id)
            if marker.exists() and job.get("status") == "pending":
                set_status(job, "cancelled")
                job["cancel_requested"] = True
                summary["cancelled"] += 1
                job_results.append({"job_id": job_id, "status": "cancelled", "reason": "cancel marker exists before start"})
                marker.unlink(missing_ok=True)
                continue
            marker.unlink(missing_ok=True)
            job["attempts"] = int(job.get("attempts", 0)) + 1
            job["cancel_requested"] = False
            job["operation_id"] = None
            job.pop('reuse', None)
            set_status(job, "running")
            runnable.append(copy.deepcopy(job))
        queue = latest_queue
        project = latest_project
        save_queue(root, queue)

    if runnable:
        worker_count = min(int(args.workers), len(runnable))
        with ThreadPoolExecutor(max_workers=worker_count, thread_name_prefix="ai-ad-editor-queue") as executor:
            # Each worker gets a frozen project snapshot. The main thread adds
            # output/provenance records as futures complete; sharing that
            # mutable dictionary would make render fingerprints order-dependent.
            futures = {executor.submit(_queue_render_one, root, copy.deepcopy(project), job, args): job for job in runnable}
            for future in as_completed(futures):
                rendered = future.result()
                job_id = str(rendered["job_id"])
                job = find_job(queue, job_id)
                try:
                    if rendered["status"] != "succeeded":
                        error = rendered["error"]
                        set_status(job, rendered["status"], error=error, operation_id=rendered.get("operation_id"))
                        summary[rendered["status"]] += 1
                        errors.append({"job_id": job_id, **error})
                        job_results.append({"job_id": job_id, "status": job["status"], "error": error})
                        with queue_cancel_lock(root, timeout=2.0):
                            cancel_path(root, job_id).unlink(missing_ok=True)
                            save_queue(root, queue)
                        continue
                    marker = cancel_path(root, job_id)
                    with queue_cancel_lock(root, timeout=2.0):
                        if marker.exists():
                            raise AppError("CANCELLED", "队列作业在渲染完成提交前收到取消请求", exit_code=8, path=str(marker))
                        result = rendered["result"]
                        render_settings = rendered["render_settings"]
                        profile = rendered["profile"]
                        output = rendered["output"]
                        sequence = rendered["sequence"]
                        report = rendered["report"]
                        encoder = render_settings.get("output", {}) if isinstance(render_settings.get("output"), dict) else {}
                        project.setdefault("outputs", []).append({"id": new_id("output"), "path": str(output), "container": encoder.get("container", job.get("container", "mp4")), "profile": profile, "canvas": render_settings.get("canvas", {}), "video": encoder.get("video", {}), "audio": encoder.get("audio", {}), "target_platform": "generic"})
                        project.setdefault("provenance", {}).setdefault("change_log", []).append({"command": "queue.run", "queue_job_id": job_id, "at": now_iso(), "output": str(output), "manifest": result.get("manifest")})
                        save_project(root, project)
                        _operation(root, result.get("operation_id", new_id("op")), {"operation_id": result.get("operation_id"), "command": "render", "queue_job_id": job_id, "status": "succeeded", "output": str(output), "manifest": result.get("manifest"), "warnings": result.get("warnings", []), "profile": profile, "settings": render_settings, "project_id": project["project"]["id"], "sequence_id": sequence["id"], "project_fingerprint": result.get("project_fingerprint"), "input_hashes": result.get("input_hashes", {}), "created_at": now_iso()})
                        queue_warnings = report.get("warnings", []) + result.get("warnings", [])
                        job["warnings"] = queue_warnings
                        set_status(job, "succeeded", operation_id=result.get("operation_id"))
                        summary["succeeded"] += 1
                        job_results.append({"job_id": job_id, "status": "succeeded", "operation_id": result.get("operation_id"), "path": str(output), "warnings": queue_warnings})
                        marker.unlink(missing_ok=True)
                        save_queue(root, queue)
                except AppError as exc:
                    error = exc.as_dict()
                    set_status(job, "cancelled" if exc.code == "CANCELLED" else "failed", error=error, operation_id=exc.operation_id)
                    summary["cancelled" if exc.code == "CANCELLED" else "failed"] += 1
                    errors.append({"job_id": job_id, **error})
                    job_results.append({"job_id": job_id, "status": job["status"], "error": error})
                    with queue_cancel_lock(root, timeout=2.0):
                        marker = cancel_path(root, job_id)
                        marker.unlink(missing_ok=True)
                        save_queue(root, queue)

    final_status = "succeeded" if not errors and summary["cancelled"] == 0 else "partial"
    _operation(root, queue_operation_id, {"operation_id": queue_operation_id, "command": "queue.run", "status": final_status, "project_id": project["project"]["id"], "summary": summary, "jobs": job_results, "workers": int(args.workers), "created_at": now_iso()})
    return _envelope("queue.run", args, data={"queue": str(queue_path(root)), "summary": summary, "jobs": job_results, "counts": _queue_counts(queue), "workers": int(args.workers)}, status=final_status, errors=errors, operation_id=queue_operation_id)


def command_queue_enqueue(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    payload = load_json(Path(args.input).expanduser().resolve())
    if args.dry_run:
        queue = load_queue(root, project_id=project["project"]["id"])
        raw_jobs = payload.get("jobs") if isinstance(payload.get("jobs"), list) else [payload]
        if not raw_jobs:
            raise argument_error("渲染队列作业不能为空")
        existing = {str(job.get("job_id")) for job in queue.get("jobs", []) if isinstance(job, dict)}
        planned: list[dict[str, Any]] = []
        for raw in raw_jobs:
            job = normalize_job(root, raw)
            if job["job_id"] in existing:
                raise argument_error(f"队列作业 ID 已存在: {job['job_id']}", "job_id")
            existing.add(job["job_id"])
            planned.append(job)
        return _envelope("queue.enqueue", args, status="planned", data={"queue": str(queue_path(root)), "jobs": planned, "count": len(planned)})
    queue, added = enqueue_render_jobs(root, project["project"]["id"], payload)
    operation_id = new_id("op")
    _operation(root, operation_id, {"operation_id": operation_id, "command": "queue.enqueue", "status": "succeeded", "project_id": project["project"]["id"], "queue": str(queue_path(root)), "jobs": [job["job_id"] for job in added], "created_at": now_iso()})
    return _envelope("queue.enqueue", args, data={"queue": str(queue_path(root)), "jobs": added, "count": len(added), "counts": _queue_counts(queue)}, operation_id=operation_id)


def _queue_job_view(root: Path, job: dict[str, Any]) -> dict[str, Any]:
    """Expose an atomic cancellation marker without mutating queue state."""
    view = copy.deepcopy(job)
    marker = cancel_path(root, str(view["job_id"]))
    if marker.exists():
        view["cancel_requested"] = True
        view["cancel_marker"] = str(marker)
    return view


def command_queue_list(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    queue = load_queue(root, project_id=project["project"]["id"])
    jobs = [_queue_job_view(root, job) for job in queue.get("jobs", []) if isinstance(job, dict) and (args.status is None or job.get("status") == args.status)]
    return _envelope("queue.list", args, data={"queue": str(queue_path(root)), "queue_version": queue.get("queue_version"), "project_id": project["project"]["id"], "counts": _queue_counts(queue), "jobs": jobs})


def command_queue_inspect(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    queue = load_queue(root, project_id=project["project"]["id"])
    job = find_job(queue, args.job_id)
    return _envelope("queue.inspect", args, data={"queue": str(queue_path(root)), "job": _queue_job_view(root, job)})


def command_queue_cancel(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    queue = load_queue(root, project_id=project["project"]["id"])
    job = find_job(queue, args.job_id)
    status = str(job.get("status"))
    marker = cancel_path(root, args.job_id)
    if status == "succeeded":
        raise AppError("QUEUE_CANCEL_INVALID", "已成功的队列作业不能取消", exit_code=2, path=args.job_id)
    if status == "failed":
        raise AppError("QUEUE_CANCEL_INVALID", "已失败的队列作业不能取消；可直接重试或重新入队", exit_code=2, path=args.job_id)
    if args.dry_run:
        return _envelope("queue.cancel", args, status="planned", data={"queue": str(queue_path(root)), "job_id": args.job_id, "status": status, "marker": str(marker)})
    acknowledged = False
    confirmed = False
    try:
        # This short channel lock arbitrates marker writes with queue start and
        # finalization. It is never held during FFmpeg rendering.
        with queue_cancel_lock(root, timeout=2.0):
            _, project = load_project(root)
            queue = load_queue(root, project_id=project["project"]["id"])
            job = find_job(queue, args.job_id)
            status = str(job.get("status"))
            if status == "succeeded":
                raise AppError("QUEUE_CANCEL_INVALID", "已成功的队列作业不能取消", exit_code=2, path=args.job_id)
            if status == "failed":
                raise AppError("QUEUE_CANCEL_INVALID", "已失败的队列作业不能取消；可直接重试或重新入队", exit_code=2, path=args.job_id)
            if status == "pending":
                try:
                    with project_write_lock(root):
                        _, latest_project = load_project(root)
                        latest_queue = load_queue(root, project_id=latest_project["project"]["id"])
                        job = find_job(latest_queue, args.job_id)
                        if job.get("status") == "pending":
                            set_status(job, "cancelled")
                            job["cancel_requested"] = True
                            save_queue(root, latest_queue)
                            queue = latest_queue
                            project = latest_project
                            acknowledged = True
                            confirmed = True
                        elif job.get("status") == "running":
                            atomic_write_text(marker, "cancel_requested\n")
                            acknowledged = True
                        elif job.get("status") == "cancelled":
                            marker.unlink(missing_ok=True)
                            acknowledged = True
                            confirmed = True
                        elif job.get("status") == "succeeded":
                            raise AppError("QUEUE_CANCEL_INVALID", "已成功的队列作业不能取消", exit_code=2, path=args.job_id)
                        elif job.get("status") == "failed":
                            raise AppError("QUEUE_CANCEL_INVALID", "已失败的队列作业不能取消；可直接重试或重新入队", exit_code=2, path=args.job_id)
                except AppError as exc:
                    if exc.code != "PROJECT_WRITE_LOCKED":
                        raise
                    atomic_write_text(marker, "cancel_requested\n")
                    acknowledged = True
                    confirmed = False
                    job["cancel_requested"] = True
            elif status == "running":
                atomic_write_text(marker, "cancel_requested\n")
                acknowledged = True
                confirmed = False
            else:
                # Repeating a cancellation request is idempotent for an already cancelled job.
                marker.unlink(missing_ok=True)
                acknowledged = True
                confirmed = True
    except AppError as exc:
        if exc.code != "QUEUE_CANCEL_CHANNEL_BUSY":
            raise
        # The finalization window is intentionally short. If another process
        # still owns it, preserve the request as a marker for the next state
        # observation instead of overwriting queue JSON from a stale snapshot.
        atomic_write_text(marker, "cancel_requested\n")
        acknowledged = True
        confirmed = False
        job["cancel_requested"] = True
    operation_id = new_id("op")
    _operation(root, operation_id, {"operation_id": operation_id, "command": "queue.cancel", "status": "succeeded", "project_id": project["project"]["id"], "job_id": args.job_id, "job_status": job.get("status"), "acknowledged": acknowledged, "confirmed": confirmed, "cancel_marker": str(marker) if marker.exists() else None, "created_at": now_iso()})
    return _envelope("queue.cancel", args, data={"queue": str(queue_path(root)), "job": job, "marker": str(marker) if marker.exists() else None, "acknowledged": acknowledged, "confirmed": confirmed}, operation_id=operation_id)


def command_queue_run(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    queue = load_queue(root, project_id=project["project"]["id"])
    workers = int(getattr(args, "workers", 1) or 1)
    if workers <= 0:
        raise argument_error("--workers 必须大于 0", "--workers")
    reuse_enabled = bool(getattr(args, 'reuse_identical', False))
    if reuse_enabled and workers != 1:
        raise argument_error('--reuse-identical 首版只支持 --workers 1', '--reuse-identical')
    if workers > 1 and not args.continue_on_error:
        raise argument_error("--workers 大于 1 时必须同时使用 --continue-on-error，以保证并发批次的失败语义明确", "--workers")
    if args.job_id:
        selected = [find_job(queue, args.job_id)]
        if selected[0].get("status") not in {"pending", "failed", "cancelled"}:
            raise AppError("QUEUE_JOB_STATE_INVALID", "指定作业必须处于 pending、failed 或 cancelled 状态", exit_code=2, path=args.job_id)
    else:
        selected = [job for job in queue.get("jobs", []) if isinstance(job, dict) and job.get("status") == "pending"]
        if args.max_jobs is not None:
            if args.max_jobs <= 0:
                raise argument_error("--max-jobs 必须大于 0", "--max-jobs")
            selected = selected[:args.max_jobs]
    if reuse_enabled:
        conflicts = _queue_output_conflicts(root, selected)
        if conflicts:
            raise AppError('QUEUE_OUTPUT_CONFLICT', '复用批次的目标路径不得重复', exit_code=2, cause=', '.join(conflicts))
    if args.dry_run:
        return _envelope("queue.run", args, status="planned", data={"queue": str(queue_path(root)), "jobs": [job.get("job_id") for job in selected], "count": len(selected), "continue_on_error": bool(args.continue_on_error), "workers": workers, 'reuse_identical': reuse_enabled})

    if workers > 1 and len(selected) > 1:
        args.workers = workers
        return _queue_run_parallel(root, project, queue, selected, args)

    queue_operation_id = new_id("op")
    summary = {"selected": len(selected), "succeeded": 0, "failed": 0, "cancelled": 0, "skipped": 0}
    errors: list[dict[str, Any]] = []
    job_results: list[dict[str, Any]] = []
    reuse_session = None
    if reuse_enabled:
        from .queue_reuse import ReuseSession
        reuse_session = ReuseSession(root)
    for job in selected:
        job_id = str(job["job_id"])
        marker = cancel_path(root, job_id)
        with queue_cancel_lock(root, timeout=2.0):
            # A marker on a pending job is a new cancellation request, even
            # when the caller names that job explicitly. A cancelled/failed job
            # with an explicit ID is a retry authorization and clears an old
            # marker before starting; a new marker written after this point
            # remains effective.
            if marker.exists() and job.get("status") == "pending":
                set_status(job, "cancelled")
                job["cancel_requested"] = True
                summary["cancelled"] += 1
                job_results.append({"job_id": job_id, "status": "cancelled", "reason": "cancel marker exists before start"})
                marker.unlink(missing_ok=True)
                save_queue(root, queue)
                continue
            marker.unlink(missing_ok=True)
            job["attempts"] = int(job.get("attempts", 0)) + 1
            job["cancel_requested"] = False
            job["operation_id"] = None
            job.pop('reuse', None)
            set_status(job, "running")
            save_queue(root, queue)
        reuse_output = None
        committed = False
        captured = None
        reused = False
        try:
            sequence = find_sequence(project, job.get("sequence_id"))
            report = validate_project(root, project, strict_rights=bool(job.get("publish", False)), target="commercial_ad")
            if not report["ok"]:
                raise AppError("PROJECT_INVALID", "项目验证失败，拒绝执行队列作业", exit_code=7 if job.get("publish") else 2, cause=json.dumps(report, ensure_ascii=False))
            render_args = _queue_job_args(root, job, args)
            render_settings, profile = _render_settings_for_args(project, render_args)
            output = ensure_inside(root, root / str(job["output"]))
            progress_callback = None
            if getattr(args, "progress", "none") == "jsonl":
                progress_callback = lambda operation_id, event_type, percent, message: _progress(args, operation_id, event_type, "queue.render", percent, message)
            if reuse_session is not None:
                reuse_session.assert_new_target(output)
                reuse_output = output
                snapshot = reuse_session.snapshot(project, sequence, render_settings, marker)
                previous = reuse_session.entries.get(snapshot['signature'])
                if previous is not None:
                    result = reuse_session.clone(previous, snapshot, project, sequence, render_settings, output,
                        profile=profile, marker=marker, progress_callback=progress_callback)
                    reused = True
                else:
                    from .queue_reuse import cache_inventory, check_entries
                    existing_cache = cache_inventory(root, marker)
                    result = render_project(root, project, sequence, output, dry_run=False, render_settings=render_settings, profile=profile, cancel_file=marker, progress_callback=progress_callback)
                    reuse_session.unchanged(snapshot, project, sequence, render_settings, marker)
                    check_entries(existing_cache, marker)
                    captured = reuse_session.capture(snapshot, result, job_id)
            else:
                result = render_project(root, project, sequence, output, dry_run=False, render_settings=render_settings, profile=profile, cancel_file=marker, progress_callback=progress_callback)
            with queue_cancel_lock(root, timeout=2.0):
                if marker.exists():
                    raise AppError("CANCELLED", "队列作业在渲染完成提交前收到取消请求", exit_code=8, path=str(marker))
                encoder = render_settings.get("output", {}) if isinstance(render_settings.get("output"), dict) else {}
                project.setdefault("outputs", []).append({"id": new_id("output"), "path": str(output), "container": encoder.get("container", job.get("container", "mp4")), "profile": profile, "canvas": render_settings.get("canvas", {}), "video": encoder.get("video", {}), "audio": encoder.get("audio", {}), "target_platform": "generic"})
                project.setdefault("provenance", {}).setdefault("change_log", []).append({"command": "queue.run", "queue_job_id": job_id, "at": now_iso(), "output": str(output), "manifest": result.get("manifest")})
                save_project(root, project)
                _operation(root, result.get("operation_id", new_id("op")), {"operation_id": result.get("operation_id"), "command": "render", "queue_job_id": job_id, "status": "succeeded", "output": str(output), "manifest": result.get("manifest"), "warnings": result.get("warnings", []), "profile": profile, "settings": render_settings, "project_id": project["project"]["id"], "sequence_id": sequence["id"], "project_fingerprint": result.get("project_fingerprint"), "input_hashes": result.get("input_hashes", {}), "created_at": now_iso(), **({'reuse': result['reuse']} if reuse_session is not None else {})})
                queue_warnings = report.get("warnings", []) + result.get("warnings", [])
                job["warnings"] = queue_warnings
                if reuse_session is not None:
                    job['reuse'] = {key: copy.deepcopy(value) for key, value in result['reuse'].items() if key != 'snapshot'}
                set_status(job, "succeeded", operation_id=result.get("operation_id"))
                summary["succeeded"] += 1
                job_results.append({"job_id": job_id, "status": "succeeded", "operation_id": result.get("operation_id"), "path": str(output), "warnings": queue_warnings, **({'reuse': {k: v for k, v in result['reuse'].items() if k != 'snapshot'}} if reuse_session is not None else {})})
                marker.unlink(missing_ok=True)
                save_queue(root, queue)
                committed = True
                if reuse_session is not None:
                    if captured is not None:
                        reuse_session.remember(captured)
                    if reused:
                        reuse_session.reused += 1
        except AppError as exc:
            error = exc.as_dict()
            set_status(job, "cancelled" if exc.code == "CANCELLED" else "failed", error=error, operation_id=exc.operation_id)
            summary["cancelled" if exc.code == "CANCELLED" else "failed"] += 1
            errors.append({"job_id": job_id, **error})
            job_results.append({"job_id": job_id, "status": job["status"], "error": error})
            with queue_cancel_lock(root, timeout=2.0):
                marker.unlink(missing_ok=True)
                save_queue(root, queue)
            if exc.code != "CANCELLED" and not args.continue_on_error:
                break
        finally:
            if reuse_output is not None and not committed:
                reuse_output.unlink(missing_ok=True)
                reuse_output.with_suffix(reuse_output.suffix + '.manifest.json').unlink(missing_ok=True)

    final_status = "succeeded" if not errors and summary["cancelled"] == 0 else "partial"
    _operation(root, queue_operation_id, {"operation_id": queue_operation_id, "command": "queue.run", "status": final_status, "project_id": project["project"]["id"], "summary": summary, "jobs": job_results, "created_at": now_iso()})
    return _envelope("queue.run", args, data={"queue": str(queue_path(root)), "summary": summary, "jobs": job_results, "counts": _queue_counts(queue), **({'reuse_summary': {'encoded_successes': reuse_session.encoded, 'reused_successes': reuse_session.reused, 'scope': 'current_invocation', 'persistent_cache': False}} if reuse_session is not None else {})}, status=final_status, errors=errors, operation_id=queue_operation_id)


def command_quality_mask(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    asset = asset_map(project).get(args.asset_id)
    if asset is None:
        raise argument_error("蒙版资产未登记", "asset-id")
    plan = prepare_mask_review(root, asset, channel=args.channel, threshold=args.threshold, fps=args.fps,
                              max_edge=args.max_edge, max_frames=args.max_frames, budget_mib=args.budget_mib,
                              expectations=args.expectations, scene_cuts=args.scene_cut_frame)
    report = resolve_local_path(root, args.report, field="report") if args.report else root / "validation" / f"mask_{new_id('review')}.json"
    try:
        report.resolve().relative_to((root / "validation").resolve())
    except ValueError as exc:
        raise argument_error("蒙版报告必须位于项目 validation 目录", "report") from exc
    if report.suffix.lower() != ".json" or report == Path(plan['source']['path']) or plan['expectations'] and report == Path(plan['expectations']['path']):
        raise argument_error("蒙版报告须为 JSON 且不能覆盖输入", "report")
    if args.dry_run:
        return _envelope("quality.mask", args, status="planned", data={"report": str(report), "plan": {k: v for k, v in plan.items() if k != 'events'}})
    result = review_mask(root, plan)
    atomic_write_json(report, {"created_at": now_iso(), "project_id": project['project']['id'], **result})
    return _envelope("quality.mask", args, status="succeeded" if result['ok'] else "failed", data={"report": str(report), **result},
                     warnings=result['warnings'], errors=result['errors'])


def command_quality_check(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    media = Path(args.input).expanduser().resolve()
    if not media.exists() or not media.is_file():
        raise argument_error("质量检查输入不存在", str(media))
    sequence = find_sequence(project, args.sequence_id) if args.sequence_id else None
    tps = int(project["settings"]["timebase"]["ticks_per_second"])
    expected_duration = (int(sequence["duration_tick"]) / tps) if sequence else None
    quality_settings, profile = _render_settings_for_args(project, args)
    if args.dry_run:
        return _envelope("quality.check", args, status="planned", data={"input": str(media), "expected_duration": expected_duration, "expensive": bool(args.expensive), "require_audio": bool(args.require_audio), "max_av_sync_ms": args.max_av_sync_ms, "target_lufs": args.target_lufs, "lufs_tolerance": args.lufs_tolerance, "fail_on_black": bool(args.fail_on_black), "max_true_peak_dbfs": args.max_true_peak_dbfs, "profile": profile, "settings": quality_settings})
    result = check_output(media, quality_settings, expected_duration, require_audio=args.require_audio, run_expensive=args.expensive, max_av_sync_ms=args.max_av_sync_ms, target_lufs=args.target_lufs, lufs_tolerance=args.lufs_tolerance, fail_on_black=args.fail_on_black, max_true_peak_dbfs=args.max_true_peak_dbfs)
    report_path = Path(args.report).expanduser().resolve() if args.report else root / "validation" / f"quality_{new_id('run')}.json"
    atomic_write_json(report_path, {"report_version": "0.1.0", "created_at": now_iso(), "project_id": project["project"]["id"], "input": str(media), "profile": profile, "settings": quality_settings, **result})
    status = "succeeded" if result["ok"] else "failed"
    return _envelope("quality.check", args, data={"report": str(report_path), **result}, status=status, warnings=result.get("warnings", []), errors=result.get("errors", []))


def command_quality_golden(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    media = Path(args.input).expanduser().resolve()
    if not media.exists() or not media.is_file():
        raise argument_error("golden 质量输入不存在", str(media))
    manifest_path = Path(args.manifest).expanduser().resolve() if args.manifest else root / "validation" / "golden-quality.json"
    ensure_inside(root, manifest_path)
    existing_manifest: dict[str, Any] | None = None
    if args.mode == "verify":
        if not manifest_path.exists() or not manifest_path.is_file():
            return _envelope("quality.golden", args, status="failed", data={"manifest": str(manifest_path), "mode": args.mode}, errors=[{"code": "QUALITY_GOLDEN_MISSING", "message": f"找不到 golden 清单: {manifest_path}"}])
        existing_manifest = load_json(manifest_path)
        manifest_errors = validate_golden_manifest(existing_manifest)
        if manifest_errors:
            return _envelope("quality.golden", args, status="failed", data={"manifest": str(manifest_path), "mode": args.mode, "golden_version": existing_manifest.get("golden_version")}, errors=manifest_errors)
        if args.sequence_id is None and existing_manifest.get("sequence_id"):
            args.sequence_id = existing_manifest.get("sequence_id")
        if args.profile is None and existing_manifest.get("profile"):
            args.profile = existing_manifest.get("profile")
            if args.profile == "custom":
                canvas = existing_manifest.get("canvas") if isinstance(existing_manifest.get("canvas"), dict) else {}
                args.width = canvas.get("width")
                args.height = canvas.get("height")
    sequence = find_sequence(project, args.sequence_id) if args.sequence_id else None
    tps = int(project["settings"]["timebase"]["ticks_per_second"])
    expected_duration = (int(sequence["duration_tick"]) / tps) if sequence else None
    if args.mode == "verify" and expected_duration is None and existing_manifest is not None:
        stored_expected = existing_manifest.get("expected_duration_seconds")
        expected_duration = float(stored_expected) if stored_expected is not None else None
    quality_settings, profile = _render_settings_for_args(project, args)
    overrides = {"require_audio": args.require_audio, "expensive": args.expensive, "max_av_sync_ms": args.max_av_sync_ms, "target_lufs": args.target_lufs, "lufs_tolerance": args.lufs_tolerance, "fail_on_black": args.fail_on_black, "max_true_peak_dbfs": args.max_true_peak_dbfs}
    constraints = normalize_golden_constraints(existing_manifest.get("constraints") if existing_manifest else None, overrides)
    if args.dry_run:
        return _envelope("quality.golden", args, status="planned", data={"mode": args.mode, "manifest": str(manifest_path), "input": str(media), "sequence_id": args.sequence_id, "expected_duration": expected_duration, "golden_version": GOLDEN_VERSION, "profile": profile, "settings": quality_settings, "constraints": constraints})
    result = check_output(media, quality_settings, expected_duration, require_audio=constraints["require_audio"], run_expensive=constraints["expensive"], max_av_sync_ms=constraints["max_av_sync_ms"], target_lufs=constraints["target_lufs"], lufs_tolerance=constraints["lufs_tolerance"], fail_on_black=constraints["fail_on_black"], max_true_peak_dbfs=constraints["max_true_peak_dbfs"])
    if args.mode == "capture":
        if not result["ok"]:
            return _envelope("quality.golden", args, status="failed", data={"mode": args.mode, "manifest": str(manifest_path), **result}, warnings=result.get("warnings", []), errors=result.get("errors", []))
        manifest = build_golden_manifest(media, project_id=project["project"]["id"], sequence_id=args.sequence_id, expected_duration=expected_duration, settings=quality_settings, profile=profile, result=result, constraints=constraints)
        manifest["created_at"] = now_iso()
        atomic_write_json(manifest_path, manifest)
        operation_id = new_id("op")
        _operation(root, operation_id, {"operation_id": operation_id, "command": "quality.golden", "mode": "capture", "status": "succeeded", "manifest": str(manifest_path), "created_at": now_iso()})
        return _envelope("quality.golden", args, data={"mode": args.mode, "manifest": str(manifest_path), "golden_version": GOLDEN_VERSION, **result}, operation_id=operation_id, warnings=result.get("warnings", []))
    mismatches = compare_golden_manifest(existing_manifest or {}, media, project_id=project["project"]["id"], settings=quality_settings, result=result)
    stored_expected = (existing_manifest or {}).get("expected_duration_seconds")
    if stored_expected is not None and expected_duration is not None and abs(float(stored_expected) - float(expected_duration)) > 0.001:
        mismatches.append({"code": "QUALITY_GOLDEN_EXPECTED_DURATION_MISMATCH", "expected": stored_expected, "actual": expected_duration, "tolerance": 0.001})
    errors = list(result.get("errors", [])) + mismatches
    status = "succeeded" if not errors else "failed"
    return _envelope("quality.golden", args, data={"mode": args.mode, "manifest": str(manifest_path), "golden_version": GOLDEN_VERSION, "mismatches": mismatches, **result}, status=status, warnings=result.get("warnings", []), errors=errors)


def command_quality_scopes(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    media = Path(args.input).expanduser().resolve()
    if not media.exists() or not media.is_file():
        raise argument_error("色彩 scope 输入不存在", str(media))
    scope_id = new_id("scope")
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else root / "cache" / "scopes" / scope_id
    try:
        output_dir.relative_to(root)
    except ValueError as exc:
        raise argument_error("scope 输出目录必须位于项目目录内", str(output_dir)) from exc
    if args.dry_run:
        return _envelope("quality.scopes", args, status="planned", data={"input": str(media), "output_dir": str(output_dir), "at_seconds": args.at_seconds, "scope_types": ["waveform", "vectorscope", "histogram"]})
    result = generate_scopes(media, output_dir, at_seconds=args.at_seconds)
    report_path = root / "validation" / f"scopes_{scope_id}.json"
    atomic_write_json(report_path, {"report_version": SCOPE_VERSION, "created_at": now_iso(), "project_id": project["project"]["id"], **result})
    operation_id = new_id("op")
    _operation(root, operation_id, {"operation_id": operation_id, "command": "quality.scopes", "status": "succeeded", "report": str(report_path), "artifacts": result["artifacts"], "created_at": now_iso()})
    return _envelope("quality.scopes", args, data={"report": str(report_path), **result}, operation_id=operation_id)


def command_convert_import(args: argparse.Namespace) -> dict[str, Any]:
    source = Path(args.input).expanduser().resolve()
    destination = Path(args.output).expanduser().resolve()
    if not source.exists() or not source.is_file():
        raise argument_error("转换输入不存在", str(source))
    if destination.exists() and any(destination.iterdir()):
        raise argument_error("转换输出目录必须不存在或为空", str(destination))
    if args.dry_run:
        return _envelope("convert.import", args, status="planned", data={"input": str(source), "output": str(destination), "format": source.suffix.lower()})
    try:
        result = import_external(source, destination, strict=args.strict)
    except ValueError as exc:
        raise argument_error(str(exc), str(source)) from exc
    report = result["report_data"]
    status = "succeeded" if not report.get("failures") else "failed"
    return _envelope("convert.import", args, data=result, status=status, warnings=report.get("warnings", []), errors=report.get("failures", []))


def command_convert_export(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    output = Path(args.output).expanduser().resolve()
    if args.bake_tracking and (args.strict or args.target_format not in {'agent-json', 'package'}):
        raise argument_error('--bake-tracking 适用于 agent-json/package；外部格式自动烘焙并报告损失', '--bake-tracking')
    if args.dry_run:
        return _envelope("convert.export", args, status="planned", data={"project": str(root), "output": str(output), "format": args.target_format,
            "tracking_bake_requested": args.bake_tracking, "tracking_bake_pixel_verification_executed": False})
    try:
        result = export_external(root, project, output, args.target_format, strict=args.strict, bake_tracking=args.bake_tracking)
    except ValueError as exc:
        raise argument_error(str(exc), "--target-format") from exc
    report = result["report_data"]
    return _envelope("convert.export", args, data=result, status="failed" if report.get("failures") else "succeeded", warnings=report.get("warnings", []), errors=report.get("failures", []))


def command_template_apply(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    template = load_json(Path(args.input))
    variables = load_json(Path(args.variables)) if args.variables else {}
    if not isinstance(variables, dict):
        raise argument_error("模板变量必须是 JSON 对象", "--variables")
    try:
        resolved = instantiate(template, variables)
    except (KeyError, ValueError) as exc:
        raise argument_error(str(exc), str(Path(args.input))) from exc
    operations = resolved.get("operations") or resolved.get("changes") or []
    if not isinstance(operations, list):
        raise argument_error("模板 operations/changes 必须是数组")
    if args.dry_run:
        return _envelope("template.apply", args, status="planned", data={"template_id": template.get("id"), "version": template.get("version"), "operations": operations, "variables": variables})
    applied = apply_template_operations(project, operations, resolved.get("sequence_id"))
    snapshot = resolved.get("template_snapshot", {"id": template.get("id"), "version": template.get("version"), "variables": variables})
    snapshot_variables = resolved.get("template_snapshot", {}).get("variables", variables)
    project.setdefault("templates", []).append({"id": template.get("id") or new_id("template"), "version": template.get("version", "0.0.0"), "variables": [{"name": key, "value": value} for key, value in snapshot_variables.items()], "assets": sorted({item.get("clip", {}).get("asset_id") for item in applied if isinstance(item.get("clip"), dict) and item.get("clip", {}).get("asset_id")})})
    operation_id = new_id("op")
    project.setdefault("provenance", {}).setdefault("change_log", []).append({"operation_id": operation_id, "command": "template.apply", "template_snapshot": snapshot, "applied": applied, "at": now_iso()})
    save_project(root, project)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "template.apply", "status": "succeeded", "template_snapshot": snapshot, "applied": applied, "created_at": now_iso()})
    return _envelope("template.apply", args, data={"template_snapshot": snapshot, "applied": applied}, operation_id=operation_id)


def command_template_batch(args: argparse.Namespace) -> dict[str, Any]:
    root, _ = load_project(args.project)
    template = load_json(Path(args.input))
    variables_path = Path(args.variables).expanduser().resolve()
    variants = _load_variants(variables_path)
    output_root = Path(args.output).expanduser().resolve()
    if args.dry_run:
        return _envelope("template.batch", args, status="planned", data={"template_id": template.get("id"), "variant_count": len(variants), "output_root": str(output_root), "publish": bool(args.publish)})
    report = run_template_batch(root, template, variants, output_root, publish=args.publish, continue_on_error=args.continue_on_error)
    report_path = root / "validation" / f"batch_{new_id('report')}.json"
    atomic_write_json(report_path, report)
    status = "succeeded" if report["failed"] == 0 else "failed"
    return _envelope("template.batch", args, data={"report": str(report_path), **report}, status=status, errors=[item for item in report["variants"] if item["status"] != "succeeded"])


def command_fragment(args: argparse.Namespace) -> dict[str, Any]:
    try:
        return _command_fragment(args)
    except OSError as exc:
        raise AppError('FRAGMENT_IO_FAILED', '片段组本地文件操作失败；未发布的版本或未提交工程将回滚',
                       exit_code=2, path=str(getattr(exc, 'filename', None) or args.library), cause=str(exc)) from exc


def _command_fragment(args: argparse.Namespace) -> dict[str, Any]:
    from .artifact_locks import artifact_entry, verification_scope, verification_summary
    command = 'fragment.'+args.action
    library = fragments.library_path(args.library)
    with verification_scope():
        if args.action == 'list':
            return _envelope(command, args, data={'fragments': fragments.list_fragments(library, args.query)})
        if args.action == 'inspect':
            payload, info = fragments.inspect(library, args.id, args.version, max_bytes=args.max_bytes)
            return _envelope(command, args, data={'fragment': payload, **info, 'verification': verification_summary()}, warnings=payload.get('warnings', []))
        # Read handles freeze all source metadata and request bytes on Windows;
        # the normal project operation lock protects cooperating mutations.
        source_root = Path(args.project).expanduser().resolve()
        if source_root.name.lower() == 'project.json':
            source_root = source_root.parent
        artifact_entry(project_file(source_root), 'fragment-project-metadata')
        artifact_entry(ledger_file(source_root), 'fragment-rights-metadata')
        artifact_entry(Path(args.input).expanduser().resolve(), 'fragment-request')
        root, project = load_project(args.project)
        ledger = load_ledger(root)
        request = _load_changes(args.input)
        if args.expected_project_sha256 is not None and args.expected_project_sha256 != edit_project_fingerprint(project):
            raise AppError('FRAGMENT_PROJECT_CHANGED', '工程已偏离已审查片段组计划', exit_code=2)
        validation = validate_project(root, project, strict_rights=False)
        if not validation['ok']:
            raise AppError('PROJECT_INVALID', '片段组操作前工程无效', exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
        if args.action == 'save':
            payload, sources = fragments.prepare_save(root, project, ledger, request, max_bytes=args.max_bytes)
            if fragments.entry_path(library, payload['id'], payload['version']).exists():
                raise AppError('FRAGMENT_VERSION_EXISTS', '片段组版本已存在；请使用新版本号', exit_code=2)
            info = {'fragment_sha256': fragments.digest(payload), 'project_sha256': edit_project_fingerprint(project),
                    'files': len(payload['files']), 'bytes': sum(i['bytes'] for i in payload['files'])}
            if args.expected_fragment_sha256 is not None and args.expected_fragment_sha256 != info['fragment_sha256']:
                raise AppError('FRAGMENT_VERSION_CHANGED', '待保存内容已偏离已审查计划', exit_code=2)
            if not args.dry_run:
                info.update(fragments.save(library, payload, sources))
            return _envelope(command, args, status='planned' if args.dry_run else 'succeeded',
                             data={'fragment': payload, 'plan': info, 'verification': verification_summary()}, warnings=payload.get('warnings', []))
        payload, info = fragments.inspect(library, request.get('id'), request.get('version'), max_bytes=args.max_bytes)
        if args.expected_fragment_sha256 is not None and args.expected_fragment_sha256 != info['fragment_sha256']:
            raise AppError('FRAGMENT_VERSION_CHANGED', '片段组版本已偏离已审查摘要', exit_code=2)
        candidate, candidate_ledger, plan = fragments.prepare_apply(project, ledger, payload, info, request)
        warnings = list(payload.get('warnings', []))
        if not plan['rights']['ok']:
            warnings.append({'code': 'FRAGMENT_RIGHTS_REVIEW_REQUIRED', 'message': '导入保留原权利限制；商业发布仍受门禁约束'})
        if args.dry_run:
            return _envelope(command, args, status='planned', data={'plan': plan, 'verification': verification_summary()}, warnings=warnings)
    # Source handles remain frozen for resource copying. Project/ledger read
    # locks must end before their atomic replacements; use a second scope for
    # immutable library files, with metadata fingerprint rechecked below.
    with verification_scope():
        payload, current_info = fragments.inspect(library, request['id'], request['version'], max_bytes=args.max_bytes)
        if current_info['fragment_sha256'] != info['fragment_sha256']:
            raise AppError('FRAGMENT_VERSION_CHANGED', '复制前片段组清单发生变化', exit_code=2)
        if edit_project_fingerprint(load_project(root)[1]) != plan['project_sha256'] or fragments.digest(load_ledger(root)) != fragments.digest(ledger):
            raise AppError('FRAGMENT_PROJECT_CHANGED', '复制前工程或台账发生变化', exit_code=2)
        snapshot = create_snapshot(root, project, label='before-fragment-apply')
        copied = None
        try:
            copied = fragments.copy_resources(root, fragments.entry_path(library, payload['id'], payload['version']), plan)
            validation = validate_project(root, candidate, strict_rights=False)
            if not validation['ok']:
                raise AppError('FRAGMENT_PROJECT_INVALID', '插入后工程未通过验证', exit_code=2, cause=json.dumps(validation, ensure_ascii=False))
            operation_id = new_id('op')
            record = {'operation_id': operation_id, 'command': command, 'created_at': now_iso(),
                      'before_snapshot_id': snapshot['snapshot_id'], 'plan': plan}
            candidate.setdefault('provenance', {}).setdefault('change_log', []).append(copy.deepcopy(record))
            save_ledger(root, candidate_ledger)
            save_project(root, candidate)
            _operation(root, operation_id, {**record, 'status': 'succeeded'})
            return _envelope(command, args, data={'plan': plan, 'validation': validation, 'before_snapshot': snapshot,
                'verification': verification_summary()}, warnings=warnings, operation_id=operation_id)
        except BaseException:
            if copied is not None and copied.exists():
                shutil.rmtree(copied)
            raise


def command_library_index(args: argparse.Namespace) -> dict[str, Any]:
    source_root = Path(args.root).expanduser().resolve()
    output = Path(args.output).expanduser().resolve()
    if not source_root.exists() or not source_root.is_dir():
        raise argument_error("素材库根目录不存在", str(source_root))
    if args.incremental and not args.previous:
        raise argument_error("--incremental 必须同时提供 --previous 上一版目录", "--previous")
    previous_catalog = None
    if args.previous:
        previous_path = Path(args.previous).expanduser().resolve()
        previous_catalog = load_json(previous_path)
        previous_root = Path(str(previous_catalog.get("root", ""))).expanduser().resolve()
        if previous_root != source_root:
            raise argument_error("增量目录的 root 必须与 --root 相同", str(previous_path))
    incremental = bool(args.incremental or args.previous)
    if args.dry_run:
        return _envelope("library.index", args, status="planned", data={"root": str(source_root), "output": str(output), "max_files": args.max_files, "incremental": incremental, "previous": str(Path(args.previous).expanduser().resolve()) if args.previous else None, "visual_hash": bool(args.visual_hash)})
    catalog = index_directory(
        source_root,
        output,
        max_files=args.max_files,
        license_spdx=args.license_spdx,
        verification_status=args.verification_status,
        previous_catalog=previous_catalog,
        incremental=incremental,
        include_visual_hash=bool(args.visual_hash),
    )
    return _envelope("library.index", args, data={"catalog": str(output), "indexed_count": catalog["indexed_count"], "error_count": len(catalog["errors"]), "warning_count": len(catalog.get("warnings", [])), "index_refresh": catalog.get("index_refresh", {})})


def command_library_search(args: argparse.Namespace) -> dict[str, Any]:
    catalog_path = Path(args.catalog).expanduser().resolve()
    catalog = load_json(catalog_path)
    results = search_catalog(
        catalog,
        query=args.query,
        kind=args.kind,
        verification_status=args.verification_status,
        min_duration=args.min_duration,
        max_duration=args.max_duration,
        min_width=args.min_width,
        min_height=args.min_height,
        has_audio=args.has_audio,
        duplicate_only=args.duplicate_only,
        limit=args.limit,
    )
    return _envelope("library.search", args, data={"catalog": str(catalog_path), "count": len(results), "results": results, "search": {"source": "deterministic-local", "vector_index": False}})


def command_library_duplicates(args: argparse.Namespace) -> dict[str, Any]:
    catalog_path = Path(args.catalog).expanduser().resolve()
    catalog = load_json(catalog_path)
    groups = duplicate_groups(catalog, include_unique=args.include_unique)
    return _envelope("library.duplicates", args, data={"catalog": str(catalog_path), "count": len(groups), "groups": groups, "method": "sha256-exact"})


def command_library_similar(args: argparse.Namespace) -> dict[str, Any]:
    catalog_path = Path(args.catalog).expanduser().resolve()
    catalog = load_json(catalog_path)
    groups = visual_similarity_groups(catalog, max_distance=args.max_distance)
    visual_count = sum(
        1
        for record in catalog.get("records", [])
        if isinstance(record, dict)
        and isinstance(record.get("semantic"), dict)
        and isinstance(record["semantic"].get("visual_hash"), dict)
    )
    return _envelope(
        "library.similar",
        args,
        data={"catalog": str(catalog_path), "count": len(groups), "groups": groups, "method": "ahash-v1", "visual_hash_records": visual_count, "max_distance": max(0, int(args.max_distance))},
        warnings=[] if visual_count else [{"code": "VISUAL_HASH_UNAVAILABLE", "message": "目录未包含视觉哈希；请重新执行 library index --visual-hash"}],
    )


def command_look(args: argparse.Namespace) -> dict[str, Any]:
    try:
        return _handle_look(args)
    except OSError as exc:
        raise AppError('LOOK_IO_FAILED', '本地风格文件操作失败', exit_code=5, cause=str(exc)) from exc


def _handle_look(args: argparse.Namespace) -> dict[str, Any]:
    command = 'look.' + args.action
    status = 'planned' if args.dry_run else 'succeeded'
    if args.action == 'list':
        return _envelope(command, args, status=status, data=looks.list_looks(args.query, args.category))
    if args.action == 'inspect':
        return _envelope(command, args, status=status, data=looks.inspect_look(args.id))
    if args.action == 'preview':
        data = looks.preview(args.id, args.output, input_path=args.input, strength=args.strength, dry_run=args.dry_run)
        return _envelope(command, args, status=status, data=data, warnings=[{'code':'LOOK_PARTIAL_STRENGTH', 'message':w} for w in data.get('warnings', [])])
    root, project = load_project(args.project)
    candidate, plan = looks.plan_apply(project, args.id, args.strength, clip_id=args.clip_id,
        sequence_id=args.sequence_id, global_scope=args.global_scope, append=args.append)
    warnings = [{'code':'LOOK_CREATIVE_SDR', 'message':looks.catalog()['color_contract']}]
    if 0 < args.strength < 1:
        warnings.append({'code':'LOOK_PARTIAL_STRENGTH', 'message':'静态强度在 encoded RGB 中混合 identity LUT；不是线性光像素混合'})
    if args.dry_run:
        return _envelope(command, args, status=status, data=plan, warnings=warnings)
    snapshot = create_snapshot(root, project, label='before-look-apply')
    ledger = load_ledger(root)
    resource = looks.install_in_project(root, args.id, ledger)
    validation = validate_project(root, candidate, rights_ledger=ledger)
    if not validation['ok']:
        raise AppError('LOOK_PROJECT_INVALID', '应用风格后的项目未通过验证', exit_code=3, cause=json.dumps(validation['errors'], ensure_ascii=False))
    operation_id = new_id('op')
    candidate.setdefault('provenance', {}).setdefault('change_log', []).append({
        'operation_id':operation_id, 'command':command, 'look_id':args.id,
        'before_snapshot_id':snapshot['snapshot_id'], 'at':now_iso()})
    save_project(root, candidate)
    save_ledger(root, ledger)
    _operation(root, operation_id, {'operation_id':operation_id, 'command':command, 'status':'succeeded',
        'look_id':args.id, 'snapshot_id':snapshot['snapshot_id'], 'created_at':now_iso()})
    return _envelope(command, args, data={**plan, 'resource':resource, 'snapshot':snapshot},
                     warnings=warnings, operation_id=operation_id)


def command_lut_register(args: argparse.Namespace) -> dict[str, Any]:
    root, project = load_project(args.project)
    source = Path(args.input).expanduser().resolve()
    registration = prepare_lut_registration(root, source, lut_id=args.lut_id, name=args.name)
    preview = {key: value for key, value in registration.items() if key != "_source_path"}
    rights_record = {
        "asset_id": registration["id"],
        "kind": "lut",
        "sha256": registration["sha256"],
        "source_url": registration["source"]["source_url"],
        "source_version": "local",
        "retrieved_at": registration["registered_at"],
        "creator": args.creator,
        "license_spdx": args.license_spdx,
        "license_url": require_local_reference(args.license_url, field="--license-url") if args.license_url else "",
        "attribution": "",
        "permitted_uses": list(dict.fromkeys(args.permitted_use)),
        "restrictions": [],
        "evidence": require_local_reference(args.evidence, field="--evidence") if args.evidence else ("" if args.verification_status == "unverified" else registration["source"]["source_url"]),
        "verification_status": args.verification_status,
        "verified_by": "ai-ad-editor" if args.verification_status == "verified" else "",
        "takedown_status": "clear",
        "notes": "Registered by local LUT library CLI",
    }
    if args.dry_run:
        return _envelope("lut.register", args, status="planned", data={"lut": preview, "rights_record": rights_record})
    snapshot = create_snapshot(root, project, label="before-lut-register")
    registered = register_lut(root, registration)
    ledger = load_ledger(root)
    add_record(ledger, rights_record)
    operation_id = new_id("op")
    project.setdefault("provenance", {}).setdefault("change_log", []).append({
        "operation_id": operation_id,
        "command": "lut.register",
        "lut_id": registered["id"],
        "sha256": registered["sha256"],
        "before_snapshot_id": snapshot["snapshot_id"],
        "at": now_iso(),
    })
    save_project(root, project)
    save_ledger(root, ledger)
    _operation(root, operation_id, {"operation_id": operation_id, "command": "lut.register", "status": "succeeded", "lut_id": registered["id"], "snapshot_id": snapshot["snapshot_id"], "created_at": now_iso()})
    return _envelope("lut.register", args, data={"lut": registered, "rights": rights_record, "snapshot": snapshot, "library": str(root / "assets" / "lut-library.json")}, operation_id=operation_id)


def command_lut_list(args: argparse.Namespace) -> dict[str, Any]:
    root, _ = load_project(args.project)
    records = list_luts(root, query=args.query)
    return _envelope("lut.list", args, data={"library": str(root / "assets" / "lut-library.json"), "library_version": "0.1.0", "count": len(records), "luts": records, "network": "disabled"})


def command_lut_inspect(args: argparse.Namespace) -> dict[str, Any]:
    root, _ = load_project(args.project)
    return _envelope("lut.inspect", args, data=inspect_lut(root, args.lut_id))


def command_doctor(args: argparse.Namespace) -> dict[str, Any]:
    checks: dict[str, Any] = {"platform": platform.platform(), "python": sys.version.split()[0], "native_windows": os.name == "nt", "network_default": "disabled", "virtualization_commands": {}}
    checks["runtime_storage"] = configure_local_runtime()
    for name in ("ffmpeg", "ffprobe", "docker", "wsl", "cargo", "node"):
        checks["virtualization_commands" if name in {"docker", "wsl"} else "tools"] = checks.get("virtualization_commands" if name in {"docker", "wsl"} else "tools", {})
        checks["virtualization_commands" if name in {"docker", "wsl"} else "tools"][name] = shutil.which(name)
    checks["ffmpeg_version"] = ffmpeg_version() if checks["tools"].get("ffmpeg") else None
    checks["local_features"] = {
        "flite_tts": flite_available() if checks["tools"].get("ffmpeg") else False,
        "ffmpeg_whisper_asr": ffmpeg_whisper_available() if checks["tools"].get("ffmpeg") else False,
    }
    checks["policy"] = {"docker_or_wsl_started": False, "closed_services_enabled": False, "jianying_runtime_enabled": False}
    checks['schema_validation'] = schema_contract.probe()
    if args.project:
        policy_report = audit_local_tree(Path(args.project))
        checks["project_policy"] = policy_report
    ok = bool(checks["native_windows"] and checks["tools"].get("ffmpeg") and checks["tools"].get("ffprobe") and checks['schema_validation']['ok'])
    return _envelope("doctor", args, data={"ok": ok, "checks": checks}, status="succeeded" if ok else "failed", errors=[] if ok else [{"code": "DEPENDENCY_UNAVAILABLE", "message": "FFmpeg/FFprobe 或随包 Schema 执行器不完整", "retryable": False}])


def command_schema_show(args: argparse.Namespace) -> dict[str, Any]:
    _,schema,_=schema_contract.read_contract()
    return _envelope('schema.show',args,status='planned' if args.dry_run else 'succeeded',data={'contract':schema_contract.descriptor(),'schema':schema})


def command_schema_export(args: argparse.Namespace) -> dict[str, Any]:
    output=resolve_local_path(Path.cwd(),args.output,field='output')
    result=schema_contract.export_contract(output,dry_run=args.dry_run)
    return _envelope('schema.export',args,status='planned' if args.dry_run else 'succeeded',data={'output':str(output),'contract':result})


def command_operation_inspect(args: argparse.Namespace) -> dict[str, Any]:
    root, _ = load_project(args.project)
    path = root / "operations" / f"{args.operation_id}.json"
    if not path.exists():
        raise AppError("OPERATION_NOT_FOUND", f"找不到操作记录: {args.operation_id}", exit_code=3, path=str(path))
    return _envelope("operation.inspect", args, data={"path": str(path), "operation": load_json(path)})


def command_version(args: argparse.Namespace) -> dict[str, Any]:
    return _envelope("version", args, data={"cli_version": VERSION, "schema_version": SCHEMA_VERSION, "engine": ENGINE_ID, "runtime": "python+ffmpeg-local", "network": "disabled",'schema_validation':schema_contract.probe()})


def command_capabilities(args: argparse.Namespace) -> dict[str, Any]:
    return _envelope("capabilities", args, data=build_capability_manifest())


def command_policy_audit(args: argparse.Namespace) -> dict[str, Any]:
    root = Path(args.project).expanduser().resolve()
    report = audit_local_tree(root)
    error = policy_error_from_findings(report)
    if error:
        return _envelope("policy.audit", args, data=report, status="failed", errors=[error.as_dict()])
    return _envelope("policy.audit", args, data=report)


def _idempotency_context(args: argparse.Namespace) -> tuple[Path, Path, str] | None:
    key = getattr(args, "idempotency_key", None)
    if key and getattr(args, 'domain', None) == 'motion' and getattr(args, 'action', None) == 'pack' and getattr(args, 'pack_action', None) != 'apply':
        raise argument_error('运镜包幂等键仅用于 apply；捕获/查询不写工程幂等记录', 'idempotency_key')
    project_value = getattr(args, "project", None)
    if not key or getattr(args, "dry_run", False) or not project_value:
        return None
    root = Path(project_value).expanduser().resolve()
    if root.suffix.lower() == ".json" and root.name.lower() == "project.json":
        root = root.parent
    command = _command_name(args)
    return root, idempotency_record_path(root, command, str(key)), request_fingerprint(command, args)


def command_ocr(args: argparse.Namespace) -> dict[str, Any]:
    from .ocr_cli import handle
    return handle(args)


def command_face(args: argparse.Namespace) -> dict[str, Any]:
    from .face_cli import handle
    return handle(args)


def command_diagnostics(args):
    from . import pipeline_diagnostics as diagnostic_store
    root, _ = load_project(args.project)
    if args.action == 'list':
        data = diagnostic_store.list_records(root)
        if args.operation_id:
            data['records'] = [row for row in data['records'] if row['operation_id'] == args.operation_id]
    elif args.action == 'show':
        manifest, files = diagnostic_store.inspect_record(root, args.diagnostic_id, expected_sha256=args.expected_manifest_sha256)
        data = {'manifest': manifest, 'manifest_sha256': diagnostic_store.digest(files['manifest.json'])}
        if args.include_logs:
            data['logs'] = {name: raw.decode('utf8') for name, raw in files.items() if name.endswith('.log')}
    else:
        from .policy import require_local_reference
        require_local_reference(args.output, field='output')
        output = Path(args.output)
        if not output.is_absolute():
            output = root / output
        data = diagnostic_store.export_record(root, args.diagnostic_id, output,
            expected_sha256=args.expected_manifest_sha256, dry_run=args.dry_run)
    return _envelope('diagnostics.' + args.action, args, data=data, status='planned' if args.dry_run else 'succeeded')


_READ_ONLY_PROJECT_COMMANDS = {
    ('vfx','list'),('vfx','inspect'),('vfx','show'),('vfx','animation-properties'),
    ("media", "model-session"),
    *(('semantic', action) for action in ('adapter-list','adapter-inspect','index-list','verify','calibration-list','search')),
    ('surface','inspect'),
    ('diagnostics', 'list'), ('diagnostics', 'show'), ('diagnostics', 'export'),
    ("project", "inspect"),
    ("operation", "inspect"),
    ("queue", "list"),
    ("queue", "inspect"),
    ('cache','list'),
    ("lut", "list"),
    ("lut", "inspect"),
    ("rights", "check"),
    ("rights", "list"),
    ("rights", "history"),
    ("rights", "impact"),
    ("validate", None),
    ("policy", "audit"),
    ("subtitle", "evaluate"),
    ("quality", "check"),
    ("quality", "mask"),
    ("motion", "list"),
    ("motion", "inspect"),
    ('motion', 'html-inspect'),
    ('motion', 'html-fields'),
    ('motion', 'html-controls'),
    ('motion', 'html-quality'),
}


def _project_operation_lock(args: argparse.Namespace):
    """Return the operation-wide lock for a mutating project command."""
    project = getattr(args, "project", None)
    key = (getattr(args, "domain", None), getattr(args, "action", None))
    adapter_read_only = (key in {("audio", "enhancement-adapter"), ("interpolate", "adapter"), ("lipsync", "adapter"), ("audio", "adapter"), ("media", "adapter")} and getattr(args, "adapter_action", None) in {"list", "inspect"}) or (key in {("tts", "adapter"), ("tts", "voice"), ("asr", "adapter"), ('ocr','adapter'), ('face','adapter')} and getattr(args, "registration_action", None) in {"list", "inspect"})
    pack_read_only = key == ('motion', 'pack') and getattr(args, 'pack_action', None) != 'apply'
    if not project or getattr(args, "dry_run", False) or key in _READ_ONLY_PROJECT_COMMANDS or adapter_read_only or pack_read_only or key == ("queue", "cancel"):
        return contextlib.nullcontext()
    return project_write_lock(project)


from .lipsync_cli import adapter_command as command_lipsync_adapter, generate_command as command_lipsync_generate
from .interpolation_cli import adapter_command as command_interpolation_adapter, generate_command as command_interpolation_generate

COMMANDS: dict[tuple[str, str | None], Callable[[argparse.Namespace], dict[str, Any]]] = {
    ('lipsync','adapter'): command_lipsync_adapter,
    ('lipsync','generate'): command_lipsync_generate,
    ('interpolate','adapter'): command_interpolation_adapter,
    ('interpolate','generate'): command_interpolation_generate,
    ('surface','export'):command_surface,
    ('surface','inspect'):command_surface,
    ('cache','list'):command_cache,
    ('cache','prune'):command_cache,
    ('preview','frame'): command_preview,
    ('preview','range'): command_preview,
    ('preview','cache-list'): command_preview,
    ('preview','cache-prune'): command_preview,
    ('diagnostics', 'list'): command_diagnostics,
    ('diagnostics', 'show'): command_diagnostics,
    ('diagnostics', 'export'): command_diagnostics,
    ('ocr','adapter'): command_ocr,
    ('face','adapter'): command_face,
    ('face','scan'): command_face,
    ('face','retouch'): command_face,
    ('ocr','scan'): command_ocr,
    ('ocr','anchors'): command_ocr,
    ('schema','show'): command_schema_show,
    ('schema','export'): command_schema_export,
    ("project", "init"): command_project_init,
    ("project", "inspect"): command_project_inspect,
    ("project", "snapshot"): command_project_snapshot,
    ("project", "restore"): command_project_restore,
    ("project", "migrate"): command_project_migrate,
    ("project", "recover"): command_project_recover,
    ("media", "ingest"): command_media_ingest,
    ("media", "stabilize"): command_media_stabilize,
    ("media", "matting"): command_media_matting,
    ("media", "inpaint"): command_media_matting,
    ("media", "outpaint"): command_media_matting,
    ("media", "generate"): command_media_generate,
    ("media", "model-session"): command_model_session,
    ('media', 'mask-edit'): command_media_mask_edit,
    ("media", "relink"): command_media_relink,
    ("media", "adapter"): command_media_adapter,
    ("media", "track"): command_media_track,
    ("media", "track-bind"): command_media_track_bind,
    ("media", "reframe"): command_media_reframe,
    ("media", "understand"): command_media_understand,
    ("media", "prepare"): command_media_prepare,
    ('media', 'contact-sheet'): command_media_contact_sheet,
    ("media", "highlights"): command_media_highlights,
    ("media", "beat-cut"): command_media_beat_cut,
    ("media", "multicam"): command_media_multicam,
    ("media", "smart-cut"): command_media_smart_cut,
    ("audio", "extract"): command_audio_extract,
    ("audio", "separate"): command_audio_separate,
    ("audio", "adapter"): command_audio_adapter,
    ("ad", "plan"): command_ad_plan,
    ("ad", "apply"): command_ad_apply,
    ("subtitle", "validate"): command_subtitle_validate,
    ("subtitle", "normalize"): command_subtitle_normalize,
    ("subtitle", "segment"): command_subtitle_segment,
    ("subtitle", "transcribe"): command_subtitle_transcribe,
    ('subtitle', 'align'): command_subtitle_align,
    ("tts", "synthesize"): command_tts_synthesize,
    ("tts", "adapter"): command_tts_registration,
    ("asr", "adapter"): command_asr_adapter,
    ("subtitle", "evaluate"): command_subtitle_evaluate,
    ("tts", "voice"): command_tts_registration,
    ("effects", "list"): command_effects_list,
    ("effects", "inspect"): command_effects_inspect,
    ("motion", "list"): command_motion_list,
    ("motion", "inspect"): command_motion_inspect,
    ("motion", "apply"): command_motion_apply,
    ('motion', 'html-register'): command_html_register,
    ('motion', 'html-source'): command_html_source,
    ('motion', 'stroke-source'): command_html_source,
    ('motion', 'html-inspect'): command_html_inspect,
    ('motion', 'html-fields'): command_html_fields,
    ('motion', 'html-controls'): command_html_controls,
    ('motion', 'html-quality'): command_html_quality,
    ('motion', 'html-render'): command_html_render,
    ("timeline", "compose"): command_timeline_compose,
    ("timeline", "edit"): command_timeline_edit,
    ("timeline", "transition"): command_timeline_transition,
    ("validate", None): command_validate,
    ("rights", "check"): command_rights_check,
    ("rights", "list"): command_rights_list,
    ("rights", "history"): command_rights_history,
    ("rights", "update"): command_rights_update,
    ("rights", "export"): command_rights_export,
    ("rights", "batch-update"): command_rights_batch_update,
    ("rights", "impact"): command_rights_impact,
    ("rights", "retract"): command_rights_retract,
    ("rights", "decide"): command_rights_decide,
    ("rights", "apply"): command_rights_apply,
    ("render", None): command_render,
    ("queue", "enqueue"): command_queue_enqueue,
    ("queue", "list"): command_queue_list,
    ("queue", "inspect"): command_queue_inspect,
    ("queue", "run"): command_queue_run,
    ("queue", "cancel"): command_queue_cancel,
    ("quality", "check"): command_quality_check,
    ("quality", "mask"): command_quality_mask,
    ("quality", "golden"): command_quality_golden,
    ("quality", "scopes"): command_quality_scopes,
    ("convert", "import"): command_convert_import,
    ("convert", "export"): command_convert_export,
    ("template", "apply"): command_template_apply,
    ("template", "batch"): command_template_batch,
    ("library", "index"): command_library_index,
    ("library", "search"): command_library_search,
    ("library", "duplicates"): command_library_duplicates,
    ("library", "similar"): command_library_similar,
    ('fragment', 'save'): command_fragment,
    ('fragment', 'apply'): command_fragment,
    ('fragment', 'list'): command_fragment,
    ('fragment', 'inspect'): command_fragment,
    ("lut", "register"): command_lut_register,
    ('look', 'list'): command_look,
    ('look', 'inspect'): command_look,
    ('look', 'preview'): command_look,
    ('look', 'apply'): command_look,
    ("lut", "list"): command_lut_list,
    ("lut", "inspect"): command_lut_inspect,
    ("doctor", None): command_doctor,
    ("operation", "inspect"): command_operation_inspect,
    ("version", None): command_version,
    ("capabilities", None): command_capabilities,
    ("policy", "audit"): command_policy_audit,
}

from .community_cli import COMMAND_KEYS as COMMUNITY_COMMAND_KEYS, command as community_command
COMMANDS.update({key: (lambda args: community_command(args, _envelope)) for key in COMMUNITY_COMMAND_KEYS})
from .capture import command as capture_command
COMMANDS.update({("capture", action): (lambda args: capture_command(args, _envelope)) for action in ("devices", "record")})
from .semantic_cli import ACTIONS as SEMANTIC_ACTIONS, command as semantic_command
COMMANDS.update({('semantic', action): (lambda args: semantic_command(args, _envelope)) for action in SEMANTIC_ACTIONS})
from .semantic_upgrade import command as semantic_upgrade_command
COMMANDS[('project', 'upgrade-semantic')] = lambda args: semantic_upgrade_command(args, _envelope)
from .stem_separation_cli import command as stem_separation_command
COMMANDS[('audio', 'separate-stems')] = lambda args: stem_separation_command(args, _envelope)
from .enhancement_cli import command as enhancement_command, adapter_command as enhancement_adapter_command
COMMANDS[('audio', 'enhance')] = enhancement_command
COMMANDS[('audio', 'enhancement-adapter')] = enhancement_adapter_command
from .dubbing_cli import command as dubbing_command
COMMANDS[('dub', 'subtitles')] = lambda args: dubbing_command(args, _envelope)
from .ad_storyboard_cli import ACTIONS as STORYBOARD_ACTIONS, command as storyboard_command
COMMANDS.update({('ad', action): (lambda args: storyboard_command(args, _envelope, _operation)) for action in STORYBOARD_ACTIONS})
from .motion_pack_cli import command as motion_pack_command
COMMANDS[('motion', 'pack')] = lambda args: motion_pack_command(args, _envelope, _operation)
from .procedural_cli import command as command_vfx
COMMANDS.update({('vfx',action):command_vfx for action in ('list','inspect','apply','update','show','animate','animation-properties')})


def main(argv: list[str] | None = None) -> int:
    # Agent pipe consumers use UTF-8 regardless of the Windows console locale.
    # Keep in-memory streams used by embedding callers unchanged.
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        configure_local_runtime()
        handler = COMMANDS[(args.domain, getattr(args, "action", None))]
        replayed = False
        idempotency = _idempotency_context(args)
        with _project_operation_lock(args):
            transaction_root = getattr(args, "project", None)
            command_key = (args.domain, getattr(args, "action", None))
            adapter_read_only = (command_key in {("audio", "enhancement-adapter"), ("interpolate", "adapter"), ("lipsync", "adapter"), ("audio", "adapter"), ("media", "adapter")} and getattr(args, "adapter_action", None) in {"list", "inspect"}) or (command_key in {("tts", "adapter"), ("tts", "voice"), ("asr", "adapter"), ('ocr','adapter'), ('face','adapter')} and getattr(args, "registration_action", None) in {"list", "inspect"})
            pack_read_only = command_key == ('motion', 'pack') and getattr(args, 'pack_action', None) != 'apply'
            transaction_enabled = bool(transaction_root) and not getattr(args, "dry_run", False) and command_key not in _READ_ONLY_PROJECT_COMMANDS and not adapter_read_only and not pack_read_only and command_key not in {("project", "recover"), ("queue", "cancel")}
            with (project_transaction(transaction_root, command=_command_name(args)) if transaction_enabled else contextlib.nullcontext({"active": False, "recovered": False})) as transaction:
                if idempotency:
                    root, record_path, fingerprint = idempotency
                    if record_path.exists():
                        record = load_json(record_path)
                        if record.get("fingerprint") != fingerprint:
                            raise AppError("IDEMPOTENCY_CONFLICT", "幂等键已经绑定到不同请求", exit_code=2, path=str(record_path))
                        result = json.loads(json.dumps(record.get("response", {}), ensure_ascii=False))
                        result.setdefault("warnings", []).append({"code": "IDEMPOTENT_REPLAY", "message": "已返回相同幂等键的既有结果", "operation_id": result.get("operation_id")})
                        replayed = True
                    else:
                        result = handler(args)
                        atomic_write_json(record_path, {"record_version": "0.1.0", "command": _command_name(args), "key": args.idempotency_key, "fingerprint": fingerprint, "response": result, "created_at": now_iso()})
                else:
                    result = handler(args)
            if transaction.get("recovered"):
                result.setdefault("warnings", []).append({"code": "PROJECT_TRANSACTION_RECOVERED", "message": "执行本次命令前已恢复上次中断的项目元数据事务", "transaction_id": transaction.get("recovery", {}).get("transaction_id"), "command": transaction.get("recovery", {}).get("command")})
            cleanup = transaction.get('job_cleanup', [])
            if cleanup:
                result.setdefault('data', {})['job_cleanup'] = cleanup
                if any(row.get('status') != 'cleaned' for row in cleanup):
                    result.setdefault('warnings', []).append({'code':'JOB_WORKSPACE_PRESERVED', 'message':'部分任务工作目录保留；查看 job_cleanup 并显式 project recover --cleanup-jobs'})

        _print(result, args.format)
        return 0 if result.get("ok") else (7 if args.domain == "rights" or getattr(args, "publish", False) else 2)
    except AppError as exc:
        result = _envelope(_command_name(args), args, status="failed", errors=[exc.as_dict()], operation_id=exc.operation_id)
        _print(result, args.format)
        return exc.exit_code
    except (KeyError, ValueError, TypeError) as exc:
        result = _envelope(_command_name(args), args, status="failed", errors=[{"code": "INTERNAL_INPUT_ERROR", "message": str(exc), "retryable": False}])
        _print(result, args.format)
        return 9

