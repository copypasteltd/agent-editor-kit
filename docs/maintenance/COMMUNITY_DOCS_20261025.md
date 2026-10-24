# Community/GPU documentation maintenance

The current local extension uses CLI 0.1.3, one registered Skill, 17 internal task
modules and the four model pins recorded in the application. Keep the published
alpha.3 runtime and original Skill/gallery assets byte-identical.

`scripts/document_community_materials.py` adds the extension to the restored
three-language READMEs without removing historical functional/service/Skill/case
tables. It requires actual final CPU/GPU evidence and preserves stable IDs,
commands and link targets during simplified/traditional conversion.

The older `build_product_readmes.py`, `readme_unified_skill.py` and
`consolidate_agent_ffmpeg_skills.py` reconstruct their historical alpha.3 layouts.
They are retained for reproduction and must not be used as the current update
entrypoint: the consolidation script can replace newer Skill references and the
older README generator does not include this extension. Update the current docs
in place, or use the additive community generator with matching real evidence.

For a new application/model build:

1. Preserve the former local bundle, model manifests, inference responses and
   failed attempts. Build into new owned directories on E:.
2. Verify source/media/model notices and every file hash; pin the actual four
   model inventories, then freeze and build the base application.
3. Install from the pinned offline bundle; test actual native CPU/CUDA paths,
   strict failures, explicit fallback, portable model installation, preview/render
   and editable-package round trip as appropriate to the changes.
4. Pin the one Skill to the new installed manifest, configure explicit local
   CPU/GPU paths, register its owned junction, and test the real discovery entry.
5. Maintain all three READMEs, current capability/manual links, resource/voice
   catalogs, case media/provenance and separate numbered verification rows. Do
   not combine historical regression counts or claim listening from PCM metrics.
6. Build a new matching small Skill kit. Keep model archives and the base runtime
   separate; audit packaged bytes and actual native use from a new directory.
7. Run `scripts/audit_community_delivery.py` for this fixed delivery and Git's
   diff checks. Adapt future audit requirements to their actual version/evidence;
   do not falsify old receipt counts. Commit on main and use the configured
   ordinary auto-push to `copypasteltd/agent-editor-kit`.

The current audit checks only local filesystem links; it does not silently open
browsers, create virtual environments, download models, or certify legal/semantic
acceptance. If a browser is separately used, close its unused tabs afterwards.

## 同日目标差距评估增量

当前评估为 `docs/product/GOAL_GAPS_20261025.md`；6 次固定安装版只读 CLI、GitHub 发行查询和文档检查保存在 `docs/validation/evidence/goal-gaps-20261025-r1/`。本次仅补充三语 README 的 R38 和当前差距入口，不修改产品内核、Skill、模型或已有发行附件。

`audit_community_delivery.py` 的 R37 计数是素材/GPU 阶段快照约束；不要为了让历史脚本通过而删除后续 README 行。当前文档校验以本次 `documentation-check.json` 为准，原 R1/R2/R3 证据保留其日期和范围。
