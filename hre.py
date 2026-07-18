#!/usr/bin/env python
"""Single-file entry point — sandbox-safe.

Some agent sandboxes reject `python -m horse_edge.cli` or relative paths
("non-absolute file path"). Run THIS file by its absolute path instead; it adds
its own folder to sys.path, so it works from any working directory:

    python "C:\\Users\\you\\HorseEdgeEngine\\hre.py" score "C:\\Users\\you\\HorseEdgeEngine\\race.json"

Same subcommands as the module CLI: guide | ingest | template | score | demo.
Always pass absolute file paths to keep sandboxes happy.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from horse_edge.cli import main

if __name__ == "__main__":
    main()
