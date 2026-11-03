# Application v0.4: TM, chests, shops and bosses

This version adds ten parameters: seven change/protection booleans, two other boss booleans and a
compatibility mode. The total is 52 parameters, including 47 booleans, in fourteen native
categories. The engine is `tm-items-boss-rules-v6`.

## TMs

- `randomize_tm_moves` swaps the original 50 capabilities TM without a fixed point. This is not a
  draw among all the attacks in the game.
- Each object description TM follows its capacity, in all five languages. The strings and object
  names remain intact. Only the description identifiers are moved.
- `tm_compatibility_mode`: `original`, `type`, `universal` or `random`. The type mode uses the final
  types, even if they are randomized.
- `tm_ensure_offensive` guarantees a TM offensive compatible in rewriting modes. A guy without TM
  Native offensive, notably Insect, can be untyped. This fall is reported in the report.
- The eight capabilities HM and their eight compatibility bytes remain intact. The `original` mode
  retains all compatibility bytes, even if the warranty is checked. Compatibility does not give the
  object TM to the player.

## Boxes and shops

`randomize_field_items` changes the object identifiers in the verified table of the 74 PAL
treasures. With the recommended protections, 38 placements are eligible. The keys, Flutes of Time,
stones and empty boxes are protected. The quantities, models, coordinates, rooms and reception flags
do not change. The objects given by scripts of characters remain outside the perimeter.

`randomize_shop_items` transforms the six stocks identified 3, 4, 5, 6, 7 and 9. A doublon-free
global mapping preserves the suffixes common to the catalogues and remains in the native allocation
of 122 entries. The other eight lists retain their current stock. Menus, coins and items at zero
prices remain protected. Special pocket purification perfumes also remain of origin.

Replacements retain an identical category of use. Three protections are adjustable.

- `items_similar_value`: price between half and double the native price, for trunks and stocks.
- `keep_capture_items`: Keep the Balls present for both surfaces.
- `shop_keep_healing`: keep care and use items sold in combat.

The two additions of existing stones remain independent. Their composition with the randomization of
stocks preserves the six stones available in the selected shops. The five language archives receive
the same tables. Their eleven other members remain identical after decompression.

## Bosses

The two settings apply to Bouledisco, Dakim, Venus, Teck, Helgonza, Jakylla and Nosfrat: 32
identified variants, 161 populated slots, 16 of which are obscure protected and 145 eligible
non-Shadow Pokémon. No single level threshold identification is used.

- `boss_stronger`: current +10 per cent, after the global multiplier, limited to 100. Minimum IV 20
  and minimum EV 64/stat if the total does not exceed 510. Existing values are not lowered.
- `boss_team_variety`: replace the editable family duplicates according to the species filters.
  Capabilities are recalculated for the rerolled species if their randomization is activated, with
  the final types.

The Shadow Pokémon, special markers, empty slots, scripts and team sizes are preserved. Duplicates that
cannot be solved without touching these protections are reported and retained. The rule of the 48
dark families remains independent.

## Presets and reproduction

The recommended preset adds the TM according to the types, chests, stored stocks and variety of
bosses. The boss reinforcement remains deactivated. New changes remain deactivated in the core
values of the LTC, to keep old usages. Examples of options.

```
--randomize-tm-moves --tm-compatibility-mode type --randomize-field-items
--randomize-shop-items --no-shop-keep-healing --boss-stronger --boss-team-variety
```

The local JSON report in `build/v04-qa/` records the seed, options and validation hashes.

## References and limitations

The binary observations, pinned primary sources and search terminals are detailed in
[TMs](reverse-engineering/V04_TM_RESEARCH.md), [objects](reverse-engineering/V04_ITEMS_RESEARCH.md)
and [boss](reverse-engineering/V04_BOSS_RESEARCH.md). Validation of bytes and invariants does not
certify balancing or a complete scenario played. Dolphin controls are recorded separately with
observed results.

## Local validation

**147 tests Python et trois tests Rust passent.** They cover the 50 TM, 386 species, eight HM
preserved, matched descriptions, compatibilitys with final types, chests and protected markers,
duplicate-free stock matching, 122 entry capacity, five languages and boss rules composed with other
randomizations. Temporary conversion profiles have their own error and cancellation tests.

| Test | Result |
| --- | --- |
| Recommended presetting, seed test history | ISO SHA-256 `9699bea0c4b16f7baf8e98cf7555d665c977d26d944b0ff444ae2a90760e81c1` |
| Second construction from the same source | SHA-256 identique |
| Runable Windows, even seed/preset | Same ISO, 100 % success, 10.78 s observed |
| All changes disabled | ISO strictly identical to the source `1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9` |
| RVZ → RVZ with advanced rules and 145 reinforced boss slots | ISO after recompression SHA-256 `b926659b65792834b07d61c7107a1ab89999074a9bbea61578f83ab81e7a18a1` |
| Same RVZ test after correction of the conversion profile | Even ISO, roundtrip checked, 21,72 s, no blocking window |
| Runable Windows final, RVZ → RVZ, preset recommended | Even recommended ISO, roundtrip checked, 100% success, 15.56 s, no blocking window |

Each ISO is compared on its 1 459 978 240 bytes at the source and only the exact replacements
expected. The source is ground again at the end of the processing. The RVZ produced are recompressed
and compared before publication. The 2 011 files of `game/` and the 20 files inventoried in the
original Dolphin profile keep their fingerprints, verified after the test has been closed.

### Observation Dolphin

Dolphin 2609a cold-started the advanced RVZ, without quick-MI, with a memory card copied in an
isolated profile. The bag displays **CT06 Fullness**, **CT41 Lance-Flamme** and **CT49 Queue de
Fer**, in accordance with the report. The visible description for TM06 is Calm Mind. Native
control always forbids learning to Shadow Pokémon. The test on the loaded team confirms this
restriction. No effective learning after purification is claimed.

The stocks and bosses are controlled in the data and by the tests. Their purchases and fights of
this version have not been replayed. There is also a need to browse the chests at stake, the late
gifts and the complete scenario. Captures and local manifests: `build/v04-qa/evidence/` and
`build/v04-qa/validation.json`, excluded from the distributions.

### Conversion non interactive

One trial exposed a DolphinTool `IOS_FS: Failed to rename temporary FST file` box in its temporary
Wii profile. Conversion and complete verification were successful after closing this diagnosis, but
a modal box is not suitable for a worker in the background.

The converter now prepares only its own temporary `dolphin-user/Config/Dolphin.ini` with
`Interface/UsePanicHandlers=False`. Other settings are kept, as well as checks of the return code,
the output existence, each ISO byte and the RVZ roundtrip. The personal Dolphin profile is not
changed. The key is declared in the [configuration primaire de
Dolphin](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/Config/MainSettings.cpp).
