#!/usr/bin/env python3
"""Executable script to launch HPoker CLI."""

import sys
import os

# Ensure project root is in sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from cli.main import main

if __name__ == "__main__":
    main()
