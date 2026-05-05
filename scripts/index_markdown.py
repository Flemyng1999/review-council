#!/usr/bin/env python
"""Thin wrapper for Markdown provenance indexing."""

import sys

from review_council.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["index-markdown", *sys.argv[1:]]))
