# 依据本地数据分析投放与变体 / campaign-analytics

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Local campaign tables → ROAS/CPA/funnel/suggestions

Commands: `advisory Skill`. No ad-platform connector; metrics depend on data/attribution assumptions.

## Workflow

Inspect the supplied dataset, period, units and missing values. State attribution assumptions and compute
metrics from actual rows. Keep observed facts separate from hypotheses. Recommend the next creative test
and pass its brief to the ad/editor modules. No ad-account connection or real-time campaign access is provided.
Review the credited local analysis helpers and their dependencies before use.

## Attributed resources

[Upstream workflow](references/upstream/workflow.md) retains author, source commit and license. Use specific frameworks/helpers only when relevant; inspect their inputs and dependencies first. The shared runtime contract governs execution.
