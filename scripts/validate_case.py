#!/usr/bin/env python
"""Thin wrapper around the package CLI."""

import sys

from review_council.cli import main


if __name__ == "__main__":
    raise SystemExit(main(["validate-case", *sys.argv[1:]]))
