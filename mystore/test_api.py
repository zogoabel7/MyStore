import gi
import sys

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("AppStream", "1.0")

from mystore.lib.plugin_loader import PluginLoader
from mystore.lib.jobs import PluginJob, PluginJobAction
from mystore.lib.app import AppState
import logging

logging.basicConfig(level=logging.DEBUG)

def _on_test_done(job):
    print(f"Job {job.action} done. Results:", len(job.results) if isinstance(job.results, list) else "not a list")
    if job.results:
        for r in job.results[:3]:
            print(f" - {r.id} ({r.name}): URL={r.url}, Screens={len(r.screenshots)}")
    else:
        print("Empty results")

def run_tests():
    loader = PluginLoader()
    loader.setup()

    # Test SEARCH
    print("Testing SEARCH 'vlc'...")
    search_job = PluginJob(PluginJobAction.SEARCH, query="vlc")
    search_job.run(loader)
    _on_test_done(search_job)

    # Test GET_INSTALLED
    print("Testing GET_INSTALLED...")
    installed_job = PluginJob(PluginJobAction.GET_INSTALLED)
    installed_job.run(loader)
    _on_test_done(installed_job)
    
    # Test REFINE specifically
    if installed_job.results:
        print("Testing REFINE on first installed app...")
        refine_job = PluginJob(PluginJobAction.REFINE, app=installed_job.results[0])
        refine_job.run(loader)
        _on_test_done(refine_job)

if __name__ == "__main__":
    run_tests()
