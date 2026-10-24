# agent editor kit: download, install and render your first video

[简体中文](QUICKSTART.md) · [繁體中文](QUICKSTART.zh-TW.md) · [Release downloads](https://github.com/copypasteltd/agent-editor-kit/releases/tag/v0.1.0-alpha.3) · [Complete manual](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/README.en.md)

**v0.1.0-alpha.3 prerelease / CLI 0.1.2 / 500 looks / 17 Skills.** This is a native Windows editing CLI for Agents. Complete CapCut functionality and broad natural-media quality remain development targets; consult the actual capability contracts.

## 1. Prerequisites and downloads

Use existing **Windows x64, CPython 3.13 x64, FFmpeg and ffprobe**. Put FFmpeg/ffprobe on PATH and adjust the Python path below for your machine. Installation is offline, without Docker, WSL, containers, virtual environments or global pip changes.

Download these Release assets into a folder such as `E:/Downloads/`:

| File | Required | Purpose |
|---|---|---|
| `agent-editor-kit-v0.1.0-alpha.3-cp313-win_amd64.zip` | Yes | Application and eight pinned wheels; no multipart assembly needed |
| `agent-editor-kit-v0.1.0-alpha.3-agent-kit.zip` | Yes | Installer, 17 Skills, registration script, three-language guides, runnable example and CC0 inputs |
| `SHA256SUMS.txt` | Recommended | Compare download SHA-256 values; the installer also enforces the runtime ZIP hash |
| `agent-editor-kit-v0.1.0-alpha.3-gallery.zip` | For client look selection | N002 original, all 500 actual look samples, offline gallery, rights and comparison-board inputs |

Python, FFmpeg, Node/Chromium, model weights and GPU drivers are not bundled. Basic editing and the included example require no model or Node. Transcription, speech, matting and repair use their separately prepared local dependencies.

## 2. Extract the Agent kit and install the runtime

Choose a new tools directory. Keep the runtime ZIP intact; the installer verifies and extracts it:

```powershell
$avkPython = 'C:/Python313/python.exe'
$avkHome = 'E:/tools/agent-editor-kit-alpha3'
$avkArchive = 'E:/Downloads/agent-editor-kit-v0.1.0-alpha.3-cp313-win_amd64.zip'
Expand-Archive -LiteralPath 'E:/Downloads/agent-editor-kit-v0.1.0-alpha.3-agent-kit.zip' -DestinationPath $avkHome
Set-Location $avkHome
& $avkPython -I -B -X utf8 ./install.py --archive $avkArchive
```

Successful JSON has `ok: true`. The app is installed under `$avkHome/local/agent-ffmpeg/v0.1.0-alpha.3/installed/`, with its binding at `$avkHome/local/agent-ffmpeg/runtime.json`. Existing installations are preserved; reuse their launcher or choose a new tools directory.

## 3. Register Skills and inspect actual capabilities

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./register-agent-ffmpeg-local-skills.ps1
$avk = Join-Path $avkHome 'skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk doctor
& $avk capabilities
& $avk schema show
```

Registration creates 17 `$agent-ffmpeg-local-*` junctions in Codex's Skill discovery directory; editable sources remain in the tools directory. Conflicting existing Skills are preserved and reported. Users already running this repository's local installation can keep their existing entry points.

If the client does not list newly registered Skills yet, reopen the conversation to rediscover them. Invoke:

```text
$agent-ffmpeg-local-editor Turn E:/media/product.mp4 into a 15-second vertical ad.
Inspect the media and actual capabilities, create an editable timeline and preview,
then render, check quality and export the project package. Add audio explicitly when
preserving source sound. Show actual look candidates and record the final ID, strength and scope.
```

## 4. Run the first-video example

No additional media is needed. Included CC0 fictional-product images and a synthetic pulse exercise ingest, timeline editing, motion, a look at strength 0.65, explicit audio, preview, local publication-rights checks, actual rendering, quality checks and project-package roundtrip:

```powershell
& $avkPython -I -B -X utf8 ./run-example.py --output 'E:/video-work/aek-first-demo'
```

The output directory must not exist. Main outputs:

| Path relative to the example output | Contents |
|---|---|
| `project/project.json` | Editable project |
| `project/renders/demo.mp4` | Actual 360×640, 30 fps, six-second, 180-frame video with audio |
| `demo.aevpkg.zip` | Importable project and referenced media package |
| `restored/` | Imported and validated project |
| `commands.json`, `logs/` | Actual CLI arguments, responses, errors and timings |
| `verification.json`, `probe.json` | Encoded-output and full-decode checks |

This demonstrates installation and the editing workflow; it does not establish natural-ad quality, listening quality or complete CapCut parity.

## 5. Show clients all 500 looks

Extract the optional gallery ZIP into the same `$avkHome`:

```powershell
Expand-Archive -LiteralPath 'E:/Downloads/agent-editor-kit-v0.1.0-alpha.3-gallery.zip' -DestinationPath $avkHome
Start-Process (Join-Path $avkHome 'docs/assets/looks-n002-20261024-r1/index.html')
```

Search/filter the offline page, compare original/output and export a shortlist JSON. Agents can also produce a compact comparison board:

```powershell
$aekGallery = Join-Path $avkHome 'skills/agent-ffmpeg-local-editor/scripts/look_gallery.py'
& $avkPython -I -S -B -X utf8 $aekGallery --ids t3-fuji-superia-800 nt-bw-agfa-apx-100 fl-0000634-darkblue --output 'E:/video-work/client-look-options'
```

Trial the client's selected strength on their actual footage, then record stable ID, strength and clip/global scope before applying. Gallery samples use strength 1.0. Image rights and LUT licenses are separate. Close unused browser tabs after browsing.

## 6. Use your own media and the CLI

Read each command's `--help` and use actual asset IDs from ingest responses. Video files containing sound do not automatically create timeline audio. Supply actual media provenance and rights before using the local `render --publish` gate; that option does not upload files.

```powershell
& $avk project init 'E:/video-work/my-ad' --name 'My ad'
& $avk media ingest --project 'E:/video-work/my-ad' --input 'E:/media/product.mp4'
& $avk timeline compose --help
& $avk look list --query '黑白'
& $avk look inspect --id t3-kodak-gold-200
& $avk render --help
& $avk quality check --help
```

The workflow is ingest → author/apply changes with actual IDs → validate → preview → render → inspect encoded media/audio/rights → export the editable package. The example script includes working edit-JSON generation.

[Modules, services and Skills](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/README.en.md) · [Known gaps](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/docs/product/GOAL_GAPS_20261024.md) · [Multipart fallback installation](https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.3/docs/releases/v0.1.0-alpha.3/USAGE.md)
