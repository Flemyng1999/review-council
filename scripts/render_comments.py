#!/usr/bin/env python
"""Thin wrapper for rendering author-facing comments."""

import sys

from review_council.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["render-comments", *sys.argv[1:]]))
