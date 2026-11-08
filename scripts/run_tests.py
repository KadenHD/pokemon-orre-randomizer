"""Run the test suite in the current checkout with a hang traceback."""
import faulthandler
from pathlib import Path
import sys
import unittest


if __name__ == "__main__":
    sys.path.insert(0, str(Path.cwd()))
    faulthandler.dump_traceback_later(8 * 60, exit=True)
    unittest.main(module=None, argv=[sys.argv[0], "discover", "-s", "tests", "-v"])
