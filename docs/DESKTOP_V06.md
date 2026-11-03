# Multilingual interface — v0.6

The v0.6.1 reproduces the French and English texts: shorter wording, common vocabulary in the
headings, aids focused on the effect of options and error messages oriented towards the following
action. The 59 settings and their values remain unchanged. The profiles v0.5, v0.6 and v0.6.1 remain
accepted. The [Drafting Conventions](INTERFACE_COPY.md) describe the vocabulary chosen.

The interface follows the language of the system at the first launch: French or English, with a
back-up on English if no proposed system language is supported. **System**, **French** and
**English** The names of the languages remain recognizable in their own language.

The change immediately applies to the 59 parameters, fourteen categories, descriptions, accessible
aids, choices, actions, titles and filters of dialogs, recoverable errors and progress messages. The
number of fields follows the chosen locale. The native controls of file selectors remain those of
the system. Their buttons can therefore follow the language of Windows.

The form remains intact: seed, paths, format, parameters, active category, RVZ pane and progression.
The choice is also available during a creation. The status and steps already displayed are
retranslated from their source messages.

## Local preference and reproduction

Only the `interface/language` key is stored in a QSettings user INI file, organization and
application `ColosseumRandomizer`. The value is `system`, `fr`, or `en`. No ROM path nor seed is
saved in this preference. An illegible or unknown choice comes back to the system. An impossible
write is reported in the interface without preventing the choice for the session.

The language is not part of the 59 rules, shared profiles or arguments of the engine. It does not
change the language of the ROM or its hashes. The engine remains `starter-shadow-boss-rules-v7`. The
v0.6 accepts the profiles v0.5 and v0.6, with engine version control, schema, values and original
footprint. A v0.5 cannot import a profile exported by a newer version.

## Implementation and control

The English catalogue is a Python module included offline in the sources and executable. French is
the source language. The set messages keep their parameters separate: paths and seeds are never
translated. The raw technical details of a system error or format remain diagnostics in their
original language, preceded by a translated interface message.

The detection uses the ordered IU languages of
[QLocale](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QLocale.html#PySide6.QtCore.QLocale.uiLanguages),
and preference uses [QSettings](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QSettings.html). The
suite passes **211 tests Python et trois tests Rust**. It includes.

- system languages with regions and variants, priority and withdrawal;
- cover of wordings, descriptions, choices and formatting parameters;
- manual choice stored, then back to the system;
- maintenance of rules, Unicode seeds, paths containing braces and profiles;
- change during a real Qt worker in the background, without restarting it;
- errors, cancellation, success and titles/filters of the selectors;
- actions accessible in a window of 680 × 540 in French and English;
- compatibility and detection of falsification of profiles v0.5.

An end-of-work race observed during these checks has also been corrected: the native thread
completes its cleaning before the interface releases its reference and reactivates the settings. The
test windows are explicitly destroyed on the thread UI to isolate their Qt objects.

The validation limits of the game remain those of [report
Dolphin](DOLPHIN_VALIDATION_2026-10-31.md). This evolution of the interface does not add any new
randomization settings.

## Windows executable test

The reconstructed version was opened under Windows in French system mode, changed to English, closed
and re-launched: the English choice is found. The import of the reference profile v0.5 succeeds in
this English interface. A complete creation takes **11,30 s**. The result, the paths and the seed
remain displayed when returning to French.

The generated ISO has been reprinted independently:
`648cc8c0744c87fce40a7d4dbdd3f6f95f8df29bc48415ee33507cb5d1894b35`, identical to the reference v0.5
for the same seed and the same rules. The source remains intact and all output bytes are checked by
the engine. Therefore, the language of the interface does not change this reference result.

The audit after this trial finds the source images, the 2,011 files of the game, the 2,691 files of
the Dolphin installation and the 46 files of the personal Dolphin profile unchanged. Reports,
captures and test images remain private under `build/`, out of distribution.
