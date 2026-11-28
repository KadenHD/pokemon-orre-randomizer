# Shiny Pokémon

Both randomizing desktop presets enable a **seeded 5% chance** for supported
starters, gifts and trainer/Shadow encounters. This is a per-key probability,
not a quota: a preview can contain more or fewer shinies. The same original,
seed, settings and engine version keep the decisions. Increasing the rate for
the same seed retains already-selected
shinies and can add others. Customization does not require changing species.

| Game | Custom-rate scope | Seed behavior |
| --- | --- | --- |
| Colosseum | Starters, ordinary/event gifts, trainer and Shadow generation calls | Stable decision per encounter/Shadow ID |
| XD | Starter, ordinary gifts and optionally all 83 Shadow IDs | Stable decision per key/Shadow ID; enabled in both presets |
| XD wild Poké Spots | Separate 5% rate for new ordinary wild encounters by default | Fresh roll per new encounter; the seed fixes the roster, not each appearance's shiny status |

The original generation-III test has probability 1/8192 (about 0.0122%) where
the encounter permits it. Game-specific shiny restrictions still matter.
Unchecking customization preserves native behavior. At 0%, supported newly
generated encounters cannot be shiny; at 100%, they are guaranteed shiny.

In XD, **Apply the rate to Shadow Pokémon** removes the native Shadow lock
when customization is enabled. Both randomizing presets select it. Disabling
this option keeps the lock without changing the starter or gift policy.

Shadow Lugia has a custom white-body, dark-belly shiny appearance with its
original red eyes. It applies to XD's protected encounter and Colosseum's
optional bonus encounter. The mesh, skeleton and animations are unchanged.
The variant swaps the authored body and belly material colors and darkens the
belly texture, preserving the original red eyes and transparency.
By default, after purification it uses Lugia's ordinary pink shiny appearance, with the
same saved personality and trainer identity. Unpurified non-shiny Shadow Lugia
uses the original dark appearance; after purification it normally uses ordinary
Lugia's non-shiny appearance.

XD's real-time appearances read the saved Shadow identity when available.
Before that encounter is generated, customized Shadow shinies can use its
already chosen seeded status. Prerecorded videos remain original.

In XD, **Poké Spots → Customize wild shiny odds** sets a separate rate for
new ordinary wild encounters. Both randomizing presets enable it at 5% by default.
Every new encounter rolls again in-game, including encounters with the same
species. The field model shows the result before battle and keeps it in battle
and after capture. Disable the option to retain the original odds.
The game rolls at encounter generation and reuses the stored PID on the field,
in battle and after capture. The seed fixes the roster, while the game determines
each new encounter's shiny result. The preview can show a guaranteed result at
0% or 100%. A wild Pokémon already waiting at a Poké Spot keeps its original PID.

## Preview and saves

Since v2.1.4, Deoxys's initial form is also chosen from the seed in
both games. A separate saved form tag keeps a Meteorite form change independent
of its PID, shiny status and Shadow progress. Colosseum gains XD's three extra
forms, including matching normal/shiny portraits and full-body DNA artwork in
Original and HD modes. See [Deoxys forms](DEOXYS_FORMS.md) for item use and scope.

Known results use normal/shiny portraits decoded from the ROM, including the
evolution portraits. Shadow Lugia uses its original dark portrait or a matching
recolored white shiny portrait; its provenance is in the bundled model manifest.
The portrait keeps the 3D variant's black eye mask, red iris and white neck
and jaw. Normal and shiny Shadow Lugia portraits have a black background inside
their frames. Colosseum uses opaque square tiles. XD retains its original
circular alpha mask and fits the complete head inside it with a small margin.
The application's previews and Pokémon sheets use the selected game's format,
including both Shadow Lugia variants. The baked purple disc is removed from
both derived variants.
The native outer Shadow frame stays intact. Purified Lugia normally uses its
ordinary portrait. In both games, turn on **Keep legendary Shadow appearances**
in Advanced > Shinies to retain the Shadow model and portrait after purification.
The option starts off and applies to Legendary and Mythical Pokémon, including
shiny variants and all four Deoxys Formes. Purification and the saved PID follow
the usual rules.
The display policy applies to randomized Shadow Lugia as well as XD001 and
Colosseum's optional bonus encounter.
A small red superscript star follows a shiny's name.
Seeded encounter previews and creation use the same decisions and do not roll
independently. Wild Poké Spot rows cannot predict an intermediate-rate shiny roll.

Custom shiny chances for supported starters, gifts and trainer/Shadow encounters
use the seed in both games, including intermediate rates. Wild Poké Spots roll
separately for each new encounter. Colosseum no longer offers an unlinked mode.
Older profiles with that mode enabled are verified first, then linked to the
seed without changing their chance. The preview, battles and supported field
scenes share those decisions.
Disabling customization still preserves the game's original behavior.

The randomized Plusle gift and Miror B.'s randomized cave dancers also display
their known shiny colors in the story scenes, including at rates below 100%.
Eagun's partner also follows his first purification gift's seeded appearance,
including at intermediate rates imported from an older unlinked profile.

Colosseum's DNA analyzer and door keypad use the replacements and known shiny
colors of the eight Shadow encounters referenced by the puzzle. Mightyena's
sample retains its original appearance. When shiny status is unknown, the
analyzer and keypad use normal colors.

One Unown form is drawn from the seed and shared by both games. Battles,
scripted field appearances, seeded previews and the DNA lab use that form
with the appropriate normal or shiny palette. The form applies within the
generated ROM. A different ROM can still derive the form from the Pokémon's
unchanged personality value.

Spinda uses the actual personality value to position its spots. Supported
new encounters derive their PID from the seed and their encounter key,
subject to the native constraints and the original trainer's identity where
needed for shiny status. Existing Shadow Pokémon keep their saved PID.
XD wild encounters keep the game's per-appearance PID. The Poké Spot model
reads that same PID before the encounter begins.

Matching 3D scenes use the same PID where the game or seed provides enough
information. When custom Shadow shiny rules are enabled in XD, Spinda's Gateon
Port model uses the seed before the first battle. After the encounter has a
saved PID, both the spots and the palette follow that PID and the player's
trainer IDs, even when the configured shiny rate changes.

Colosseum's DNA analyzer can read a stored Shadow PID or reproduce a
seeded draw with the current player. Its 3D Spinda hologram uses that spot
pattern. The keypad keeps the game's full-body Spinda image and adds a separate
32px spot-pattern inset when the PID is known. The fixed spots on the
pre-rendered body image do not change. An unseeded encounter has no PID inset
until its personality has been generated.

The desktop Pokémon sheet shows a swatch of the exact spot texture when the
PID is known. If the PID is known but its shiny palette depends on the save,
the sheet shows the positions and explains that the game determines the color.
When the PID itself depends on the save or the encounter, the sheet explains
when the game determines the spots.

Other species retain native PID generation. Existing Pokémon and previously
generated Shadow PIDs are not regenerated by replacing the ROM. Preview results
assume a new game. The app does not change save files.

## Compatibility and implementation

Imported profiles preserve their stored rate. After verification, legacy
Colosseum profiles with unlinked custom shinies are converted to seeded draws.
Disabled customization stays disabled. Desktop defaults differ from legacy
low-level Colosseum/CLI defaults; use a profile for exact reproduction.

The Colosseum seeded draw uses the `seeded-shiny-status-v1` SHA-256 domain and an
encounter key. Wrappers select native always/never-shiny modes while preserving
the game's personality constraints. XD uses its own guarded starter/gift paths.
Its Shadow wrappers use the `xd-shadow-shiny-status-v1:<Shadow ID>` draw domain,
select the native always/never-shiny PID generator and align the Shadow's owner
with the player's full SID/TID before capture. Capture and purification preserve
that personality and therefore its shiny status. The enemy-owner override runs
after the native anti-shiny loop, with no loop back into PID generation.
Every supported region has its own checked addresses and original instructions.
Current engine identities are recorded in creation reports.

For historical native evidence, see [initial shiny tests](DOLPHIN_SHINIES_VALIDATION_2026-11-01.md),
[seeded fixtures](SEEDED_SHINIES_VALIDATION_2026-11-02.md), and
[XD research](reverse-engineering/XD.md). The [validation index](VALIDATION.md)
distinguishes controlled runtime fixtures from played scenes and full campaigns.
