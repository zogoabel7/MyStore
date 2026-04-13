class StorePlugin:
    """
    Python clone of GsPlugin.
    Plugins execute tasks like setup, refine, search inside jobs.
    """
    def __init__(self, loader, name):
        self.loader = loader
        self.name = name

    def setup(self):
        """Called once when plugin is loaded."""
        pass

    def search(self, query, apps):
        """
        Add StoreApp objects matching `query` to the `apps` list or
        update existing ones.
        """
        pass

    def refine(self, app):
        """
        Called to refine a single app with more details 
        (e.g., adding AppStream descriptions or icons).
        """
        pass

    def get_installed(self, apps):
        """Add installed apps to the list."""
        pass

    def list_category(self, category_id, apps, limit=None):
        """Add apps belonging to the requested overview category."""
        pass

    def list_overview(self, apps, limit=None):
        """Add a small curated list for the overview page."""
        pass

    def install(self, app):
        """Install the app."""
        return False

    def uninstall(self, app):
        """Uninstall the app."""
        return False
