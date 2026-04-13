# Contribuer à MyStore

Merci de vouloir contribuer ! Ce document explique comment participer au projet.

---

## Comment contribuer

### 1. Fork & Clone

```bash
# Fork le repo sur GitHub, puis :
git clone https://github.com/zogoabel7/MyStore.git
cd MyStore/mystore
```

### 2. Créer une branche

```bash
git checkout -b ma-feature
```

### 3. Développer

Installe les dépendances :

```bash
sudo apt install python3 python3-gi \
  gir1.2-gtk-4.0 gir1.2-adwaita-1 \
  gir1.2-appstream-1.0 gir1.2-packagekit-glib2 \
  python3-apt
```

Lance l'application pour tester :

```bash
python3 -m mystore
```

### 4. Commit & Push

```bash
git add .
git commit -m "Description claire du changement"
git push origin ma-feature
```

### 5. Pull Request

Ouvre une PR sur GitHub vers la branche `main`. Décris le changement, la motivation, et les tests effectués.

---

## Types de contributions bienvenus

- **Bug fixes** — corriger un problème existant
- **Nouvelles fonctionnalités** — nouveau plugin, nouvelle vue UI, etc.
- **Améliorations UI/UX** — meilleure interface, animations, accessibilité
- **Documentation** — README, commentaires de code, doc technique
- **Tests** — les tests actuels sont cassés, toute aide est bienvenue
- **Traductions** — l'UI est en français, d'autres langues sont les bienvenues
- **Nettoyage** — supprimer le code mort, les relicats, les répertoires vides

---

## Conventions de code

- **Python 3.8+** compatible
- **Indentation :** 4 espaces
- **Style :** PEP 8 (avec tolérance pour les noms longs type GNOME)
- **Imports GI :** toujours `gi.require_version()` avant l'import du module
- **Threads :** jamais de modification GTK hors du thread principal → utiliser `GLib.idle_add()`
- **Logging :** utiliser `logging.getLogger("mystore.xxx")` plutôt que `print()`
- **Commentaires :** en français ou anglais, les deux sont acceptés

---

## Zones prioritaires

Ces parties du projet ont besoin d'aide en priorité :

1. **Tests fonctionnels** — les fichiers dans `tests/` sont cassés (importent des classes inexistantes)
2. **Plugin Flatpak** — mentionné dans le README original mais jamais implémenté
3. **Progression d'installation** — aucune barre de progression ou retour visuel
4. **Gestion d'erreurs** — les échecs d'installation ne sont pas remontés à l'utilisateur
5. **Rafraîchissement du cache APT** — le cache n'est jamais invalidé après une installation
6. **Chargement async des screenshots** — actuellement potentiellement bloquant
7. **Nettoyage** — `data/cache.json` inutilisé, `assets/` et `ui/` vides, `src/` wrappers inutiles

---

## Signaler un bug

Ouvre une **Issue** sur GitHub avec :

- Description du problème
- Étapes pour reproduire
- Comportement attendu vs observé
- Version de Kali/Debian et des dépendances (`python3 --version`, `dpkg -l gir1.2-gtk-4.0`, etc.)
- Logs pertinents (lancer avec le logger : `python3 -m mystore` affiche les logs dans le terminal)

---

## Code of Conduct

Soyez respectueux et constructif. Ce projet est ouvert à tous, quelle que soit l'expérience. Les contributions débutantes sont encouragées.
