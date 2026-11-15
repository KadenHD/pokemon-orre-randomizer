# XD Shadow Lugia models and portraits

Every randomized Shadow Lugia uses XD's original dark model. Shiny specimens
use the added light-body/dark-belly variant, with a white lower neck and the
original red eyes. The native Shadow aura and lighting remain, so the light
surface can look lavender in the party screen. This palette was added by the
randomizer; it is not an unused retail shiny model.

The advanced **Keep Lugia's Shadow appearance** option is
off by default. It changes appearance only:

| Specimen | Default | Retention option enabled |
| --- | --- | --- |
| Shadow Lugia | Original dark model | Original dark model |
| Shiny Shadow Lugia | Custom light-body/dark-belly model | Custom light-body/dark-belly model |
| Purified former Shadow Lugia | Ordinary white-and-blue model | Original dark model |
| Shiny purified former Shadow Lugia | Ordinary white-and-pink model | Custom light-body/dark-belly model |
| Lugia that has never been Shadow | Ordinary model, including its native shiny palette | Ordinary model, including its native shiny palette |

The same policy applies to portraits. Purification requirements, moves, ribbons,
saved identity and battle mechanics stay native.

## Resource and identity selection

The native species remains Lugia (249). XD already selects dark model index 417
for any real Shadow Lugia, including randomized encounters other than XD001
(Shadow ID 73). The patch appends resource `0x7DF41E00` to the existing
`pkx_darklugia.fsys` archive (group 2263). Native resource
`0x19661E00` and all original archive members remain intact. No new FST entry or
save-format field is needed.

The native Dark Lugia face has a separate resource and ignores the normal shiny
frame choice. At the specimen-aware face selector, the real Pokémon's PID and
OT choose virtual face ID `0x7F00` for the normal dark face or `0x7F01` for the
custom shiny face. A guarded texture getter maps these IDs to resources
`0x7DF71200` and `0x7DF51200` in `poke_face.fsys` group `0x5C0`. A descriptor
hook maps both virtual IDs back to native face ID 345 for geometry and framing,
while their texture cache keys remain distinct. A normal Lugia in another slot
therefore cannot inherit XD001's shiny face.

Both variants retain the original round alpha mask: 244 transparent pixels
outside the circle and 1,520 opaque pixels inside each 42px tile. The baked
violet disk is replaced with black inside the circle. The complete source head
is area-resampled to 36px and centered with 3px padding. Every visible source
pixel contributes inside the opaque area, and the resulting silhouette keeps
at least one opaque pixel of separation from the transparent boundary.
The same alpha mask was checked against native Eevee, Blastoise and Lugia faces.
This XD hook does not edit Colosseum's square portrait atlas or interface PNGs.
The original source resource `0x21581200` and native header are preserved. The
red iris retains its native color through fitting. The added CI8 resources split palette entries and remap pixel
indices by anatomical region, so its dark eye mask can differ from white teeth
even when the original pixels shared a palette entry. Ordinary Lugia's face is
a different resource.

The native `ModelSequence` constructor already receives a shiny decision for
battle and Pokémon-menu displays. Its rare-resource lookup lacks an alternate
for model 417. A guarded hook at the resource-load boundary selects the added
model when that decision is true and skips the generic palette transform.
It uses that specimen's native decision directly. It never consults Shadow 73
as a substitute for another Lugia's PID or shiny status.

Authored field scenes use separate DAT resources in `people_archive.fsys`:

| Native model | Original resource | Shiny resource |
| --- | --- | --- |
| `darklugia` | `0x166C0400` | `0x7DF60400` |
| `darklugia_0100` | `0x1F540400` | `0x7DF70400` |
| `dlugia` | `0x220E0400` | `0x7DF80400` |

The first DAT is byte-identical to the battle PKX's DAT. The other two have
their own authored geometry and motion. Each receives the same audited
body/belly color conversion, preserving its original pose, skeleton, eye
texture and animations. All original archive members remain intact.
`peopleReadObject` and `peopleOpenSub` select the appropriate alternate before
the native resource load. These three authored XD001 resources use the saved
Shadow 73 PID and player OT. Before that encounter has generated its PID, they
can use its already chosen seed status. A generated encounter with no available
player record keeps the native display rather than guessing.
Their guarded hook positions are adjacent to the existing Gateon/Spinda
selectors so the two features can compose. Other resource IDs keep their
original path. No global resource getter or loaded-RAM palette patch is used.

Gateon's scripted Shadow encounter has its own route. If Shadow 30 is randomized
to Lugia, its field actor uses the real dark PKX converted to DAT, with an added
shiny alias `0x7DF90400`. The selector reads Shadow 30's saved or seeded identity,
independently of XD001. Its size follows the existing Gateon height limit.
Ordinary NPC Pokémon, including Wakin's and Miror B.'s companions, do not receive
this Shadow-only replacement.

The legacy face ID 345 fallback belongs to authored XD001 displays that lack a
specimen pointer. Specimen-aware battle, menu and Snag List portraits use their
own PID/OT path. The face hook selects the texture before loading, so the native
load/copy/cache and drawing pipeline all use the same processed texture. None
of these display hooks generates a PID, rerolls an encounter or writes a saved
Pokémon.

## Appearance after purification

When retention is enabled, four guarded display calls use a cosmetic predicate:
the full specimen must be Lugia and carry a real Shadow ID 1-83. They cover the
menu model, battle model, face selection and face descriptor. The native shared
`isShadow` predicate remains untouched for every gameplay caller. Lugia with
Shadow ID 0 stays ordinary, even if its PID matches a former Shadow Lugia.

The native Snag List clears the Shadow ID on its temporary purified display
copy. One additional guarded hook preserves the selected Shadow ID on that
copy for Lugia only. It does not change the stored Pokémon or Shadow record.

The Purify Chamber loads a second model for Lugia's final reveal, with a
hardcoded ordinary model ID 249. A separate guarded hook changes that request
to 417 only when retention is enabled and the full specimen still carries a
valid former Shadow ID. The constructor receives the unchanged native PID and
shiny decision. Both retail Lugia PKX files contain 17 animation metadata slots,
including the final reveal slot. With retention disabled, the ceremony keeps
its ordinary model request and shiny Lugia becomes white and pink.

## Native admission checks

| Revision 0 | Constructor | Resource-load hook | Native resource loader | PID/OT shiny check |
| --- | --- | --- | --- | --- |
| Europe | `0x801DA970` | `0x801DABDC` | `0x801D5D74` | `0x80145A20` |
| USA | `0x801D8E20` | `0x801D908C` | `0x801D426C` | `0x8014415C` |
| Japan | `0x801D3CC0` | `0x801D3F2C` | `0x801CF10C` | `0x8013F568` |

The field selection points are `0x802A05B8` / `0x8029E664` / `0x80298F44` in
`peopleReadObject`, and `0x802A0FAC` / `0x8029F058` / `0x80299938` in
`peopleOpenSub`, respectively. Their current and original instruction windows
must match before any output is produced.

Retention hooks are independently admitted in each original:

| Display request | Europe | USA | Japan |
| --- | --- | --- | --- |
| Menu model predicate | `0x801418C8` | `0x80140004` | `0x8013B410` |
| Battle model predicate | `0x80207478` | `0x80205744` | `0x802003F0` |
| Face predicate | `0x80112FE0` | `0x8011189C` | `0x8010D0BC` |
| Face descriptor predicate | `0x801139D8` | `0x80112294` | `0x8010DAB4` |
| Purified Snag List copy | `0x80050B48` | `0x800509F8` | `0x8004F5D0` |
| Final purification model | `0x80234E3C` | `0x80232FF8` | `0x8022D994` |

The last hook replaces only the `li r3,249` instruction. The full specimen
remains in r31, with its native PID and shiny decision already in r4/r5. All
six retention hooks are omitted when the option is off.

Each region requires its fingerprinted original executable, the exact current
and original instruction window, the original shiny-check routine, and the
expected model-table resource. Unexpected layouts are rejected. The same native
Dark Lugia archive was independently extracted from all three originals and
matched SHA-256
`d1110fda0ea1ddb0138554780e6000fd4543bc2d6c40a49e2658065024966ac8`.

The shared palette helper changes the audited body/belly materials and belly
CMPR texture. Mesh, skeleton, animation schedules, red-eye texture and palette
remain unchanged. The source and variant have the same PKX length.

## Verification and limits

Instruction-execution tests cover per-specimen native shiny selection, authored
field saved-PID selection and seeded fallback, missing-player behavior,
register/LR preservation, ordinary Lugia, invalid Shadow IDs and unrelated
models. Ceremony tests exercise normal and shiny flags with Shadow IDs 0, 1, 30,
73, 83 and 84, preserving the specimen's bytes and identity arguments.
Installation and composition with existing Shadow shiny, Snag List and
Gateon/Spinda hooks pass for all three regional originals, with retention both
off and on. Every original archive member is preserved.

Muted European Dolphin tests used isolated instances and copied QA cards:

- A mixed party and the Snag List displayed normal and shiny Shadow Lugia,
  purified former Shadow Lugia and never-Shadow Lugia with both option values.
  Ordinary Lugia retained its native model and portrait throughout.
- A real Purify Chamber ceremony with retention off revealed ordinary pink
  shiny Lugia. With retention on, it retained the custom light-body/dark-belly
  model through the heart-opening and nickname screens. Saving confirmed the
  purified flag while preserving Shadow ID 30, PID `CD0D6B85` and OT `E74441CE`.
  The copied fixture started with a ready heart gauge; this test does not claim
  to replay its earlier gauge reduction.
- Greevil's native XD001 presentation, ensuing battle and capture displayed the
  custom shiny model and matching portrait. Additional randomized Lugia in
  Greevil's team, including Shadow IDs 75 and 78, also used the custom model and face.

These checks supplement the earlier native capture/purification replay in
[XD Shadow shinies validation](../XD_SHADOW_SHINIES_VALIDATION.md).

An additional bounded native trace of Greevil's XD001 presentation observed
`peopleOpenSub` loading `0x166C0400` and `0x1F540400`. A replay of the production
patch displayed the light body, dark belly and red eyes during that dialogue,
then the same appearance in the ensuing native battle and its HUD face.

The routing covers all native model 417 requests, the three authored XD001
resources and the known Gateon Shadow actor. It does not establish that every
authored scene uses these paths. Prerecorded movies remain original. Current
screenshots, fixture hashes, regional composition reports and the ceremony
diagnosis are retained under the ignored
`build/v1220-lugia-general-20261115/` directory. Earlier evidence remains under
`build/v1220-xd-lugia-shiny-qa/`.

The final round-framed face variants were replayed in separate muted PAL
profiles at 0% and 100%, with an unseen Shadow 73 on copied QA cards. Both
played Greevil's original presentation and entered the native Lugia battle.
Read-only checks confirmed a non-shiny and a shiny identity respectively.
Their HUD portraits stayed inside XD's circular frame, over black, with the
complete head and neck visible. Those earlier display checks do not claim a new
capture or purification. Native screenshots and input/source hashes are in
`build/v1220-story-driver-20261113/xd-round-normal-frames/` and
`build/v1220-story-driver-20261113/xd-round-shiny-frames/`.
