# Validation scope

This index records the v1.0.0 foundation and subsequent validation follow-ups.
Dated reports in `docs/` describe their named versions and scenarios; they are
historical evidence rather than the current feature specification.

## Automated and packaged checks

- Python tests cover guarded edits, disc identity, both games' options, allocation,
  previews, profiles, translations, reports and GUI state.
- Preset tests compare all shared fields across games and balance fields across
  modes. Exports from the actual published RC2 source archive verify that imports
  keep old values. RC1 version/engine compatibility is checked too.
- GitHub Actions runs Windows and Linux tests. Tests requiring local ROMs declare
  and skip those prerequisites on public runners.
- Rust/Python codec output is compared. Archive audits check CRCs, hashes, paths,
  notices and the allowlisted interface pack.
- Windows diagnostics cover 456 UI states, six languages and two sizes, including
  both games and home. Isolated smoke tests remove developer tools from PATH and
  use fresh application data. The installer is installed, checked and uninstalled.
- Published asset sizes and SHA-256 digests are verified after release.

Counts evolve; the Actions run for a release tag records that build's results.

### Interface parity (v1.2.1)

The local suite completed 527 tests with no failures (two platform skips).
The frozen Windows executable passed 456 UI states with bundled images, sounds
and music, using isolated preferences. Eleven dedicated parity regressions check
shared labels, help, pending rosters, multilingual search, loading/cancellation,
stale results, single-click sheets, report comparison and verified-plan reuse.

Real read-only previews were computed from the European Colosseum and XD
originals. XD's pending roster and internal/National Pokédex mapping were checked
against all three regional data sets. For XD, recommended, Pokémon-only and copy
preview plans matched freshly computed creation patches; copy produced zero
patches. Originals remained unchanged. No new Dolphin gameplay check was needed
for this presentation update; prior native-validation limits still apply.

### Creation-details follow-up (v1.2.2)

Additional regressions exercise both games' actual Qt worker callbacks and the
shared creation log. They check that validation errors never reveal Details,
including in all six languages, while genuine generation exposes it before the
first progress event. Success, failure, cancellation, navigation, translation and
a new invalid attempt preserve the intended visibility and reset behavior.

### Pokémon sheets (v1.2.7)

Read-only previews from the European originals for both games were rendered
in Qt to check original descriptions, move badge alignment and Shadow moves.
The bundled catalogs were checked in all six interface languages. Each language
has 76 ability descriptions and 355 Colosseum or 372 XD move descriptions.
These checks cover application presentation and packaging.

## Native Dolphin checks

Colosseum reports cover selected battles, starters, shinies and regional gifts:

- [Disc round trip](reverse-engineering/ROUNDTRIP.md)
- [Dolphin validation](DOLPHIN_VALIDATION_2026-10-31.md)
- [Shiny validation](DOLPHIN_SHINIES_VALIDATION_2026-11-01.md)
- [Seeded preview](SEEDED_SHINIES_VALIDATION_2026-11-02.md)
- [Regional gifts](REGIONAL_GIFTS_DOLPHIN_2026-11-03.md)

XD's [research report](reverse-engineering/XD.md) records regional structures,
story protections and native follow-ups. The corrected v6 runtime hook was
checked with matched European QA saves and separate original/modified images:

| Measurement | Original | Modified |
| --- | --- | --- |
| Vivid Scent, Rhyhorn's Heart Gauge starting at 6000 | 5700 (−300) | 5100 (−900), purification ×3 |
| First measured EXP award in the same trainer battle | 165 | 248, EXP ×1.5 |
| Last measured EXP award | 91 | 137, EXP ×1.5 |
| Total EXP gained by each participant | 522 | 785, rounding per award |

Both battles and the purification flow returned normally. Original ROMs,
personal saves and personal Dolphin settings were preserved. The v1 preset
alignment changes which existing options are selected; it does not change these
native hooks.

## Full-Pokédex Poké Spots (v1.1.0)

The local suite ran 510 tests, with 508 passing and two Windows-specific skips.
The full encounter draw and Duking request synchronization were checked against
the European, US and Japanese originals, including all native text-bank patches.
The same seed produced the same nine species across regions. A separate European
ISO passed full output-byte verification and DolphinTool's disc verification;
its encounters matched the preview. Keeping gift rewards unchanged still updated
the requests. Both preview lists were checked in all six interface languages.

The published RC2 source archive supplied an independent v6 reference. Its two
exported XD presets produced identical ISO patch bytes under v6 and v7 when
imported with the native Poké Spot shuffle. New full-pool draws have separate
keys; the older draw domains remain unchanged.

These checks validate data, text, previews and disc construction. A newly played
Duking exchange and full campaign for each possible draw are not claimed here.

### Pending Poké Spot encounters (v1.2.15)

In muted French PAL Dolphin sessions, the Spot Monitor registered a new
Vulpix at Rock with a 0% wild shiny rate, and new shiny Taillow and Sentret
at Oasis and Cave with a 100% rate. The test cards started just before the
encounter timer. After saving, separate copies loaded the pending encounters
at their respective spots with the rate reversed. The on-field message and
model matched the battle species. All three captures were saved, and the
captured entries retained the exact pending personality and owner IDs.

### Phenac dialogue replays (v1.2.15)

Muted French PAL sessions used separate copies of a player save, prepared at
the two relevant story states. The boy outside the Pre Gym cheered for Chinchou
and then explained he was imitating Justy. The first battle against Folly used
Slakoth and Ekans. The game displayed both names in his defeat line, followed
by the native continuation. The output ISO’s `openingdemo.thp` matched the
original disc byte for byte.

## XD Shadow shiny unlock (v1.2.0)

The [dedicated report](XD_SHADOW_SHINIES_VALIDATION.md) records guarded patches
for all three regions at 0%, 5% and 100%, 83 preview decisions and portraits,
and controlled native Dolphin calls. Native PID generation, player ownership,
capture metadata and the purification state transition retained the expected
shiny status. This is function-level runtime evidence, not a newly played
capture-to-purification sequence. The current suite and relocated Windows app
passed 516 tests (two platform skips) and 204 UI states respectively.

## Shadow Lugia replay (v1.2.10)

The [French PAL replay](XD_SHADOW_SHINIES_VALIDATION.md#shadow-lugia-in-v1210)
covers the final scene, a native capture, both final battles, purification in
the chamber, and reloading the purified shiny Lugia from the PC after a full
emulator restart. It used the default preset at 5% and prepared test cards.

## Default preset campaign checkpoints (v1.2.10)

Fresh French PAL games used separate, blank cards and the desktop Pokémon +
moves preset. In XD, seed `xd-final-0` passed the opening simulator battle.
The first lab save contained the reported level 10 Larvitar and its four moves.
In Colosseum, seed `orre-campaign-preset` started with Dratini and Oddish and
passed the opening fights at Outskirt Stand and Phenac City. After the Phenac
fight, Gafar's French dialogue still named Whismur, although he used Nincada
and Seedot. The rescue scene continued and the game saved normally at the
Phenac Pokémon Center. These two checkpoints cover the opening of each game.

## Phenac victory dialogue

The post-battle message uses the final species from Folly's two team slots.
If they are different, it names both in team order. The first page uses the
ROM's localized species names and the following page is preserved byte for
byte. Verification covered all five European language banks on two seeds and
the American English and Japanese banks on one seed. Only the target message
pointer and its appended replacement changed in each bank. A European
no-change build matched the original ISO's SHA-256.

Three fresh French PAL runs in muted Dolphin played through the opening
battles to the victory message. Gafar named Nincada and Seedot on
`orre-campaign-preset`, Ekans and Zigzagoon on `phenac-dialogue-2`, and
Whismur on the no-change build. The rescue sequence continued after the new
line on `phenac-dialogue-2`. A separate rebuild using the earlier campaign's
exact options and seed reloaded its test card and reached the Phenac Colosseum
reception.

The XD campaign test card reloaded at the simulator with seed `xd-final-0`.
The next lab cutscene completed, the player reached the regional map and
returned, and the game saved outside the lab on the copied card.

## Dialogue that follows a randomized species

The audit extracted 494,940 native message entries from the European,
American and Japanese retail discs of both games. The count includes menu
text, language variants and duplicate banks. Native trainer tables and
field scripts were used to review references to battle teams, including
references expressed through types, moves or abilities.

Colosseum updates the Johto starter rematches, related PDA mail and other
Shadow reports, plus Gafar's first battle, the Phenac Gym opponents and the
Snagem Hideout rematches. XD covers both lab outcomes, Mt. Battle and
Colosseum opponents, Eagun's battle and the final Shadow Dragonite. The
Gateon Port sailor can offer an evolution item to a player who started
with another species, so that branch no longer assumes they released Eevee.
Atill's Teddiursa remark reads Atill's team. Naps's tutorial has its own patch. The
Mt. Battle remark about Castform and Wailord reads both final team slots.
Remarks about type themes, abilities and move combinations are adapted when
the randomized battle changes their premise.

The direct trainer message IDs were cross-checked against the native party
tables in all three regions of each game. Four Colosseum battle messages
named species absent from their original parties. Rows 190 and 362, linked to
battles 192 and 364, use the same placeholder party at slot 238. Their revised
introductions avoid naming a species or move. Both of Reman's chants now use
the first two Pokémon in trainer row 655. Function 32 of `D2_cloud_3` selects
one of these chants for the first opponent. The patch updates the fight bank
and its Mt. Battle copies. Fixed scene actors remain separate from trainer
dialogue patches.

The follow-up audit included field dialogue and remarks that imply a team
without naming its Pokémon. Candidates were checked against the speaker's
native party, moves, types and abilities, plus the script branch that displays
the message. Checking those links distinguishes a real team strategy from a
trainer's personal preference, a fixed story actor or an unused message.
The party used for dialogue is the final one after team policies. For example,
Colosseum updates Folly's line when the fully evolved opponents setting alone
turns his Whismur into Exploud.

Toti's introduction and defeat at Pyrite keep their dance theme when her
two parties still have dance moves. In XD, the Mt. Battle field lines account
for real team details, such as Gratin's trapping strategy, Ebilo's flower and
butterfly pair, and Tulon's Rain Dance. The Orre Colosseum lines distinguish
changes to party composition from changes to the moves or abilities a tactic
requires.

The follow-up used seed `orre-dialogue-context` on all six verified retail
discs. Both randomization presets, a moves-only configuration and the
unchanged preset were checked for each game. Colosseum also ran with only
fully evolved opponents enabled, and XD ran with only types and abilities
randomized. The emitted language banks preserved page counts for the new
edits and added no explicit line breaks. The unchanged preset emitted no
patches. Width estimates also covered the longest pairs of species names in
the new XD field lines.

Muted PAL Dolphin runs replayed Lola's introduction and defeat in Pyrite on
a copy of the personal Colosseum card. In XD, copies of the Mt. Battle QA card
rendered the new zone 13, 66 and 67 lines. Zone 66 named Machoke and Graveler,
which both appeared in the battle. The test images placed the player near the
targets and invoked the native booth scripts for the XD encounters. The
protected source cards and personal profile matched their original hashes
afterward.

### XD Battle Simulator

All 12 lessons use fixed rental teams. The advanced species settings used to
change their types, abilities and base stats through the shared species table.
Virtual battles now use the retail table for those rentals. Normal battles
continue to use the randomized table. The opening simulator battle and Battle
CDs use the same virtual battle modes.

Generated builds of the European, American and Japanese editions preserved the
12 rental teams and their original lesson text in the six playable languages,
with types, abilities and base stats randomized outside the simulator. A test
runs the regional PowerPC hook before, during and after the virtual encounters.

In muted Dolphin, the French PAL lesson on matching Pokémon and move types
completed with Rattata using Quick Attack to defeat Makuhita. The same build
uses Electric-type Rattata in the adventure, while the virtual lesson used
its original Normal-type data.

Checks on all six discs with seed `dialogue-audit-1`, and on both European
discs with `dialogue-audit-2`, found no added line breaks in the changed text.
Where a longer name could crowd the lab or Phenac dialogue, the patch
shortens the sentence within the native layout. Two European no-change
builds matched their respective original SHA-256 hashes.

In muted Dolphin, the French PAL Colosseum build loaded an isolated copy of
the personal card and opened its PDA inbox. The original card was verified
unchanged. In a new game with seed `orre-campaign-preset`, Gafar's defeat
line read “GAFAR: NINGALE et GRAINIPIOT K.O. !” on one line, matching his
two Pokémon in battle. The French PAL XD build completed the opening simulator
fight with seed `xd-final-0`. Both lab dialogue pages named Larvitar
(`EMBRYLEX`) in the native box. In a separate muted PAL replay with seed
`dialogue-audit-1`, the player fought Rodolphe in Mt. Battle zone 82 on a
prepared copy of the XD test card. His post-battle dialogue read
“Mon duo, CHARMINA et GROLEM !”, the two team slots that originally held
Castform and Wailord. The line fit the original box on one line. The four
Colosseum battle message rewrites were checked in the regional ROM data,
including each copy in the Mt. Battle archives.

For v1.2.12, a muted French PAL replay used a copy of a test save with
Larvitar as the starter. The sailor's Water Stone and Moon Shard
explanations both referred to an Eevee. The game confirmed receipt of
the Moon Shard. The item dialogue was also checked in the other language
banks on the European, American and Japanese discs.

## Limits

Selected scenes and synthetic fixtures do not prove a complete playthrough or
balance across all seeds. No full campaign or second physical Windows PC is
claimed for v1.2.0. These are additional coverage opportunities, not completed
checks. Distinguish observed game failures from limitations of prepared QA scenes.
