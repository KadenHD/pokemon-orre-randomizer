# Field Pokémon animations

The battle models do not provide a common walking or running slot. PKX
metadata selects Idle, attacks, damage reactions and fainting animations;
extra slots have species-specific meanings. Reusing an attack as a walking
animation would not be a valid general solution.

The converter resolves the PKX **Idle** slot before choosing a DAT animation.
The Idle slot is not the same thing as DAT animation zero. On the European
Colosseum disc, 144 of the 527 PKX model members use a nonzero Idle index.
For example, Plusle's battle Idle is DAT index 3, while its first three DAT
clips are short overlays. Earlier versions repeated raw index zero in every
field slot, which could make a replacement look frozen or repeatedly blink.

The corrected converter reads the Colosseum metadata after the aligned DAT
and particle payloads, or the XD metadata at PKX offset `0x84`. It uses the
matching joint, material and shape animations, and retains valid relocations
when attaching a model or changing its size. Shiny conversion covers texture
frames from nonzero animation slots as well as the base textures.

## Retail field models

A read-only census of the European Colosseum room archives found 24 distinct
Pokémon field-model names whose species can be resolved through the retail
model table. Of those, 21 DATs are **byte-identical** to the corresponding
battle DAT. Their presence in a room does not imply an extra walking clip.

Those 21 are Abra, Ho-Oh, Pikachu, Aron, Oddish, Magikarp, Marill, Zigzagoon,
Jigglypuff, Ludicolo, Torchic, Wobbuffet, Delcatty, Mightyena, Taillow, Lombre,
Lotad, Treecko, Makuhita, Shroomish and Skarmory.

The three different assets belong to Castform, Plusle and Umbreon. A difference
in bytes alone does not identify a walking animation or make its skeleton
compatible with another species.

Plusle's rescue and gift scenes have a dedicated native ten-motion DAT at
resource `0x06F90400` in `M2_guild_1F_1.fsys` and `M2_cave_1F_2.fsys`. If the
gift is still Plusle, the converter keeps those ten native motion slots and
pads unused slots safely. A custom shiny palette is applied to that field
model without replacing its choreography with battle Idle. This path reads
only the selected Colosseum ROM; it does not require XD or downloaded models.

For other replacements, the safe fallback remains their own battle Idle.
The scene still moves the actor along its native path, so a Pokémon without
a compatible locomotion clip can slide. True walking for every species would
require additional authored or retargeted animations; this patch does not
claim to provide them.

## Verification

The European Colosseum and XD supported-species tables were read directly.
For each game, all 386 species converted successfully in regular and shiny
form, and all 28 shiny Unown forms converted successfully. This checks the
native pointer graphs and palettes, not every animation's appearance in play.
The separate Colosseum census converted all 527 retail PKX model members.

The original USA and Japanese Plusle resources were also extracted read-only.
Their dedicated field models converted in both palettes using the matching
fingerprinted regional DOL. Unit tests cover the two metadata layouts,
nonzero joint/material selection, preserved native field slots, attachment
wrappers, missing-motion rejection and alternate-frame shiny textures.

A muted French PAL Dolphin replay used an isolated copy of an existing QA
memory card and the seed `field-idle-spinda-qa`, with the Plusle replacement
filtered to Spinda and a seeded 100% shiny rate. The native handover scene
displayed green shiny Spinda with its seeded spots, its actual Idle animation
and the matching name in the dialogue. A short GIF covers the idle movement
and the scene's translation of the actor. It demonstrates animated Idle, not
an authored walking gait. The source card, test ISO, emulator executable and
personal save directories had no hash changes during that replay.

A second muted replay retained Plusle's species with `gift_plusle=False` and
a seeded 100% shiny rate. Its native hop and approach choreography played in
the handover scene, with the matching Plusle name. Both patched story-room
actors matched the expected shiny conversion byte for byte. The ten original
joint, material and shape motion-pointer tables were retained; the shiny model
also differed from its regular-palette conversion. This checks the shiny-only
scene gate as well as preserving the native motions when species randomization
is disabled. The replay used another copied QA card and no global input; all
protected-file and personal-save hash comparisons were unchanged.

The prerecorded opening movie is unchanged. These selected runtime checks do
not establish that every species has been visually reviewed in every scene.

The animation-slot layout is also described in the
[GameCube model add-on documentation](https://github.com/StarsMmd/Blender-Addon-Gamecube-Models/blob/main/technical-docs/exporter_setup.md#animation-slots).
