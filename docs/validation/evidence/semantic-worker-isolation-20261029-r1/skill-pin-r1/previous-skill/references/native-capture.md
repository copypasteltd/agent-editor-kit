# Native Windows capture

Use `capture devices` to list current camera/microphone IDs without recording.
Use `capture record --help` before a finite recording. Choose `--kind window`
with an exact `--window-title`, `screen` with an optional explicit region,
`camera` with a returned video ID, or `microphone` with a returned audio ID.
Video includes audio only when a microphone ID is explicitly supplied.

```powershell
& $avk capture devices
& $avk capture record --project './workspace/demo' --kind window --window-title 'Your application title' --duration-seconds 5 --encoder auto --asset-id take-01 --dry-run
& $avk capture record --project './workspace/demo' --kind window --window-title 'Your application title' --duration-seconds 5 --encoder auto --asset-id take-01
```

Read the returned asset ID/URI and use it in the ordinary editable timeline.
`auto` prefers NVENC when NVIDIA is available, records failure and CPU fallback;
`h264_nvenc` is strict GPU encoding and `libx264` is explicit CPU encoding.
`--cancel-file` supports cancellation before or during recording. Existing
assets/directories are preserved. Incomplete media stays in diagnostic cache.

The current evidence covers two-second CPU/GPU captures of an owned test window,
complete decode, moving pixels and expected failure/cancellation. Actual camera,
microphone, AV sync, permission/device loss and long recording quality remain
unaccepted. Source evidence does not grant rights to recorded content.

[Workflow, actual MP4/GIF and limits](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/NATIVE_CAPTURE.md)
