"""Compatibility entry point; implementation lives in the installable package."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

if __name__ == "__main__":
    import runpy
    runpy.run_module("colosseum_randomizer.engine.randomize_accessible", run_name="__main__")
else:
    from colosseum_randomizer.engine.randomize_accessible import *  # noqa: F401,F403
