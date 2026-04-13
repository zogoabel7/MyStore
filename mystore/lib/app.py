import gi
gi.require_version('GObject', '2.0')
from gi.repository import GObject
from enum import Enum

class AppState(Enum):
    UNKNOWN = 0
    INSTALLED = 1
    AVAILABLE = 2
    INSTALLING = 3
    REMOVING = 4
    UPDATABLE = 5
    DOWNLOADING = 6

class StoreApp(GObject.Object):
    """
    Python clone of GsApp (gs-app.c) from GNOME Software.
    Holds state, metadata and origin for a single app entity.
    """

    __gsignals__ = {
        'state-changed': (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self, app_id, **kwargs):
        super().__init__(**kwargs)
        self._app_id = app_id
        self._name = ""
        self._summary = ""
        self._description = ""
        self._icon_name = "application-x-executable"
        self._icon_path = ""
        self._version = ""
        self._state = AppState.UNKNOWN
        self._sources = []       # like origins in GsApp
        self._categories = []
        self._screenshots = []
        self._url = ""
        self._metadata = {}      # internal store for quirks

    @property
    def id(self): return self._app_id
    
    @property
    def name(self): return self._name or self._app_id

    @property
    def has_name(self): return bool(self._name)
    
    @name.setter
    def name(self, val): self._name = val

    @property
    def summary(self): return self._summary

    @summary.setter
    def summary(self, val): self._summary = val

    @property
    def description(self): return self._description

    @description.setter
    def description(self, val): self._description = val

    @property
    def icon_name(self): return self._icon_name

    @icon_name.setter
    def icon_name(self, val): self._icon_name = val

    @property
    def icon_path(self): return self._icon_path

    @icon_path.setter
    def icon_path(self, val): self._icon_path = val or ""

    @property
    def state(self): return self._state

    @state.setter
    def state(self, val):
        if self._state != val:
            self._state = val
            self.emit('state-changed')

    @property
    def is_installed(self):
        return self._state in [AppState.INSTALLED, AppState.UPDATABLE]

    @property
    def sources(self): return self._sources

    def add_source(self, source):
        if source not in self._sources:
            self._sources.append(source)

    @property
    def categories(self): return self._categories

    @categories.setter
    def categories(self, val): self._categories = val

    @property
    def screenshots(self): return self._screenshots

    @screenshots.setter
    def screenshots(self, val): self._screenshots = val

    @property
    def url(self): return self._url

    @url.setter
    def url(self, val): self._url = val

    def set_metadata(self, key, value):
        self._metadata[key] = value

    def get_metadata(self, key):
        return self._metadata.get(key)
