#!/usr/bin/env python
"""Thin wrapper for creating a review case."""

import sys

from review_council.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["init-case", *sys.argv[1:]]))
