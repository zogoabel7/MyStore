STORE_CATEGORY_SPECS = [
    {
        "id": "media",
        "label": "Média",
        "icon": "multimedia-player-symbolic",
        "terms": ("AudioVideo", "Audio", "Video", "Player"),
    },
    {
        "id": "graphics",
        "label": "Graphisme",
        "icon": "applications-graphics-symbolic",
        "terms": ("Graphics", "2DGraphics", "RasterGraphics", "VectorGraphics"),
    },
    {
        "id": "dev",
        "label": "Développement",
        "icon": "applications-engineering-symbolic",
        "terms": ("Development", "IDE", "GUIDesigner", "Debugger"),
    },
    {
        "id": "internet",
        "label": "Internet",
        "icon": "applications-internet-symbolic",
        "terms": ("Network", "WebBrowser", "Chat", "Email"),
    },
    {
        "id": "office",
        "label": "Bureautique",
        "icon": "applications-office-symbolic",
        "terms": ("Office", "Calendar", "Finance", "ProjectManagement"),
    },
    {
        "id": "system",
        "label": "Système",
        "icon": "applications-system-symbolic",
        "terms": ("System", "Monitor", "PackageManager", "Settings"),
    },
    {
        "id": "games",
        "label": "Jeux",
        "icon": "applications-games-symbolic",
        "terms": ("Game", "ActionGame", "StrategyGame", "LogicGame"),
    },
    {
        "id": "security",
        "label": "Sécurité",
        "icon": "security-high-symbolic",
        "terms": ("Security",),
    },
    {
        "id": "utils",
        "label": "Utilitaires",
        "icon": "applications-utilities-symbolic",
        "terms": ("Utility", "TextEditor", "Calculator", "Clock"),
    },
    {
        "id": "tools",
        "label": "Outils",
        "icon": "applications-other-symbolic",
        "terms": ("Filesystem", "Settings", "PackageManager", "Monitor"),
    },
]

_CATEGORY_BY_ID = {spec["id"]: spec for spec in STORE_CATEGORY_SPECS}


def get_category_spec(category_id):
    return _CATEGORY_BY_ID.get(category_id)


def get_category_terms(category_id):
    spec = get_category_spec(category_id)
    return spec["terms"] if spec else ()


def category_matches(app_categories, category_id):
    terms = set(get_category_terms(category_id))
    if not terms:
        return False

    for category in app_categories or []:
        if category in terms:
            return True

        if "::" in category:
            if any(part in terms for part in category.split("::")):
                return True

    return False
