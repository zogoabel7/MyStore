# MyStore

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)

Clone de **GNOME Software** pour **Kali Linux** — gestionnaire d'applications graphique basé sur APT, AppStream et PackageKit, avec une interface GTK 4 / Libadwaita.

---

## Lancement

### Prérequis

Dépendances système (Debian/Kali) :

```bash
sudo apt install python3 python3-gi \
  gir1.2-gtk-4.0 gir1.2-adwaita-1 \
  gir1.2-appstream-1.0 gir1.2-packagekit-glib2 \
  python3-apt
```

> **Note :** `gir1.2-appstream-1.0` et `gir1.2-packagekit-glib2` sont optionnels — l'application fonctionne sans mais avec des capacités réduites (pas de métadonnées riches ni de résolution PackageKit).

### Démarrage

Depuis le répertoire parent de `mystore/` :

```bash
# Méthode officielle (module Python)
python3 -m mystore

# Méthode rapide (lanceur wrapper)
python3 mystore/mystore.py
```

Les deux méthodes sont équivalentes. `mystore.py` lance un `subprocess` de `python3 -m mystore` pour éviter les problèmes de shadowing de path.

---

## Arborescence réelle du projet

```
mystore/
├── __main__.py              → Entry point pour `python3 -m mystore`
├── app.py                   → Classe MyStoreApp(Adw.Application), logging, thème sombre
├── window.py                → UI complète (485 lignes) : onglets, navigation, recherche, détails
├── mystore.py               → Lanceur rapide (subprocess vers -m mystore)
├── test_api.py              → Test manuel synchrone (SEARCH, GET_INSTALLED, REFINE)
│
├── lib/                     → Cœur métier (modèles, jobs, plugins)
│   ├── __init__.py          → Vide
│   ├── app.py               → StoreApp (GObject) + AppState (enum)
│   ├── categories.py        → 10 catégories avec mapping de termes
│   ├── jobs.py              → PluginJob + PluginJobAction, exécution async en thread
│   ├── plugin.py            → StorePlugin (classe de base abstraite)
│   └── plugin_loader.py     → PluginLoader : charge 3 plugins, dispatch en threads
│
├── plugins/                 → Implémentations concrètes des backends
│   ├── aptcache.py          → Plugin APT (python3-apt, search par scoring, catégories)
│   ├── appstream.py         → Plugin AppStream (métadonnées riches, icônes, screenshots)
│   └── packagekit.py        → Plugin PackageKit (resolve, install/remove, fallback apt)
│
├── src/                     → Wrappers de migration (délèguent à mystore/*)
│   ├── __init__.py
│   ├── app.py               → Délègue à mystore.app.MyStoreApp
│   └── window.py            → Réexporte mystore.window.MyStoreWindow
│
├── tests/                   → Tests (⚠ cassés — voir section Zones d'ombre)
│   ├── test_lib_wrapper.py  → Importe des classes inexistantes
│   └── test_plugins.py      → Importe PluginManager inexistant
│
├── data/
│   └── cache.json           → Cache JSON (137 Ko, non utilisé par le code actuel)
│
├── assets/                  → Vide (prévu pour icônes/images)
├── ui/                      → Vide (prévu pour composants graphiques réutilisables)
│
└── README.md                → Ce fichier
```

---

## Architecture détaillée

### Flux de données

```
Utilisateur (UI)
  │
  ▼
window.py (MyStoreWindow)
  │  crée un PluginJob avec callback
  ▼
PluginLoader.process_async(job)
  │  lance un thread daemon
  ▼
PluginJob.run(loader)
  │  exécute l'action séquentiellement sur les plugins
  │  (ordre : aptcache → appstream → packagekit)
  ▼
Chaque plugin traite l'action (search/refine/install/…)
  │
  ▼
GLib.idle_add(callback, job)  → retour sur le thread principal GTK
  │
  ▼
window.py met à jour l'UI (liste, boutons, spinner)
```

### Cycle de vie d'une recherche

1. L'utilisateur tape dans `SearchEntry` → signal `search-changed`
2. Un `GLib.timeout_add(500ms)` debounce est posé (`_on_search_changed`)
3. Au déclenchement, `_trigger_search()` crée une vue de recherche (NavigationPage push) et un `PluginJob(SEARCH, query=…, callback=_on_search_done)`
4. `PluginLoader.process_async()` lance un thread
5. Dans le thread, `PluginJob._run_search()` :
   - Privilégie le plugin `aptcache` (search par scoring de tokens)
   - Si aucun résultat, fallback sur les autres plugins (appstream, etc.)
   - Merge les résultats par `app.id` (déduplication, fusion des sources)
6. `GLib.idle_add()` rappelle `_on_search_done(job)` sur le thread GTK
7. L'UI affiche les `Adw.ActionRow` ou un `Adw.StatusPage` vide

### Cycle de vie d'une installation

1. L'utilisateur clique sur "Installer" dans la vue détails
2. `PluginJob(INSTALL, app=…)` est envoyé
3. `_run_install()` :
   - Passe l'état à `INSTALLING` via `GLib.idle_add` (UI se met à jour)
   - Itère sur les plugins ; si un retourne `True` → succès
   - `PkPlugin.install()` essaie PackageKit en premier, fallback `pkexec apt install -y`
   - Si succès → état `INSTALLED` ; si échec → état `AVAILABLE`

---

## Composants détaillés

### `lib/app.py` — StoreApp

Modèle central, clone Python de `GsApp` de gnome-software.

| Propriété | Type | Description |
|-----------|------|-------------|
| `id` | str (readonly) | Identifiant unique (nom de package, desktop file, ou ID AppStream) |
| `name` | str | Nom d'affichage (fallback vers `id` si vide) |
| `summary` | str | Résumé court |
| `description` | str | Description longue (HTML possible depuis AppStream) |
| `icon_name` | str | Nom d'icône thème (ex: `vlc`) |
| `icon_path` | str | Chemin absolu vers un fichier icône |
| `state` | AppState | État courant (émets le signal `state-changed`) |
| `sources` | list[str] | Origines : `"apt"`, `"appstream"`, `"desktop"`, `"packagekit"` |
| `categories` | list[str] | Catégories AppStream (ex: `["AudioVideo", "Player"]`) |
| `screenshots` | list[str] | URLs des captures d'écran |
| `url` | str | Page d'accueil |
| `is_installed` | bool (computed) | `True` si état `INSTALLED` ou `UPDATABLE` |

**Signal GObject :** `state-changed` — émis automatiquement quand `app.state` change, connecté dans `_create_details_view()` pour mettre à jour les boutons.

### `lib/app.py` — AppState (Enum)

| Valeur | Signification |
|--------|---------------|
| `UNKNOWN` | État non résolu (app vient d'être créée) |
| `INSTALLED` | App installée sur le système |
| `AVAILABLE` | App disponible mais non installée |
| `INSTALLING` | Installation en cours |
| `REMOVING` | Désinstallation en cours |
| `UPDATABLE` | Installée avec mise à jour disponible |
| `DOWNLOADING` | Téléchargement en cours (non utilisé actuellement) |

### `lib/jobs.py` — PluginJob & PluginJobAction

**PluginJobAction** — Actions possibles :

| Action | Paramètres | Description |
|--------|------------|-------------|
| `SEARCH` | `query`, `limit` | Recherche textuelle |
| `REFINE` | `app` | Enrichit une app avec détails (description, icône, état installé) |
| `INSTALL` | `app` | Installation via plugins |
| `UNINSTALL` | `app` | Désinstallation via plugins |
| `GET_INSTALLED` | — | Liste les apps installées |
| `LIST_CATEGORY` | `category`, `limit` | Apps d'une catégorie |
| `GET_OVERVIEW` | `limit` | Sélection éditoriale pour la page d'accueil |

**PluginJob** — Logique d'exécution :

- `run(loader)` : exécute l'action dans le thread courant
- `_merge_app_results()` : déduplique par `app.id`, fusionne les sources
- Priorité plugin : `aptcache` est toujours essayé en premier pour SEARCH, LIST_CATEGORY, GET_OVERVIEW ; les autres plugins sont fallback
- `GET_INSTALLED` filtre les apps sans catégorie/icône (garde seulement les apps GUI)
- Callback appelé via `GLib.idle_add()` pour revenir sur le thread GTK

### `lib/categories.py` — 10 catégories

| ID | Label | Icône | Termes AppStream |
|----|-------|-------|-------------------|
| `media` | Média | `multimedia-player-symbolic` | AudioVideo, Audio, Video, Player |
| `graphics` | Graphisme | `applications-graphics-symbolic` | Graphics, 2DGraphics, … |
| `dev` | Développement | `applications-engineering-symbolic` | Development, IDE, … |
| `internet` | Internet | `applications-internet-symbolic` | Network, WebBrowser, Chat, … |
| `office` | Bureautique | `applications-office-symbolic` | Office, Calendar, … |
| `system` | Système | `applications-system-symbolic` | System, Monitor, … |
| `games` | Jeux | `applications-games-symbolic` | Game, ActionGame, … |
| `security` | Sécurité | `security-high-symbolic` | Security |
| `utils` | Utilitaires | `applications-utilities-symbolic` | Utility, TextEditor, … |
| `tools` | Outils | `applications-other-symbolic` | Filesystem, Settings, … |

La fonction `category_matches()` supporte les catégories avec séparateur `::` (ex: `AudioVideo::Player`).

---

## Plugins détaillés

### `plugins/aptcache.py` — AptCachePlugin

**Rôle :** Recherche et catégorisation via le cache APT local (`python3-apt`).

**Fonctionnement :**
- Le cache APT est chargé en lazy (premier appel à `_ensure_records()`)
- Chaque paquet est filtré : pas de libs, pas de `-dev`, `-doc`, `-common`, etc.
- Un paquet est considéré "app utilisateur" si sa section est dans une liste blanche OU si son nom/résumé contient des mots-clés (browser, editor, player…)
- Recherche par scoring : nom exact (120), préfixe (90), sous-chaîne (70), dans le résumé (35)
- Catégorisation par section APT + mots-clés (double matching)
- Les résultats sont triés : installés en premier, puis alphabétique

**Limites :**
- Pas d'icônes (seul AppStream les fournit)
- Pas de description longue (seul le `summary` APT est disponible)
- Le cache est construit une seule fois et jamais rafraîchi (il faudrait un mécanisme d'invalidation)

### `plugins/appstream.py` — AsPlugin

**Rôle :** Métadonnées riches (descriptions, icônes, screenshots, URLs) via AppStream.

**Fonctionnement :**
- `As.Pool()` chargé au setup — contient tous les composants AppStream du système
- Search : `pool.search(query)` puis filtrage des composants `DESKTOP_APP` non-Flatpak/Snap
- `get_installed()` : itère les fichiers `.desktop` dans `/usr/share/applications`, `/usr/local/share/applications`, `~/.local/share/applications`, et `/var/lib/flatpak/exports/share/applications` — lit les clés Name, Comment, Icon, Categories via `GLib.KeyFile`
- `refine()` : pour une app donnée, cherche le composant AppStream correspondant via :
  1. Lookup exact par ID (avec/sans `.desktop`)
  2. Recherche fuzzy avec scoring (`_pick_best_component`) basé sur : package names (300 pts), component ID (220 pts), nom exact (160 pts), nom partiel (140 pts)
  3. Recherche par tokens du nom (split sur `-`, parties > 2 chars)
- Extraction d'icônes : privilégie `CACHED`/`LOCAL` avec chemin fichier (score 200+largeur), puis `STOCK` (score 100+largeur)
- Screenshots : prend l'image la plus large de chaque screenshot

**Limites :**
- Les screenshots sont des URLs HTTP — `Gtk.Picture` les charge de manière potentiellement bloquante
- Le matching fuzzy peut parfois associer une mauvaise app (faux positifs sur les noms génériques)
- Les composants Flatpak/Snap/AppImage sont exclus (`_is_supported_component`)

### `plugins/packagekit.py` — PkPlugin

**Rôle :** Résolution d'état (installé/disponible), installation/désinstallation via PackageKit.

**Fonctionnement :**
- Client DBus PackageKit au setup
- Si PackageKit est indisponible (pas de daemon, pas de permission) → le plugin se désactive automatiquement (`_disable()`)
- `refine()` : résout l'état installé via PK `resolve`, fallback `dpkg-query` + `apt-cache show`
- `install()` / `uninstall()` : essaie PackageKit en premier, fallback `pkexec apt install/remove -y`
- `_resolve_dpkg_package()` : pour une app desktop, trouve le paquet APT propriétaire via `dpkg-query -S`
- `_package_candidates()` : génère toutes les variantes de nom possibles (avec/sans `.desktop`, slug, basename, lowercase)

**Limites :**
- PackageKit est souvent indisponible sur Kali (daemon pas lancé par défaut) → le fallback apt est le chemin réel dans la plupart des cas
- L'installation via `pkexec` ouvre une boîte de dialogue polkit — pas de progression dans l'UI
- Pas de gestion des erreurs utilisateur (si l'install échoue, l'état revient à AVAILABLE mais aucun message n'est affiché)

---

## Interface graphique (window.py)

### Structure

```
Adw.ApplicationWindow
└── Adw.NavigationView
    └── Adw.NavigationPage "Accueil"
        └── Adw.ToolbarView
            ├── Adw.HeaderBar (avec Adw.ViewSwitcherTitle)
            └── Adw.ViewStack
                ├── Onglet "Explorer" (icon: folder-symbolic)
                │   ├── SearchEntry (debounce 500ms)
                │   ├── Hero "Sélection pour Kali Linux"
                │   ├── FlowBox catégories (3-5 colonnes)
                │   └── ListBox apps populaires
                └── Onglet "Installées" (icon: system-software-install-symbolic)
                    ├── Titre "Vos Applications"
                    └── ListBox apps installées
```

### Navigation push

Les vues de recherche et de détails sont poussées dans le `NavigationView` (navigation type mobile) :

- **Vue recherche** : titre dynamique, `ListBox` de résultats, spinner
- **Vue détails** : grille (icône 128px + nom + source + boutons), screenshots horizontaux scrollables, description dans `Adw.PreferencesGroup`

### Boutons Installer/Désinstaller

La méthode `_update_details_buttons()` gère 4 états visuels :

| État app | Bouton Installer | Bouton Désinstaller |
|----------|-------------------|---------------------|
| `INSTALLING`/`DOWNLOADING` | Visible, insensible, "Installation en cours…" | Caché |
| `REMOVING` | Caché | Visible, insensible, "Désinstallation…" |
| `INSTALLED`/`UPDATABLE` | Caché | Visible, sensible, "Désinstaller" |
| `AVAILABLE`/`UNKNOWN` | Visible, sensible, "Installer" | Caché |

---

## Zones d'ombre et problèmes connus

### Tests cassés

Les fichiers `tests/test_lib_wrapper.py` et `tests/test_plugins.py` importent des classes qui **n'existent pas** dans le code actuel :

- `test_lib_wrapper.py` → `from mystore.lib.app import App`, `from mystore.lib.app_list import AppList`, `from mystore.lib.catalog import Catalog`
- `test_plugins.py` → `from mystore.lib.plugins import PluginManager`

Ces classes faisaient partie d'une ancienne structure ou étaient prévues pour la migration mais n'ont jamais été implémentées. Les tests échoueront systématiquement.

### `data/cache.json` non utilisé

Le fichier `data/cache.json` (137 Ko) existe mais **aucun code ne le lit ni n'écrit dedans**. C'est un relicat d'une ancienne implémentation avec un système de cache. Il pourrait être supprimé ou réactivé.

### Répertoires `assets/` et `ui/` vides

Ces répertoires sont prévus dans l'architecture mais sont actuellement vides. Les icônes et composants UI sont directement intégrés dans `window.py`.

### `src/` — Wrappers de migration incomplète

Les fichiers `src/app.py` et `src/window.py` ne font que déléguer à `mystore.app` et `mystore.window`. Ils ont été créés pour une migration progressive vers une structure proche de gnome-software, mais cette migration n'a pas été poursuivie.

### README obsolète (celui-ci le remplace)

L'ancien README décrivait une architecture avec `catalog/core.py`, `catalog/cache.py`, `backends/apt.py`, `backends/flatpak.py` et `workers.py` — **aucun de ces fichiers n'existe**. L'architecture réelle est `lib/` + `plugins/`.

### Pas de Flatpak

Le README mentionnait Flatpak, mais **aucun plugin Flatpak n'existe**. Seuls APT, AppStream et PackageKit sont implémentés.

### Pas de workers.py

Le fichier `workers.py` mentionné dans l'ancien README n'existe pas. Les tâches en arrière-plan sont gérées par `PluginLoader.process_async()` via des threads daemon simples.

### Pas de progression d'installation

L'installation/désinstallation ne montre aucune barre de progression. L'UI passe seulement de "Installer" → "Installation en cours…" → "Désinstaller" (ou retour à "Installer" si échec). Aucune indication de téléchargement ou de pourcentage.

### Pas de rafraîchissement du cache APT

Le cache APT est construit une seule fois au premier accès et n'est jamais invalidé. Si l'utilisateur installe une app, la liste des apps installées ne se mettra pas à jour tant que l'application n'est pas redémarrée.

### Thread safety partielle

`AptCachePlugin` utilise un lock pour la construction du cache, mais les opérations de lecture sur `self._records` ne sont pas protégées. En pratique, cela fonctionne car le cache est construit une fois puis seulement lu, mais ce n'est pas formellement thread-safe.

### Screenshots bloquants

Les screenshots AppStream sont des URLs HTTP chargées via `Gtk.Picture.set_file(Gio.File.new_for_uri(url))`. Cela peut bloquer l'UI ou échouer silencieusement si le réseau est lent.

### Pas de gestion d'erreur utilisateur

Quand une installation échoue, l'état revient à `AVAILABLE` mais aucun message d'erreur n'est affiché à l'utilisateur. L'échec est seulement loggé.

### `AppState.DOWNLOADING` non utilisé

L'état `DOWNLOADING` est défini dans l'enum mais n'est jamais assigné nulle part dans le code.

---

## Dépendances

| Paquet | Rôle | Obligatoire |
|--------|------|-------------|
| `python3` (≥ 3.8) | Runtime | ✅ |
| `gir1.2-gtk-4.0` | Toolkit graphique | ✅ |
| `gir1.2-adwaita-1` | Widgets Libadwaita | ✅ |
| `python3-gi` | Bindings GObject | ✅ |
| `python3-apt` | Cache APT | ✅ (plugin aptcache) |
| `gir1.2-appstream-1.0` | Métadonnées apps | ❌ (sans: pas de descriptions, icônes, screenshots) |
| `gir1.2-packagekit-glib2` | Installation via PK | ❌ (sans: fallback pkexec apt) |

---

## Réponse : script d'installation ?

**Oui, c'est tout à fait possible.** Un script d'installation pourrait :

1. Installer les dépendances système listées ci-dessus
2. Copier le package `mystore/` dans un emplacement standard (ex: `/opt/mystore/` ou `/usr/lib/python3/dist-packages/mystore/`)
3. Créer un fichier `.desktop` dans `/usr/share/applications/` pour l'intégrer au menu d'applications
4. Créer un script wrapper dans `/usr/local/bin/mystore` pour le lancement
5. Optionnellement installer un schéma GSettings pour l'ID `com.mystore.app`

C'est un projet tout à fait réalisable — dis-moi si tu veux que je le crée.
