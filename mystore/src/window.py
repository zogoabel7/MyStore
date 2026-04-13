"""`src.window` wrapper exposing the GTK window implementation.

This mirrors the gnome-software `src/` layout but delegates to the
existing `mystore.window.MyStoreWindow` implementation to keep behaviour
unchanged while the repository is migrated incrementally.
"""

from mystore.window import MyStoreWindow

__all__ = ["MyStoreWindow"]
