# Pokémon XD disc and gameplay tables

The first investigation used three retail revision-0 RVZ dumps. DolphinTool
extracted `common.fsys` and `deck_archive.fsys` directly from each RVZ. The boot
header and `main.dol` were read from the corresponding ISO conversions.
Offsets below are file offsets within the named object. Multibyte fields are
big-endian.

| Region | Disc ID | Starter routine in `main.dol` | Species table in `common_rel` |
| --- | --- | ---: | ---: |
| Europe | `GXXP01` | `0x1CD724` | `0x2BD68` |
| North America | `GXXE01` | `0x1CBC50` | `0x29DA8` |
| Japan | `GXXJ01` | `0x1C6AF4` | `0x28B5C` |

The `common_rel` member is REL module 88 in all three dumps. The existing
unique self-relocation target parser finds the same table indices in each
region. The field meanings were checked against the pinned community
[REL index definitions](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/XDRelIndexes.swift).

## Starter and other rewards

All three starter routines initialize Eevee (133) at level 10 with 1,250 EXP.
The species immediate is at `+0x02` and the level byte is at `+0x0B`. The move
immediates at `+0x12`, `+0x16`, `+0x1A`, and `+0x1E` are 33, 39, 44, and 28.
The EXP immediate is at `+0x66`. A replacement needs its own growth rate and
usable moves at the same level. [Starter routine reference](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGStarterPokemon.swift)

Other acquisition paths have their own routines. The Shadow Togepi gift
initializes species 175 at level 25 and explicitly uses Shadow ID 81. The four
trade rewards initialize Elekid, Meditite, Shuckle, and Larvitar at level 20.
The three Mt. Battle prizes initialize Chikorita, Cyndaquil, and Totodile at a
shared level of 5. Changing these requires checking the acquisition scripts
and player-facing names in each language. [Shadow gift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGTradeShadowPokemon.swift),
[trade rewards](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGTradePokemon.swift),
[Mt. Battle prizes](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGMtBattlePokemon.swift).

### Localized gift randomization

The gift option replaces seven non-Shadow rewards. Four are trades with
Hordel or Duking and three are the Mt. Battle prizes. It edits only the
species immediate in each DOL constructor. The original level, moves,
nickname, and award conditions remain in effect. Independent story options
can update the species Hordel or Duking requests.

The scripts and banks use three different name paths.

- In `D2_crater_colo.fsys`, `win_100` populates the prize menu with message
  IDs `0x7A49` through `0x7A4B`. Confirmation uses the selected menu
  message. The patch replaces the three labels with the names from each
  playable language's native species bank.
- In `M2_guild_1F_2.fsys`, the three calls to
  `ginzaru_pokemon_change` pass received and requested name IDs separately.
  The patch changes the received-name operands at TCOD offsets `0xD30`,
  `0xD74`, and `0xDB8`. It verifies that the original species comparisons,
  requested-name operands, and trade flags still match the retail script.
  Each native bank resolves the replacement name using its own language.
- In `S1_shop_1F.fsys`, messages `0xA438`, `0xA43B`, `0xA43C`,
  `0xA43E`, and `0xA443` use a literal for Elekid, or its nickname in
  Japanese. The patch updates those literals, including affected French
  and Italian articles, and keeps the original message controls intact.

Bank edits append the replacement messages and retarget only their
directory entries. The earlier payload and unrelated aliases remain
intact. This covers the five European banks, the North American English
bank, and the Japanese bank. All three discs accepted the same seven
choices from a fixed seed during binary verification. This check confirms
the patch data and language paths. It does not exercise reward acquisition
in the running game.

## Trainer decks and Shadow identities

XD stores trainer data in `deck_archive.fsys`. Europe and North America have
identical archives containing both suffixed and unsuffixed deck files. Europe
selects `_EU.bin` and the other releases select `.bin`. Japan's archive
contains the unsuffixed files only. All DPKM rows of the main decks are identical
between variants. The regional differences in those decks are confined to the
trainer records.

| Deck | DTNR rows | DPKM rows | First DPKM row | Active normal rows referenced by trainers |
| --- | ---: | ---: | ---: | ---: |
| Story | 233 | 823 | `0x3328` | 726 |
| Colosseum | 69 | 319 | `0x0F48` | 318 |
| Hundred | 101 | 322 | `0x1648` | 321 |

Each deck starts with a `0x10`-byte header. Each section has a `0x10`-byte
header with its byte length at `+0x04` and row count at `+0x08`. DTNR records
are `0x38` bytes. The six team references are consecutive u16 fields from
`+0x1C`. Bit `n` in the mask at `+0x04` directs slot `n` to the Shadow
deck. The other slots refer to a DPKM record in the current deck. Record zero
is the empty sentinel. DPKM records are `0x20` bytes with species at `+0x00`,
level at `+0x02`, held item at `+0x04`, and four moves starting at `+0x14`.
[Deck sections](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/enums/XGDecks.swift),
[team references](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGTrainer.swift).

The Shadow deck has 128 DDPK records of `0x18` bytes, starting at `0x20`.
Each active record points to a unique Story DPKM row through its u16 at
`+0x06`. Across all trainer decks, 96 slots refer to 83 Shadow IDs. A species
change in the shared Story record applies to every appearance of that ID.
Both archives carry byte-identical copies of the DDPK data, including regional
aliases where present. Species-only edits can leave all DDPK copies intact,
including their Shadow moves, capture rates, and Heart Gauges.
[Pokémon and Shadow record definitions](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGTrainerPokemon.swift).

Shadow Lugia is ID 73 and Story row 699. Its reference is trainer row 199,
slot zero. Shadow Togepi is ID 81 and Story row 1, shared with the native gift
identity. The first Shadow encounter, Teddiursa, is ID 1 and Story row 28.
Its reference is trainer row 17, slot zero. These three identities retain
their original species with the default settings. The 13 active Story DPKM records with no direct
team reference or Shadow mapping also retain their original species. Virtual,
Bingo, Imasugu, and Sample are distinct from the Story, Colosseum, and
Hundred decks.

## Species, evolutions, and Poké Spots

The species table contains 415 records of `0x124` bytes at relocation index
88, with its count at index 89. The EXP growth rate is at `+0x00`, the
National Pokédex number at `+0x0E`, and the name ID at `+0x18`. Native name
banks decode Eevee as `EVOLI` in the French bank, `EEVEE` in English, and
`イーブイ` in Japanese. Internal species IDs differ from National Pokédex
numbers for some entries. IDs 413 and 414 are the special Bonsly and Munchlax
encounters. [Species record reference](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGPokemonStats.swift).

Five evolution records of six bytes start at `+0xA6`. Each holds a method byte
at `+0`, condition u16 at `+2`, and target u16 at `+4`. The three dumps have
four trade routes (`0x05`), eight held-item trade routes (`0x06`), and one
Beauty route (`0x0F`). Eevee uses the XD key-item method (`0x10`) with
conditions 516 and 517 for Espeon and Umbreon. Converting routes for Slowpoke,
Poliwhirl, and Clamperl requires preserving their separate branches. One
native chest each contains a Fire, Water, and Leaf Stone. The European
`pocket_menu` REL has no evolution stones in its stock lists, so these three
placements alone do not provide unlimited stones. Learnsets begin at
`+0xC4`, with 19 four-byte records holding level at `+0` and move at `+2`.
[Evolution methods](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/enums/XGEvolutionMethods.swift),
[treasure fields](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGTreasure.swift).

Rock, Oasis, and Cave each contain three identical encounter records across
the three regions. Their pointer/count index pairs are 12/13, 15/16, and
18/19. The records start at `0x2FAC`, `0x2FD0`, and `0x2FF4` in each REL.
Each `0x0C`-byte record holds minimum and maximum level at `+0` and `+1`,
species u16 at `+2`, and encounter weight at `+7`. The separate all-spots
table at `0x3018` contains the two special encounters. The third slot in each
of Rock, Oasis, and Cave remains available for Duking's trades. The other six
slots can change species while retaining levels, weights, and Poké Snack
behavior. [Poké Spot record reference](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGPokeSpotPokemon.swift).

## Native script dependencies

- **Duking's trades.** In `M2_guild_1F_2.fsys`, `talk_005_ginzaru` calls
  `Pokemon.getSpecies` at TCOD offsets `0xB2C` and `0xD00` in each region.
  The following comparisons use 332 (Trapinch), 311 (Surskit), and 194
  (Wooper). This is why the three rare Poké Spot slots keep those species.
- **First capture tutorial.** `M5_out.agent_battle` starts battle 224,
  which uses Story trainer 17, Pokémon row 28, and Shadow ID 1. The
  encounter and capture are at level 11 with catch-rate override 120. The
  operand 216 at `M5_out+0x6798` selects a separate battle. The species
  operand for the tutorial is at `M5_labo_1F+0x818C` in Europe and the US
  and `+0x816C` in Japan. It supplies message variable 78 for `0x9DBA`.
  Three other messages name Teddiursa explicitly.
- **Hordel and Lugia.** `S1_shop_1F` checks for Togepi or Togetic. The optional
  gift replacement updates both species checks. The lab scripts check Shadow
  ID 73 for Lugia's dedicated purification events.
- **Eevee's item choice.** The Gateon Port sailor checks the party and PC
  for Eevee in `M6_junk_1F`. The PC check is at `0x1DE4` in all three
  builds. An Eevee stored in the PC has to be retrieved. If the player has
  no Eevee, the branch at `0x1E28` still offers a choice of one evolution
  item. The fallback text in the English bank treats Eevee as released.

The script observations use decoded TCOD instruction words and the pinned
[built-in function reference](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/scripts/XD/XGScriptClassFunctionsData.swift).

## Poké Spot trades and scripted Pokémon feasibility

Each spot's `esaba_A`, `esaba_B`, or `esaba_C` script reads the selected wild
species and has dedicated branches for its three original ordinary species.
Those branches select the field model, apply the corresponding visual
settings, and show the actor. All three revisions use the same mappings.
The Oasis script has no generic actor setup for an unrecognized species.
Through engine v3, the ordinary-slot randomizer changed the encounter table alone,
so a successful build does not establish that those Pokémon can be seen
and approached. A permutation within each spot preserves the native
model branches and allows its rare slot to change. An expanded pool needs
verified field models and compatible scene scripts.

Duking's three trades check the outgoing species twice. The three native
operands are at `0xB48/0xB98/0xBE8` and `0xD1C/0xD60/0xDA4` in
`M2_guild_1F_2`. The outgoing species name IDs are at
`0xD38/0xD7C/0xDC0`. The `ARRY` table also stores them at
`0x1754/0x175C/0x1764` for messages `0x9293` and `0x9294`, which list
the two or one trades still available. These are separate from the incoming
reward names and trade flags. Two room messages, `0x9172` and `0x9174`, and the field
tutorial message `esaba_B:0xB1BE` contain all three names in every playable
language. A bounded scan found no Trapinch species check in the separate
Pre Gym room script that mentions a lost Trapinch.

The fixed Teddiursa names occur in `M5_labo_1F:0x9CDD`,
`D1_labo_B2:0x759E`, and the playable `fight_common` message bank
`0x5688`. Changing the first Shadow species requires adapting those three
references as well as the lab's dynamic message operand. Retaining the
battle and Shadow IDs keeps the existing progression checks in place.
A replacement must remain catchable with the generated starter and battle
rules.

For Hordel, Shadow ID 81 is shared by Story row 1 and a separate gift
constructor. The species immediate is at file offset `0x1C705E` in Europe,
`0x1C5762` in the US, and `0x1C0C72` in Japan. The room script checks for
Togepi or Togetic, original ownership, and purification. Engine v5 optionally
replaces the gift with the base form of a two-stage family with an available
evolution route. It changes both species in the script and its name lookups,
four literal messages in each playable language, the DOL constructor, and all
Story deck variants. The gift remains at level 25 and retains Shadow ID 81.
The existing purification and ownership checks and the DDPK row are preserved.
The preview and journal list both accepted forms. V4 profiles import with
the new option off and keep their previous species draws.

Lugia's special path additionally compares the species directly in the DOL.
The three regional executables use species 249 for chamber eligibility,
walking-based Heart Gauge progress, the Shadow reveal, and the purification
ceremony. The final battle also loads Lugia-specific effects and models.
Changing the deck row alone would bypass those checks. A future replacement
needs to preserve Shadow ID 73 and handle those native paths and assets.

An in-memory probe permuted the three native species at each spot, changed
both sets of Duking's checks and the displayed requirement IDs, and
retargeted all three localized messages. A separate probe replaced the
tutorial Teddiursa with Shroomish in each Story deck copy and checked the
lab operand and all three localized message references. Both probes covered
the European, US, and Japanese resources and produced no output ROM.
Engine v4 uses the within-spot permutation and supports the tutorial
replacement as an independent advanced setting. Profiles and reports from
v3 import with a notice when their Poké Spot draws will change.

Separate EU, US, and Japanese v4 images passed DolphinTool verification.
Reading the final images confirmed both trade predicates, the trade menu
names, and the updated dialogue in every playable bank. The sample kept
Shadow ID 1 at level 11 with the native catch-rate override of 120, even
with the general catch minimum set to 200. The European image reached the
game's health and safety screen in an isolated Dolphin session. A Windows
firewall dialog prevented the capture and trade checks.

The EU, US, and Japanese v5 images passed DolphinTool verification. An
independent read of the resulting images confirmed the gift constructor, the
level-25 Story row, the unchanged Shadow 81 record, both accepted forms in
the room script, and the four updated messages in each playable language.

An offline controller replay on the initial European v5 ISO reached the
research lab after the opening simulation. The party screen displayed the
seed's level-10 Horsea in French. The replay used a fresh isolated memory
card and did not modify the ISO or the personal Dolphin profile. It also
identified two literal Eevee references in lab message `M5_labo_2F:0x9C42`.
The engine now updates both references in each playable bank when the
starter species changes.

On the final European v5 ISO, copies of that native save loaded the room
with Hordel, Duking's room, and the kidnapping sequence outside the lab.
Three prepared saves set the pending rare encounter at each Poké Spot.
Dolphin rendered Gligar at Rock, Phanpy at Oasis, and Zubat at Cave, then
entered all three battles with the expected species. These runs exercised
the map actors and the battle handoff. Separate replays completed each of
Duking's three trades and received Hordel's Shadow Feebas. Two further
replays completed Hordel's trade with Feebas and Milotic using prepared
purified party specimens. The initial trade replays revealed that Duking
still used the original names in the one- and two-species prompts. After
patching `ARRY`, two replays on the corrected European ISO showed the
seeded names in both prompts.

On the corrected European ISO with seed `xd-story-check`, the first Shadow
capture tutorial showed a level-11 Rhyhorn. A prepared card equipped the
Snag Machine and provided the five Poké Balls for this scene. Throwing a
regular Poké Ball won the battle against Spy Naps and advanced to the
post-battle story dialogue outside the lab. Three separate Poké Spot
tests used prepared pending rare encounters and a Master Ball each.
Capturing Gligar at Rock, Phanpy at Oasis, and Zubat at Cave reached the
nickname prompt for the correct species in all three cases.

The field interaction accepted a Poké Snack at each spot. The Rock test
card set flag 1404 to reflect Duking's earlier handout, which the native
`esaba_A.esa_set` script requires before opening the deposit menu.
Separate timed tests loaded cards with 10 Poké Snacks already placed,
the step counter near the upper threshold, and no pending encounter.
Walking outside the baited spot caused the game to populate the pending
species and personality fields. It selected Trapinch (332) at Rock,
Hoppip (187) at Oasis, and Wooper (194) at Cave, matching the corresponding
entries in the seed report. The rare catches above used separate cards
with the rare encounter already pending.

## Evidence boundary

REA opened the European DOL and reported entry point `0x80003154`. The
available Windows provider did not offer DOL byte reads, so the starter
immediates were checked directly against the extracted PowerPC instruction
words. This report records static observations on the three revision-0
retail images. In-game checks are separate evidence for scene triggers, catching and
purifying a replacement Shadow Pokémon, and obtaining the special rewards.
The inspected discs and their extracted contents remain local.

## Gateon Port evolution stones

The three regional scripts in `M6_shop_1F.fsys` select cash inventory
descriptors 6, 14, and 15 depending on progression. Archive member
`0x02f21c00` contains the `pocket_menu` REL, module 250 in Europe and the
US and module 2 in Japan. The US and Japanese archives also contain
message and image members named `pocket_menu`. The REL contains
21 descriptors at `0x1C8` and 184 zero-terminated stock cells at
`0x300`. The three Gateon stocks are
nested. Their shared suffixes fit the six new stones within 159 cells while
preserving the original stock in each branch. Other stores retain their
original items and order. All five European `pocket_menu` archives are patched
alongside the single archive in each of the US and Japanese builds.

The common REL has native names and use effects for IDs 93–98. The Moon Stone
was the only one without a cash price. It is assigned the same price of 2,100
as the other five. The western spelling edits add spaces to selected native
compound names without moving the REL's tables or changing unrelated text.
German and Japanese retain their native spellings.

## First randomizer validation

The three regional RVZ sources produced separate ISO images with seed
`orre-xd-v1`. The pipeline verified each output against its expected patch
ranges, then hashed the RVZ again to verify source preservation. DolphinTool
reported no problems on all three ISOs. An unchanged European ISO matched
its decoded input byte for byte. Converting the randomized European ISO to
RVZ and back reproduced the exact randomized ISO.

The three regions produced identical encounter and evolution reports for this
seed. The starter was Mudkip at level 10 with 560 EXP. There were 1,365 changed
ordinary trainer slots, 80 replaced Shadow species, 83 distinct Shadow
families, six changed Poké Spot slots, and 13 converted evolution routes.
The three protected Shadows, the rare trade encounters, the two special
Poké Spot encounters, and the original gift scripts were preserved.

REA identified the European DOL as PowerPC with entry point `0x80003154`
and SHA-256 `a90eae103e6e8471e41c92df1f894f98c2f98d1f9f3a0aca84964492135f5cfd`.
Its Windows provider did not support deeper DOL reads. The instruction
signatures were independently checked against the local DOL bytes in each
region before patching.

An isolated Dolphin 2609a session on the European work build reached the
French title screen, created a fresh memory-card file, completed the native
Salamence versus Metagross tutorial, and displayed Mudkip at level 10 in the
party summary at the lab. The work build and the delivered European ISO have
identical modified DOL bytes, SHA-256
`6a35b50fa6ab78dbfb1aa29c1c5e564058d45563f3b07473a91d8a8ec3023bf7`.
The delivered build additionally preserves the tutorial Teddiursa. The
emulator exited with status 0 and the monitor reported that the personal
profile was unchanged. A complete campaign, later Shadow encounters, and
evolution triggers require separate play tests.

## Second randomizer validation

The second engine revision produced a new set of regional ISOs with the
same sample seed, `orre-xd-v1`. The tool checked the complete output bytes
and rehashed each input RVZ. DolphinTool reported no problems in Europe,
the US, and Japan. An independent read of the final ISO files found all six
items in Gateon descriptors 6, 14, and 15 for every shipped menu archive.
The three regions agreed on all encounter, gift, and evolution outcomes.
The sample contained 83 distinct Shadow families and seven distinct reward
families, with no overlap between those two groups.
The European RVZ also decompressed to the exact verified European ISO.

The desktop preview used the same patch plan and matched the European
creation report, including all seven rewards. It decoded the starter's
normal-color portrait from the original XD ISO. The portrait is a GX C8
texture with 8×4 indexed tiles followed by an RGB5A3 palette. The preview
opened the supplied ISO read-only and wrote no disc image.
[Dolphin GX decoder](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/VideoCommon/TextureDecoder_Generic.cpp)

The isolated Dolphin session reached the European disc's entry point in
the first engine revision. The debugger connection then lost synchronization
and Windows Security obscured the game window. The final European ISO was
also opened in Dolphin with a separate, empty memory card and the network
debugger disabled. The earlier security dialog remained visible. Shadow
capture, purification, save/reload, the Poké Spot encounter and trade, and a
complete evolution scene remain unverified in game.

## Advanced rules validation

The advanced build was generated from the original European, US, and Japanese
RVZ files. Each ISO passed DolphinTool verification. The sample used a 100%
shiny rate for the starter and gifts, ×1.5 battle EXP, and ×3 purification
alongside randomized moves, TMs, types, stats, items, and teams. The boss
settings covered 14 story fights and rematches across seven characters,
with 27 associated Shadow IDs. All three reports showed 83 distinct Shadow
families. The European output also survived conversion to RVZ and back to
ISO with the same SHA-256.

The EXP and purification patches use a new executable text section. The
disc builder relocates the FST when that section grows past the original
DOL boundary. The starter and gift shiny policies use the native PID
generator and preserve XD's original Shadow policy. Instruction-level tests
cover the new hooks. An isolated Dolphin session with the debugger disabled
displayed the European game's health and safety screen. A Windows firewall
dialog prevented further input. The test monitor confirmed that the personal
Dolphin profile was unchanged.

## Release candidate validation

The `0.21.0rc1` Windows ZIP and installer were downloaded from GitHub and
matched their published SHA-256 digests. The executable from that ZIP passed
diagnostics with fresh application data and no developer tools on PATH. The
checks included the three XD screens at two window sizes in all six languages.

A separate European ISO used the `xd-story-check` seed, a 100% shiny rate
for the starter and eligible gifts, ×1.5 battle EXP, and ×3 purification.
A fresh Dolphin playthrough reached the lab and wrote an in-game save.
Reading the newest slot confirmed a level-10 Horsea with a shiny PID.
Reloading the card in a separate session preserved that starter and its
shiny appearance in the party summary.

At the Relic Stone, the native ceremony purified Rhyhorn. This check started
with a prepared card that unlocked access to the Relic and set Rhyhorn's
Heart Gauge to zero.

A prepared level-39 Kadabra gained one level from a Rare Candy. Dolphin
played the evolution scene and reported that Kadabra evolved into Alakazam
at level 40.

A Cave play test placed Poké Snacks in the native menu, left the spot for
the lab and let the game choose an encounter. The prepared card placed
the step counter near the appearance threshold. The game produced a
non-rare encounter. The earlier rare catches used cards with the encounter
already pending.

The numerical effects of the battle EXP and Heart Gauge multipliers are
covered by instruction-level tests. A matched comparison of their awards
and gauge changes in Dolphin is still pending.
