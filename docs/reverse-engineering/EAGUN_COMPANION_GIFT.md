# Eagun's partner and purification gift

With accessible event gifts enabled, the first purification reward is Eagun's
companion. Its existing `pikachu-event` constructor supplies the species; there
is no additional draw. The patch copies that final species and native name ID
to Eagun's story-battle party row **2822**, referenced by trainer **780** in
battle **525**. Its level, moves, PP, item and native battle conditions remain
unchanged. The second purification reward remains independent.

The Pikachu actor packaged with Eagun's home, the Relic Stone and the finale
uses this same gift species. Native cries and written cry captions follow the
species in every original playable language. Large models use the existing
field scale cap; the original actor, camera and animation cues stay in place.

## Appearance identity

When the shiny result is fixed by the seed or a guaranteed 0/100% setting,
Eagun's battle slot takes the gift's shiny decision. Its field models use that
same decision. Unown uses the existing shared seed-selected form in battle and
field scenes.

For Spinda, the earlier battle uses the gift's private PID seed, unconstrained
gender/nature arguments and native gift owner ID `0x7991`. The field texture
uses that same predicted full PID. This exception is restricted to ordinary
Spinda in row 2822 and exists only with accessible event gifts enabled. Other
trainers retain their existing Spinda owner and seed rules; Shadows retain
their native saved identity handling.

The party-copy hook checks the native CK3 trainer-row field at `+0xD6`. Its
setter is independently checked in all three retail executables:

| Region | Native setter |
| --- | --- |
| Europe | `0x80121470` |
| USA | `0x8011D494` |
| Japan | `0x8011AC68` |

Each setter's exact body stores the row at `+0xD6`. Emitted-PowerPC tests cover
the PID-generation owner, the later party-copy owner, caller qualification,
neighboring rows, Shadows, unrelated species, volatile-register clobbers and
unchanged native arguments/stack/nonvolatile registers.

Custom shiny rates now always use the seed. `Options` normalizes the retired
`seeded_shinies=False` value to `True` when customization is enabled, including
after an older profile's checksum has been verified. The rate and encounter
keys remain unchanged. The unlink control is removed from the interface.
Thus intermediate custom rates also supply the same determined decision to
the gift, Eagun's battle partner and field conversion. Disabling customization
retains native behavior; existing saved Pokémon are not regenerated.

## Home visibility without hiding Eagun

The native home script's initial `SHOW` for companion actor **3** starts at
`0x138`. Only its visibility-argument instruction at **`0x158`** is redirected
to an appended expression, returning to the original call at **`0x15E`**:

`visible = !(gift receipt 2740 && safe story completion)`

The safe predicate includes the native P★DA exchange flag **3535**. A pending
native Master Ball handoff (**2531 && !3541**) retains the original companion
visibility too. Older saves that received the legacy reward before exchanging
numbers therefore retain their native story presentation.

This changes neither Eagun's actor **0** nor any actor definition, talk entry,
story branch, event loop or item handoff. In particular, the native interaction
pointer at `0x38`, setup epilogue at `0x678` and P★DA exchange code remain byte
identical. The event-gift v2 patch still preserves the home CMS itself; the
separate companion layer owns this one guarded operand. It cannot reinstall
the old Eagun-hiding setup or interaction redirect.

Tests execute all 1,024 receipt/story/handoff combinations. Native admission
and byte whitelists are checked for Europe, USA and Japan. Additional European
in-memory compositions convert the actual Pikachu, shiny Unown and normal/
shiny Spinda resources in all three affected rooms, preserving source files.
These establish format and behavior-model coverage. An additional muted PAL
Dolphin replay awarded shiny Spinda with the predicted PID `8351FAC0` and native
owner `00007991`. Its green field model and localized cry appeared at Eagun's
home before the gift. A separate home-entry fixture, carrying the exact native
awarded party and observed receipt, hid that companion while retaining Eagun.
The room switch was a fixture precondition, not a claim of walking back through
the map. No personal save or existing ROM was changed.
