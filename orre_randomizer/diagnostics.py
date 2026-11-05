"""Offline packaged-app check. Never opens a ROM or personal preferences."""
from __future__ import annotations
import argparse
from dataclasses import replace
import json
import os
from pathlib import Path
import sys
import tempfile


def run_checks(report: Path, *, screenshots: bool = False) -> dict:
    from PySide6.QtCore import QCoreApplication, QEvent, QSettings, Qt, qVersion
    from PySide6.QtGui import QFont, QFontDatabase
    from PySide6.QtWidgets import QApplication, QScrollArea
    from . import __version__, native_codec
    from .engine.analyze_game import decompress_lzss_python
    from .engine.rebuild_iso import compress_lzss_python
    from .gui import MainWindow, recommended_preset
    from .i18n import LANGUAGES
    from .options import Options
    from .locales.selection_names import SPECIES_NAMES
    from .ui_exclusions import ExclusionDialog
    from .resources import application_icon, application_logo, interface_assets, menu_icon, music_track

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
            "music_available": music_track() is not None,
            "game_cursor_available": menu_icon() is not None,
            "application_icon_available": application_icon() is not None,
            "application_logo_available": application_logo() is not None,
            "rom_opened": False, "personal_preferences_opened": False,
            "home_states": [], "states": [], "exclusion_states": [], "shiny_states": [], "preview_states": [],
            "consolidation_states": [], "xd_states": [], "xd_parity_states": []}
    with tempfile.TemporaryDirectory(prefix="diagnostic-prefs-", dir=report.parent) as folder:
        window = MainWindow(settings=QSettings(str(Path(folder)/"preferences.ini"), QSettings.Format.IniFormat),
                            system_languages=["fr-FR"])
        try:
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
                    window.show()
                    app.processEvents()
                    assert window.open_colosseum.isVisible() and window.open_colosseum.isEnabled()
                    assert window.rect().contains(window.open_colosseum.mapTo(window, window.open_colosseum.rect().center()))
                    assert not window.next_button.isVisible()
                    home = {"language": language, "width": width, "height": height}
                    if screenshots:
                        home["screenshot"] = f"home-{language}-{width}.png"
                        assert window.grab().save(str(report.parent / home["screenshot"]))
                    window.open_xd.click()
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
                            assert window.grab().save(str(report.parent / state["screenshot"]))
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
                            state["screenshot"] = f"xd-parity-{language}-{width}-category{xd.rule_groups.index(category)}.png"
                            assert window.grab().save(str(report.parent / state["screenshot"]))
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
                            state["screenshot"] = f"xd-parity-{language}-{width}-tab{tab}.png"
                            assert window.grab().save(str(report.parent / state["screenshot"]))
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
                            assert window.grab().save(str(path))
                            state["screenshot"] = name
                        data["states"].append(state)
                    for kind, selected in (("species_set", (1, 133)), ("type_set", (10, 17))):
                        dialog = ExclusionDialog(kind, selected, language, window.text, window)
                        dialog.show()
                        app.processEvents()
                        assert dialog.value() == selected
                        assert dialog.items.count() == (386 if kind == "species_set" else 17)
                        assert dialog.buttons.isVisible() and dialog.search.isVisible()
                        state = {"language": language, "width": width, "kind": kind, "selection_retained": True}
                        if screenshots:
                            name = f"{report.stem}-{language}-{width}-{kind}.png"
                            path = report.parent / name
                            if path.exists():
                                raise FileExistsError(path)
                            assert dialog.grab().save(str(path))
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
                        assert seed_switch.isVisible() and seed_switch.isEnabled() == enabled
                        assert seed_switch.isChecked() == seeded
                        if window.rule_nav.isVisible():
                            selected = window.rule_nav.visualItemRect(window.rule_nav.currentItem())
                            assert selected.top() >= 0 and selected.bottom() <= window.rule_nav.viewport().height()
                        else:
                            assert window.category_selector.isVisible()
                            assert window.category_selector.currentIndex() == window.rule_nav.currentRow()
                        assert window.next_button.isVisible() and window.next_button.isEnabled()
                        state = {"language": language, "width": width, "height": height,
                                 "enabled": enabled, "seeded": seeded, "percent": chance,
                                 "rate_accessible": True, "seed_switch_accessible": True}
                        if screenshots:
                            name = f"{report.stem}-{language}-{width}-shiny-{'on' if enabled else 'off'}-{'seeded' if seeded else 'runtime'}-{chance}.png"
                            path = report.parent / name
                            if path.exists():
                                raise FileExistsError(path)
                            assert window.grab().save(str(path))
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
                        assert window.status.text() == window.text("Adelbert remet ces cadeaux après le nombre de purifications choisi.")
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
                            assert window.grab().save(str(path))
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
                        assert window.grab().save(str(path))
                        state["search_screenshot"] = name
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
                        assert window.grab().save(str(path))
                        state["review_screenshot"] = name
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
        finally:
            window.close()
            window.deleteLater()
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    data["successful"] = True
    return data


def main(arguments=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    parser.add_argument("--screenshots", action="store_true")
    args = parser.parse_args(arguments)
    # Exclusive creation protects previous evidence. Use a new writable directory.
    with args.report.open("x", encoding="utf-8") as stream:
        try:
            result = run_checks(args.report, screenshots=args.screenshots)
        except Exception as error:
            json.dump({"successful": False, "error": f"{type(error).__name__}: {error}"}, stream, indent=2)
            stream.write("\n")
            return 1
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
