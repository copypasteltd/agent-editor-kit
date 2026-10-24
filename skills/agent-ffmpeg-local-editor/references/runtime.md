# Installed-release runtime contract

This namespace calls the locally installed `v0.1.0-alpha.4-local.1` / CLI 0.1.3
package using this Skill's `scripts/run.ps1`. Its 17 modules share the launcher.
The editable Skill source stays on E:; Codex reads
Windows directory junctions. `local/agent-ffmpeg/runtime.json` selects the native Python and installed path.

The current native local build, offline packs, hashes and fresh-directory procedure
are recorded in [local delivery](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/COMMUNITY_LOCAL_DELIVERY.md).
The public alpha.3 archive/kit remains CLI 0.1.2 with its historical scope; do not
combine its installer or manifest with the new Skill. The 500-look gallery remains
usable as a separate offline selection reference. Historical six-second examples
and their original runtime pins remain unchanged.
The launcher verifies the release pin, installation receipt and launcher digest, then runs the installed
`run.py` with `-I -S -B -X utf8`. It sets temporary/runtime paths on E: and offline model environment flags.
These flags are not an operating-system network sandbox; do not invoke network tools or providers.

Use the matching local bundle with the native Windows CPython 3.13 installer,
then install each explicitly supplied model archive against its catalog pin.
Record the native Python, installation receipt/launcher hashes and model paths
in local runtime configuration before running the registrar. See the delivery
guide for the exact verified command and hashes. No virtual environment is used.
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

## GPU speech and translation

Read [community-materials.md](community-materials.md). Optional
`community_config` in runtime.json points to an existing local JSON with `voice`
and `translation` objects, each containing `cpu_pack`, `gpu_pack` and
`cuda_library_directory`. The launcher sets `AEK_COMMUNITY_DEVICE_CONFIG` only
for its child process. GPU packs stay separate from the base application.
`auto` prefers a supported GPU with enough free memory and reports fallback;
`cuda` is strict. Do not stop other GPU workloads. Model integrity checks apply
before inference, including CPU retries. No implicit source or network fallback.

## 500 offline looks

Read [looks.md](looks.md). `look apply` copies LUT/license/provenance into the project. Built-in preset evidence uses relative project paths; unrelated user media evidence still needs review after relocation.
