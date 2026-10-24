# Preserved first public-demo attempt

The installed CLI completed rendering and full decoding, but visual inspection
found cropped oversized captions. The example authored 1080-pixel canvas styles
and then overrode the render raster to 360 pixels. A render width/height override
changes composition dimensions; it is not a final resize of those text styles.

This attempt remains as evidence of the failed presentation. The corrected public
example is [r2](../community-materials-20261025-r2/verification.json), which authors
the sequence at its intended 360 × 640 raster with matching pixel-based styles.
No product-runtime change or new model inference is represented by this correction.
