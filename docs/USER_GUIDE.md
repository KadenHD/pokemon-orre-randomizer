# User guide

## Start a run

Both games use **ROM → Settings → Create**. Supply an unmodified
[supported original](COMPATIBILITY.md). Choose a new output path: existing
files are never replaced. Start a new game in Dolphin to match the preview;
the app never imports or edits saves.

**Pokémon + moves** and **Pokémon only** share the same balance policy: similar
strength, family diversity, base starters from three-stage families and a
custom 5% shiny chance where supported. Only move, TM and item randomization
differ. Levels, EXP, purification and catch-rate multipliers stay at ×1.
**Unchanged copy** changes no game data. Switching Simple/Advanced preserves
your choices; selecting a preset replaces them. Category resets use that game's
Pokémon + moves defaults. Imported profiles retain their saved values.

## Seeds, previews and profiles

Seeds are exact UTF-8 text, including spaces and case. The preview calculates
encounters from the same patch plan as creation. A changed seed, source or
setting makes it stale. The animation ends on the computed result without
another random draw. The lists show starters, Shadow Pokémon, gifts and, in XD,
Poké Spots. A single click opens a Pokémon sheet. A small red star marks a shiny;
a question mark represents a replacement not yet calculated.

**Profiles**, beside language and audio, imports/exports portable JSON settings.
Profiles belong to one game and contain no source/output paths. Reports can also
restore settings but may contain local paths: review them before sharing.
Fixed choices, exclusions and strict filters take priority over best-effort
cross-group family diversity. Remaining duplicates appear in the report.

## Starters and evolutions

Change the stage, disable the three-stage-family filter or select a species
manually in Advanced. Only routes present in the generation-III game count.
Colosseum retains starting levels 26 and 25; XD retains level 10. Starting EXP
follows the replacement's growth curve. Colosseum's pair rules compare final
strength, require distinct families and complementary types. XD has one starter.

Manual selections bypass individual stage/power filters; exclusions and pair
constraints still apply. Impossible combinations produce an explanation.
Accessible-evolution rules adapt routes that cannot normally be completed in
that game. For example, Colosseum's trade-with-item adaptation changes Onix →
Steelix to leveling from level 40. Evolution stones are sold in Phenac and Pyrite
in Colosseum, and Gateon Port in XD. XD retains native Eevee shard routes.
The Pokémon sheet shows the actual final requirements and evolution portraits,
including shiny variants. See [starter rules](STARTER_STAGES.md).

## Colosseum rewards

Plusle, Ho-Oh, Pikachu and Celebi have separate species controls. **Make event
gifts obtainable** adds Eagun's purification rewards at the Relic Stone:
Pikachu's gift after 10 purifications at level 30, Celebi's after 25 at level 45
by default. Each threshold and level can be adjusted independently.

Eagun becomes available after the purification introduction and its follow-up
after the Skrub encounter, avoiding duplication during story scenes. Each reward
is available once per save. Changing a gift's species does not remove its other
requirements. Dialogue follows the ROM language.

## XD encounters and trades

Shadow Lugia remains protected. Both randomizing presets replace tutorial
Teddiursa by default. Its advanced control can retain the original species.
The tutorial replacement retains level 11 and the original catch rate; its
dialogue names the replacement. Both presets also replace Hordel's Shadow
Togepi; its separate advanced control can retain the original species.
The replacement is a base form from a two-stage family with an accessible
evolution, so Hordel accepts it after purification either before or after
evolving. Imported profiles retain their saved choices.

Both randomizing presets draw the nine regular Poké Spot encounters from XD's
full supported generation-I–III Pokédex. Generation, species/type exclusions,
legendary restrictions and similar-strength matching still apply. The three
rare slots use different species, so Duking has three distinct, obtainable
requests. Each location has three different species; all nine are different
when the pool is large enough. Levels and encounter rates remain native.

Duking's species checks, dialogue and the gifts preview follow those rare slots,
including when gift rewards themselves are kept unchanged. Dialogue uses the
ROM's own languages. Disable **Draw from the full Pokédex** in Advanced to keep
the original three-species shuffle. Profiles from earlier engines retain that
older shuffle when imported. At least three allowed species are needed for the
full draw. The two special encounters and Mt. Battle prize requirements retain
their native rules.

## Advanced rules

Search settings in the current language by label, explanation, category or
choice. Similar-strength matching uses final species stats. Move rules can
require damaging and same-type attacks, prevent duplicates, and exclude
self-destruct or one-hit knockout moves. Required Shadow markers and scripted
data are protected. Types, abilities, stats, held items, TMs, treasure and shop
stock can be adjusted separately. Key items and scripted rewards are protected.

Opponent levels use a global multiplier or original-level bands of 1–35, 36–50
and 51–100; these are not story chapters. EXP and purification controls affect
native calculations and do not skip purification's story requirements.
See [validation](VALIDATION.md) for measured results.

## Shinies

The presets use a seeded 5% probability per supported encounter key, not a quota
on the preview. Nature, IVs and the full game RNG remain native. Colosseum
supports starter, gift, trainer and Shadow decisions, plus an optional unlinked
mode that leaves the draw to the game. XD customization covers its starter,
ordinary gifts and, with **Apply the rate to Shadow Pokémon**, all 83 Shadow
IDs. Both randomizing presets enable this unlock. The seed fixes each Shadow's
status, which is retained after capture and purification. Disable the separate
Shadow option to keep XD's native lock. Wild Poké Spots keep native odds.
Previously generated Shadow Pokémon retain their saved PID; use a new game
for the preview to match every encounter. Shadow Lugia keeps its special dark
appearance until purification.
Disabling customization preserves native rules. The original generation-III
probability is 1/8192, approximately 0.0122%, where that game's encounter rules
permit shinies. See [shiny behavior](SHINIES.md).

## Outputs and storage

Creation writes the verified image, a JSON report and an offline HTML journal
in the interface language. Keep the report, source identity, seed and engine
version for reproduction. RVZ bytes also depend on DolphinTool's version.

Allow roughly 1.5 GiB for ISO → ISO, 2.8 GiB for RVZ → ISO and up to 5.6 GiB
for RVZ → RVZ. An RVZ preview can retain a decoded ISO in temporary storage
until the window closes. Completion, cancellation and handled errors remove
owned temporary files. A forced stop can leave `.orre-*` directories; inspect
their location before removing them.

The CLI retains its existing defaults: use a profile for exact desktop settings.
Run `python -m orre_randomizer.cli --help`; add `--game xd` for XD profiles,
`--dolphin-tool` for RVZ and `--journal-language en` for an English journal.
