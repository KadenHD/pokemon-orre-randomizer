"""Offline packaged-app check. Never opens a ROM or personal preferences."""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
import os
import hashlib
from pathlib import Path
import sys
import tempfile


def check_menu_artwork() -> dict:
    """Exercise each self-contained menu renderer using authenticated assets."""
    from PySide6.QtGui import QImage
    from .hd_menu_catalog import SUPPORTED, menu_image, menu_recipes, menu_vectors
    from .hd_menu_atlases import render_menu_atlas
    regional = {game: menu_recipes(game) for game in sorted(SUPPORTED)}
    assert all(regional.values()), "A regional menu catalogue is unavailable"
    vectors = menu_vectors()
    assert {"latin", "japanese"} <= set(vectors["families"])
    registered = {key: row for rows in regional.values() for key, row in rows.items()}
    samples = {}
    for target, row in sorted(registered.items()):
        if row.get("file") and not row.get("bundled_donor"):
            continue  # External HD pack donors are checked at preparation.
        recipe = row["transform"]
        method = recipe["type"]
        if method in samples:
            continue
        if row.get("bundled_donor"):
            donor = menu_image(row["bundled_donor"], tuple(row["source_native_dimensions"]))
            source, metadata = donor.image, donor.metadata
        else:
            source, metadata = QImage(), {"kind": "authored-vector-artwork"}
        output, receipt = render_menu_atlas(source, recipe, source_metadata=metadata)
        size = [value * 4 for value in recipe["native_dimensions"]]
        assert not output.isNull() and [output.width(), output.height()] == size
        samples[method] = {"target": target, "dimensions": size,
                           "rgba_sha256": receipt["output_rgba_sha256"]}
    assert samples, "No authenticated menu sample could be rendered"
    return {"regional_recipe_counts": {game: len(rows) for game, rows in regional.items()},
            "unique_recipes": len(registered), "rendered_methods": samples,
            "external_packs_opened": False, "rom_opened": False}


def check_form_materials() -> dict:
    """Verify the entire bundled stock-material catalogue without a ROM or pack."""
    from PySide6.QtGui import QImage
    from .hd_form_materials import material_recipes
    from .hd_menu_catalog import SUPPORTED, _asset_bytes
    regional = {game: material_recipes(game) for game in sorted(SUPPORTED)}
    rows = {key: row for recipes in regional.values() for key, row in recipes.items()}
    for name, row in rows.items():
        payload, digest = _asset_bytes("form-materials/" + name)
        image = QImage.fromData(payload, "PNG")
        if (digest != row["sha256"] or image.isNull()
                or [image.width(), image.height()] != row["dimensions"]):
            raise ValueError("Packaged stock form material differs from its reviewed source")
    return {"checked_images": len(rows), "regional_counts": {g: len(r) for g, r in regional.items()},
            "rom_opened": False, "external_packs_opened": False}


def check_launcher_upgrades(parent: Path) -> dict:
    """Exercise real upgrades in disposable runs, including the frozen runtime copy.

    Synthetic files deliberately stand in for ROMs and saves: this check never
    opens a personal run, starts Dolphin or downloads a pack.
    """
    from . import __version__
    from .hd_packs import PACKS
    from .launcher_updates import upgrade_launcher, upgrade_status
    from .play_folders import launcher_command

    results = []
    with tempfile.TemporaryDirectory(prefix="launcher-upgrade-check-", dir=parent) as directory:
        root = Path(directory)
        for game, game_id in (("colosseum", "GC6E01"), ("xd", "GXXE01")):
            folder = root / game
            folder.mkdir()
            pins = {name: PACKS[name].key for name in (game, "colosseum")}
            manifest = {"schema": 1, "orre_version": "0.0.0", "game": game,
                "game_id": game_id, "seed": "offline-upgrade-check", "rom": "Game/game.iso",
                "shared": str(root / "Shared"), "dolphin": str(root / "Dolphin.exe"),
                "language": "en", "pack": PACKS[game].key, "packs": pins,
                "settings": {"graphics": "original", "speed": 1, "native_music": False}}
            protected = {"game.json": (json.dumps(manifest, indent=2) + "\n").encode(),
                "Game/game.iso": b"synthetic disc sentinel, never emulated",
                "DolphinUser/GC/MemoryCardA.USA.raw": b"synthetic saved game",
                "DolphinUser/StateSaves/run.sav": b"synthetic state",
                "DolphinUser/Config/GCPadNew.ini": b"synthetic custom controls",
                "Textures/NativeReferences/keep.bin": b"synthetic frozen resource"}
            for name, payload in protected.items():
                path = folder / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(payload)
            native = "Launcher.exe" if os.name == "nt" else "Launcher"
            (folder / native).write_bytes(b"previous native launcher")
            descriptor = b"ORRE-LAUNCHER-1\nold runtime sentinel\nold directory sentinel\n"
            (folder / "launcher-runtime.txt").write_bytes(descriptor)
            path = folder / "game.json"
            result = upgrade_launcher(path)
            assert result["changed"] and result["version"] == __version__
            assert not upgrade_status(path)["available"]
            backup = Path(result["backup_directory"])
            assert (backup / native).read_bytes() == b"previous native launcher"
            assert (backup / "launcher-runtime.txt").read_bytes() == descriptor
            command, _ = launcher_command(path)
            assert Path(command[0]).is_file() and command[-2:] == ["--play-folder", str(path)]
            for name, payload in protected.items():
                assert (folder / name).read_bytes() == payload, name
            results.append({"game": game, "version": result["version"],
                "protected_files_unchanged": len(protected), "backup_verified": True,
                "pack_pins_unchanged": True, "current_runtime_resolved": True})
    return {"runs": results, "frozen_runtime_copy": bool(getattr(sys, "frozen", False)),
            "personal_runs_opened": False, "emulator_started": False}


def check_run_management(parent: Path) -> dict:
    """Use actual SQLite/card/code operations and widgets with disposable sentinels."""
    from unittest.mock import patch
    import time
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings
    from PySide6.QtWidgets import QApplication
    from . import __version__
    from .challenges import encode_challenge, decode_challenge
    from .gui import MainWindow
    from .hd_packs import PACKS
    from .options import Options
    from .run_library import RunLibrary
    from .save_backups import backup_cards, restore_backup, list_backups
    from .storage import scan_storage
    from .ui_run_tools import LibraryDialog, BackupDialog, StorageDialog, ChallengeDialog
    from .support_report import operation_snapshot, remember_failure, save_report
    from .ui_support_report import SupportReportDialog
    from .xd import XDOptions

    app = QApplication.instance() or QApplication([])
    with tempfile.TemporaryDirectory(prefix="run-tools-check-", dir=parent) as directory:
        root = Path(directory)
        library = RunLibrary(root / "Library")
        folders = []
        # The sentinels cannot be launched. Mock only emulator detection so an
        # unrelated personal Dolphin session is neither queried nor changed.
        with patch("orre_randomizer.run_safety.dolphin_arguments", return_value=[]):
            for game, game_id, options in (("colosseum", "GC6E01", Options.none()),
                                           ("xd", "GXXE01", XDOptions.unchanged())):
                folder = root / game
                (folder / "Game").mkdir(parents=True)
                (folder / "DolphinUser/GC").mkdir(parents=True)
                rom = folder / "Game/game.iso"; rom.write_bytes(b"synthetic disc, never emulated")
                card = folder / "DolphinUser/GC/MemoryCardA.USA.raw"
                original = b"synthetic saved card"; card.write_bytes(original)
                manifest = {"schema": 1, "orre_version": __version__, "game": game,
                    "game_id": game_id, "seed": "offline-run-tools", "rom": "Game/game.iso",
                    "rom_sha256": hashlib.sha256(rom.read_bytes()).hexdigest(),
                    "shared": str(root / "Shared"), "dolphin": str(root / "never-executed.exe"),
                    "language": "en", "pack": PACKS[game].key,
                    "settings": {"graphics": "original", "speed": 1, "native_music": False}}
                path = folder / "game.json"; path.write_text(json.dumps(manifest), "utf-8")
                library.register(path)
                snapshot = backup_cards(folder)
                card.write_bytes(b"later synthetic progress")
                restore_backup(folder, snapshot)
                assert card.read_bytes() == original and len(list_backups(folder)) == 2
                assert hashlib.sha256(rom.read_bytes()).hexdigest() == manifest["rom_sha256"]
                decoded_game, profile = decode_challenge(encode_challenge(manifest["seed"], options))
                assert decoded_game == game and profile.options == options and profile.seed == manifest["seed"]
                folders.append(folder)
            assert len(library.entries()) == 2
            plan = scan_storage(root / "Shared", library.entries())
            assert plan.categories["roms"] > 0 and not plan.candidates

            settings = QSettings(str(root / "preferences.ini"), QSettings.Format.IniFormat)
            settings.setValue("interface/music", False); settings.setValue("interface/sounds", False)
            settings.setValue("launcher/shared", str(root / "Shared"))
            window = MainWindow(settings=settings, system_languages=["en"],
                                start_on_home=True, allow_update_checks=False)
            window.run_library = library
            states = []
            try:
                for cls, args in ((LibraryDialog, ()), (BackupDialog, (folders[0],)),
                                  (StorageDialog, ()), (ChallengeDialog, ())):
                    dialog = cls(window, *args)
                    try:
                        dialog.show()
                        deadline = time.monotonic() + 8
                        while dialog.task is not None:
                            app.processEvents(); time.sleep(.005)
                            if time.monotonic() > deadline:
                                raise RuntimeError("Run-tool diagnostic worker deadline")
                        app.processEvents()
                        if cls is LibraryDialog:
                            assert dialog.list.rowCount() == 2
                        elif cls is BackupDialog:
                            assert dialog.list.rowCount() == 2
                        elif cls is StorageDialog:
                            assert dialog.plan is not None and not dialog.clean.isEnabled()
                        else:
                            decode_challenge(dialog.code.toPlainText())
                        bounds = dialog.layout().minimumSize()
                        assert bounds.width() <= dialog.width() and bounds.height() <= dialog.height()
                        states.append(cls.__name__)
                    finally:
                        dialog.close(); dialog.deleteLater()
                        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
                for game in ("colosseum", "xd"):
                    (window.show_xd if game == "xd" else window.show_colosseum)()
                    owner = window.xd if game == "xd" else window
                    owner.seed.setText("offline-support-check")
                    operation_snapshot(owner, "creation")
                    remember_failure(owner, OSError("private diagnostic sentinel, never exported"), False)
                    dialog = SupportReportDialog(window)
                    try:
                        dialog.show(); app.processEvents()
                        reviewed = json.loads(dialog.preview.toPlainText())
                        destination = root / (game + "-support.json")
                        save_report(destination, dialog.document, include_seed=dialog.include_seed.isChecked())
                        assert json.loads(destination.read_text("utf-8")) == reviewed
                        assert reviewed["game"] == game and reviewed["seed"] == "offline-support-check"
                        assert reviewed["operation"]["error"] == {"kind": "io", "code": "file_access_failed"}
                        assert "private diagnostic sentinel" not in destination.read_text("utf-8")
                        assert dialog.layout().minimumSize().width() <= dialog.width()
                        assert dialog.layout().minimumSize().height() <= dialog.height()
                    finally:
                        dialog.close(); dialog.deleteLater()
                        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            finally:
                window.close(); window.deleteLater()
                QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    return {"games": 2, "sqlite_roundtrip": True, "card_restore_verified": True,
            "challenge_roundtrips": 2, "storage_read_only": True, "dialogs": states,
            "support_exports": 2, "support_dialog_reviewed": True,
            "personal_runs_opened": False, "emulator_started": False}


def run_checks(report: Path, *, screenshots: bool = False, screenshot_scope: str = "all") -> dict:
    if screenshot_scope not in {"all", "smoke"}:
        raise ValueError("Unknown diagnostic screenshot scope")
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt, qVersion
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication, QScrollArea
    from . import __version__, native_codec, disc_images
    from .engine.analyze_game import decompress_lzss_python
    from .engine.rebuild_iso import compress_lzss_python
    from .gui import MainWindow, recommended_preset
    from .i18n import LANGUAGES
    from .options import Options
    from .locales.selection_names import SPECIES_NAMES
    from .ui_exclusions import ExclusionDialog
    from .resources import application_icon, application_logo, interface_assets, menu_icon
    from .update_apply import automatic_updates_supported, update_kind

    app = QApplication.instance() or QApplication(["OrreRandomizer diagnostics"])
    if sys.platform == "win32":
        QFontDatabase.addApplicationFont(str(Path(os.environ.get("SystemRoot", "C:/Windows"))/"Fonts/segoeui.ttf"))
        QFontDatabase.addApplicationFont(str(Path(os.environ.get("SystemRoot", "C:/Windows"))/"Fonts/YuGothR.ttc"))
        app.setFont(QFont("Segoe UI", 10))
    sample = bytes(range(256)) * 16 + b"Orre diagnostics" * 64
    encoded = compress_lzss_python(sample)
    assert decompress_lzss_python(encoded) == sample
    codec = native_codec.backend()
    if codec == "rust-lzss-v1":
        assert native_codec.compress(sample) == encoded
        assert native_codec.decompress(encoded, len(sample)) == sample

    images, sounds = interface_assets()
    data = {"version": __version__, "qt": qVersion(), "codec": codec,
            "frozen": bool(getattr(sys, "frozen", False)),
            "images": sorted(images), "sounds": sorted(sounds),
            "game_cursor_available": menu_icon() is not None,
            "application_icon_available": application_icon() is not None,
            "application_logo_available": application_logo() is not None,
            "rom_opened": False, "personal_preferences_opened": False,
            "home_states": [], "states": [], "exclusion_states": [], "shiny_states": [], "preview_states": [],
            "consolidation_states": [], "xd_states": [], "xd_parity_states": []}
    capture_counts = {"enabled": screenshots, "scope": screenshot_scope,
                      "rendered": 0, "saved": 0, "rendered_without_png": 0}
    data["screenshot_capture"] = capture_counts

    def capture(widget, path, *, retained=True):
        frame = widget.grab()
        assert not frame.isNull()
        capture_counts["rendered"] += 1
        # CI only retains its main state matrix. Paint the remaining states as
        # before, but avoid encoding PNGs that the smoke wrapper discards.
        if screenshot_scope == "smoke" and not retained:
            capture_counts["rendered_without_png"] += 1
            return False
        assert frame.save(str(path))
        capture_counts["saved"] += 1
        return True
    data["hd_text_font"] = None
    if images:
        from .hd_text_vectors import SOURCE as FONT_SOURCE, _sources
        fonts = Path(__file__).resolve().parent / "assets/game/fonts"
        font, cmap = _sources(fonts / "NotoSansJP.ttf", fonts / "OFL-NotoSansJP.txt")
        font_sample = "AaéÉÄñàあ"
        assert all(ord(char) in cmap for char in font_sample)
        assert font.getmask(font_sample, mode="L").getbbox(), "The bundled vector font did not render"
        data["hd_text_font"] = {"verified_donor_and_license": True, "sample_rendered": True,
                                "recipe": FONT_SOURCE["recipe"], "rasterizer": FONT_SOURCE["rasterizer"]}
        data["hd_menu_artwork"] = check_menu_artwork()
        data["hd_form_materials"] = check_form_materials()
    data["disc_converter"] = None
    if disc_images.library_path().is_file():
        import threading
        with tempfile.TemporaryDirectory(prefix="disc-diagnostic-") as directory:
            source = Path(directory) / "synthetic.gcm"
            sample = bytearray(262144)
            sample[:6] = b"GC6E01"
            sample[0x1c:0x20] = b"\xc2\x33\x9f\x3d"
            source.write_bytes(sample)
            compressed = source.with_suffix(".rvz")
            decoded = source.with_suffix(".iso")
            disc_images.convert(source, compressed, threading.Event())
            disc_images.convert(compressed, decoded, threading.Event())
            assert hashlib.sha256(decoded.read_bytes()).digest() == hashlib.sha256(sample).digest()
            data["disc_converter"] = disc_images.BACKEND
    if data["frozen"]:
        assert data["disc_converter"], "The packaged app must include the disc converter"
    data["windows_update_helper_available"] = Path(__file__).with_name("windows_update.ps1").is_file()
    data["automatic_updates_supported"] = automatic_updates_supported()
    data["update_package_kind"] = update_kind()
    if data["frozen"] and sys.platform == "win32":
        assert data["windows_update_helper_available"] and data["automatic_updates_supported"]
    with tempfile.TemporaryDirectory(prefix="diagnostic-prefs-", dir=report.parent) as folder:
        settings = QSettings(str(Path(folder)/"preferences.ini"), QSettings.Format.IniFormat)
        settings.setValue("interface/music", False)
        settings.setValue("interface/sounds", False)
        settings.setValue("launcher/shared", str(Path(folder) / "Shared"))
        window = MainWindow(settings=settings, system_languages=["fr-FR"], allow_update_checks=False)
        try:
            data["game_folder_default"] = all(owner.play_folder.enabled.isChecked() for owner in (window, window.xd))
            assert data["game_folder_default"]
            # The older state matrix intentionally exercises the ROM-only workflow.
            for owner in (window, window.xd):
                owner.play_folder.enabled.setChecked(False)
            from .native_music_render import renderer_path, load_renderer
            native_launcher = Path(__file__).parent / "_native/OrreLauncher.exe"
            data["game_folder_launcher_available"] = native_launcher.is_file()
            data["native_music_renderer_available"] = renderer_path().is_file()
            if data["frozen"]:
                assert data["game_folder_launcher_available"] and data["native_music_renderer_available"]
                load_renderer()
            assert not window.music_requested and not window.audio.enabled
            data["music_tracks"] = {scene: path.name for scene, path in window.music_tracks.items() if path is not None}
            data["music_available"] = "colosseum" in data["music_tracks"]
            assert not window.windowIcon().pixmap(16, 16).isNull()
            assert not window.windowIcon().pixmap(256, 256).isNull()
            data["home_logo_dimensions"] = {
                game: [button.logo.width(), button.logo.height()]
                for game, button in (("colosseum", window.home.colosseum), ("xd", window.home.xd))
            }
            data["application_icon_sizes"] = sorted(size.width() for size in window.windowIcon().availableSizes())
            assert {16, 256} <= set(data["application_icon_sizes"])
            window.seed.setText("diagnostic-étoile-42")
            assert all(not window.rule_nav.item(index).icon().isNull()
                       for index in range(window.rule_nav.count()))
            for language in LANGUAGES:
                window.language_combo.setCurrentIndex(window.language_combo.findData(language))
                assert window.language == language
                if language != "en":
                    assert window._qt_translator is not None
                assert window.seed.text() == "diagnostic-étoile-42"
                assert window.current_options() == recommended_preset()
                for width, height in ((1040, 800), (680, 540)):
                    window.step = 0
                    window.refresh_navigation()
                    window.resize(width, height)
                    window.show_home()
                    assert window.music.path == window.music_tracks["home"]
                    window.show()
                    app.processEvents()
                    assert window.open_colosseum.isVisible() and window.open_colosseum.isEnabled()
                    assert window.rect().contains(window.open_colosseum.mapTo(window, window.open_colosseum.rect().center()))
                    assert not window.next_button.isVisible()
                    home = {"language": language, "width": width, "height": height}
                    if screenshots:
                        home["screenshot"] = f"home-{language}-{width}.png"
                        assert capture(window, report.parent / home["screenshot"])
                    window.open_xd.click()
                    assert window.music.path == window.music_tracks["xd"]
                    xd = window.xd
                    assert window.game_views.currentWidget() is xd and window.surface.xd
                    assert xd.source.text() == ""
                    for step in range(3):
                        xd.step = step
                        xd.pages.setCurrentIndex(step)
                        xd.refresh_navigation()
                        app.processEvents()
                        action = xd.create_button
                        assert xd.pages.currentIndex() == step and action.isVisible() and action.isEnabled()
                        assert window.rect().contains(action.mapTo(window, action.rect().center()))
                        state = {"language": language, "width": width, "height": height, "step": step + 1}
                        if screenshots:
                            state["screenshot"] = f"xd-{language}-{width}-step{step + 1}.png"
                            assert capture(window, report.parent / state["screenshot"])
                        data["xd_states"].append(state)
                    xd.step = 1
                    xd.pages.setCurrentIndex(1)
                    xd.workspace_tabs.setCurrentIndex(0)
                    xd.set_advanced_mode(True)
                    for category in xd.rule_groups:
                        xd.rule_panel.categories.setCurrentRow(xd.rule_groups.index(category))
                        app.processEvents()
                        assert window.rect().contains(xd.create_button.mapTo(window, xd.create_button.rect().center()))
                        state = {"language": language, "width": width, "height": height, "category": category}
                        if screenshots:
                            name = f"xd-parity-{language}-{width}-category{xd.rule_groups.index(category)}.png"
                            if capture(window, report.parent / name, retained=False):
                                state["screenshot"] = name
                            else:
                                state["rendered_without_png"] = True
                        data["xd_parity_states"].append(state)
                    xd.workspace_tabs.setCurrentIndex(1)
                    for tab, count in ((0, 1), (1, 83), (2, 7), (3, 9)):
                        xd.encounter_tabs.setCurrentIndex(tab)
                        app.processEvents()
                        assert not xd.preview_button.isHidden()
                        assert xd.preview_count.text() != window.text("Aucun résultat") or tab == 0
                        if tab:
                            assert not xd.preview_search.isHidden()
                            assert xd.preview_details.topLevelItemCount() == count
                            assert xd.preview_details.viewport().height() >= 46
                        state = {"language": language, "width": width, "height": height, "tab": tab}
                        if screenshots:
                            name = f"xd-parity-{language}-{width}-tab{tab}.png"
                            if capture(window, report.parent / name, retained=False):
                                state["screenshot"] = name
                            else:
                                state["rendered_without_png"] = True
                        data["xd_parity_states"].append(state)
                    xd.encounter_tabs.setCurrentIndex(0)
                    xd.workspace_tabs.setCurrentIndex(0)
                    xd.set_advanced_mode(False)
                    xd.rule_panel.categories.setCurrentRow(0)
                    window.show_home()
                    window.open_colosseum.click()
                    assert window.game_views.currentWidget() is window.colosseum
                    window.back_button.click()
                    assert window.game_views.currentWidget() is window.home
                    window.open_colosseum.click()
                    assert window.seed.text() == "diagnostic-étoile-42"
                    data["home_states"].append(home)
                    for step, advanced in ((0, False), (1, False), (1, True), (2, False)):
                        window.set_advanced_mode(advanced)
                        window.step = step
                        window.refresh_navigation()
                        window.resize(width, height)
                        window.show()
                        app.processEvents()
                        action = window.create_button if step == 2 else window.next_button
                        assert action.isVisible() and action.isEnabled()
                        assert window.rect().contains(action.mapTo(window, action.rect().center()))
                        assert window.language_combo.isVisible()
                        assert window.settings.height() > 0
                        assert window.source.text() == ""
                        assert window.current_options() == recommended_preset()
                        state = {"language": language, "qt_locale": window.locale().name(),
                                 "qt_translation_loaded": window._qt_translator is not None,
                                 "width": width, "height": height,
                                 "step": step + 1, "advanced": advanced, "action_accessible": True}
                        if screenshots:
                            name = f"{report.stem}-{language}-{width}-step{step+1}-{'advanced' if advanced else 'simple'}.png"
                            path = report.parent / name
                            if path.exists():
                                raise FileExistsError(path)
                            assert capture(window, path)
                            state["screenshot"] = name
                        data["states"].append(state)
                    for kind, selected in (("species_set", (1, 133)), ("type_set", (10, 17))):
                        dialog = ExclusionDialog(kind, selected, language, window.text, window)
                        dialog.show()
                        app.processEvents()
                        assert dialog.value() == selected
                        assert dialog.items.count() == (386 if kind == "species_set" else 18)
                        assert dialog.buttons.isVisible() and dialog.search.isVisible()
                        state = {"language": language, "width": width, "kind": kind, "selection_retained": True}
                        if screenshots:
                            name = f"{report.stem}-{language}-{width}-{kind}.png"
                            path = report.parent / name
                            if path.exists():
                                raise FileExistsError(path)
                            assert capture(dialog, path)
                            state["screenshot"] = name
                        data["exclusion_states"].append(state)
                        dialog.close()
                        dialog.deleteLater()
                    window.step = 1
                    window.set_advanced_mode(True)
                    window.refresh_navigation()
                    window.rule_nav.setCurrentRow(window.rule_nav.count() - 1)
                    for enabled, seeded, chance in ((False, True, 1), (True, True, 0),
                                                     (True, True, 1), (True, False, 1), (True, True, 100)):
                        window.set_options(replace(Options.recommended(), custom_shinies=enabled,
                                                   seeded_shinies=seeded, shiny_chance_percent=chance))
                        app.processEvents()
                        app.processEvents()
                        window.keep_rule_visible()
                        rate = window.rule_fields["shiny_chance_percent"]
                        assert rate.isVisible() and rate.isEnabled() == enabled
                        assert rate.value() == chance
                        seed_switch = window.rule_checks["seeded_shinies"]
                        assert not seed_switch.isVisible() and not seed_switch.isEnabled()
                        assert not enabled or window.current_options().seeded_shinies
                        if window.rule_nav.isVisible():
                            selected = window.rule_nav.visualItemRect(window.rule_nav.currentItem())
                            assert selected.top() >= 0 and selected.bottom() <= window.rule_nav.viewport().height()
                        else:
                            assert window.category_selector.isVisible()
                            assert window.category_selector.currentIndex() == window.rule_nav.currentRow()
                        assert window.next_button.isVisible() and window.next_button.isEnabled()
                        state = {"language": language, "width": width, "height": height,
                                 "enabled": enabled, "seeded": window.current_options().seeded_shinies,
                                 "legacy_requested_seeded": seeded, "percent": chance,
                                 "rate_accessible": True, "seed_switch_removed": True}
                        if screenshots:
                            name = f"{report.stem}-{language}-{width}-shiny-{'on' if enabled else 'off'}-{'seeded' if seeded else 'runtime'}-{chance}.png"
                            path = report.parent / name
                            if path.exists():
                                raise FileExistsError(path)
                            assert capture(window, path)
                            state["screenshot"] = name
                        data["shiny_states"].append(state)
                    # Synthetic layout fixture only; diagnostics never opens a ROM.
                    sample = dict(national_dex=1, name_fr="BULBIZARRE", name_en="BULBASAUR",
                                  name_de="BISASAM", name_es="BULBASAUR", name_it="BULBASAUR")
                    row = dict(sample, species=1, original=sample, shiny=True, portrait_png=b"")
                    window.set_advanced_mode(False)
                    for policy, chance in (("always", 100), ("seeded", 1)):
                        window.set_options(replace(Options.recommended(), custom_shinies=True,
                                                   seeded_shinies=True, shiny_chance_percent=chance))
                        window.preview_key = window.preview_configuration()
                        window.preview_result = {"shiny_policy": policy,
                            "starters": [dict(row, key=key, level=level, shiny=policy == "always" or key == "umbreon")
                                         for key, level in (("umbreon", 26), ("espeon", 25))],
                            "shadows": [dict(row, shadow_id=index, shiny=policy == "always" or index % 2 == 0)
                                        for index in range(1, 49)],
                            "gifts": [dict(row, level=10, event=index >= 2, shiny=policy == "always" or index % 2 == 0)
                                      for index in range(4)]}
                        window.render_preview()
                        window.workspace_tabs.setCurrentIndex(1)
                        window.preview_tabs.setCurrentIndex(0)
                        app.processEvents()
                        app.processEvents()
                        assert not isinstance(window.settings.widget(1), QScrollArea)
                        viewport = window.preview_pages.currentWidget().viewport()
                        for portrait in window.portraits.values():
                            position = portrait.mapTo(viewport, portrait.rect().topLeft())
                            assert viewport.rect().contains(position)
                            assert viewport.rect().contains(position + portrait.rect().bottomRight())
                        window.preview_tabs.setCurrentIndex(1)
                        app.processEvents()
                        assert window.preview_thread is None
                        assert window.encounters_tree.topLevelItemCount() == 48
                        assert window.encounters_tree.viewport().height() >= 46
                        window.preview_search.setText("no-match-998877")
                        assert window.preview_count.text() == window.text("Aucun résultat")
                        window.preview_search.clear()
                        window.preview_tabs.setCurrentIndex(2)
                        assert window.encounters_tree.topLevelItemCount() == 4
                        assert window.status.text() == window.text("Les conditions d’obtention sont indiquées pour chaque cadeau.")
                        window.preview_tabs.setCurrentIndex(1)
                        assert window.preview_shiny_status.text() == window.text(
                            "★ 100 % : starters chromatiques garantis." if policy == "always"
                            else "Statuts chromatiques fixés par la seed.")
                        if policy == "seeded":
                            ordinary = window.preview_species_name(row)
                            assert window.preview_names["espeon"].text() == window.text(
                                "{name} · Niv. {level}", name=ordinary, level=25)
                            assert window.encounters_tree.topLevelItem(0).text(1) == ordinary
                            assert "★" in window.encounters_tree.topLevelItem(1).text(1)
                        state = {"language": language, "width": width, "height": height,
                                 "synthetic_fixture": True, "shadows": 48, "gifts": 4,
                                 "shiny_policy": policy, "shiny_status_visible": True,
                                 "shiny_guarantee_visible": policy == "always",
                                 "seeded_statuses_visible": policy == "seeded"}
                        if screenshots:
                            app.processEvents()
                            name = f"{report.stem}-{language}-{width}-encounters-{policy}.png"
                            path = report.parent / name
                            if path.exists():
                                raise FileExistsError(path)
                            assert capture(window, path)
                            state["screenshot"] = name
                        data["preview_states"].append(state)
                    window.workspace_tabs.setCurrentIndex(0)
                    # Presentation-only consolidation fixture: never calls the
                    # engine, opens a ROM or reveals a random encounter.
                    custom = replace(Options.recommended(), starter_umbreon_species=94,
                        starter_espeon_species=208, experience_multiplier=2,
                        custom_shinies=True, shiny_chance_percent=12.5)
                    window.set_advanced_mode(True)
                    window.set_options(custom)
                    window.rule_search.setText("shiny")
                    app.processEvents()
                    app.processEvents()
                    assert window.rule_content.currentIndex() == 1
                    assert window.rule_results.count() >= 3
                    assert window.rule_results.viewport().height() >= 60
                    assert window.rule_search.width() >= 120
                    assert window.current_options() == custom
                    assert not window.rule_reset.isEnabled()
                    state = {"language": language, "width": width, "height": height,
                        "synthetic_fixture": True, "settings_search": True,
                        "search_results_viewport_height": window.rule_results.viewport().height(),
                        "source_and_rng_used": False}
                    if screenshots:
                        name = f"{report.stem}-{language}-{width}-settings-search.png"
                        path = report.parent / name
                        if path.exists():
                            raise FileExistsError(path)
                        if capture(window, path, retained=False):
                            state["search_screenshot"] = name
                        else:
                            state["rendered_without_png"] = True
                    selected = next(window.rule_results.item(index) for index in range(window.rule_results.count())
                        if window.rule_results.item(index).data(Qt.ItemDataRole.UserRole) == "custom_shinies")
                    window.open_rule_result(selected)
                    app.processEvents()
                    app.processEvents()
                    assert window.rule_groups[window.rule_nav.currentRow()] == "Chromatiques"
                    assert window.rule_content.currentIndex() == 0 and window.rule_search.text() == ""
                    assert window.rule_pages.height() >= 46
                    window.reset_rule_category()
                    assert window.current_options() == replace(custom, custom_shinies=True, shiny_chance_percent=5.0)
                    window.step = 2
                    window.refresh_navigation()
                    window.review_toggle.setChecked(False)
                    app.processEvents()
                    app.processEvents()
                    assert SPECIES_NAMES[language][94] in window.review_details.text()
                    assert SPECIES_NAMES[language][208] in window.review_details.text()
                    assert window.review_details.isHidden()
                    assert window.rect().contains(window.create_button.mapTo(window, window.create_button.rect().center()))
                    state.update(category_reset_isolated=True, manual_choices_visible=True,
                        effective_review=True, active_form_viewport_height=window.rule_pages.height())
                    if screenshots:
                        name = f"{report.stem}-{language}-{width}-effective-review.png"
                        path = report.parent / name
                        if path.exists():
                            raise FileExistsError(path)
                        if capture(window, path, retained=False):
                            state["review_screenshot"] = name
                        else:
                            state["rendered_without_png"] = True
                    window.set_options(replace(Options.none(), starter_umbreon_species=94,
                        starter_espeon_species=208, shiny_chance_percent=100))
                    assert window.text("Copie à l’identique : aucune donnée du jeu ne sera modifiée.") in window.review_details.text()
                    assert not window.review_toggle.isHidden()
                    state["inactive_remembered_values_ignored"] = True
                    data["consolidation_states"].append(state)
                    window.step = 1
                    window.refresh_navigation()
                    window.set_options(recommended_preset())
                    window.rule_nav.setCurrentRow(0)
            if not sounds:
                assert not window.sound_toggle.isEnabled()
            if not data["music_available"]:
                assert not window.music_toggle.isEnabled()
            from .ui_game_folder import PackDialog
            from .ui_theme import theme_palette
            from PySide6.QtGui import QPalette
            data["pack_manager_states"] = []
            for language in LANGUAGES:
                window.language_combo.setCurrentIndex(window.language_combo.findData(language))
                dialog = PackDialog(window)
                try:
                    dialog.show()
                    app.processEvents()
                    assert dialog.thread is None and dialog.done.isEnabled()
                    expected_palette = theme_palette(dialog.palette(), home=True)
                    assert dialog.palette().color(QPalette.ColorRole.Base) == expected_palette.color(QPalette.ColorRole.Base)
                    state = {"language": language, "width": dialog.width(), "height": dialog.height(),
                             "private_empty_cache": True, "network_install_started": False}
                    if screenshots:
                        state["screenshot"] = f"hd-packs-{language}.png"
                        assert capture(dialog, report.parent / state["screenshot"])
                    data["pack_manager_states"].append(state)
                finally:
                    dialog.close()
                    dialog.deleteLater()
                    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            data["automatic_update_check"] = {
                "closed": window.update_checker.closed,
                "started": window.update_checker.started,
                "reply_created": window.update_checker.reply is not None,
                "timer_active": window.update_checker.timeout.isActive(),
            }
            assert data["automatic_update_check"] == {
                "closed": True, "started": False, "reply_created": False, "timer_active": False}
        finally:
            window.close()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    data["run_management_check"] = check_run_management(report.parent)
    data["successful"] = True
    return data


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--screenshots", action="store_true")
    parser.add_argument("--screenshot-scope", choices=("all", "smoke"), default="all",
                        help="Keep every PNG, or only the CI smoke evidence while still rendering every state")
    parser.add_argument("--launcher-upgrade-check", action="store_true",
                        help="Also upgrade disposable synthetic runs, including a private runtime copy")
    args = parser.parse_args(arguments)
    # Exclusive creation protects previous evidence. Use a new writable directory.
    try:
        stream = args.report.open("x", encoding="utf-8")
    except OSError:
        # Windowed executables have no terminal. Refuse the path without an
        # unhandled traceback dialog that would block unattended checks.
        return 2
    with stream:
        callback_errors = []
        previous_hook = sys.excepthook

        def record_callback_error(kind, error, _traceback):
            callback_errors.append(f"{kind.__name__}: {error}")

        # Qt reports exceptions raised by Python slots through excepthook.
        # They do not propagate out of processEvents(), even when a captured
        # screen still looks valid. A frozen-app check must fail on them too.
        sys.excepthook = record_callback_error
        try:
            result = run_checks(args.report, screenshots=args.screenshots, screenshot_scope=args.screenshot_scope)
            if args.launcher_upgrade_check:
                result["launcher_upgrade_check"] = check_launcher_upgrades(args.report.parent)
            if callback_errors:
                raise RuntimeError("UI callbacks failed: " + "; ".join(callback_errors))
        except Exception as error:
            json.dump({"successful": False, "error": f"{type(error).__name__}: {error}"}, stream, indent=2)
            stream.write("\n")
            return 1
        finally:
            sys.excepthook = previous_hook
        result["unhandled_event_errors"] = callback_errors
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
