# Installed-release runtime contract

This namespace always calls the locally installed `v0.1.0-alpha.3` package, using the editor Skill's
`scripts/run.ps1`. Other Skills share this launcher. The editable Skill source stays on E:; Codex reads
Windows directory junctions. `local/agent-ffmpeg/runtime.json` selects the native Python and installed path.

Public release downloads and fresh-machine instructions are at
[alpha.3 quickstart](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/docs/releases/v0.1.0-alpha.3/QUICKSTART.en.md).
Download the runtime ZIP plus Agent kit ZIP, extract the kit, run its `install.py --archive <runtime.zip>`,
then register its 17 Skills. The optional gallery ZIP extracts into the same kit directory. `run-example.py`
exercises an actual six-second edit/render/check/package workflow using included CC0 inputs.
The launcher verifies the release pin, installation receipt and launcher digest, then runs the installed
`run.py` with `-I -S -B -X utf8`. It sets temporary/runtime paths on E: and offline model environment flags.
These flags are not an operating-system network sandbox; do not invoke network tools or providers.

To install on another checkout with existing Windows CPython 3.13 x64 and FFmpeg/ffprobe on PATH:

```powershell
& C:/Python313/python.exe -E -B -X utf8 scripts/install_look500_release.py --activate --evidence E:/path/to/checkout/docs/validation/evidence/my-local-install
.\register-agent-ffmpeg-local-skills.ps1
```

Run the install script in the repository; the pinned release ZIP parts are in `docs/releases/v0.1.0-alpha.3/artifacts/`.
The installer preserves existing destinations. An unavailable installation requires repair/reinstallation,
not a source fallback. The namespace manifest registers only `$agent-ffmpeg-local-editor`; its 17 modules are internal references. The registrar retires only this checkout's 16 previous specialist junctions. Legacy `video-cut-` Skills are separate.

## Project workflow

Read actual command help, `capabilities` and `schema show` before authoring JSON. Example with `$avk` set
as in SKILL.md (all source files and changes.json must already exist):

```powershell
$avkProject = 'E:/video-work/my-ad'
& $avk project init $avkProject --name 'My ad'
& $avk media ingest --project $avkProject --input 'E:/media/product.mp4'
# Use the returned data.asset.id in the edit JSON. Audio is an explicit track.
& $avk timeline compose --project $avkProject --input 'E:/video-work/changes.json'
& $avk validate --project $avkProject
& $avk preview frame --project $avkProject --frame 0
& $avk render --project $avkProject --output 'E:/video-work/my-ad/renders/ad.mp4'
& $avk quality check --project $avkProject --input 'E:/video-work/my-ad/renders/ad.mp4'
```

For publication, add actual license/source evidence and check `rights check`; `--publish` is only a local gate.
Project packages can retain absolute license-evidence paths: when moving hosts, rebind and recheck those paths.

## Rendering and verification

The default renderer uses FFmpeg. Explicit `settings.pixel_pipeline.engine = "float32-native-v1"` selects
its advertised subset and requires complete source/working/delivery signal settings and budgets from the
schema. `surface export` is a separate frame-bundle interchange command. Do not treat experimental later
Float32 transitions or legacy development notes as release capabilities. Node/Chromium and model weights
are optional existing dependencies, not bundled base features.

Return exact output paths, warnings, exit codes and error details. Verify actual decoded files and manifests;
static frames, continuous playback, automatic audio checks and human listening have separate acceptance.
The alpha package does not provide complete CapCut parity.

## 500 offline looks

Read [looks.md](looks.md). `look apply` copies LUT/license/provenance into the project. Built-in preset evidence uses relative project paths; unrelated user media evidence still needs review after relocation.
