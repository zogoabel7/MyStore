import sys
import logging
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from .window import MyStoreWindow

log = logging.getLogger("mystore")

class MyStoreApp(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id="com.mystore.app",
            flags=Gio.ApplicationFlags.FLAGS_NONE,
        )
        self._window = None

    def do_activate(self):
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.PREFER_DARK)

        if self._window is None:
            self._window = MyStoreWindow(application=self)
        self._window.present()

def setup_logging():
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        datefmt="%H:%M:%S",
    )

def main():
    setup_logging()
    log.info("Starting MyStore (Libadwaita)")
    app = MyStoreApp()
    return app.run(sys.argv)

if __name__ == "__main__":
    main()
