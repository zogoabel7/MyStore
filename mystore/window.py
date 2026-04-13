import gi
import logging

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Gtk, Adw, Gio, GLib

from mystore.lib.categories import STORE_CATEGORY_SPECS, get_category_spec
from mystore.lib.plugin_loader import PluginLoader
from mystore.lib.jobs import PluginJob, PluginJobAction
from mystore.lib.app import AppState

log = logging.getLogger("mystore.window")


class MyStoreWindow(Adw.ApplicationWindow):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        self.set_title("MyStore")
        self.set_default_size(1024, 768)
        
        # Load engine
        self.loader = PluginLoader()
        self.loader.setup()

        # Navigation View wraps everything
        self.nav_view = Adw.NavigationView()
        self.set_content(self.nav_view)

        # ─── Toolbar View & Header ───
        self.toolbar_view = Adw.ToolbarView()
        
        self.header = Adw.HeaderBar()
        self.toolbar_view.add_top_bar(self.header)

        # ─── View Switcher (Tabs) ───
        self.view_stack = Adw.ViewStack()
        self.toolbar_view.set_content(self.view_stack)

        self.switcher_title = Adw.ViewSwitcherTitle()
        self.switcher_title.set_stack(self.view_stack)
        self.switcher_title.set_title("MyStore")
        self.header.set_title_widget(self.switcher_title)

        # ─── Tabs Creation ───
        self._build_explore_tab()
        self._build_installed_tab()

        # Wrap in NavPage
        self.main_page = Adw.NavigationPage.new(self.toolbar_view, "Accueil")
        self.nav_view.add(self.main_page)

        # ─── Data State ───
        self._current_app = None
        self._search_timeout = None

        self._load_categories()
        # Load a small overview closer to GNOME Software's curated landing page
        job = PluginJob(PluginJobAction.GET_OVERVIEW, callback=self._on_popular_loaded, limit=12)
        self.loader.process_async(job)

        self._load_installed()

    # ──────────────────────────────────────────────
    #  TAB: EXPLORER
    # ──────────────────────────────────────────────
    def _build_explore_tab(self):
        scroll = Gtk.ScrolledWindow()
        scroll.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        scroll.set_vexpand(True)

        home_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        home_box.set_margin_top(48)
        home_box.set_margin_bottom(48)
        home_box.set_margin_start(48)
        home_box.set_margin_end(48)
        home_box.set_halign(Gtk.Align.CENTER)
        
        clamp = Adw.Clamp()
        clamp.set_maximum_size(800)
        clamp.set_child(home_box)
        scroll.set_child(clamp)

        # Search box in the page
        self.search_entry = Gtk.SearchEntry()
        self.search_entry.set_placeholder_text("Rechercher une application…")
        self.search_entry.set_hexpand(True)
        self.search_entry.add_css_class("circular")
        self.search_entry.connect("search-changed", self._on_search_changed)
        self.search_entry.connect("activate", self._on_search_activate)
        
        search_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        search_row.append(self.search_entry)
        home_box.append(search_row)

        hero_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        hero_title = Gtk.Label(label="Sélection pour Kali Linux")
        hero_title.add_css_class("title-1")
        hero_title.set_halign(Gtk.Align.START)
        hero_box.append(hero_title)
        
        hero_subtitle = Gtk.Label(label="Découvrez des applications graphiques et des outils système puissants.")
        hero_subtitle.add_css_class("dim-label")
        hero_subtitle.set_halign(Gtk.Align.START)
        hero_box.append(hero_subtitle)
        home_box.append(hero_box)

        self.categories_flow = Gtk.FlowBox()
        self.categories_flow.set_homogeneous(True)
        self.categories_flow.set_min_children_per_line(3)
        self.categories_flow.set_max_children_per_line(5)
        self.categories_flow.set_selection_mode(Gtk.SelectionMode.NONE)
        self.categories_flow.set_column_spacing(12)
        self.categories_flow.set_row_spacing(12)
        home_box.append(self.categories_flow)

        self.popular_group = Gtk.ListBox()
        self.popular_group.add_css_class("boxed-list")
        self.popular_group.set_selection_mode(Gtk.SelectionMode.NONE)
        home_box.append(self.popular_group)
        self._popular_placeholder = Gtk.Label(label="Chargement…")
        self._popular_placeholder.add_css_class("dim-label")
        self._popular_placeholder.set_margin_top(12)
        self._popular_placeholder.set_margin_bottom(12)
        self.popular_group.append(self._popular_placeholder)

        self.view_stack.add_titled_with_icon(scroll, "explore", "Explorer", "folder-symbolic")

    # ──────────────────────────────────────────────
    #  TAB: INSTALLED (DOWNLOADS)
    # ──────────────────────────────────────────────
    def _build_installed_tab(self):
        scroll = Gtk.ScrolledWindow()
        clamp = Adw.Clamp()
        clamp.set_maximum_size(800)
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        box.set_margin_top(32)
        box.set_margin_bottom(32)
        box.set_margin_start(16)
        box.set_margin_end(16)
        clamp.set_child(box)
        scroll.set_child(clamp)

        title = Gtk.Label(label="Vos Applications")
        title.add_css_class("title-1")
        title.set_halign(Gtk.Align.START)
        box.append(title)

        self.installed_group = Gtk.ListBox()
        self.installed_group.add_css_class("boxed-list")
        self.installed_group.set_selection_mode(Gtk.SelectionMode.NONE)
        box.append(self.installed_group)

        self._installed_placeholder = Gtk.Spinner()
        self._installed_placeholder.set_halign(Gtk.Align.CENTER)
        self._installed_placeholder.start()
        box.append(self._installed_placeholder)

        self.view_stack.add_titled_with_icon(scroll, "installed", "Installées", "system-software-install-symbolic")

    # ──────────────────────────────────────────────
    #  SEARCH VIEW (Navigation Push)
    # ──────────────────────────────────────────────
    def _create_search_view(self, title):
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        scroll = Gtk.ScrolledWindow()
        clamp = Adw.Clamp()
        clamp.set_maximum_size(800)
        
        search_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=24)
        search_box.set_margin_top(32)
        search_box.set_margin_bottom(32)
        clamp.set_child(search_box)
        scroll.set_child(clamp)
        toolbar_view.set_content(scroll)

        self.search_title = Gtk.Label(label=title)
        self.search_title.add_css_class("title-1")
        self.search_title.set_halign(Gtk.Align.START)
        search_box.append(self.search_title)

        self.search_group = Gtk.ListBox()
        self.search_group.add_css_class("boxed-list")
        self.search_group.set_selection_mode(Gtk.SelectionMode.NONE)
        search_box.append(self.search_group)

        self.search_spinner = Gtk.Spinner()
        self.search_spinner.set_halign(Gtk.Align.CENTER)
        self.search_spinner.set_margin_top(48)
        self.search_spinner.start()
        search_box.append(self.search_spinner)

        page = Adw.NavigationPage.new(toolbar_view, "Recherche")
        self.nav_view.push(page)
        return page

    # ──────────────────────────────────────────────
    #  DETAILS VIEW
    # ──────────────────────────────────────────────
    def _create_details_view(self, app):
        toolbar_view = Adw.ToolbarView()
        header = Adw.HeaderBar()
        toolbar_view.add_top_bar(header)

        scroll = Gtk.ScrolledWindow()
        clamp = Adw.Clamp()
        clamp.set_maximum_size(800)
        
        details = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=32)
        details.set_margin_top(32)
        details.set_margin_bottom(32)
        details.set_margin_start(16)
        details.set_margin_end(16)
        clamp.set_child(details)
        scroll.set_child(clamp)
        toolbar_view.set_content(scroll)

        header_grid = Gtk.Grid(column_spacing=24, row_spacing=8)
        details.append(header_grid)

        app_icon = Gtk.Image()
        app_icon.set_pixel_size(128)
        if app.icon_path:
            app_icon.set_from_file(app.icon_path)
        else:
            icon_name = app.icon_name or "application-x-executable"
            app_icon.set_from_icon_name(icon_name)
        header_grid.attach(app_icon, 0, 0, 1, 3)

        name_lbl = Gtk.Label(label=app.name)
        name_lbl.add_css_class("title-1")
        name_lbl.set_halign(Gtk.Align.START)
        name_lbl.set_wrap(True)
        header_grid.attach(name_lbl, 1, 0, 1, 1)

        source_lbl = Gtk.Label(label=f"Source: {', '.join(app.sources)}")
        source_lbl.add_css_class("dim-label")
        source_lbl.set_halign(Gtk.Align.START)
        header_grid.attach(source_lbl, 1, 1, 1, 1)

        # Buttons
        btn_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        self.btn_install = Gtk.Button(label="Installer")
        self.btn_install.add_css_class("suggested-action")
        self.btn_install.add_css_class("pill")
        self.btn_install.set_valign(Gtk.Align.CENTER)
        self.btn_install.connect("clicked", self._on_install_clicked)
        btn_box.append(self.btn_install)

        self.btn_remove = Gtk.Button(label="Désinstaller")
        self.btn_remove.add_css_class("destructive-action")
        self.btn_remove.add_css_class("pill")
        self.btn_remove.set_valign(Gtk.Align.CENTER)
        self.btn_remove.connect("clicked", self._on_remove_clicked)
        btn_box.append(self.btn_remove)

        self._update_details_buttons(app)
        header_grid.attach(btn_box, 1, 2, 1, 1)
        
        # Link Button (URL)
        if app.url:
             link_btn = Gtk.LinkButton(uri=app.url, label="Site Web")
             link_btn.set_halign(Gtk.Align.END)
             header_grid.attach(link_btn, 2, 0, 1, 1)

        # Screenshots Carousel
        if app.screenshots:
            screenshots_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=16)
            screenshots_box.set_halign(Gtk.Align.CENTER)
            ss_scroll = Gtk.ScrolledWindow()
            ss_scroll.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.NEVER)
            ss_scroll.set_min_content_height(400)
            ss_scroll.set_child(screenshots_box)
            ss_scroll.add_css_class("card")
            
            for url in app.screenshots:
                # Load images nicely (can be done with GdkPixbuf async, but for simplicity we rely on Picture if its a local cache or raw URI)
                # Note: AppStream returns HTTP URIs, so ideally we shouldn't block, 
                # but Gtk.Picture can handle URIs implicitly or fail gracefully.
                picture = Gtk.Picture()
                picture.set_file(Gio.File.new_for_uri(url))
                picture.set_content_fit(Gtk.ContentFit.CONTAIN)
                picture.set_size_request(600, -1)
                screenshots_box.append(picture)
                
            details.append(ss_scroll)

        # Description
        desc_group = Adw.PreferencesGroup(title="Description")
        desc_lbl = Gtk.Label()
        desc_lbl.set_text(app.description)
        desc_lbl.set_wrap(True)
        desc_lbl.set_halign(Gtk.Align.START)
        desc_lbl.set_xalign(0)
        
        desc_row = Adw.ActionRow()
        desc_row.set_child(desc_lbl)
        desc_group.add(desc_row)
        details.append(desc_group)

        page = Adw.NavigationPage.new(toolbar_view, "Détails")
        self.nav_view.push(page)
        self._current_app = app
        app.connect("state-changed", self._on_app_state_changed)
        return page

    def _update_details_buttons(self, app):
        if app.state in [AppState.INSTALLING, AppState.DOWNLOADING]:
            self.btn_install.set_visible(True)
            self.btn_install.set_sensitive(False)
            self.btn_install.set_label("Installation en cours…")
            self.btn_remove.set_visible(False)
        elif app.state == AppState.REMOVING:
            self.btn_install.set_visible(False)
            self.btn_remove.set_visible(True)
            self.btn_remove.set_sensitive(False)
            self.btn_remove.set_label("Désinstallation…")
        elif app.is_installed:
            self.btn_install.set_visible(False)
            self.btn_remove.set_visible(True)
            self.btn_remove.set_sensitive(True)
            self.btn_remove.set_label("Désinstaller")
        else:
            self.btn_install.set_visible(True)
            self.btn_remove.set_visible(False)
            self.btn_install.set_sensitive(True)
            self.btn_install.set_label("Installer")
            
    def _on_app_state_changed(self, app):
        if self._current_app == app:
            self._update_details_buttons(app)

    # ──────────────────────────────────────────────
    #  EVENTS & ACTIONS
    # ──────────────────────────────────────────────
    def _on_search_changed(self, entry):
        if self._search_timeout:
            GLib.source_remove(self._search_timeout)
        self._search_timeout = GLib.timeout_add(500, self._trigger_search)

    def _on_search_activate(self, entry):
        if self._search_timeout:
            GLib.source_remove(self._search_timeout)
            self._search_timeout = None
        self._trigger_search()

    def _trigger_search(self):
        self._search_timeout = None
        query = self.search_entry.get_text().strip()
        if not query: return False

        self._create_search_view(f"Résultats pour « {query} »")
        job = PluginJob(PluginJobAction.SEARCH, query=query, callback=self._on_search_done)
        self.loader.process_async(job)
        return False

    def _on_search_done(self, job):
        self.search_spinner.stop()
        self.search_spinner.set_visible(False)
        self.search_group.remove_all()

        if not job.results:
            empty = Adw.StatusPage()
            empty.set_title("Aucun résultat")
            empty.set_description("Essayez d'autres mots-clés.")
            empty.set_icon_name("system-search-symbolic")
            self.search_group.append(empty)
        else:
            for app in job.results:
                row = self._create_app_row(app)
                self.search_group.append(row)

    def _on_category_clicked(self, category):
        spec = get_category_spec(category)
        title = f"Catégorie : {spec['label']}" if spec else f"Catégorie : {category}"
        self._create_search_view(title)
        job = PluginJob(PluginJobAction.LIST_CATEGORY, category=category, callback=self._on_search_done, limit=120)
        self.loader.process_async(job)

    def _on_install_clicked(self, btn):
        if self._current_app:
            job = PluginJob(PluginJobAction.INSTALL, app=self._current_app)
            self.loader.process_async(job)

    def _on_remove_clicked(self, btn):
        if self._current_app:
            job = PluginJob(PluginJobAction.UNINSTALL, app=self._current_app)
            self.loader.process_async(job)

    def _create_app_row(self, app):
        row = Adw.ActionRow()
        row.set_title(app.name)
        row.set_subtitle(app.summary)

        icon = Gtk.Image()
        if app.icon_path:
            icon.set_from_file(app.icon_path)
        else:
            icon.set_from_icon_name(app.icon_name or "application-x-executable")
        icon.set_pixel_size(48)
        row.add_prefix(icon)

        if app.is_installed:
            badge = Gtk.Label(label="Installé")
            badge.add_css_class("success")
            row.add_suffix(badge)

        row.set_activatable(True)
        gesture = Gtk.GestureClick.new()
        gesture.connect("pressed", lambda g, n, x, y: self._on_app_row_activated(app))
        row.add_controller(gesture)
        return row

    def _on_app_row_activated(self, app):
        self._create_details_view(app)
        job = PluginJob(PluginJobAction.REFINE, app=app, callback=self._on_details_refined)
        self.loader.process_async(job)

    def _on_details_refined(self, job):
        if job.app and self._current_app == job.app:
            self._update_details_buttons(job.app)

    # ──────────────────────────────────────────────
    #  HOME PAGE LOADERS
    # ──────────────────────────────────────────────
    def _load_categories(self):
        child = self.categories_flow.get_first_child()
        while child:
            next_child = child.get_next_sibling()
            self.categories_flow.remove(child)
            child = next_child

        for spec in STORE_CATEGORY_SPECS:
            cat = spec["id"]
            btn = Gtk.Button()
            btn.get_style_context().add_class("flat")
            btn.set_size_request(140, 80)
            
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
            box.set_valign(Gtk.Align.CENTER)
            
            icon = Gtk.Image.new_from_icon_name(spec["icon"])
            icon.set_pixel_size(32)
            box.append(icon)
            
            lbl = Gtk.Label(label=spec["label"])
            box.append(lbl)

            btn.set_child(box)
            btn.connect("clicked", lambda b, c=cat: self._on_category_clicked(c))
            self.categories_flow.append(btn)

    def _on_popular_loaded(self, job):
        self.popular_group.remove(self._popular_placeholder)
        if not job.results:
            lbl = Gtk.Label(label="Rien à afficher.")
            lbl.set_margin_top(12)
            lbl.set_margin_bottom(12)
            self.popular_group.append(lbl)
            return
        for app in job.results:
            self.popular_group.append(self._create_app_row(app))

    def _load_installed(self):
        job = PluginJob(PluginJobAction.GET_INSTALLED, callback=self._on_installed_loaded)
        self.loader.process_async(job)

    def _on_installed_loaded(self, job):
        self._installed_placeholder.stop()
        self._installed_placeholder.set_visible(False)
        if not job.results:
            empty = Adw.StatusPage()
            empty.set_title("Rien d'installé")
            empty.set_description("Vos applications s'afficheront ici.")
            self.installed_group.append(empty)
            return
            
        for app in job.results[:50]:
            self.installed_group.append(self._create_app_row(app))
