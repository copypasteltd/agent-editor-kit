# Fresh LUTs ingestion audit

This records LUTr — LUTrepository's deterministic ingestion of the local
FreshLUTs capture. The source site's terms declare uploaded LUTs to be
[CC0-1.0](https://freshluts.com/termsandconditions), including commercial use.
Per-file notices still take precedence as a reason to withhold an ambiguous
asset.

## Result

| Check | Count |
|---|---:|
| Index records | 727 |
| Captured `.cube` files | 720 |
| Published canonical transforms | 679 |
| Duplicate files collapsed | 31 |
| Duplicate groups | 27 |
| Conflicting rights notices quarantined | 8 |
| Missing captures | 7 |
| Invalid CUBE files | 2 |
| Overlaps with the pre-existing LUTr catalog | 0 |
| Camera-label profiles resolved | 337 |
| Camera-label profiles still partial | 5 |

The 337 resolved profiles retain `Color-Space-Confidence:
inferred-from-source-label`; the upstream gamma selector is evidence, not a
manufacturer-verified declaration embedded in the file. Legacy Blackmagic
Film, DJI D-Log, CineStyle, Cinelike-D, and GoPro profiles are explicitly
labelled as approximations in the browser. Five `RED Color` records identify a
gamut but no transfer curve, so their `Input-Color-Space` remains empty.

The importer compares the declared grid, domain, and normalized floating-point
sample sequence. It ignores filenames, titles, comments, whitespace, and number
formatting. Within a duplicate group the lowest stable FreshLUTs numeric ID is
canonical; every collapsed asset is retained in its v2 `Duplicate-Assets`
header field and in the local JSON import report.

## Duplicate groups

Canonical IDs followed by collapsed upstream IDs:

`12 ← 47`; `17 ← 70`; `26 ← 63`; `34 ← 69`; `38 ← 43`;
`126 ← 200, 815, 2044, 2234`; `149 ← 164`; `175 ← 176`;
`211 ← 214`; `212 ← 2704`; `285 ← 502`; `406 ← 407`;
`454 ← 2728`; `591 ← 992`; `597 ← 599`; `936 ← 937`;
`1237 ← 1837`; `1246 ← 1247`; `1248 ← 1249`; `1250 ← 1251`;
`1263 ← 1264`; `1336 ← 1337, 1342`; `1533 ← 1534`;
`1568 ← 1569`; `2072 ← 2729`; `2458 ← 2459`; `2712 ← 2713`.

## Withheld assets

The following files contain a copyright assertion that conflicts with the
site-wide CC0 declaration, so they remain under the ignored
`submissions-quarantine/` tree and are never copied to the hosted catalog:

- 185 — CELLULOÏD
- 274 — Relatives
- 275 — Drone Real Estate Punch
- 295 — Cinematic Clean
- 501 — 4K-ALEXA-LOG
- 1002 — Juan LUT
- 1004 — DUNE Inspired LUT - Merga
- 1605 — Forest

FreshLUTs IDs 401 and 503 have no valid `LUT_3D_SIZE`. IDs 932, 1270, 1465,
1615, 1997, 2093, and 2418 have no captured CUBE payload. All nine are skipped
with a reason in `submissions-raw/freshluts-import-report.json`.

## Reproduce locally

```powershell
node scripts\import-freshluts.mjs
node scripts\convert-all-to-cube.mjs
node scripts\validate-cubes.mjs
node scripts\build-prototype.mjs
```

Raw captures, generated submissions, quarantine contents, and the detailed JSON
report are intentionally excluded from Git. Only canonical metadata-rich CUBE
files are hosted.
