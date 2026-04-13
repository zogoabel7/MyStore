import threading
import logging
from gi.repository import GLib

from .app import AppState

log = logging.getLogger("mystore.lib.jobs")

class PluginJobAction:
    SEARCH = 1
    REFINE = 2
    INSTALL = 3
    UNINSTALL = 4
    GET_INSTALLED = 5
    LIST_CATEGORY = 6
    GET_OVERVIEW = 7

class PluginJob:
    """
    Python clone of GsPluginJob.
    It encapsulates the logic of running an action sequentially across all plugins
    in a background thread, and then returning the result to the main thread.
    """
    def __init__(self, action, query=None, app=None, callback=None, category=None, limit=None):
        self.action = action
        self.query = query
        self.app = app
        self.callback = callback
        self.category = category
        self.limit = limit
        self.results = []
        self.success = False

    def run(self, loader):
        """Execute this job in the current background thread against the loader's plugins."""
        try:
            if self.action == PluginJobAction.SEARCH:
                self._run_search(loader)
            elif self.action == PluginJobAction.REFINE:
                self._run_refine(loader)
            elif self.action == PluginJobAction.INSTALL:
                self._run_install(loader)
            elif self.action == PluginJobAction.UNINSTALL:
                self._run_uninstall(loader)
            elif self.action == PluginJobAction.GET_INSTALLED:
                self._run_get_installed(loader)
            elif self.action == PluginJobAction.LIST_CATEGORY:
                self._run_list_category(loader)
            elif self.action == PluginJobAction.GET_OVERVIEW:
                self._run_get_overview(loader)
        except Exception as e:
            log.error(f"Job failed: {e}")
        
        if self.callback:
            GLib.idle_add(self.callback, self)

    def _merge_app_results(self, apps_list):
        apps_dict = {}

        for app in apps_list:
            if app.id not in apps_dict:
                apps_dict[app.id] = app
                continue

            existing = apps_dict[app.id]
            existing.sources.extend(source for source in app.sources if source not in existing.sources)

        return list(apps_dict.values())

    def _refine_results(self, loader, apps):
        for app in apps:
            for plugin in loader.plugins:
                plugin.refine(app)

    def _set_app_state(self, app, state):
        app.state = state
        return False

    def _run_search(self, loader):
        apps_list = []

        preferred = [p for p in loader.plugins if getattr(p, "name", "") == "aptcache"]
        fallback = [p for p in loader.plugins if getattr(p, "name", "") not in {"aptcache", "packagekit"}]

        for plugin in preferred:
            plugin.search(self.query, apps_list)

        if not apps_list:
            for plugin in fallback:
                plugin.search(self.query, apps_list)

        # 2. Merge by app_id
        self.results = self._merge_app_results(apps_list)
        if self.limit is not None:
            self.results = self.results[:self.limit]

    def _run_refine(self, loader):
        if self.app:
            for p in loader.plugins:
                p.refine(self.app)
        self.success = True

    def _run_install(self, loader):
        if not self.app: return
        GLib.idle_add(self._set_app_state, self.app, AppState.INSTALLING)
        for p in loader.plugins:
            if p.install(self.app):
                self.success = True
                GLib.idle_add(self._set_app_state, self.app, AppState.INSTALLED)
                return
        GLib.idle_add(self._set_app_state, self.app, AppState.AVAILABLE)

    def _run_uninstall(self, loader):
        if not self.app: return
        GLib.idle_add(self._set_app_state, self.app, AppState.REMOVING)
        for p in loader.plugins:
            if p.uninstall(self.app):
                self.success = True
                GLib.idle_add(self._set_app_state, self.app, AppState.AVAILABLE)
                return
        GLib.idle_add(self._set_app_state, self.app, AppState.INSTALLED)

    def _run_get_installed(self, loader):
        apps_list = []
        for p in loader.plugins:
            if getattr(p, "name", "") == "packagekit":
                continue
            p.get_installed(apps_list)

        # Filter: keep only GUI apps (matching GNOME Software's default view)
        deduped = self._merge_app_results(apps_list)
        self.results = [app for app in deduped if app.categories or app.icon_path or app.icon_name != "application-x-executable"]
        self.results.sort(key=lambda app: app.name.lower())

    def _run_list_category(self, loader):
        apps_list = []

        preferred = [p for p in loader.plugins if getattr(p, "name", "") == "aptcache"]
        fallback = [p for p in loader.plugins if getattr(p, "name", "") not in {"aptcache", "packagekit"}]

        for plugin in preferred:
            plugin.list_category(self.category, apps_list, limit=self.limit)

        if not apps_list:
            for plugin in fallback:
                plugin.list_category(self.category, apps_list, limit=self.limit)

        self.results = self._merge_app_results(apps_list)
        if self.limit is not None:
            self.results = self.results[:self.limit]

    def _run_get_overview(self, loader):
        apps_list = []

        preferred = [p for p in loader.plugins if getattr(p, "name", "") == "aptcache"]
        fallback = [p for p in loader.plugins if getattr(p, "name", "") not in {"aptcache", "packagekit"}]

        for plugin in preferred:
            plugin.list_overview(apps_list, limit=self.limit)

        if not apps_list:
            for plugin in fallback:
                plugin.list_overview(apps_list, limit=self.limit)

        self.results = self._merge_app_results(apps_list)
        if self.limit is not None:
            self.results = self.results[:self.limit]
