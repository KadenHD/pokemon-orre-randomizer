# Capacity and gifts PAL — comments of 31 October 2026

Perimeter: the DOL PAL GC6P01 revision 0, SHA-256
`a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5`, and the tables of the original
`common_rel` already fingerprinted. The observations are static unless otherwise stated. No Dolphin
essay was launched in this sub-investigation.

## Instructor data

The four capacity indices are the u16 to `+0x36/+0x3E/+0x46/+0x4E` of a record of 0x50 bytes. The
blocks are spaced by eight bytes. The local examples show their previous six bytes null for ordinary
abilities. The community schema reads and writes only the u16. It does not identify a PP field of
block builder in these blocks. Do not invent a PP field to be modified.

Markers read as `0xFFFF` are, in the cases examined, complete u32 words `0xFFFFFFFF` to
`+0x34/+0x3C/+0x44/+0x4C`. Their meaning to execution remains unestablished here. Protect them and
leave intact the other bytes of the block.

The normal pool must exclude 0, 355, 357 (not available/special), 356 (black load) and 165 (fight).
Restriction options can remove the effects of K.O. in one shot (indices 12, 32, 90, 329, observed 38
effect) and suicide attacks (120, 153, effect 7).Indices, names and effects are corroborated by the
local table.

## Starters and gifts: two different mechanisms

Les starters ont quatre instructions `li r5, capacité` the existing DOL bases of Umbreon/Espeon plus
`0x14/0x24/0x34/0x44`, therefore the u16 to `+0x16/+0x26/+0x36/+0x46`. The `li r4, emplacement`
previous give 0 to 3. The following eight branches target all the native RAM setter `0x80127ECC`.
Origin values: Umbreon `[44,290,269,289]`, Espeon `[93,216,115,270]`.

The four gifts use the native builder RAM `0x80128238`, then their own metadata operations. The
primary reader describes abilities derived from level learning. Their bases do not have the same
four immediatities as starters: writing to the same offsets would corrupt unrelated instructions.
Changing only learnings would also affect other specimens of the same species, which does not
provide an independent gift option.

`engine/gift_move_hooks.py` therefore brings a specific branch to the manufacturer of each gift
requested, in a new section DOL `text2`. The wrapper calls the original manufacturer, assigns the
four capabilities with the native setter, and then makes the original result of the manufacturer. It
keeps SP, LR and the non-volatile registers r30/r31. The original arguments are given to the
manufacturer. The parameters, event conditions and metadata operations remain in place.

## Explicit reservation of added code

The initialized sections and the three zones of BSS fill their useful range up to `0x804CBCB8`. The
holes between .sdata and .sdata2 are not free. The initial SP is `0x804DBCB8`. The default native
arena low value is `0x804E3CC0`, built in OSInit by the words `3C60804E / 38633CC0`.

The added section starts precisely at `0x804E3CC0`, above the BSS and the original piles. The native
sheet `OSSetArenaLo` to `0x8009E4F0` contains `906D8168 / 4E800020`. Its first instruction now
connects to a guard that stores the maximum of the original argument and the end of the section
aligned to 32 bytes. R3 remains unchanged. The getter to `0x8009E4E0` reads the same variable.

The original branches to `0x8009D088` and `0x8009D0C4` call this setter, before the ClearArena call
of `0x8009D2D0`. ClearArena reads this getter before it is set to zero. The terminal therefore
includes the code added before the first erasing of the arena, including the paths that take a
terminal provided in low memory or the withdrawal of debug. The boot program cannot erase this
section by its original BSS zones, which end below. The observed high default terminal is
`0x81700000`, far above the added section.

The four wrappers take 128 bytes each, keeping 32: 544 bytes added to the DOL for four gifts. Only
three words of the text2 descriptor, the first instruction of the arena set and the selected
manufacturer calls change in the pre-existing DOL. The module checks this exact list and all the
starting opcodes. The ISO rebuilder must move the enlarged DOL into a safe area and adapt the boot
pointer, rather than overwrite the FST following the old DOL.

Six tests pass: independent interpretation of the PPC sub-assembly issued, calls and ABI under
crushing of the volatile registers, two branches of the guard, branch terminals, DOL descriptor,
list of permitted bytes and original signatures. These tests do not replace a cold boot and the
observation of a gift actually received.

The Community source also proposes to delete TRK functions between RAM `0x800C1948..0x800C7B9C`. The
PAL card corroborates their names. This approach is not used: the added and reserved section avoids
deleting an old subsystem.

## Held items

Local DOL table: `0x3ADDA0`, stride 0x28, 397 entries. Name u32 `+0x10`, prohibition to wear u8
`+1`, effect held u8 `+0x0B`. The names are resolved in the French texts of the REL. Audited
examples: 183 Vive Griffe, 186 Bandeau Choix, 196 Bandeau, 198 Lentilscope, 200 Rests, 219 Grelot
Coque, 179 Poudreclaire, 180 Herbe Blanche, 185 Herbe Mental, 187 King’s Rock, 221 Incense Doux.

Berries 133..142 and 168..172 have maintained effects. A useful generic subpool can combine them
with these objects. The Choosing Band deserves a filtering according to physical attacks if a
systematic utility is promised. Items 110 and 254.258 have a zero-acting effect (Pepite and
scarves). Generally avoid 181 (Macho Brace), 191 (Soul Dew), 192/193 (objects Clamperl) and 202
(Balle Lumière), whose interest is training or limited to certain species.

## Sources and provenance

Primary sources pinned to commit `f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0` de
[Pokemon-XD-Code](https://github.com/PekanMmd/Pokemon-XD-Code/tree/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0)
: `CMTrainerPokemon.swift`, `XGDemoStarterPokemon.swift`, `CMGiftPokemon.swift`, `CMItem.swift`,
`CMItems.swift`, `XGMove.swift`, `XGMoves.swift`, `XGAssemblyCode.swift`,
`XGAssemblyCodeExtensions.swift`, `XGPatcher.swift`. Carte primaire :
[GC6P01.map](https://github.com/StarsMmd/Colo-XD-PBR-symbol-maps/blob/93d5da920e7f03b8854b79963d94739ec66abd1d/GC6P01.map).
Copies and fingerprints: `analysis/generated/v03-references/`The application code does not include
the Swift implementation of these tools.
