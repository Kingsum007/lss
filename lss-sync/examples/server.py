#!/usr/bin/env python3
"""Run the packaged loopback server with this checkout's browser assets."""
from pathlib import Path
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "python" / "src"))
from lss_sync.examples.server import main
if __name__ == "__main__":
    main(browser_root=ROOT)
