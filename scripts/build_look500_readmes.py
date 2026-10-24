"""Compatibility entry point: maintain complete product manuals and the 500-look gallery.

The former condensed README builder is retained in Git history. This entry point
now delegates to the full manuals so a later filter update cannot shrink them.
"""
from build_product_readmes import main as build_product_manuals
from build_n002_gallery_docs import main as build_gallery_manuals


if __name__ == '__main__':
    build_product_manuals()
    build_gallery_manuals()
