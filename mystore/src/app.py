"""Entrypoint wrapper in `mystore/src` delegating to `mystore.app`.

This mirrors the gnome-software `src/` entrypoint surface while reusing the
existing Python application implementation.
"""

import sys

from ..app import MyStoreApp


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    app = MyStoreApp()
    return app.run(argv)


if __name__ == "__main__":
    main()
