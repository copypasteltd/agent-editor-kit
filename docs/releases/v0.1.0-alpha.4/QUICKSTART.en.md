# agent editor kit / CLI0.1.66

Native Windows CPython3.13 x64 application. The only public entry is `$agent-ffmpeg-local-editor`, with 17 internal modules. Python, FFmpeg/ffprobe, drivers, model weights and the complete music runtime are separate local dependencies. Do not use Docker, WSL or virtual environments.

1. Download both ZIPs, SHA256SUMS.txt and this quickstart from the same release into one directory. Replace the example paths. Compare each computed digest with the checksum list before extracting into new directories; the installer also checks the internal application inventory.

```powershell
$downloads = "E:/video-tools/downloads"
$bundle = "E:/video-tools/application-bundle"
$kit = "E:/video-tools/skill-kit"
Get-Content -LiteralPath "$downloads/SHA256SUMS.txt"
Get-FileHash -LiteralPath "$downloads/agent-editor-kit-v0.1.0-alpha.4-cp313-win_amd64.zip" -Algorithm SHA256
Get-FileHash -LiteralPath "$downloads/agent-editor-kit-community-unified-skill-r59.zip" -Algorithm SHA256
Expand-Archive -LiteralPath "$downloads/agent-editor-kit-v0.1.0-alpha.4-cp313-win_amd64.zip" -DestinationPath $bundle
Expand-Archive -LiteralPath "$downloads/agent-editor-kit-community-unified-skill-r59.zip" -DestinationPath $kit
```

2. Install the application offline into a new target. This does not download models. Before model setup, the installed entry can already run version/doctor and basic editing commands.

```powershell
$python = "C:/Python313/python.exe"
$installed = "E:/video-tools/application-installed"
& $python -E -B -X utf8 "$bundle/install.py" --bundle $bundle --target $installed --manifest-sha256 "sha256:1da7f0a678ea678f49af6d9b847dfd8912b11ede04aad22f8d87ee247ee1117a"
& $python -I -S -B -X utf8 "$installed/run.py" version
& $python -I -S -B -X utf8 "$installed/run.py" doctor
```

3. Configure basic editing by binding the unified Skill to the installation above. Timeline editing, filters, captions, previews and rendering are available through this entry. Configure voice, translation and semantic models separately below. The configurator backs up previous settings and creates a basic binding without inherited machine model paths.

```powershell
& $python -E -B -X utf8 "$kit/scripts/activate_community_runtime.py" --installed $installed --base-only
```

Optional models: prepare verified `kokoro-zh-en-int8` and `opus-zh-en-cpu-int8` CPU packs before enabling voice/translation. `kokoro-zh-en-cuda13` and `opus-zh-en-cuda12-int8` are optional GPU packs. PACKS is the parent of these extracted pack directories. Model configuration requires both CPU packs and verifies each selected pack before binding it. The two release ZIPs do not contain these packs; use the source, license, digest and reproduction links below.

[Model catalog and pinned manifests](https://github.com/copypasteltd/agent-editor-kit/blob/main/product/src/ai_ad_editor/material_data/model-packs.json) · [CPU pack builder](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/build_community_model_pack.py) · [GPU pack builder](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/build_community_gpu_packs.py) · [Offline pack installer](https://github.com/copypasteltd/agent-editor-kit/blob/main/scripts/install_community_pack.py)

```powershell
$packs = "E:/video-tools/model-packs"
& $python -E -B -X utf8 "$kit/scripts/activate_community_runtime.py" --installed $installed --packs $packs
```

For GPU packs, replace the configuration command with the following and provide the actual matching DLL directories. Speech and translation require different CUDA versions. Use `--device auto` to prefer the configured GPU, and inspect the actual device/provider and any reported CPU fallback.

```powershell
& $python -E -B -X utf8 "$kit/scripts/activate_community_runtime.py" --installed $installed --packs $packs --voice-cuda-lib "E:/video-tools/cuda13/bin" --translation-cuda-lib "E:/video-tools/cuda12/bin"
```

4. Register the one Skill and inspect the actual installed version. A same-name entry pointing elsewhere is preserved and registration refuses to replace it. For upgrades, read the shipped delivery guide rather than deleting an unknown directory. Select `$agent-ffmpeg-local-editor` from the outer Agent.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "$kit/register-agent-ffmpeg-local-skills.ps1"
$entry = "$kit/skills/agent-ffmpeg-local-editor/scripts/run.ps1"
& $entry version
& $entry doctor
& $entry capabilities
& $entry model-pack list
& $entry gpu inspect
```

5. Create a project and ingest your authorized media. The example video, still, subtitles, narration text and changes.json must exist. Read the returned `data.asset.id`, then author changes.json using the schema and command help; never copy a random asset ID from an old case. Author video and audio tracks separately, preview real look candidates and record client choices before composing.

```powershell
$aekProject = "E:/video-work/my-ad"
& $entry project init $aekProject --name "My ad"
& $entry media ingest --project $aekProject --input "E:/media/product.mp4"
& $entry schema show
& $entry timeline compose --help
& $entry look list --query "Kodak"
& $entry look inspect --id t3-kodak-gold-200
& $entry look preview --id t3-kodak-gold-200 --input "E:/media/still.png" --output "$aekProject/exports/film-preview.png" --strength 0.65
& $entry timeline compose --project $aekProject --input "E:/video-work/changes.json"
& $entry look apply --project $aekProject --id t3-kodak-gold-200 --global --strength 0.65 --dry-run
& $entry look apply --project $aekProject --id t3-kodak-gold-200 --global --strength 0.65
```

The optional speech/translation examples perform actual inference. Prepare their inputs, model packs and configuration first, and use a new asset ID. Review complete audio, pronunciation, translation meaning and duration. Then author voice-changes.json with the actual audio asset ID and an explicit audio track before the final compose command below; place translated subtitles on their intended track too.

```powershell
& $entry voice list
& $entry voice synthesize --project $aekProject --voice zf_001 --input "E:/media/narration.txt" --device auto --asset-id asset_voice
& $entry translate subtitles --project $aekProject --from zh-Hans --to en --input "E:/media/captions.srt" --output exports/bilingual.srt --mode bilingual --device auto
& $entry timeline compose --project $aekProject --input "E:/video-work/voice-changes.json"
```

6. Validate, preview, render and inspect the encoded movie, then export an editable project package. Import into a new directory and re-render; check images, complete audio, clocks and recipes separately. Inspect exit codes and JSON ok/status/errors/warnings/artifacts together. Automated quality checks do not replace continuous playback or listening.

```powershell
& $entry validate --project $aekProject
& $entry preview frame --project $aekProject --frame 0
& $entry render --project $aekProject --output "$aekProject/renders/ad.mp4"
& $entry quality check --project $aekProject --input "$aekProject/renders/ad.mp4"
& $entry convert export --project $aekProject --target-format package --output "$aekProject/exports/ad.aevpkg.zip"
& $entry convert import --input "$aekProject/exports/ad.aevpkg.zip" --output "E:/video-work/restored-ad"
& $entry render --project "E:/video-work/restored-ad" --output "E:/video-work/restored-ad/renders/replay.mp4"
& $entry rights check --project $aekProject
```

Neural music additionally needs an explicitly registered existing local adapter, native runtime and weights; the four packs above do not supply that model. Read [neural music](../../../skills/agent-ffmpeg-local-editor/references/neural-music.md). Editable score synthesis, loop repair and neural generation are separate operations.

```powershell
& $entry music generate --help
& $entry delivery --help
```

[Skill and 17 modules](../../../skills/agent-ffmpeg-local-editor/SKILL.md) · [Client look selection](../../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md) · [Speech, translation and audio](../../../skills/agent-ffmpeg-local-editor/references/community-materials.md) · [Upgrade, recovery and rollback](../../product/DELIVERY_CONTROLLER.md)

Before publishing media, add source/model/voice-use rights evidence and run rights check. render --publish is a local rights gate, not an upload. Review generated content individually; these attachments exclude unreviewed model audio. A new directory on the same host does not establish clean-host or cross-machine acceptance. Full CapCut parity and all original G01–G38 conditions remain open.

`v0.1.0-alpha.4-local.64` / CLI`0.1.66`
