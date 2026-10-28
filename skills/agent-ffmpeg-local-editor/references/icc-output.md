# RGB ICC output and native soft proof / CLI0.1.48

Use the pinned unified launcher. Inspect `native_icc_output_profiles` and read
`docs/product/ICC_OUTPUT.md` in the small kit for the complete contract.

1. Ingest authorized media, compose the editable timeline, declare actual
   source signals and linear working RGB with `float32-native-v1`.
2. Obtain the client's authorized RGB ICC v2/v4 output file. Keep it inside the
   project without junctions; record its actual SHA256 and an explicit intent
   in local JSON (`icc_profile`, `sha256`, `intent`, optional boolean BPC).
   Never substitute a vendor-name look or infer physical monitor calibration.
3. Validate, then run `surface render --project PROJECT --sequence-id SEQUENCE
   --output renders/icc --output-profile-json target.json --dry-run` on ONE line.
   Remove `--dry-run` to deliver actual RGBA16 PNG frames, each with the exact
   embedded ICC, plus `output.icc`, stereo 48000Hz `audio.f32le`, `sequence.json`.
   Default range policy rejects CMM output outside0..1. Explicit `--range-policy
   clip` counts application clipping across all frames. The native profile may
   itself compress/map values; that is not counted as application clipping.
4. Use `--start-frame` / `--stop-frame` for half-open timeline CFR intervals.
   Audio uses exact ceil-aligned sample boundaries clamped to authored duration.
   `--max-output-mib` is an output-file budget up to8192MiB, not a peak RSS bound.
   For nits-based working RGB, also declare target `reference_white_nits`.
   Linear values scale by working/output nits before ICC encoding.
5. `surface inspect-output --project PROJECT --input renders/icc` verifies ALL
   hashes, PNG CRCs/decompressed pixels/exact embedded profiles and finite PCM
   with sample counts. It is read-only. This is our filter-0 RGBA16 transport
   verifier, not a general external-PNG validator or proof of media rights.
6. For a client review simulation, author `pixel_pipeline.proofing` containing
   `profile` (same complete relative RGB descriptor, NO nits) and explicit
   `simulation_intent`. Standard `render` / `preview frame` / `preview range`
   use native SOFTPROOFING after an optional declared display mapping and before
   standard output encoding. No alarm colors or physical paper brightness are
   inferred. A matrix-only profile may produce nearly identical proof output.
7. Final `surface render` does NOT apply view simulation a second time. Review
   device PNGs with an ICC-aware viewer. Standard movie previews keep their true
   VUI; never merely label arbitrary ICC device RGB as BT709/BT2020 YUV.
8. Export/import editable packages and replay. Proof profiles are snapshotted
   into portable dependencies and included in actual-byte cache fingerprints.
   A target supplied only as a command argument is not an authored project
   dependency: preserve/distribute it separately unless also used by the proof
   declaration. Packaging bytes does not grant redistribution rights.
9. Show C58 actual MP4/GIF/frame and diagnostic profile provenance before client
   selection. Distinguish a synthetic diagnostic profile from a commercial
   printer/monitor profile. CMM conversion uses CPU; supported authored GPU
   operators remain native OpenCL. No CMYK/ICC5/full ACES/dynamic HDR or measured
   display/printer/artistic acceptance is claimed.
