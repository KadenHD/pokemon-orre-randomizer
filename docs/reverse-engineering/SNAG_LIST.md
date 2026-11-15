# Snag List model identities

The Snag List in both games creates a temporary Pokémon for its rotating model.
The retail code supplies an unrelated, explicitly non-shiny personality value
instead of the saved Shadow Pokémon's identity. A shiny in the party can
therefore appear in ordinary colors in this panel. Spinda's spots can also
disagree with the captured Pokémon.

`orre_randomizer/snag_list.py` corrects that display object. It reads the saved
Shadow PID and the current player's full trainer ID, without regenerating a PID
or changing a captured Pokémon, purification record, save flag or battle team.
Unown retains the ROM's existing seeded form policy; Spinda receives the exact
saved personality value, so its spot positions are preserved too. Shadow Lugia
uses its special Shadow model until purification; a saved shiny individual can
select the custom white-body, dark-belly material variant without changing its
identity.

Captured and purified entries use their saved identity. An uncaught, generated
Shadow can use the same owner when custom Shadow shiny rules are enabled,
because those rules already assign the player's trainer ID in battle. Without
that owner policy, uncaught entries retain the retail display rather than
guessing their original trainer's identity. Unknown entries and missing player
data also keep the native fallback.

## Native evidence

The entry points below were checked against the independently fingerprinted
revision-0 executables. Addresses are PowerPC RAM addresses, not file offsets.

| Game / region | Display call replaced |
| --- | --- |
| Colosseum Europe | `0x8003ED64` |
| Colosseum USA | `0x8003CA90` |
| Colosseum Japan | `0x8003BDF0` |
| XD Europe | `0x80050B08` |
| XD USA | `0x800509B8` |
| XD Japan | `0x8004F590` |

In the USA Colosseum DOL, `pdaSnagListRun` calls the stored-PID reader
`darkPokemonSaveGet8` at `0x8003CA84`, discards the result, then calls
`pokemonBiosSetRnd` with the panel's shared random value. The replacement only
changes that final setter call. The stored-PID reader and generated/captured
flag readers are resolved from the verified native caller instructions.

In the USA XD DOL, `GetPokemonPointer__10menuPdaDPMFl` calls
`pokemonCreateRndFit` at `0x800509B8` with arguments `-1, -1, 0, 0`. The result
is then copied into its temporary display Pokémon. The replacement returns the
actual saved PID instead and supplies the player's trainer ID to that display.
`DarkPokemon::getRnd` reads offset `0x1C`; the native capture-status getter
extracts the top three bits of byte zero, with status 3 or above captured.

Original DOL hashes and the complete call windows are checked before applying
either hook. The temporary model uses PID offset `0x04` and OT offset `0x14`
in Colosseum; XD's caller sets PID offset `0x28` and the hook sets OT offset
`0x24`. Existing arena reservations are extended with their native stack/BSS
guards preserved.

## Validation

The thirteen tests in `tests/test_snag_list.py` execute the emitted PowerPC
instructions with native-call ABI clobbers. They cover saved shiny and ordinary
PIDs, PID zero, Unown and Spinda species, player/record availability, uncaught
entries with and without custom ownership, stack/link/nonvolatile registers,
and fallback generator arguments. Saved Shadow records and player IDs remain
unchanged. The patch was also applied to all six fingerprinted retail DOLs.

These instruction checks establish the display data passed to the native model
loader. They are separate from visual Dolphin validation of the resulting
rotating model.

European Dolphin runs also compared the same saved specimen in the party
summary and in the native Snag List: a purified shiny Entei in Colosseum and a
captured shiny Shadow Spinda in XD. The native lists retained their shiny
colors; Spinda retained the same spots and Shadow aura. Every run used a
private copied card, offline movie input, muted audio and an isolated Dolphin
profile. Protected originals and personal saves had no changes.

These were controlled QA fixtures, not complete playthroughs. The old
Colosseum fixture had mismatched party/cache species; its new private copy
aligned only that specimen's species with native Shadow 21 (Entei), retaining
its PID and trainer ID. The XD specimen's party and Shadow records were used
unchanged; a new copy enabled only the native PDA-unlock flag so that its Snag
List could be opened. USA and Japanese builds have executable checks, but no
separate visual run for this correction.

## Optional Colosseum bonus encounter

The native list scans Shadow IDs 1 through 96 and allocates room for 96 rows.
The original story roster uses 48 of those IDs; the additional encounter uses
reserved ID 96. The existing list can therefore display a 49th encounter
without replacing any original entry or changing Ho-Oh's original roster.

The model-request hook is installed for the general Lugia display policy.
Only the builder-cache fallback for the bonus entry requires
`postgame_shadow_lugia=True`:

| Region | Builder cache read | Model request |
| --- | --- | --- |
| Europe | `0x8003F2D8` | `0x8003EDC4` |
| USA | `0x8003D004` | `0x8003CAF0` |
| Japan | `0x8003C364` | `0x8003BE50` |

An older save can have an empty species cache for previously unused ID 96.
The builder-local reader returns Lugia for that one empty cache, then lets the
original seen/progress checks decide whether to list it. Every existing cache
value and every other Shadow ID remains unchanged; no save record is written.

The retail display ordinarily uses a placeholder Shadow ID. For every Lugia
row, the temporary Pokémon instead receives its actual Shadow ID and its native purified
gauge sentinel (`-100`) only when the list's native state is purified. The
ported XD model selector can consequently show dark Lugia while it is a
Shadow and ordinary or shiny Lugia after purification. The saved PID and owner
remain the source of shiny status in both states.

The Snag List's menu worker bypasses the ordinary Pokémon-summary loader: it
copies model index, PID and shiny flags into a compact display request. The
bonus model layer also intercepts both model-index reads in that native
request. It supplies the additional dark-resource marker only for an
Lugia with Shadow provenance, until purification by default, or afterward when
the advanced appearance-retention option is enabled. The actual species and
saved identity stay unchanged. Never-Shadow Lugia remain ordinary.

The extra tests execute the real cache and model stubs across all original
IDs, native cached values, purified/unpurified states, unrelated Lugia rows,
other species and null pointers. Adjacent flags, saved PID and trainer ID are
preserved. The native 96-row allocation instruction and each call window are
checked in all three regional originals.

The European bonus encounter was also checked using the actual captured
Lugia's native runtime identity, followed by its completed native purification.
The Snag List added ID 96, retained its saved PID and owner, and returned to
ordinary Lugia's pink shiny palette after purification. The pre-variant dark
model check exposed the compact-request path described above; its model-index
hooks corrected that path.

This used an endgame QA copy with the access flags staged, not a full campaign.
Its original 18 visible cached entries stayed byte-for-byte identical and in
the same order; the bonus made 19. Other original entries remained subject to
their native seen/progress filters. The builder's 96-row capacity is verified
in the executables, without claiming this copy represents 48 played captures.

The final European display check reused a level-70 Lugia captured in the native
bonus battle and its subsequent native purification. The saved PID and trainer
ID remained identical: the Shadow state used the white-body, dark-belly XD
variant, while the purified state used Colosseum's pink shiny Lugia. Its native
party portrait and Snag List matched those states. Menu lighting and the Shadow
aura tint the white body purple; the normal dark-body variant remains visibly
distinct. A separate, explicitly controlled non-shiny copy changed only the
party PID and matching saved Shadow PID for that comparison. It was not claimed
as a naturally captured non-shiny specimen.

The same display build was checked in the native party screen, combat HUD,
target selection and a successful Master Ball capture. The copied rendering
fixture reduced the opponent to the unchanged Lugia record; the separate
six-member gameplay validation is documented with the bonus event. The saved
identity survived this additional native capture too. The portrait uses
an anatomical mask for a white neck/lower jaw and charcoal eye triangle,
retaining the red iris, mouth and teeth. Native
texture decoding, pixel invariants and offscreen Qt rendering cover that last
neck-only image refinement; it is not claimed as another Dolphin replay.
The later backdrop correction adds an opaque black matte to derived normal and
shiny faces in both games, including the thin purple disc edge. Original source
portraits and the native outer Shadow frame remain intact. Its current rendering
checks are recorded with the postgame and XD Shadow Lugia model follow-ups.

## Original completion totals

The native global capture and purification counters scan Shadow IDs 1 through
96, even though the story roster contains 48. Populating bonus ID 96 would
therefore change title-screen, PC and saved-summary totals to 49. When the bonus
option is enabled, two counter-local flag calls return zero only for ID 96.
Every other ID still calls the original reader. The real capture/purification
flags for Lugia remain available to its Snag List row, battle and Relic ceremony.

| Region | Purified-counter call | Captured-counter call |
| --- | --- | --- |
| Europe | `0x801F3AA8` | `0x801F3B08` |
| USA | `0x801EF234` | `0x801EF294` |
| Japan | `0x801EAAF4` | `0x801EAB54` |

Each full 96-byte counter body and its native flag-reader field is checked
before patching. Independent PowerPC tests cover zero, 17, 47 and 48 original
entries, with bonus capture and purification flags both set and unset. The
original totals remain unchanged; nearby IDs such as 48 and 95 retain their
native behavior, and no saved flag is written.

The complete direct-call audit places these aggregate counters in title and PC
save/summary code. Other calls to the raw capture/purification readers concern
individual Pokémon, party/storage handling, TV news, battle and purification;
they retain the real ID 96 flags. `scriptGetDarkPokemonNum` counts the current
six-member party and must continue to include an unpurified Lugia. The native
fixed-48 roster used by Ho-Oh and the bulk original-roster flag operations is
unchanged. The bonus is consequently an additional encounter, rather than a
new prerequisite for the original completion conditions.

The title and PC callers contain no captured-equals-purified early exit that
could block a bonus purification at an original total of 48/48. The Relic
ceremony instead checks the party and individual Shadow flags, which retain
the real bonus state.
