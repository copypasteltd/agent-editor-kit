"""Build detailed Chinese look references from measured data and reviewed notes."""
from __future__ import annotations

import ctypes
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[1]
LOCAL = ROOT / "docs/local"
EVIDENCE = ROOT / "docs/validation/evidence/look-profiles-20261024-r1"


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def traditional(text):
    protected = []

    def hold(match):
        protected.append(match.group())
        return f"__PROTECTED_{len(protected) - 1:05}__"

    text = re.sub(r"```[\s\S]*?```|`[^`\n]+`|(?<=\]\()[^\n)]+(?=\))", hold, text)
    convert = ctypes.WinDLL("kernel32", use_last_error=True).LCMapStringEx
    convert.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32, ctypes.c_wchar_p, ctypes.c_int,
                        ctypes.c_wchar_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_longlong]
    convert.restype = ctypes.c_int
    required = convert("zh-TW", 0x04000000, text, -1, None, 0, None, None, 0)
    if not required:
        raise ctypes.WinError(ctypes.get_last_error())
    buffer = ctypes.create_unicode_buffer(required)
    if not convert("zh-TW", 0x04000000, text, -1, buffer, required, None, None, 0):
        raise ctypes.WinError(ctypes.get_last_error())
    text = buffer.value
    for before, after in [("视频", "影片"), ("視頻", "影片"), ("項目", "專案"),
                          ("幀", "影格"), ("哈希", "雜湊"), ("鏈接", "連結"),
                          ("信息", "資訊"), ("軟件", "軟體"), ("數據", "資料"),
                          ("采樣", "取樣"), ("這里", "這裡"), ("后", "後"),
                          ("默認", "預設"), ("質量", "品質"), ("字節", "位元組"),
                          ("十六進制", "十六進位"), ("標簽", "標籤"), ("文檔", "文件"),
                          ("范圍", "範圍"), ("并", "並"), ("之后", "之後"),
                          ("于", "於"), ("注冊", "註冊"), ("錄制", "錄製")]:
        text = text.replace(before, after)
    for i, original in enumerate(protected):
        text = text.replace(f"__PROTECTED_{i:05}__", original)
    return text


def main():
    analysis = json.loads((EVIDENCE / "analysis.json").read_bytes())
    notes = json.loads((LOCAL / "LOOK_PRESET_NOTES.json").read_bytes())
    rows = analysis["records"]
    assert analysis["script_sha256"] == digest(ROOT / "scripts/analyze_look_profiles.py")
    assert len(rows) == len(notes["records"]) == 100
    assert [r["id"] for r in rows] == [r[0] for r in notes["records"]]
    parts = [
        "# 100 个风格预设：实际效果与逐项数值\n",
        "[简体中文](LOOK_PRESET_DETAILS.md) · [繁體中文](LOOK_PRESET_DETAILS.zh-TW.md) · [编号与全部原始预览](LOOK_PRESETS.md) · [核验回执](../validation/evidence/look-profiles-20261024-r1/verification.json)\n",
        "这里说明本机 `v0.1.0-alpha.2` 实际安装的 100 个 LUT，保留既有 001–100 编号。每项都包含真实颜色作用、灰阶曲线、三个肤色测试块、红绿蓝映射、场景建议、注意点、试用强度和既有 PNG/MP4。说明基于安装版字节与采样结果，不按胶片名字推测颗粒、宽容度或镜头效果。\n",
        "## 怎样理解这些数据\n",
        "- **测量条件**：强度 1.0、四面体插值、编码 SDR RGB。十六进制是量化到 8 位后的颜色；内部保留浮点数。\n"
        "- **灰阶百分比**：指输入 RGB 码值的百分比，50% 为三通道 127.5；不表示场景反射率、18% 灰或线性曝光。\n"
        "- **Y′ 码值**：`0.2126 R′ + 0.7152 G′ + 0.0722 B′`，范围 0–255，用于对照灰阶明暗；不是线性亮度、EV 或显示器实测。\n"
        "- **中段跨度比**：`(Y′75% − Y′25%) / 127.5`；1 表示与输入的这段跨度相同，大于 1 表示这段拉开，小于 1 表示这段收窄。它不能代表整条曲线或感知对比评分。\n"
        "- **肤色块与三色块**：只描述固定合成色块的变化，不代表人脸检测、肤色保护或所有真实肤色。三色色块刻意使用非满饱和输入，便于看色相与饱和度变化。\n"
        "- **建议与实测分开**：场景和强度是人工选型起点，尚未进行自然素材画质验收。目录中的默认推荐强度仍为 1；这里的范围不修改产品默认值。纯黑白效果用 1，低于 1 会混回原始颜色。\n"
        "- **共同边界**：均为逐像素色彩 LUT。它们本身不生成颗粒、划痕、暗角、柔焦、发光、空间雾、边框、美颜或 AI 特效，也不自动执行曝光/白平衡校正。\n",
        "上游标签不是官方胶片、徕卡或剪映滤镜认证，也不保证精确复现真实胶片。`sp-` 来自 Striped Purple，保留 16³/32³/64³ 原网格；`t3-` 来自 t3mujinpack，144³ 原生 RGB8 Hald 被转换成 33³ CUBE，存在已披露的近似误差。本轮读取安装版并与 100 张既有 FFmpeg PNG 逐像素对照，单通道差值不超过 1 个 8 位码值；这不是对自然画面质量的评分。\n",
        "[机器可读测量](../validation/evidence/look-profiles-20261024-r1/analysis.json) · [可编辑逐项说明](LOOK_PRESET_NOTES.json) · [数值分析脚本](../../scripts/analyze_look_profiles.py) · [文档生成脚本](../../scripts/build_look_profile_docs.py)\n",
        "## 可视色块对照\n",
        "每张图第一行是原色，之后每行是一个 LUT 的直接数值采样。图表是计算结果，没有重新生成视频；原生 FFmpeg 画面与成片见各项链接。\n",
        "![001–049：灰阶、肤色与三色的实际 LUT 采样](../assets/look-profiles-20261024-r1/palette-001-049.png)\n",
        "![050–100：灰阶、肤色与三色的实际 LUT 采样](../assets/look-profiles-20261024-r1/palette-050-100.png)\n",
        "## 快速目录\n",
        "编号沿用原目录；名称保持上游原文。灰阶曲线相似不代表所有颜色相同，某些胶片预设属于细微区别。\n",
        "| # | 名称 / 稳定 ID | 实际作用 | 建议试用场景 |\n|---|---|---|---|"
    ]
    for row, note in zip(rows, notes["records"]):
        parts.append(f"| {row['number']:03} | [{row['name']}](#preset-{row['id']})<br>`{row['id']}` | {note[1]} | {note[2]} |")
    parts += ["\n## 容易混淆的区别\n",
              "| 对照组 | 这批实际 LUT 的区别 |\n|---|---|\n"
              "| 1910s / 1920s / 1930s | 1910s 暖棕、抬黑、亮端平台；1920s 中性黑白且灰阶基本不动；1930s 黄橄榄单色、端点较完整。 |\n"
              "| Grey Matter / Horchata | 灰阶明暗关系接近，前者彩色大幅收敛成暖灰，后者保留彩色。 |\n"
              "| Infrared / Infrared 2 | 同样将绿色置换成紫红，但第一版更强，第二版更保留原色分量。不是两种红外传感器模拟。 |\n"
              "| Lomochrome Purple 1–5 | 第 1、2 版绿转洋红，第 3–5 版绿转黄绿/橄榄；第 1 版红变深紫，第 5 版绿更暗、蓝更亮青。 |\n"
              "| Velvia 100 / 50 | 50 的低灰更深，中灰略暗；100 中灰略亮。两者都有明显彩色增强。 |\n"
              "| Portra 160 VC / 400 VC | 灰阶几乎相同，400 VC 的蓝色色块更鲜、更偏正蓝；不是两种显著不同的对比曲线。 |\n"
              "| Kodakchrome 200 / 64 | 关系很接近；200 与 64 主要是细微低灰、肤色和蓝色差异。上游拼写原样保留。 |\n"
              "| NC / VC / UC | 是上游方案名称。某个 NC 也可能增强蓝色，不能据名称认为所有颜色都更淡。 |\n",
              "## 逐项详情\n"]
    gray_keys = ["gray_0", "gray_10", "gray_25", "gray_50", "gray_75", "gray_90", "gray_100"]
    for row, note in zip(rows, notes["records"]):
        s = row["samples"]
        source = row["source"]
        upstream = f"https://github.com/{source['repository']}/blob/{source['commit']}/{quote(source['path'], safe='/')}"
        grayscale_only = row["cube_vertices"]["all_vertices_achromatic_within_one_code"]
        gray_description = "所有 CUBE 顶点三通道差不超过 1 码值，属于数值上的近中性黑白。" if grayscale_only else "保留色彩或带有单色染色；灰阶样本中性不代表彩色色相不变。"
        monotonic = "4097 点采样的 Y′ 非递减。" if row["neutral_ramp"]["monotonic_y_with_tolerance_1e_7"] else "4097 点采样存在局部 Y′ 倒退，不是严格单调曲线。"
        parts.extend([
            f"<a id=\"preset-{row['id']}\"></a>\n\n### {row['number']:03} · {row['name']}\n",
            f"**稳定 ID**：`{row['id']}` · **类别**：`{row['category']}` · **网格**：{row['grid_size']}³ · **许可**：MIT。\n",
            f"**实际作用**：{note[1]}\n",
            f"**建议试用**：{note[2]}。**建议起始强度**：{note[4]}。**注意**：{note[3]}\n",
            f"**黑白与灰阶**：{gray_description} 纯黑 → `{s['gray_0']['hex']}`，纯白 → `{s['gray_100']['hex']}`；50% 中灰 → `{s['gray_50']['hex']}`。\n",
            "| 输入中性灰 | 0% | 10% | 25% | 50% | 75% | 90% | 100% |\n|---|---:|---:|---:|---:|---:|---:|---:|",
            "| 输出 Y′ 码值 | " + " | ".join(f"{s[key]['y_code']:.1f}" for key in gray_keys) + " |",
            "| 输出 RGB | " + " | ".join(f"`{s[key]['hex']}`" for key in gray_keys) + " |\n",
            f"中段跨度比 **{row['neutral_ramp']['midrange_chord_ratio_25_to_75']:.3f}×**；4097 点中性灰采样的最大通道差 **{row['neutral_ramp']['max_channel_spread_code']:.1f}** 码值。前者看明暗跨度，后者看灰阶染色，二者不能互相替代。{monotonic}\n",
            "| 固定测试色块 | 输入 RGB | 输出 RGB | Y′ 变化 | HSV 饱和度：输入 → 输出 |\n|---|---|---|---:|---|"
        ])
        for key, label in [("skin_light", "浅肤色测试块"), ("skin_medium", "中肤色测试块"), ("skin_dark", "深肤色测试块"),
                           ("red", "偏柔红色色块"), ("green", "偏柔绿色色块"), ("blue", "偏柔蓝色色块")]:
            before = analysis["method"]["inputs"][key]
            after = s[key]
            parts.append(f"| {label} | `{before['hex']}` | `{after['hex']}` | {after['y_code'] - before['y_code']:+.1f} | "
                         f"{before['hsv']['s'] * 100:.1f}% → {after['hsv']['s'] * 100:.1f}% |")
        preview = f"../assets/look-presets-20261024-r1/previews/{row['id']}.png"
        video = f"../assets/look-presets-20261024-r1/videos/{row['id']}.mp4"
        parts.append(f"\n[实际 FFmpeg PNG]({preview}) · [既有 1 秒成片]({video}) · [固定版本上游文件]({upstream})\n")
        if row["id"].startswith("t3-"):
            n = row["normalization"]
            parts.append(f"原生 {source['grid_size']}³ RGB8 Hald → 33³；8192 个既有抽样点的最大 RGB 误差 "
                         f"`{n['sampled_max_abs_rgb_error']:.6f}`，平均绝对误差 `{n['sampled_mean_abs_rgb_error']:.6f}`，单位 0–1；"
                         "这是转换误差抽样，不是全域上界或质量评分。\n")
        else:
            parts.append(f"保留上游 {source['grid_size']}³ CUBE 网格；未把它重采样成统一网格。\n")
    parts.extend([
        "## 来源与复现\n",
        "来源以目录固定提交为准：[Striped Purple 固定版本说明](../validation/evidence/lut-research-20261024-r1/stripedpurple--color-grading-luts/README.md) · "
        "[t3mujinpack 固定版本说明](../validation/evidence/lut-research-20261024-r1/t3mujinpack--t3mujinpack/README.md)。"
        "前者主要声明 Photoshop LUT 使用方式，没有提供这 49 项逐一的效果保证；后者说明是基于色彩曲线和通道混合的社区胶片模拟。本文逐项效果由实际安装版数据补足。\n",
        "```powershell\n$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'\n"
        "& $avk look inspect --id sp-lomochrome-purple-3\n"
        "& $avk look preview --id sp-lomochrome-purple-3 --input 'E:/media/frame-sdr.png' --output 'E:/work/lomo3.png' --strength 0.65\n```\n",
        "预览输入需要替换成实际存在的 SDR 图片，输出使用新路径。完整应用流程见 [alpha.2 使用手册](../releases/v0.1.0-alpha.2/USAGE.md)。\n",
        "复现本轮分析（需本机既有安装、NumPy、Pillow 和固定历史 PNG；Windows 原生，不下载、不调用 Docker/WSL）：\n",
        "```powershell\n& 'C:/Python313/python.exe' -E -B -X utf8 scripts/analyze_look_profiles.py\n"
        "& 'C:/Python313/python.exe' -E -B -X utf8 scripts/build_look_profile_docs.py\n"
        "& 'C:/Python313/python.exe' -E -B -X utf8 scripts/verify_look_profile_docs.py\n```\n",
        "本轮新增 100 项逐项数值解释、两张计算色块图和文档检查；新增 FFmpeg 成片 0、自然素材验收 0、产品回归测试 0。"
        "既有 100 成片和 83 项产品测试保留原日期与原核验范围。\n"
    ])
    simplified = "\n".join(parts).rstrip() + "\n"
    (LOCAL / "LOOK_PRESET_DETAILS.md").write_text(simplified, encoding="utf-8", newline="\n")
    tw = traditional(simplified)
    # Language-switch labels must remain distinct after automatic conversion.
    tw = tw.replace("[簡體中文](LOOK_PRESET_DETAILS.md)", "[简体中文](LOOK_PRESET_DETAILS.md)")
    (LOCAL / "LOOK_PRESET_DETAILS.zh-TW.md").write_text(tw, encoding="utf-8", newline="\n")
    print(json.dumps({"status": "written", "profiles_per_language": 100, "languages": ["zh-CN", "zh-TW"],
                      "analysis_sha256": digest(EVIDENCE / 'analysis.json'), "notes_sha256": digest(LOCAL / 'LOOK_PRESET_NOTES.json')}, ensure_ascii=False))


if __name__ == "__main__":
    main()
