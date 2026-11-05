"""Application preferences, including the migration from the Colosseum app."""
from PySide6.QtCore import QSettings


def application_preferences():
    preferences = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                            "OrreRandomizer", "OrreRandomizer")
    preferences.setFallbacksEnabled(False)
    migration = "migration/colosseumPreferences"
    if preferences.contains(migration):
        return preferences

    legacy = QSettings(QSettings.Format.IniFormat, QSettings.Scope.UserScope,
                       "ColosseumRandomizer", "ColosseumRandomizer")
    legacy.setFallbacksEnabled(False)
    keys = legacy.allKeys()
    if keys:
        for key in keys:
            if not preferences.contains(key):
                preferences.setValue(key, legacy.value(key))
        preferences.sync()
        if preferences.status() == QSettings.Status.NoError:
            preferences.setValue(migration, True)
            preferences.sync()
    return preferences
