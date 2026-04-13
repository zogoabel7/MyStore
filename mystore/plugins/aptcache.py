import logging
import threading

import apt

from mystore.lib.app import AppState, StoreApp
from mystore.lib.categories import STORE_CATEGORY_SPECS
from mystore.lib.plugin import StorePlugin

log = logging.getLogger("mystore.plugins.aptcache")


_CATEGORY_SECTIONS = {
    "media": {"sound", "video"},
    "graphics": {"graphics"},
    "dev": {"devel"},
    "internet": {"web", "net", "mail", "comm"},
    "office": {"editors", "text", "tex"},
    "system": {"admin", "system", "utils", "gnome", "kde", "x11"},
    "games": {"games"},
    "security": {"security"},
    "utils": {"utils"},
    "tools": {"admin", "science", "math", "electronics"},
}

_CATEGORY_KEYWORDS = {
    "media": {"media", "video", "audio", "music", "player", "stream", "photo", "viewer"},
    "graphics": {"image", "photo", "graphics", "draw", "paint", "editor", "viewer"},
    "dev": {"develop", "debug", "code", "editor", "ide", "program", "git"},
    "internet": {"browser", "web", "mail", "messaging", "chat", "network", "ftp", "download"},
    "office": {"office", "document", "word", "spreadsheet", "presentation", "writer", "calc"},
    "system": {"system", "settings", "partition", "disk", "print", "power", "package"},
    "games": {"game", "steam", "play", "arcade", "puzzle"},
    "security": {"security", "encrypt", "password", "hash", "forensic", "vpn"},
    "utils": {"utility", "tool", "calculator", "clock", "archive", "file", "rename"},
    "tools": {"tool", "analyzer", "monitor", "scanner", "manager", "terminal"},
}

_EXCLUDED_PREFIXES = (
    "lib",
    "gir1.2-",
    "python3-",
    "fonts-",
    "node-",
    "ruby-",
    "golang-",
    "rust-",
)

_EXCLUDED_SUFFIXES = (
    "-dev",
    "-dbg",
    "-dbgsym",
    "-doc",
    "-docs",
    "-common",
    "-data",
    "-locale",
    "-locales",
    "-examples",
    "-test",
    "-tests",
)


class AptCachePlugin(StorePlugin):
    def __init__(self, loader):
        super().__init__(loader, "aptcache")
        self._cache = None
        self._records = None
        self._lock = threading.Lock()

    def setup(self):
        log.info("APT cache plugin ready")

    def search(self, query, apps):
        records = self._ensure_records()
        if not records:
            return

        tokens = [token.lower() for token in query.split() if token.strip()]
        if not tokens:
            return

        ranked = []
        for record in records:
            score = self._search_score(record, tokens)
            if score <= 0:
                continue
            ranked.append((score, record))

        ranked.sort(key=lambda item: (-item[0], item[1]["installed"], item[1]["name"]))
        for _, record in ranked[:50]:
            apps.append(self._app_from_record(record))

    def list_category(self, category_id, apps, limit=None):
        records = self._ensure_records()
        if not records:
            return

        matches = [record for record in records if self._record_matches_category(record, category_id)]
        matches.sort(key=lambda record: (record["installed"], record["name"]))
        for record in matches[: (limit or 40)]:
            apps.append(self._app_from_record(record))

    def list_overview(self, apps, limit=None):
        records = self._ensure_records()
        if not records:
            return

        limit = limit or 12
        per_category = max(1, limit // max(1, len(STORE_CATEGORY_SPECS)))
        seen = set()

        for spec in STORE_CATEGORY_SPECS:
            matches = [record for record in records if self._record_matches_category(record, spec["id"])]
            matches.sort(key=lambda record: (record["installed"], record["name"]))
            added = 0
            for record in matches:
                if record["name"] in seen:
                    continue
                seen.add(record["name"])
                apps.append(self._app_from_record(record))
                added += 1
                if added >= per_category or len(apps) >= limit:
                    break
            if len(apps) >= limit:
                return

    def _ensure_records(self):
        if self._records is not None:
            return self._records

        with self._lock:
            if self._records is not None:
                return self._records

            cache = apt.Cache()
            records = []
            for pkg in cache:
                if not pkg.candidate:
                    continue

                record = self._record_from_package(pkg)
                if not record:
                    continue

                records.append(record)

            self._cache = cache
            self._records = records
            log.info("APT app catalog built: %d entries", len(records))
            return self._records

    def _record_from_package(self, pkg):
        cand = pkg.candidate
        name = pkg.name
        section = (cand.section or "").split("/")[-1].lower()
        summary = (cand.summary or "").strip()

        if not summary:
            return None
        if self._is_excluded_name(name):
            return None
        if not self._looks_like_user_app(name, section, summary):
            return None

        return {
            "name": name,
            "summary": summary,
            "section": section,
            "installed": pkg.is_installed,
        }

    def _is_excluded_name(self, name):
        return name.startswith(_EXCLUDED_PREFIXES) or name.endswith(_EXCLUDED_SUFFIXES)

    def _looks_like_user_app(self, name, section, summary):
        if section in {
            "games",
            "graphics",
            "sound",
            "video",
            "web",
            "net",
            "mail",
            "editors",
            "text",
            "tex",
            "gnome",
            "kde",
            "x11",
            "admin",
            "utils",
            "science",
            "math",
            "electronics",
            "security",
            "comm",
            "devel",
            "hamradio",
        }:
            return True

        haystack = f"{name} {summary}".lower()
        useful_words = {
            "browser",
            "editor",
            "viewer",
            "player",
            "client",
            "desktop",
            "messaging",
            "mail",
            "video",
            "image",
            "music",
            "office",
            "record",
            "stream",
            "monitor",
            "tool",
            "utility",
            "game",
        }
        return any(word in haystack for word in useful_words)

    def _record_matches_category(self, record, category_id):
        section_matches = record["section"] in _CATEGORY_SECTIONS.get(category_id, set())
        keyword_matches = any(
            keyword in f"{record['name']} {record['summary']}".lower()
            for keyword in _CATEGORY_KEYWORDS.get(category_id, set())
        )
        return section_matches or keyword_matches

    def _search_score(self, record, tokens):
        haystack = f"{record['name']} {record['summary']}".lower()
        name = record["name"].lower()
        score = 0

        for token in tokens:
            if name == token:
                score += 120
            elif name.startswith(token):
                score += 90
            elif token in name:
                score += 70
            elif token in haystack:
                score += 35
            else:
                return 0

        if not record["installed"]:
            score += 10
        return score

    def _app_from_record(self, record):
        app = StoreApp(record["name"])
        app.name = record["name"]
        app.summary = record["summary"]
        app.state = AppState.INSTALLED if record["installed"] else AppState.AVAILABLE
        app.add_source("apt")
        app.set_metadata("package_name", record["name"])
        app.set_metadata("apt_section", record["section"])
        return app
