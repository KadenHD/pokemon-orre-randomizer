# Interface v0.7

The composition C offers a ROM assistant → Settings → Create, with the green panels, silver frames
and cyan selections of Colosseum.

The Simple mode offers Pokémon + moves, Pokémon only and Unchanged copy. Each choice
describes what changes. The Advanced mode displays the 60 parameters in 14 categories. Seed and
profiles remain accessible in a drawer. The choices are kept when changing mode or language. The
navigation and creation actions remain visible at 680 × 540.

The `colosseum_randomizer/assets/game/` pack contains the background, logo, portraits, a Poké Ball
cursor, three menu effects and the title theme. It is embedded in the executable and in the sources
of this local construction. The start of the interface reads no ROM and does not depend on a user
cache.

The images are decoded from native textures. The three effects are samples of the game: moving,
validating and returning, with a 25% gain. The theme is a Dolphin DSP rendering identified by the
score and the repeat of the signal: 99.25 seconds, resampled at 44,1 kHz, 15% gain, 20 Hz high-pass
filter and short melts. No MusyX player or Dolphin player is necessary to listen to the song in the
application. The beginning and the musical end were estimated by correlation. The frames exported
and their fingerprints are recorded.

Music and sounds are controlled separately and are enabled at the first launch if available.
Preferences are stored outside party profiles. On Windows, two distinct native players allow clicks
not to cut the music. No volume setting of the ns system is changed.

The "Space Stone Names" setting adds eleven spaces in native compact names in French, English,
Italian and Spanish. German compounds remain unchanged. The five languages of the game are retained.
The correction deduplicates twelve texts already identical to free space: size of the REL, table
positions, relocations and all other text IDs are preserved.

The profiles v0.5/v0.6 are validated with their original footprint and then imported with this new
setting disabled. A check reproduces exactly the ISO of the control profile v0.5. The choice Copy to
identical also disables the correction of names.

The ISO control with the recommended settings has SHA-256 footprint:
`9bb9f44aed82a12ae9e8f2cecf461c14d38074f9aaedc2c2687c5356d1ba1317`. Each creation remains fully
verified and refuses an existing destination. The previous scenario controls are recorded in the
Dolphin report. They do not constitute a new complete game played with this version.

Local evidence in `build/v07-qa/`: interface captures, native audio tests, compatibility of old
profiles, creation report and conservation audit. The sources and transformations of embedded
resources are recorded in the manifest `colosseum_randomizer/assets/game/provenance.json`.
