# Office Application v0.1 — Local Validation

Windows session of 30 October 2026. Python 3.12.2, PySide6/Qt 6.11.2, PyInstaller 6.22.3. The local
preparation does not publish anything on the Internet.

## Engine and safety

58 unit tests and local integrations pass, including previous engine tests. Qt tests cover default
rules, recoverable errors and a 680 × 540 window. Pipeline tests cover existing outputs, source
aliases, UTF-8 seeds, conversion failures, cancellation and detection of a corrupt byte outside
modified ranges. Without the local dump, game integration tests are explicitly ignored.

ISO → ISO with the test history and three enabled options.

```
source  1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9
sortie  e37dae3666fae8323cb9f9c55c679c170053c96430d0d22fe2c6057e3aeea941
```

The output is identical byte to the v3 already tested under Dolphin. The 1,459,978,240 bytes are
compared to the source plus the exact replacements expected. The hash source is recalculated at the
end. No extraction `game/` is required.

## Real Windows Track

The Qt application was opened and controlled with the native file selector on the blank local RVZ. A
separate RVZ output was created with the same engine and all options. The window remains reactive
during the worker and displays the success and path at 100%. Observed processing time: 34.7 seconds.

```
RVZ source  e7f23723e6dc28dd1660ed38a993102f9b0980b669a3c4c69f9e8b483ac4712b
RVZ sortie  65c80f187615a934fe6167d7c6e3795f807ee1b4f3fd61c2e0782d304ca22952
ISO sortie  e37dae3666fae8323cb9f9c55c679c170053c96430d0d22fe2c6057e3aeea941
```

The RVZ produced has been recompressed and its ISO compared by SHA-256 to the ISO verified before
compression. The RVZ source is intact. Conversions use a temporary DolphinTool profile, without data
deletion option.

## Distribution and limits

The build produces a folder with replaceable DLL Qt, MIT source code, licenses and exact sources of
Qt libraries. The project sources are selected by positive list, excluding ROM, extracted data, game
captures, backups and emulators. Archive and final steps to start binary are controlled locally
before delivery.

The fixed standalone binary then created a complete ISO from the blank ROM, with the output SHA-256
`e37dae3666fae8323cb9f9c55c679c170053c96430d0d22fe2c6057e3aeea941`. The interface displays 100%
success and the source is intact. The build cleans up its PATH to prevent the inclusion of
incompatible DLL ICU from other desktop tools. Qt plugins are limited to the components needed for
this interface. The virtual keyboard, QML, PDF and unused image plugins are excluded.

The source ZIP has been decompressed into a temporary folder without `game/`: 58 tests are
successfully completed, including 4 integrations ignored due to lack of ROMs. Both ZIPs pass
integrity, fingerprints and absence of ROMs or emulators. An installable Python wheel has also been
built without including any data from the game. Local evidence is stored in `build/desktop-*`.

Only the PAL GC6P01 revision 0 and its exact hash are supported. The application has not been tested
on another PC, macOS or Linux. Creating an image and technical invariants do not constitute a
validation of the balancing or a complete part. Previous Dolphin trials are in the v3 report.
