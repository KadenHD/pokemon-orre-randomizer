# TM and compatibility — PAL GC6P01, 31 October 2026

This survey and the module `orre_randomizer/engine/tm_rules.py` concerning the original DOL
SHA-256 `a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5` and `common_rel` original
SHA-256 `ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b`. The originals are read,
never written. The observations below are static.

## Substantiated structure and local measures

The primary diagram
[CMTMs.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/enums/CMTMs.swift)
places the PAL table in the DOL at `0x3B20D0`, with eight bytes per input and a capacity index u16
big endian at `+6`. It defines 50 TM and 58 TM/HM together: there is therefore **8 HM**, and not 89
compatibilitys. TM correspond to objects `0x121..0x152`. The replacement of a capacity also updates
its object description there. Copying a capacity description identifier directly to an object is not
enough, because text resources are different.

Local reading confirms 50 capabilities TM The first six bytes of the entries TM valent `00 00 00 00
00 00`, HM `01 00 00 00 00 00`The eight capacities HM are, in order, `15, 19, 57, 70, 148, 249, 127,
291`. Entries TM/HM occupent `[0x3B20D0, 0x3B22A0)`. The exact tuples are checked by the engine
before editing. The complete observation and fingerprint of the DOL are kept in
`analysis/generated/v03-references/pal-tm-original-observations.json`.

The scheme
[CMPokemonStats.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMPokemonStats.swift)
indicates a registration of species of `0x11C` bytes, types to `+0x30/+0x31` and compatibilitys
starting from `+0x34`, at one Boolean byte per TM/HM. The 50 TM occupent donc `+0x34..+0x65`, then
the eight HM `+0x66..+0x6D`. The fields of objects held start at `+0x70` and should not be affected.

In the local ADR, the table of species is at `2033100`, contains 413 entries, of which 386 species
with a national number between 1 and 386. The 58 bytes of each of these species are exclusively 0 or
1. The 27 additional entries are preserved. The bytes of HM and the following two bytes are not
modified.

The diagram
[CMItem.swift](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMItem.swift)
places the 397 PAL objects at `0x3ADDA0`, by recording `0x28` bytes. The description is a u32 big
endian at `+0x14`, distinct from the name at `+0x10`. The 50 description identifiers TM read locally
are `10195..10244`.

## Text in the five languages

The original resources `pocket_menu.fsys`, `pocket_menu_ge.fsys`, `pocket_menu_fr.fsys`,
`pocket_menu_it.fsys`, `pocket_menu_sp.fsys` each contain a table of 631 entries with the
corresponding tag UK/GE/FR/IT/SP. The **50 identifiers TM are present in each of the five tables**.
The control checks their terminals and their non-empty data. The text control sequences are left in
place. The hashes of the archives, members and 250 text intervals are kept in
`analysis/generated/v03-references/pal-tm-description-locales.json`.

The module switches only the 50 capabilities TM natives. Each ability carries the description
identifier of its former TM. Texts themselves, their return to the line, their translations and
names CT01..CT50 This method avoids the manufacture or truncation of translations. **50 capacities
already proposed in TM**, without adding any additional capacity to the catalogue of TM.

This check covers the original local resources. The engine receives REL/DOL, not the text archive.
Therefore, it does not recheck these five archives for each user ROM. It does not repair an already
modified archive.

## Rules implemented

Contract: `apply_tm_rules(original_rel, current_rel, original_dol, current_dol, seed, options,
tables=None) -> (rel, dol, report)`. The wrapper controls both original hashes and the schema
provided. It accepts an already enlarged current DOL, with a new section `text2` and its header,
without rewriting them.

- `randomize_tm_moves`: Reproducible permutation of 50 capacity/description pairs. A Sattolo cycle
  ensures that none TM retains its original capacity. The 50 native capabilities remain present once
  each.
- `tm_compatibility_mode="original"`: no compatibility byte changes, even if the TM are mixed or the
  offensive warranty is checked.
- `"type"`: a TM is compatible if the type of its final capacity is among the **finaux** types of
  the species, after a possible randomization of the types.
- `"universal"`: the 386 real species can learn the 50 TM. This includes species that are normally
  unable to learn from TM.
- `"random"`: each species/number couple of TM has a 50 per cent probability, with a deterministic
  draw independent of other couples.
- `tm_ensure_offensive=True`: in the three modes of rewriting only, adds if necessary compatibility
  with an offensive TM. He prefers the type of the species. For lack of a candidate, he explicitly
  authorizes a TM of another type and reports it. He never alters the abilities themselves.

The drawings have a clean SHA-256 domain, with separate keys for permutation, compatibility and
warranty. Activated compatibility or its warranty does not change the permutation of TM. The
warranty retains the ordinary damage at power greater than 1 and the damage based on the level
already recognized by the engine. It removes the K.O. in one stroke, suicides and Wrestling. The 50
TM natives do not contain any of these excluded capabilities. The local pool provides 28 offensive
capabilities according to this definition, spread over 16 types. The Insect type does not have
offensive TM there, hence the possible explicit withdrawal.

This guarantee means "at least one TM offensive compatible in the catalogue." It does not give the
object to the player, does not change its availability in the scenario, does not promise a TM of the
right type for each species and does not replace the four abilities learned by the Pokémon.

## Editing points and validation

The DOL only authorizes the two capacity bytes of each of the 50 TM and the four bytes of
description of each of the 50 objects TM, or not more than 300 bytes. Other object fields, including
prices, names, effects and functions, are protected. The REL only authorizes the 50 bytes TM of the
386 real species in rewriting mode, or 19,300 bytes. The reports contain the permitted offsets, the
number of changes and a full verification of the external bytes. The input sizes are retained and
the 8 HM remain strictly intact.

`python -m unittest tests.test_tm_rules -v`: **10 tests passent**, including a verification of the
original PAL. They cover the non-fixed point permutation, the capacity/description matching,
reproducibility, the independence of the hashes, the current types, the offensive fold, the strict
original mode, invalid signatures, the list of authorized bytes and an enlarged current DOL. The
learning menu test in Dolphin remains a separate integration validation. This sub-survey did not
launch Dolphin or receive TM in play.

The three primary sources are pinned to commit `f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0`. Their
copies, links and SHA-256 are listed in
`analysis/generated/v03-references/tm-research-manifest.json`. The Python implementation is
original. No third-party Swift code is integrated into the application.
