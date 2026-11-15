# User guide

## Start a run

The home screen checks GitHub once per session for a newer stable release.
In Windows builds, **Update to…** appears below the two games when one is
available. Click it to download, verify, apply the update and restart the app.
The installed edition uses the official setup EXE in silent mode; the portable
edition updates from the official ZIP in its current folder. Existing shortcuts
keep the same target. The check sends no game files, paths, seeds or saves;
offline and unavailable checks stay silent. Source checkouts are updated through Git.

During an update, a centered progress panel replaces the game choices. Other
controls, profile actions, file drops and manual closing are locked. Cancel the
download with **Cancel** or Escape to return to home. Preparation cannot be
cancelled; the app closes automatically when the verified helper is ready to
restart. Cancellation or errors restore your previous controls. ROM creation
and previews must finish first. The updater requires the expected size and GitHub
SHA-256 digest, then verifies the complete download before starting its helper.
Invalid or incomplete downloads are discarded. The portable helper waits for
this exact app process to exit, backs up bundled files, and restores them if
replacement fails. Unmanaged files, ROMs, saves and preferences are preserved.
Temporary download and staging files are removed after the attempt; a small
local diagnostic log remains. Updating starts only after clicking the button.

Both games use **ROM → Settings → Create**. Supply an unmodified
[supported original](COMPATIBILITY.md). Choose a new output path: existing
files are never replaced. Start a new game in Dolphin to match the preview;
the app never imports or edits saves.

**Pokémon + moves** and **Pokémon only** randomize species and abilities, with
family diversity and a custom 5% shiny chance where supported. Every evolution
stage is eligible: starters do not need to be base forms or belong to three-stage
families. Power matching is disabled. Only move, TM and item randomization differ.
The full preset changes held items and ordinary Ball treasures as well; empty
held-item slots remain empty and progression items stay protected.
Both presets keep all Poké Balls already sold in shops. In **Advanced > Shops**,
turn off **Keep original Poké Balls in shops** to include them in shop
randomization. This option does not affect treasure contents. The separate
**Keep original Poké Balls** option protects Balls in both chests and shops;
turn off both safeguards for unrestricted shop randomization.
Colosseum randomizes the nine ordinary cash inventories (indices 0-7 and 9).
The three type-2 shop lists are included; the herbalist, vending machine and
coupon inventories are preserved. XD keeps its eleven supported cash inventories.
Imported older Colosseum profiles retain their original six-shop scope and exact
shop draws. Selecting a fresh preset uses the expanded nine-shop scope.
Treasure contents are fixed when the ROM is created; loading a different image
through an old Dolphin save state can restore data from the previous run. Use
the normal in-game save/load flow when comparing randomized images. See the
[treasure validation notes](reverse-engineering/TREASURE_ITEMS_RUNTIME.md) for
the data audit and representative native pickups.
Moves are drawn without power or type matching. At least one attacking move
is retained, while duplicate moves, self-destruct moves and one-hit KOs are
excluded by default. TM compatibility is randomized without type matching.
These protections can be changed in Advanced.
Custom shiny rates for supported starters, gifts and trainer/Shadow encounters
use the seed in both games. Older unlinked profiles are linked when imported, retaining
their seed and chosen rate. There is no unlink switch. XD's wild Poké Spots use
a separate 5% roll per new encounter by default. Disabling a customization option
retains native behavior for its encounter scope.
Levels, EXP, purification and catch-rate multipliers stay at ×1.
Original legendary Shadow Pokémon keep their species in both presets. Under
**Advanced > Allowed Pokémon**, **Legendary and Mythical Pokémon** is unchecked
by default in both games. Randomized starters, Shadows, gifts and XD's Poké Spots
cannot draw these species unless you enable it. Fixed story encounters and
Colosseum's bonus Lugia are unaffected by this replacement filter. Under
**Advanced → Trainers**, enable **Randomize legendary Shadow Pokémon** to allow
their replacement. XD001 remains protected for XD's story regardless of this
switch. This setting does not control Colosseum's bonus battle.
**Unchanged copy** changes no game data. Switching Simple/Advanced preserves
your choices; selecting a preset replaces them. Category resets use that game's
Pokémon + moves defaults. Imported profiles retain their saved values.

In Colosseum, capturing a trainer's Shadow Pokémon no longer rerolls the unchanged
members of that team. Their species, moves, held items and seeded shiny status
stay consistent across the game's capture-state variants. Later story teams
still follow their native progression; the captured slot is removed or replaced
as in the original game. See [rematch rules](reverse-engineering/TRAINER_REMATCHES.md).

## Music and sounds

| Screen | Music |
| --- | --- |
| Home | Pyrite Town from Pokémon Colosseum |
| Pokémon Colosseum | Colosseum's title theme |
| Pokémon XD | XD: Gale of Darkness's title theme |

The track switches when you open a game or return to Home. All three tracks
loop and are available offline before you select a ROM. The **Music** switch
remembers your choice across screens and sessions. **Sounds** controls menu
effects separately. Both are enabled by default when available.

On Home, a game card highlights when you hover over it or reach it with Tab.
Returning from either game leaves the cards ready for a fresh selection.

## Seeds, previews and profiles

Seeds are exact UTF-8 text, including spaces and case. The preview calculates
encounters from the same patch plan as creation. A changed seed, source or
setting makes it stale. The animation ends on the computed result without
another random draw. The lists show starters, Shadow Pokémon, gifts and, in XD,
Poké Spots. A single click opens a Pokémon sheet. A small red star marks a shiny;
a question mark represents a replacement not yet calculated.

After selecting an original ROM, fixed encounters load automatically in the
background. Their portraits, shiny stars and sheets use the same result as ROM
creation. Randomized replacements stay hidden until you calculate the preview.
Changing the seed, ROM or settings discards the previous result.

The **Summary** tab shows original descriptions under each ability. The **Moves**
tab shows them for current moves, level-up moves and compatible TMs, where the
game supplies a description. Pokémon types and regular move types use the
original game's badges. Shadow moves have a purple badge with white text in
Colosseum and black text in XD. Hover over any badge to read its type name.
Colosseum Shadow Pokémon sheets show Shadow Rush separately from the regular moves.
Descriptions and badge labels follow the interface language. Reopen a sheet after
switching languages to see the new labels.

**Profiles**, beside language and audio, imports/exports portable JSON settings.
Profiles belong to one game and contain no source/output paths. Reports can also
restore settings but may contain local paths: review them before sharing.
After report import, the app compares your selected original with the report;
input/output paths stay as you chose them. Fixed choices, exclusions and strict
filters take priority over best-effort cross-group family diversity. Remaining
duplicates appear in the preview's extra tab and in the report.

## Starters and evolutions

By default, every evolution stage is eligible and the three-stage-family filter
is disabled. Restrict the stage or select a species manually in Advanced.
Only routes present in the generation-III game count.
Colosseum retains starting levels 26 and 25; XD retains level 10. Starting EXP
follows the replacement's growth curve. Colosseum's two starters use distinct
families by default. Optional pair rules can require similar final strength or
non-overlapping types. XD has one starter.

Manual selections bypass individual stage/power filters; exclusions and pair
constraints still apply. Impossible combinations produce an explanation.
Accessible-evolution rules adapt routes that cannot normally be completed in
that game. For example, Colosseum's trade-with-item adaptation changes Onix →
Steelix to leveling from level 40. Evolution stones are sold in Phenac and Pyrite
in Colosseum, and Gateon Port in XD. XD retains native Eevee shard routes.
The Pokémon sheet shows the actual final requirements and evolution portraits,
including shiny variants. See [starter rules](STARTER_STAGES.md).

## Optional type randomization

Enable **Advanced → Types → Change types** in either game. It is disabled in
both presets. Every species has one or two valid generation-III types; the
original single/double type count is kept, with distinct types for a dual type.
The family-consistency option shares the new types across evolution relatives.
Shedinja keeps its native types and Wonder Guard safeguard.

## Colosseum rewards

Plusle, Ho-Oh, Pikachu and Celebi have separate species controls. The Pyrite
rescue and handover show and name the randomized Plusle gift. Large species
are eligible and use smaller models in those scenes. The gift's field model
also shows its shiny colors when its status is known during ROM creation.
Replacement species use their own animated battle idle when no compatible
field motion is available, so they can glide while the scene moves them.
Keeping Plusle preserves its native scene motions, including with a custom
shiny palette. See [field animations](reverse-engineering/FIELD_ANIMATIONS.md)
for the supported scope.
The Battle Mode Mt. Battle presentation uses the species, form, and shiny
colors of the Pokémon awarded there.

Enable **Make event gifts obtainable** to receive Eagun's purification rewards
at the Relic Stone. By default, Pikachu's gift is available after 10
purifications at level 30, and Celebi's after 25 at level 45. Each threshold
and level can be adjusted independently.

The first reward is Eagun's companion. Its species follows the gift, as do its
shiny colors when determined by the seed or a guaranteed rate. Unown's form and
Spinda's spots also match. After receiving it, the companion leaves his home;
Eagun keeps his original story conversations and item handoffs. Independent
runtime shiny draws at an intermediate rate cannot be predicted for the model.

Eagun becomes available after the purification introduction and its follow-up
after the Skrub encounter, avoiding duplication during story scenes. Each reward
is available once per save. Changing a gift's species does not remove its other
requirements. Dialogue follows the ROM language.

## Colosseum's optional Shadow Lugia event

Added shrine events wait until Eagun has exchanged P★DA contact details with
you. His home actor and original interactions remain available throughout the
story. A pending Master Ball handoff takes priority over added shrine events;
receiving the Master Ball is not a prerequisite for the earlier purification
rewards. Their configured purification thresholds still apply.

Both randomizing presets enable this quest. Open **Settings → Pokémon preview →
Events** to disable it or
preview its six team members with the current seed. You can open each Pokémon's
sheet before creating the ROM. Changing the seed or settings clears the old draw.

After all 48 original Shadow Pokémon have been caught and purified, travel by
motorcycle to another area to receive Eagun's P★DA warning. Return to the
Relic Stone to meet Nascour and his six Pokémon at levels 65-70. His intended
team is Gardevoir, Xatu, Dusclops, Walrein, Blaziken and level-70 Shadow Lugia.
Both presets keep this team, its moves and its held items, independently of
the ordinary trainer settings.

Under **Advanced → Starters and gifts**, **Randomize Nascour's team** draws five
replacements using the seed and allowed species, with different evolution
families where possible. **Randomize the bonus battle's Lugia** independently
replaces the final Shadow Pokémon. Both switches are off by default. The scene
model, mail, dialogue, preview and Snag encounter follow that final choice;
the quest requirements stay the same.

Defeating him without snagging the final Shadow Pokémon leaves the battle
available. After the capture he leaves permanently and Eagun congratulates you.

When the event unlocks, Eagun sends a P★DA email after your first completed
motorcycle trip to another area. Walking out of the shrine, opening or cancelling
the map, and choosing your current area do not activate the mission.
The unread message warns you about Cipher's return and directs you to the
Relic Stone. It arrives once and uses the game's current language. Finishing
the last purification does not interrupt the ceremony or make the boss appear
beside you. The introduction plays on your return and is remembered after a
defeat; speak to Nascour to retry. An unrelated defeat never skips it.

An ordinary whiteout keeps Colosseum's original return rule: the last PC where
you saved, with your team healed. Healing at a Pokémon Center alone does not
replace that saved return point.

Lugia uses XD's dark model while it is a Shadow Pokémon, with a custom white-body,
dark-belly variant when shiny. It uses normal Colosseum purification. Its saved
shiny status follows your settings and remains unchanged after purification;
shiny Lugia then takes its usual pink appearance by default. To keep the dark
model and portrait, enable **Advanced → Shinies → Keep Lugia's Shadow appearance**.
This setting is off by default and does not keep Lugia's heart closed or change
its moves, abilities or stats.
Its bonus Snag List entry does not change the original 48 requirements for Ho-Oh.
Original capture and purification totals also remain capped at the original
roster; the bonus keeps its separate saved progress.
The run journal includes the new trainer, battle and Shadow Pokémon alongside
the original encounters.

The optional event requires a newly created ROM. Original ROMs and saves are
never replaced. See the [technical notes](reverse-engineering/POSTGAME_SHADOW_LUGIA.md)
for validation details and native mechanics.

## XD encounters and trades

XD001 (the story's Shadow Lugia) remains protected even when legendary Shadow
randomization is enabled. Both randomizing presets replace tutorial
Teddiursa by default. Its advanced control can retain the original species.
The tutorial replacement retains level 11 and the original catch rate; its
dialogue names the replacement. Creation checks that the starter has a usable
damaging attack against this opponent, including when Teddiursa is kept native.
An incompatible matchup stops creation with an explanation. Both presets also replace Hordel's Shadow
Togepi; its separate advanced control can retain the original species.
The replacement is a base form from a two-stage family with an accessible
evolution, so Hordel accepts it after purification either before or after
evolving. Imported profiles retain their saved choices.

Both randomizing presets draw the nine regular Poké Spot encounters from XD's
full supported generation-I-III Pokédex. Generation, species/type exclusions,
legendary restrictions and similar-strength matching still apply. The three
rare slots use different species, so Duking has three distinct, obtainable
requests. Each location has three different species; all nine are different
when the pool is large enough. Levels and encounter rates remain native.
Wild Pokémon at the three spots appear as their randomized species in the
overworld and in battle, including their shiny form when the game rolls one.
Large species use a smaller overworld model.

Duking's species checks, dialogue and the gifts preview follow those rare slots,
including when gift rewards themselves are kept unchanged. The preview and
journal show the requested Pokémon, its Poké Spot, its share of encounters at
that spot and the reward. The share of encounters is separate from wild shiny
odds. Dialogue uses the ROM's own languages. Disable **Draw from the full
Pokédex** in Advanced to keep
the original three-species shuffle. Profiles from earlier engines retain that
older shuffle when imported. At least three allowed species are needed for the
full draw. The two special encounters and Mt. Battle prize requirements retain
their native rules.
See [XD story safeguards](reverse-engineering/XD_STORY_SAFEGUARDS.md) for the
scope and limits of the scripted-encounter checks.

## Advanced rules

Search settings in the current language by label, explanation, category or
choice. Similar-strength matching uses final species stats. Move rules can
require damaging and same-type attacks, prevent duplicates, and exclude
self-destruct or one-hit knockout moves. Required Shadow markers and scripted
data are protected. Types, abilities, stats, held items, TMs, treasure and shop
stock can be adjusted separately. Key items and scripted rewards are protected.

Opponent levels use a global multiplier or original-level bands of 1-35, 36-50
and 51-100; these are not story chapters. EXP and purification controls affect
native calculations and do not skip purification's story requirements.
See [validation](VALIDATION.md) for measured results.

## Shinies

The presets use a seeded 5% probability per supported encounter key, not a quota
on the preview. Nature, IVs and the full game RNG remain native. Colosseum
supports starter, gift, trainer and Shadow decisions. XD customization covers its starter,
ordinary gifts and, with **Apply the rate to Shadow Pokémon**, all 83 Shadow
IDs. Both randomizing presets enable this unlock. The seed fixes each Shadow's
status, which is retained after capture and purification. Disable the separate
Shadow option to keep XD's native lock. Both presets also enable **Customize
wild shiny odds** at 5% under **Advanced → Poké Spots**. Every new wild encounter
gets a fresh in-game roll, even for the same species. Its model shows the result
before battle, and that Pokémon keeps it in battle and after capture. Change
the wild rate separately from 0% to 100%, or disable it for native odds.
Previously generated Shadow Pokémon retain their saved PID; use a new game
for the preview to match every encounter. Shiny Shadow Lugia has a custom white
body and dark belly; non-shiny Shadow Lugia retains its original dark colors.
After purification, shiny Lugia uses its usual pink appearance without rerolling
its personality or shiny status. The preview uses matching portraits. The shared
advanced setting **Keep Lugia's Shadow appearance** retains the dark model and
portrait after purification instead. It is off by default. A Lugia that was
never a Shadow Pokémon always keeps its ordinary appearance, shiny or not.
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
