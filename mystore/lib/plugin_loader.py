import threading
import logging
from .jobs import PluginJob, PluginJobAction

log = logging.getLogger("mystore.lib.plugin_loader")

class PluginLoader:
    """
    Python clone of GsPluginLoader.
    Manages loading plugins and queuing background jobs.
    """
    def __init__(self):
        self.plugins = []

    def setup(self):
        """Load and initialize all plugins. Mimics gs_plugin_loader_setup."""
        from mystore.plugins.aptcache import AptCachePlugin
        from mystore.plugins.appstream import AsPlugin
        from mystore.plugins.packagekit import PkPlugin

        # Order matters! AppStream fetches rich desktop apps, PackageKit resolves their state.
        self.plugins.append(AptCachePlugin(self))
        self.plugins.append(AsPlugin(self))
        self.plugins.append(PkPlugin(self))

        for p in self.plugins:
            log.info(f"Setting up plugin: {p.name}")
            p.setup()

    def process_async(self, job):
        """
        Mimics gs_plugin_loader_job_process_async.
        Spawns a thread to process the given job across all plugins.
        """
        def _worker():
            job.run(self)
        
        t = threading.Thread(target=_worker, daemon=True)
        t.start()
        return t
