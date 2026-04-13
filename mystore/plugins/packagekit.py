import logging
import subprocess
import gi
gi.require_version("PackageKitGlib", "1.0")
from gi.repository import PackageKitGlib as Pk

from mystore.lib.plugin import StorePlugin
from mystore.lib.app import StoreApp, AppState

log = logging.getLogger("mystore.plugins.packagekit")


def _strip_desktop_suffix(value):
    value = value or ""
    if value.lower().endswith(".desktop"):
        return value[:-8]
    return value


def _component_basename(value):
    value = _strip_desktop_suffix(value)
    return value.rsplit(".", 1)[-1]


class PkPlugin(StorePlugin):
    def __init__(self, loader):
        super().__init__(loader, "packagekit")
        self.client = None
        self._disabled = False

    def setup(self):
        self.client = Pk.Client()
        log.info("PackageKit DBus Client initialized")

    def _disable(self, context, error):
        message = str(error)
        if not self._disabled:
            log.warning(f"{context}: PackageKit indisponible, plugin désactivé: {message}")
        self._disabled = True
        self.client = None

    def _handle_error(self, context, error):
        message = str(error)
        if "Could not connect" in message or "Operation not permitted" in message:
            self._disable(context, error)
        else:
            log.error(f"{context}: {message}")

    def _package_candidates(self, app):
        candidates = []
        raw_values = []
        raw_values.extend(app.get_metadata("pkg_names") or [])
        raw_values.extend([
            app.id,
            app.get_metadata("appstream_id"),
            app.name,
        ])

        for value in raw_values:
            if not value:
                continue
            stripped = _strip_desktop_suffix(value)
            slug = stripped.replace(" ", "-")
            basename = _component_basename(stripped)
            for candidate in (
                value,
                stripped,
                slug,
                slug.lower(),
                basename,
                basename.lower(),
            ):
                if candidate and candidate not in candidates:
                    candidates.append(candidate)

        return candidates

    def _resolve_first(self, filter_enum, app):
        if not self.client:
            return None

        for candidate in self._package_candidates(app):
            try:
                resolved = self.client.resolve(filter_enum, [candidate], None, lambda p,t,d: None, None)
                packages = resolved.get_package_array()
                if packages:
                    return packages[0]
            except Exception as error:
                self._handle_error("PK resolve", error)
                return None

        return None

    def _resolve_dpkg_package(self, app):
        if app.get_metadata("package_name"):
            return app.get_metadata("package_name")

        desktop_file = app.get_metadata("desktop_file")
        if desktop_file:
            try:
                result = subprocess.run(
                    ["dpkg-query", "-S", desktop_file],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                package_name = result.stdout.split(":", 1)[0].split(",")[0].strip()
                if package_name:
                    app.set_metadata("package_name", package_name)
                    return package_name
            except Exception:
                pass

        for candidate in self._package_candidates(app):
            try:
                result = subprocess.run(
                    ["apt-cache", "show", candidate],
                    capture_output=True,
                    text=True,
                    check=True,
                )
            except Exception:
                continue

            if f"Package: {candidate}" in result.stdout:
                app.set_metadata("package_name", candidate)
                return candidate

        return None

    def _is_package_installed(self, package_name):
        try:
            result = subprocess.run(
                ["dpkg-query", "-W", "-f=${Status}", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
        except Exception:
            return False

        return "install ok installed" in result.stdout

    def _apply_apt_details(self, app, package_name):
        try:
            result = subprocess.run(
                ["apt-cache", "show", package_name],
                capture_output=True,
                text=True,
                check=True,
            )
        except Exception:
            return

        current_key = None
        fields = {}
        for raw_line in result.stdout.splitlines():
            if not raw_line.strip():
                if fields:
                    break
                continue

            if raw_line.startswith(" ") and current_key:
                fields[current_key] += "\n" + raw_line.strip()
                continue

            if ":" not in raw_line:
                continue

            key, value = raw_line.split(":", 1)
            current_key = key
            fields[key] = value.strip()

        if not app.description:
            app.description = fields.get("Description", "")
        if not app.url:
            app.url = fields.get("Homepage", "")

    def _apt_fallback_install(self, app, install=True):
        package_name = self._resolve_dpkg_package(app)
        if not package_name:
            return False

        app.add_source("apt")
        app.set_metadata("package_name", package_name)
        command = ["pkexec", "apt", "install" if install else "remove", "-y", package_name]
        try:
            subprocess.run(command, check=True)
            return True
        except Exception as error:
            log.error(f"APT fallback {'install' if install else 'remove'}: {error}")
            return False

    def search(self, query, apps):
        """Fetch package lists matching the query exactly like gs-plugin-process-pkgname"""
        if not self.client: return
        try:
            results = self.client.search_names(Pk.FilterEnum.NONE, [query], None, lambda p,t,d: None, None)
            for pkg in results.get_package_array():
                app = StoreApp(pkg.get_name())
                app.name = pkg.get_name()
                app.summary = pkg.get_summary() or ""
                app.add_source("apt")
                app.state = AppState.INSTALLED if pkg.get_info() == Pk.InfoEnum.INSTALLED else AppState.AVAILABLE
                app.set_metadata("pkg_id", pkg.get_id())
                apps.append(app)
        except Exception as e:
            self._handle_error("PK search", e)

    def get_installed(self, apps):
        if not self.client: return
        try:
            results = self.client.get_packages(Pk.FilterEnum.INSTALLED, None, lambda p,t,d: None, None)
            for pkg in results.get_package_array():
                app = StoreApp(pkg.get_name())
                app.name = pkg.get_name()
                app.summary = pkg.get_summary() or ""
                app.add_source("apt")
                app.state = AppState.INSTALLED
                app.set_metadata("pkg_id", pkg.get_id())
                apps.append(app)
        except Exception as e:
            self._handle_error("PK get_installed", e)

    def refine(self, app):
        """Add precise package details and resolve installed state."""
        if not self.client:
            package_name = self._resolve_dpkg_package(app)
            if package_name:
                app.add_source("apt")
                app.state = AppState.INSTALLED if self._is_package_installed(package_name) else AppState.AVAILABLE
                self._apply_apt_details(app, package_name)
            return
        
        # Resolve package state if unknown (typically when coming from AppStream)
        if app.state == AppState.UNKNOWN:
            pkg = self._resolve_first(Pk.FilterEnum.NONE, app)
            if pkg:
                app.state = AppState.INSTALLED if pkg.get_info() == Pk.InfoEnum.INSTALLED else AppState.AVAILABLE
                app.set_metadata("pkg_id", pkg.get_id())
                app.add_source("apt")
            else:
                package_name = self._resolve_dpkg_package(app)
                if package_name:
                    app.add_source("apt")
                    app.state = AppState.INSTALLED if self._is_package_installed(package_name) else AppState.AVAILABLE
                    self._apply_apt_details(app, package_name)

        # Fetch detailed description and URLs if missing
        pkg_id = app.get_metadata("pkg_id")
        if not pkg_id:
            package_name = self._resolve_dpkg_package(app)
            if package_name:
                self._apply_apt_details(app, package_name)
            return
        try:
            results = self.client.get_details([pkg_id], None, lambda p,t,d: None, None)
            details = results.get_details_array()
            if details:
                d = details[0]
                if not app.description:
                     app.description = d.get_description() or ""
                if not app.url:
                     app.url = d.get_url() or ""
        except Exception as e:
            self._handle_error("PK get_details", e)

    def install(self, app):
        if "apt" not in app.sources:
            package_name = self._resolve_dpkg_package(app)
            if package_name:
                app.add_source("apt")
        if "apt" not in app.sources:
            return False
        try:
            pkg_id = app.get_metadata("pkg_id")
            if not pkg_id:
                pkg = self._resolve_first(Pk.FilterEnum.NOT_INSTALLED, app)
                if pkg:
                    pkg_id = pkg.get_id()
                elif not self.client:
                    return self._apt_fallback_install(app, install=True)
                else:
                    return self._apt_fallback_install(app, install=True)
                
            self.client.install_packages(True, [pkg_id], None, lambda p,t,d: None, None)
            return True
        except Exception as e:
            self._handle_error("PK install", e)
            return self._apt_fallback_install(app, install=True)

    def uninstall(self, app):
        if "apt" not in app.sources:
            package_name = self._resolve_dpkg_package(app)
            if package_name:
                app.add_source("apt")
        if "apt" not in app.sources:
            return False
        try:
            pkg_id = app.get_metadata("pkg_id")
            if not pkg_id:
                pkg = self._resolve_first(Pk.FilterEnum.INSTALLED, app)
                if pkg:
                    pkg_id = pkg.get_id()
                elif not self.client:
                    return self._apt_fallback_install(app, install=False)
                else:
                    return self._apt_fallback_install(app, install=False)

            self.client.remove_packages([pkg_id], True, False, None, lambda p,t,d: None, None)
            return True
        except Exception as e:
            self._handle_error("PK uninstall", e)
            return self._apt_fallback_install(app, install=False)
