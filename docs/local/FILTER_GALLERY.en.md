# N002 supplied still × 500 looks: actual samples and client selection

[简体中文](FILTER_GALLERY.md) · [繁體中文](FILTER_GALLERY.zh-TW.md) · [English](FILTER_GALLERY.en.md)

[Interactive gallery](../assets/looks-n002-20261024-r1/index.html) · [Filter workflow](FILTERS.en.md) · [Measured profiles](LOOK_PRESETS.en.md) · [Actual executions](../validation/evidence/looks-n002-20261024-r1/render-verification.json)

Every look was actually executed in the installed CLI on the supplied 1672×940 still, using strength 1.0 and tetrahedral interpolation. Full-size lossless WebP RGB exactly equals CLI PNG RGB; thumbnails are browsing aids. With no embedded source profile this is an encoded-SDR-RGB trial.

![Original and eleven actual looks](../assets/looks-n002-20261024-r1/selection-board.jpg)

## Every actual look sample

| # | Individual samples, full-size images and IDs |
|---|---|
| 001–100 | [100 actual previews](filter-gallery/001-100.en.md) |
| 101–200 | [100 actual previews](filter-gallery/101-200.en.md) |
| 201–300 | [100 actual previews](filter-gallery/201-300.en.md) |
| 301–400 | [100 actual previews](filter-gallery/301-400.en.md) |
| 401–500 | [100 actual previews](filter-gallery/401-500.en.md) |

## Contact sheets: 50 looks each

- [001–050](../assets/looks-n002-20261024-r1/sheets/001-050.jpg)
- [051–100](../assets/looks-n002-20261024-r1/sheets/051-100.jpg)
- [101–150](../assets/looks-n002-20261024-r1/sheets/101-150.jpg)
- [151–200](../assets/looks-n002-20261024-r1/sheets/151-200.jpg)
- [201–250](../assets/looks-n002-20261024-r1/sheets/201-250.jpg)
- [251–300](../assets/looks-n002-20261024-r1/sheets/251-300.jpg)
- [301–350](../assets/looks-n002-20261024-r1/sheets/301-350.jpg)
- [351–400](../assets/looks-n002-20261024-r1/sheets/351-400.jpg)
- [401–450](../assets/looks-n002-20261024-r1/sheets/401-450.jpg)
- [451–500](../assets/looks-n002-20261024-r1/sheets/451-500.jpg)

## Presenting and recording client choices

1. Select 3–6 looks for the brief and show the original with actual samples, numbers, names, stable IDs, strength and license.
2. Clients can give a number/ID or open the offline gallery to filter, shortlist and export JSON. GitHub does not execute repository HTML; open a downloaded copy locally.
3. Export a client-specific board with the Skill helper. A 100% sample must not be presented as strength 0.65.
4. Run look preview on the actual target frame with the chosen ID/strength. Record final ID, strength and clip/global scope before application and retain snapshots.
5. Inspect encoded output/warnings. This image does not establish all skin, scene, HDR or video-temporal quality.

```powershell
$aekGallery = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/look_gallery.py'
& 'C:/Python313/python.exe' -I -S -B -X utf8 $aekGallery --query '黑白' --limit 6
& 'C:/Python313/python.exe' -I -S -B -X utf8 $aekGallery --ids t3-fuji-superia-800 nt-bw-agfa-apx-100 fl-0000634-darkblue --output 'E:/video-work/client-look-options'
```

[Example board](../assets/looks-n002-20261024-r1/client-shortlist-example/board.jpg) · [Returned selection](../assets/looks-n002-20261024-r1/client-shortlist-example/selection.json) · [Skill procedure](../../skills/agent-ffmpeg-local-editor/references/client-look-selection.md)

## Source, strength and display limits

The user supplied the source and explicitly requested these demonstrations; the image is not labeled MIT/CC0. Every LUT retains its MIT/CC0/CC BY-SA license, creator and change/source record. Image and LUT rights are separate; see [complete notices and per-item credits](../assets/looks-n002-20261024-r1/SOURCE_AND_LICENSES.md). The 500 distinct transforms include related curves rather than 500 unrelated families.

[Desktop screenshot](../assets/looks-n002-20261024-r1/gallery-desktop.png) · [Mobile screenshot](../assets/looks-n002-20261024-r1/gallery-mobile.png) · [Actual UI recording](../assets/looks-n002-20261024-r1/gallery-walkthrough.webm)
