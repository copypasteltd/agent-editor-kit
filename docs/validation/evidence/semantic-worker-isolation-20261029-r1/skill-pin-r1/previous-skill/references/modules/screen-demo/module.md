# 录屏锚点、缩放与产品演示 / screen-demo

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Recording + action anchors → zoom/return/caption demo

Commands: `timeline compose; ocr anchors; preview range`. OCR needs existing models; text boxes are not clickable-control bounds.

For new native Windows media, read [capture](../../native-capture.md) and use
`capture devices/record` with an explicit source and finite duration. The actual
CPU/GPU window-recording example is linked there; camera/microphone/AV sync
acceptance remains separate.

## Workflow

Map actual actions, pauses and visible results to source times. Use supported timeline keyframes or camera
presets, keeping cursor actions and result text legible. Retain honest waits or disclose sped-up sections.
Preview key anchors at output resolution, render and verify the result. Close unused tabs if a separate browser tool is used.
