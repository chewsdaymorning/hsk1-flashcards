#!/usr/bin/env python3
"""Entry point: ``python run.py run --mock``.

Exists so the tool can be started without remembering ``-m``; imports are plain
absolute package imports, no sys.path juggling.
"""

from wohnungssuche.main import main

if __name__ == "__main__":
    raise SystemExit(main())
