# Show actual look choices to a human client

Use this workflow for requests to browse, compare, choose or present the 500 installed looks. This is a selection aid; apply edits with the pinned CLI only after the required ID, strength and target scope are clear.

## Available actual previews

- [Offline N002 comparison gallery](../../../docs/assets/looks-n002-20261024-r1/index.html): all 500 looks, number/name/ID search, category/license filters, original split, shortlist, three UI languages and JSON export. GitHub does not run the HTML; open the checked-out file locally. No server or network is needed.
- [Numbered sample guide](../../../docs/local/FILTER_GALLERY.md), [Traditional Chinese](../../../docs/local/FILTER_GALLERY.zh-TW.md), [English](../../../docs/local/FILTER_GALLERY.en.md).
- [Manifest](../../../docs/assets/looks-n002-20261024-r1/manifest.json) maps each number and stable ID to full/thumbnail images, actual RGB hashes, author/source/license, measured description and suggested trial strength. Original source SHA-256: `babaa64ce3434a23133c41a1d2b4fad384a5e6707546b527508d4731ba83ab4b`.
- Each sample is an actual installed-CLI execution on the same 1672×940 user-supplied still, tetrahedral interpolation, **strength 1.0**. Full WebPs are lossless and match native PNG pixels; thumbnails, boards and GIF are resized aids. The GIF cycles stills, not newly rendered video.
- The image has no embedded profile; these are encoded SDR RGB examples, not camera/HDR calibration, skin protection or acceptance of all natural footage. All 500 transforms include related upstream curve variants, not 500 unrelated families.
- Image rights and LUT rights are separate: the user supplied the source for this requested demonstration; the image is not MIT/CC0. Read [source and output credits](../../../docs/assets/looks-n002-20261024-r1/SOURCE_AND_LICENSES.md) and each LUT's obligations. Do not transfer its source-image permission to a client's unrelated commercial production.

## Build a client shortlist

Search by the brief using `look list`/`look inspect` or the helper below. Choose a small useful set, usually 3–6, based on requested color, contrast, genre, material and license. Display the **original plus actual candidate images**, with number, readable name, stable ID, preview strength, meaningful color changes and license. Mere ID lists do not satisfy a request for visual choice.

The helper reads existing verified previews and exports a labeled `board.jpg` plus `selection.json` in a **new absolute output directory**. It imports Pillow from the pinned local installation and never edits a timeline or fetches assets. It requires the checkout's `docs/assets/looks-n002-20261024-r1/`; the runtime ZIP alone does not include this gallery.

```powershell
$aekSkillRoot = Split-Path (Split-Path $avk -Parent) -Parent
$aekGallery = Join-Path $aekSkillRoot 'scripts/look_gallery.py'
& 'C:/Python313/python.exe' -I -S -B -X utf8 $aekGallery --query '黑白' --limit 6
& 'C:/Python313/python.exe' -I -S -B -X utf8 $aekGallery --ids t3-fuji-superia-800 nt-bw-agfa-apx-100 fl-0000634-darkblue --output 'E:/video-work/client-look-options'
```

Render a returned local board in chat with its **absolute file path**, for example `![滤镜候选](/absolute/path/to/board.jpg)`. Link full-size candidates when detail matters. If opening a browser for the user, close unused tabs after the requested comparison.

The gallery export uses `aek-look-shortlist-v1`; read its `source_sha256`, `preview_strength` and each `looks[].id`. It records **candidates**, not an applied edit or final approval. Numeric labels are browsing conveniences: resolve them through the manifest and use stable IDs in CLI calls.

## Turn a choice into an edit

Record the client's selected ID(s), desired strength and clip/global target. If the user already provided these, proceed within that scope; do not ask again. If they are still choosing, present the comparison and collect the missing choice rather than silently selecting a different look.

For the actual target material, generate new PNG previews with `look preview --input TARGET --strength VALUE`. A 100% N002 sample must never be labeled as 0.65 or as already applied to the client's own footage. The gallery's split slider changes only the original comparison area. Use the requested intensity, or compare a few actual strengths when the choice is still open.

Inspect the final `look inspect` metadata and license. Use `look apply --dry-run` for the explicit scope, then apply, preview/render and inspect the encoded result. Default replacement preserves manual effects; `--append` intentionally stacks looks. Retain project snapshots and the selection record. See [look application semantics](looks.md).
