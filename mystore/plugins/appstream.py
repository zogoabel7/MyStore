import logging
import os
from pathlib import Path
import gi
gi.require_version("AppStream", "1.0")
from gi.repository import AppStream as As, GLib

from mystore.lib.categories import STORE_CATEGORY_SPECS, category_matches, get_category_terms
from mystore.lib.plugin import StorePlugin
from mystore.lib.app import StoreApp, AppState

log = logging.getLogger("mystore.plugins.appstream")


def _to_list(items):
    if not items:
        return []
    return items.as_array() if hasattr(items, "as_array") else items


def _strip_desktop_suffix(value):
    value = value or ""
    if value.lower().endswith(".desktop"):
        return value[:-8]
    return value


def _normalize_token(value):
    return "".join(char for char in (value or "").lower() if char.isalnum())


def _component_basename(component_id):
    component_id = _strip_desktop_suffix(component_id)
    return component_id.rsplit(".", 1)[-1]


class AsPlugin(StorePlugin):
    def __init__(self, loader):
        super().__init__(loader, "appstream")
        self.pool = None

    def setup(self):
        self.pool = As.Pool()
        try:
            self.pool.load()
            log.info("AppStream pool initialized")
        except Exception as e:
            log.error(f"AppStream failed: {e}")

    def search(self, query, apps):
        """Primary search method. Matches apps from AppStream metadata."""
        if not self.pool: return
        
        comps_box = self.pool.search(query)
        if not comps_box: return
        comps = _to_list(comps_box)

        for comp in comps:
            # We ONLY care about GUI apps in the search results
            if not self._is_supported_component(comp):
                continue

            apps.append(self._build_app_from_component(comp))

    def get_installed(self, apps):
        if not self.pool:
            return

        seen = set()
        for desktop_file in self._iter_desktop_files():
            app = self._build_installed_app_from_desktop(desktop_file)
            if not app or app.id in seen:
                continue

            seen.add(app.id)
            apps.append(app)

    def list_category(self, category_id, apps, limit=None):
        if not self.pool:
            return

        terms = get_category_terms(category_id)
        if not terms:
            return

        comps = self._get_components_for_terms(terms)
        for comp in self._slice_components(_to_list(comps), category_id, limit=limit or 120):
            apps.append(self._build_app_from_component(comp))

    def list_overview(self, apps, limit=None):
        if not self.pool:
            return

        limit = limit or 12
        per_category = max(1, limit // max(1, len(STORE_CATEGORY_SPECS)))
        seen_ids = set()

        for spec in STORE_CATEGORY_SPECS:
            comps = self._get_components_for_terms(spec["terms"])
            for comp in self._slice_components(_to_list(comps), spec["id"], limit=per_category):
                comp_id = comp.get_id()
                if comp_id in seen_ids:
                    continue
                seen_ids.add(comp_id)
                apps.append(self._build_app_from_component(comp))
                if len(apps) >= limit:
                    return

    def refine(self, app):
        """Refine apps that did not originate from AppStream but were found by PackageKit."""
        if not self.pool: return

        comp = self._find_component_for_app(app)
        if not comp:
            return

        self._fill_app_from_component(app, comp)

    def _build_app_from_component(self, comp):
        app = StoreApp(comp.get_id())
        self._fill_app_from_component(app, comp)
        app.add_source("appstream")
        return app

    def _slice_components(self, comps, category_id=None, limit=None):
        seen_ids = set()
        selected = []

        for comp in comps:
            if not self._is_supported_component(comp):
                continue

            if category_id is not None and not category_matches(comp.get_categories() or [], category_id):
                continue

            comp_id = comp.get_id()
            if comp_id in seen_ids:
                continue

            seen_ids.add(comp_id)
            selected.append(comp)

        selected.sort(key=lambda comp: (comp.get_name() or comp.get_id() or "").lower())
        if limit is not None:
            return selected[:limit]
        return selected

    def _get_components_for_terms(self, terms):
        components = []
        seen_ids = set()

        for term in terms:
            for comp in _to_list(self.pool.get_components_by_categories([term])):
                comp_id = comp.get_id()
                if comp_id in seen_ids:
                    continue
                seen_ids.add(comp_id)
                components.append(comp)

        return components

    def _get_component_pkgnames(self, comp):
        pkg_names = []

        try:
            pkg_names.extend(name for name in _to_list(comp.get_pkgnames()) if name)
        except Exception:
            pass

        pkg_name = comp.get_pkgname()
        if pkg_name and pkg_name not in pkg_names:
            pkg_names.append(pkg_name)

        return pkg_names

    def _is_supported_component(self, comp):
        if comp.get_kind() != As.ComponentKind.DESKTOP_APP:
            return False

        bundles = _to_list(comp.get_bundles())
        unsupported_bundles = {
            As.BundleKind.FLATPAK,
            As.BundleKind.SNAP,
            As.BundleKind.APPIMAGE,
            As.BundleKind.LINGLONG,
            As.BundleKind.LIMBA,
        }
        if any(bundle.get_kind() in unsupported_bundles for bundle in bundles):
            return False

        return True

    def _iter_desktop_files(self):
        roots = [
            Path("/usr/share/applications"),
            Path("/usr/local/share/applications"),
            Path.home() / ".local/share/applications",
            Path("/var/lib/flatpak/exports/share/applications"),
        ]

        for root in roots:
            if not root.is_dir():
                continue

            for desktop_file in sorted(root.glob("*.desktop")):
                yield desktop_file

    def _read_desktop_keyfile(self, path):
        keyfile = GLib.KeyFile()
        try:
            keyfile.load_from_file(str(path), GLib.KeyFileFlags.NONE)
        except Exception:
            return None

        group = "Desktop Entry"
        try:
            if keyfile.get_string(group, "Type") != "Application":
                return None
        except Exception:
            return None

        for key in ("Hidden", "NoDisplay", "Terminal"):
            try:
                if keyfile.get_boolean(group, key):
                    return None
            except Exception:
                pass

        try:
            name = keyfile.get_locale_string(group, "Name", None)
        except Exception:
            name = None

        try:
            comment = keyfile.get_locale_string(group, "Comment", None)
        except Exception:
            comment = ""

        try:
            icon = keyfile.get_string(group, "Icon")
        except Exception:
            icon = ""

        try:
            categories = keyfile.get_string(group, "Categories")
        except Exception:
            categories = ""

        return {
            "name": name or path.stem,
            "summary": comment or "",
            "icon": icon or "",
            "categories": [item for item in categories.split(";") if item],
        }

    def _build_installed_app_from_desktop(self, desktop_file):
        info = self._read_desktop_keyfile(desktop_file)
        if not info:
            return None

        app = StoreApp(desktop_file.name)
        app.name = info["name"]
        app.summary = info["summary"]
        app.categories = info["categories"]
        app.state = AppState.INSTALLED
        app.add_source("desktop")
        app.set_metadata("desktop_file", str(desktop_file))

        icon_value = info["icon"]
        if icon_value:
            if os.path.isabs(icon_value) and os.path.exists(icon_value):
                app.icon_path = icon_value
            else:
                app.icon_name = icon_value

        # Fast path: only exact AppStream lookups here, to keep the installed page responsive.
        component = None
        for candidate_id in (desktop_file.name, _strip_desktop_suffix(desktop_file.name)):
            comps = _to_list(self.pool.get_components_by_id(candidate_id))
            if comps:
                component = comps[0]
                break

        if component and self._is_supported_component(component):
            self._fill_app_from_component(app, component)

        return app

    def _find_component_for_app(self, app):
        for candidate_id in (f"{app.id}.desktop", app.id):
            comps = _to_list(self.pool.get_components_by_id(candidate_id))
            if comps and self._is_supported_component(comps[0]):
                return comps[0]

        best = self._pick_best_component(_to_list(self.pool.search(app.id)), app)
        if best:
            return best

        search_term = app.name if app.has_name and app.name != app.id else None
        if search_term:
            best = self._pick_best_component(_to_list(self.pool.search(search_term)), app)
            if best:
                return best

        for token in [part for part in _strip_desktop_suffix(app.id).replace("_", "-").split("-") if len(part) > 2]:
            best = self._pick_best_component(_to_list(self.pool.search(token)), app)
            if best:
                return best

        return best

    def _pick_best_component(self, comps, app):
        best_score = 0
        best_comp = None
        app_id_variants = {
            _normalize_token(app.id),
            _normalize_token(_component_basename(app.id)),
        }

        app_name_token = _normalize_token(app.name) if app.has_name else ""

        for comp in comps:
            if not self._is_supported_component(comp):
                continue

            comp_id = comp.get_id() or ""
            comp_tokens = {
                _normalize_token(comp_id),
                _normalize_token(_strip_desktop_suffix(comp_id)),
                _normalize_token(_component_basename(comp_id)),
            }
            pkg_tokens = {_normalize_token(pkg) for pkg in self._get_component_pkgnames(comp)}
            name_token = _normalize_token(comp.get_name() or "")

            score = 0
            if app_id_variants & pkg_tokens:
                score += 300
            if app_id_variants & comp_tokens:
                score += 220
            if app_name_token and app_name_token == name_token:
                score += 160
            if app_name_token and app_name_token in comp_tokens:
                score += 140

            if score > best_score:
                best_score = score
                best_comp = comp

        return best_comp

    def _fill_app_from_component(self, app, comp):
        # We only override empty fields
        if not app.has_name:
            app.name = comp.get_name() or app.id
        
        if not app.summary:
            app.summary = comp.get_summary() or ""
        
        if not app.description:
            app.description = comp.get_description() or ""
            
        if not app.icon_path and app.icon_name == "application-x-executable":
            app.icon_path, app.icon_name = self._extract_icon_data(comp)
        
        if not app.categories:
            app.categories = list(comp.get_categories() or [])

        # Extract url
        if not app.url:
            app.url = comp.get_url(As.UrlKind.HOMEPAGE) or ""

        if not app.get_metadata("appstream_id"):
            app.set_metadata("appstream_id", comp.get_id())

        if not app.get_metadata("pkg_names"):
            app.set_metadata("pkg_names", self._get_component_pkgnames(comp))

        # Extract Screenshots
        if not app.screenshots:
            screenshots_found = []
            screens = _to_list(comp.get_screenshots_all())
            if screens:
                for ss in screens:
                    images = _to_list(ss.get_images_all())
                    if images:
                        # Pick the largest image URL simply
                        largest_image = images[0]
                        for img in images:
                            if img.get_width() > largest_image.get_width():
                                largest_image = img
                        if largest_image.get_url():
                            screenshots_found.append(largest_image.get_url())
            app.screenshots = screenshots_found

    def _extract_icon_data(self, comp):
        best_path = ""
        best_name = "application-x-executable"
        best_score = -1

        for icon in _to_list(comp.get_icons()):
            kind = icon.get_kind()
            filename = icon.get_filename() if hasattr(icon, "get_filename") else None
            name = icon.get_name() or ""
            width = icon.get_width() if hasattr(icon, "get_width") else 0

            if kind in (As.IconKind.CACHED, As.IconKind.LOCAL) and filename and os.path.exists(filename):
                score = 200 + width
                if score > best_score:
                    best_score = score
                    best_path = filename
                    best_name = name or best_name
                continue

            if kind == As.IconKind.STOCK and name:
                score = 100 + width
                if score > best_score:
                    best_score = score
                    best_path = ""
                    best_name = name

        return best_path, best_name
