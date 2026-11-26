#!/usr/bin/env python3
"""Single entry point:  python main.py [song] [options]   (see --help)."""
import sys

from lyricviz.cli import main

if __name__ == "__main__":
    sys.exit(main())
