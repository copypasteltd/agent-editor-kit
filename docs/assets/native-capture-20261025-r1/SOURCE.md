# Native capture demonstration

Input: FFmpeg `testsrc2=size=480x270:rate=15`, displayed in the test script’s own ffplay window. No third-party footage, other application window, camera or microphone was captured. The product captures media through a CLI; the player is a test fixture, not a product GUI.

Reproduction: `scripts/smoke_native_capture_20261025.py`, then `scripts/publish_capture_demo_20261025.py`. Both CPU/libx264 and GPU/NVENC outputs are two seconds, 30 frames; the GIF is a derived preview. Decode and changing-pixel checks passed. Continuous human viewing and audiovisual sync were not accepted.

The project generated these demonstration files for redistribution. FFmpeg and its optional codecs retain their own licenses; the executable is not redistributed in this media directory.
