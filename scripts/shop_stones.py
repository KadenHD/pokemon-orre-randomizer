"""Compatibility entry point; implementation lives in the installable package."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    import runpy
    runpy.run_module("orre_randomizer.engine.shop_stones", run_name="__main__")
else:
    from orre_randomizer.engine.shop_stones import *  # noqa: F401,F403
