# Application v0.2: independent rules and acceleration Rust

Version of October 30, 2026, Windows x64. The selection engine becomes `selective-story-rules-v4`.
The recommended preset keeps exactly the v3 data for the same seed.

## The 16 Booleans

| Groupe | Independent parameters |
| --- | --- |
| Trainers | `randomize_trainers`, `randomize_shadows`, `unique_shadows` |
| Starters | `starter_umbreon`, `starter_espeon` |
| Gifts and awards | `gift_plusle`, `gift_hooh`, `event_celebi`, `event_pikachu` |
| Evolutions | `evolve_trade`, `evolve_trade_items`, `evolve_coquiperl`, `evolve_day_night`, `evolve_beauty` |
| Shops | `stones_phenac`, `stones_pyrite` |

The 16 are enabled by default. Both presets restore the recommendations or disable everything. The
option of single families is turned off if the dark ones are not randomized. Each starter/gift
routine has its own derived seed. Deactivating a Pokémon does not change the draws of others.

The evolution categories modify 4, 6, 2, 2 and 1 roads respectively, keeping the targets and the
graph of the families. A setting that activates the new changes by stone without offering a shop is
refused before beginning, to preserve their accessibility. The original stock is kept and each shop
can be activated independently. The price of the Moon Stone is adjusted to 2,100 when stones are
proposed.

In CLI: `--starter-umbreon` / `--no-starter-umbreon`, and similarly for each parameter, with dashes
instead of underscores. The old shortcuts `--keep-specials`, `--keep-evolutions` and
`--allow-shadow-family-duplicates` remain accepted. JSON ratios retain the sixteen actual values.

## Measured performance

The profiling of an archive has attributed almost all the time to LZSS codecs. The Rust module
therefore implements encoding and decoding. The interface remains Qt and the Python orchestration.
It does not depend on any external crates and is built offline. The Python reference codec remains
available without Rust.

Sequential local measure of the reconstruction of the six original archives, including decoding,
encoding and controls.

| Traitement | Python | Rust |
| --- | ---: | ---: |
| Six archives | 23,234 s | 0,568 s |
| Gain on this step | | ×40,91 |

The six archives produced are identical byte for byte between the two implementations. Times are
observations on this post. The gain does not apply to DolphinTool disk, hash or conversion copies.

Complete ISO creation with the test history and all the rules enabled.

| Step | Temps |
| --- | ---: |
| Source validation | 0,922 s |
| Transformations and archives | 1,812 s |
| Copying and writing patches | 1,281 s |
| Full ISO verification | 1,953 s |
| Last source control | 0,969 s |
| Total observed | 6,94 s |

SHA-256 output: `e37dae3666fae8323cb9f9c55c679c170053c96430d0d22fe2c6057e3aeea941`. It corresponds
exactly to the ISO v3 already tested under Dolphin. The source is intact. The measurements are
reproducible with `scripts/benchmark_codec.py` (local dumping required) and the times per step now
appear in each report.

## Validation

72 Python tests and 3 Rust tests pass. The tests cross the Python and Rust codes, including
overlapping references, 4Kio buffer towers, random data and misformed flows. Rules tests separately
check the six starters/gifts, the five evolution categories, trainers/Shadow Pokémon and both stores.
The empty preset keeps exactly the original data. The recommended preset reproduces the v3.

Additional complete tests: ISO copy with all the deactivated rules identical to the original. Custom
RVZ creation with verification of its return to ISO, only 108 obscure appearances changed, 11 roads
adapted and stones to Pyrite Town alone. Since the EXE, uncheck Umbreon while keeping Espeon
activated has produced an ISO in 6.97 s. Reading the output DOL: Umbreon original (197), second
starter Slowbro (80). The report keeps the sixteen booleans well and confirms the Rust codec and the
intact source. The five Qt tests also pass after adjusting the initial size to the screen.

The originals, the old ISOs and the old version ZIPs are retained. The PAL GC6P01 revision 0
perimeter and the validation limits of the scenario remain those of the v0.1. No dump, game
resource, emulator or backup is distributed.
