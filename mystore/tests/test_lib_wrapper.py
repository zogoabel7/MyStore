"""Basic smoke tests for the new `lib` wrappers."""

import sys
from pathlib import Path

# Ensure workspace root is on sys.path so `lib` package is importable when
# running this script from the tests/ directory.
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mystore.lib.app import App
from mystore.lib.app_list import AppList
from mystore.lib.catalog import Catalog


def run():
    a = App.from_dict({"name": "test-app", "app_id": "test-app"})
    assert a.get("name") == "test-app"
    assert a.get("app_id") == "test-app"

    al = AppList([a])
    assert isinstance(al, list) and len(al) == 1
    assert hasattr(al[0], "to_dict")

    c = Catalog()
    # ensure wrapper exposes expected methods without calling heavy backends
    assert hasattr(c, "build")
    assert hasattr(c, "get_app_details")

    print("SMOKE_OK")


if __name__ == "__main__":
    run()
