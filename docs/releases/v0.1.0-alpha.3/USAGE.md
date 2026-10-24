# agent editor kit alpha.3：500 风格 / 500 looks

本地原生 Windows x64 / CPython 3.13。CLI `0.1.2`，风格目录 `2.0.0`。本版把内置风格从 100 扩展到 500，并保留原 100 套的稳定 ID 和 LUT 字节。
Native Windows release with 500 offline creative SDR looks. Existing 100 IDs and LUT bytes are preserved.

## 下载与安装 / Download and install

下载 [artifacts/](artifacts/) 中全部 `.partNN`、`parts.json`、`assemble.py`、`version.json`、`SHA256SUMS.txt` 到同一目录。分卷只是二进制分块；须先合成普通 ZIP，再解压。每卷不超过 64 MiB。基础包不包含 Python、FFmpeg 或模型。
Download every part and metadata file into one folder. Reassemble the regular ZIP before extracting; do not try opening an individual part as a ZIP. Existing native Python and FFmpeg/ffprobe are required. No download, container or virtual environment is used during installation.

```powershell
$avkPython = 'C:/Python313/python.exe'
& $avkPython -I -B -X utf8 .\assemble.py --output E:/tools/agent-editor-kit-alpha3.zip
Expand-Archive E:/tools/agent-editor-kit-alpha3.zip E:/tools/agent-editor-kit-alpha3
Set-Location E:/tools/agent-editor-kit-alpha3
$avkManifest = (Get-Content ./version.json -Raw | ConvertFrom-Json).manifest_sha256
& $avkPython -I -B -X utf8 ./bundle/install.py --target E:/tools/aek-alpha3-installed --manifest-sha256 $avkManifest
& $avkPython -I -S -B -X utf8 E:/tools/aek-alpha3-installed/run.py doctor
& $avkPython -I -S -B -X utf8 E:/tools/aek-alpha3-installed/run.py look list
```

先按 `SHA256SUMS.txt` 核验文件；合成脚本会再次核验每卷及完整 ZIP。摘要检查内容一致性，不是作者签名。
Verify SHA256SUMS first; the assembler checks every part and the full ZIP. Hashes are not publisher signatures.

## 命名、选型和应用 / Naming, selection and application

001–100 保留 `sp-` / `t3-`；101–500 使用 `nt-`（Natron）/ `fl-`（FreshLUTs）来源前缀。编号用于阅读，命令始终使用稳定 ID。不同来源同名胶片不是重复命名：ID、作者、原始变体及实际 RGB 数据均单独记录。强度档位不计为新风格。
Each entry includes its original title, source-qualified ID, localized name, measured gray/skin/RGB changes, trial strength, creator, license, source commit and preview. A source name is an approximation label, not a certified film stock or proprietary filter.

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk look list --query '黑白'
& $avk look list --query 'CC0-1.0'
& $avk look inspect --id t3-kodak-gold-200
& $avk look preview --id t3-kodak-gold-200 --input E:/media/still.png --output E:/work/preview.png --strength 0.65
& $avk look apply --project E:/work/ad --id t3-kodak-gold-200 --global --strength 0.65 --dry-run
& $avk look apply --project E:/work/ad --id t3-kodak-gold-200 --global --strength 0.65
& $avk render --project E:/work/ad --output E:/work/ad/renders/graded.mp4 --publish
```

`--clip-id` 应用到指定视频片段；`--global` 应用到项目。默认替换该作用域内置预设，保留手工效果；只有 `--append` 显式叠加。静态 0–1 强度是在编码 RGB 混合 identity 和 LUT。每次应用复制 LUT、许可和来源到项目并登记权利台账。旧 alpha.2 来源证据只在字节精确匹配时保留，人工修改仍会拒绝覆盖。
Apply to an explicit video clip or the entire project. Replace is default; append is explicit. Application copies portable license evidence and provenance into the project. Exact alpha.2 provenance is compatible; modified project resources are preserved and refused.

## 完整说明与边界 / Profiles and boundaries

[500 项功能目录与详细说明](../../local/LOOK_PRESETS.md) · [功能滤镜 README](../../local/FILTERS.md) · [本地 Skill 安装](../../local/INSTALLATION.md) · [核验记录](../../validation/LOOK500_20261024.md) · [第三方许可](THIRD_PARTY.md)。

仅创意 SDR 编码 RGB；相机 Log/HDR/Float32 的 `look apply` 显式拒绝，需先按独立色彩契约转换。Hald 转 CUBE 有逐项披露的采样近似。LUT 不产生颗粒、光晕、暗角、美颜或 AI 特效。合成测试不构成自然素材画质、听感或完整剪映等价验收。
Creative display-referred SDR RGB only. No automatic camera calibration, grain, glow, vignette, beauty or AI effects. Synthetic validation is separate from natural footage and listening acceptance.
