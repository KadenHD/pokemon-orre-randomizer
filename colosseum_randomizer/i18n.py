"""Presentation-only translations. No Qt, global locale or randomizer state.

French source messages also serve as stable translation keys. Message keeps
format parameters separate so paths and seeds are never treated as translatable
text, and an in-flight job can be rendered in a newly selected language.
"""
from __future__ import annotations

from dataclasses import fields

from .options import Options
from .locales import de, en, es, it, ja
from .feature_i18n import TEXTS as FEATURE_TEXTS, OPTION_TEXTS as FEATURE_OPTIONS
from .settings_i18n import TEXTS as SETTINGS_TEXTS

LANGUAGES = {"fr": "Français", "en": "English", "de": "Deutsch",
             "es": "Español", "it": "Italiano", "ja": "日本語"}
DEFAULT_LANGUAGE = "en"
LANGUAGE_PREFERENCES = ("system", *LANGUAGES)


class Message(str):
    """A normal French string carrying the template needed by the desktop UI."""

    def __new__(cls, template: str, **parameters):
        instance = super().__new__(cls, template.format(**parameters) if parameters else template)
        instance.template = template
        instance.parameters = parameters
        return instance


def language_preference(value) -> str:
    return value if isinstance(value, str) and value in LANGUAGE_PREFERENCES else "system"


def resolve_language(preference="system", system_languages=()) -> str:
    preference = language_preference(preference)
    if preference != "system":
        return preference
    for tag in system_languages:
        if isinstance(tag, str):
            language = tag.replace("_", "-").split("-", 1)[0].lower()
            if language in LANGUAGES:
                return language
    return DEFAULT_LANGUAGE


def _catalog(texts, option_texts) -> dict[str, str]:
    catalog = dict(texts)
    for item in fields(Options):
        label, description, *choices = option_texts[item.name]
        catalog[item.metadata["label"]] = label
        catalog[item.metadata["description"]] = description
        if choices:
            for (_, source), translated in zip(item.metadata["choices"], choices[0], strict=True):
                catalog[source] = translated
    return catalog


for code, locale in (("en", en), ("de", de), ("es", es), ("it", it), ("ja", ja)):
    locale.TEXTS.update(FEATURE_TEXTS[code])
    locale.TEXTS.update(SETTINGS_TEXTS[code])
    locale.OPTION_TEXTS.update(FEATURE_OPTIONS[code])

CATALOGS = {code: _catalog(locale.TEXTS, locale.OPTION_TEXTS)
            for code, locale in (("en", en), ("de", de), ("es", es), ("it", it), ("ja", ja))}


def translate(message: str, language: str) -> str:
    template = message.template if isinstance(message, Message) else message
    rendered = CATALOGS.get(language, {}).get(template, template)
    if isinstance(message, Message):
        parameters = {key: translate(value, language) if isinstance(value, Message) else value
                      for key, value in message.parameters.items()}
        return rendered.format(**parameters) if parameters else rendered
    return rendered


def is_translatable(message: str) -> bool:
    template = message.template if isinstance(message, Message) else message
    return template in CATALOGS["en"]
