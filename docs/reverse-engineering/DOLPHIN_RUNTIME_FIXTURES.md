# Preparation of fixtures and RAM controls under Dolphin 2609a

This search on October 31, 2026 does not change any ISO or original backup. The RAM transformations
described here prepare test conditions in an isolated Dolphin instance. They do not prove that a
normal scenario event is accessible. The observations involved must be recorded separately.

## Private Client and Protocol

`build/dolphin-validation/tools/dolphin_rsp.py` is a diagnostic RSP client, out of distribution. It
does not launch Dolphin. It only connects to `127.0.0.1`, checks `GC6P01` in RAM and keeps the
connection throughout the boot. A line-by-line JSON console allows readings, interruptions,
breakpoints and fixture entries. Any memory writing requires the expected value before modification
and an identical rereading after. Addresses are limited to the cached MEM1 GameCube,
`0x80000000..0x817FFFFF`.

The official sources of tag 2609a, commit `409881c34357d0f105fd473167d15ab0bd9c1628`, state that.

- `[General] GDBPort` activates the TCP server also under Windows. Only Unix socket transport is
  excluded under Windows. The CPU starts suspended.
- The server accepts a connection for the boot. It listens on all interfaces. This configuration
  must be reserved for the temporary QA profile.
- `m`/`M` read/write memory; `p`/`P` read/write a register. Client does not use bundled commands
  `g`/`G` : `g` only exposes the 32 GPRs and `G` reads the buffer from its command character.
- Registers 0–31 are GPRs and 32–63 are FPR PS0 values. Registers 64–70 are PC, MSR, CR,
  LR, CTR, XER, and FPSCR, respectively. A register capture excludes PS1, memory, the MMU, and the
  scheduler.

The local binary contains the strings `GDBPort`, `Waiting for gdb to connect` and `GDBStubUpdate`.
This static finding indicates that the support is compiled. The connection and RAM readings must
still be observed in the log of the executed case.

Sources:
[configuration](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/Config/MainSettings.cpp),
[start](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/Core.cpp),
[protocole](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/PowerPC/GDBStub.cpp).

### Additional response after Ctrl-C

An interruption revealed a delay of a response in the first client. After the `T05` package, reading
a registry received an empty package, then each read received the previous answer. Drainage and two
identical PC readings restored alignment before any memory writing.

Source 2609a explains this behavior: `ReadCommand` calls `SendSignal` for Ctrl-C. This function
replaces the shared buffer and its length. `ProcessCommands` then interprets the `$` character of
this response as an unknown command and sends an empty response. The corrected client consumes this
additional package immediately after a Ctrl-C actually sent. A natural stop point arrival does not
add this drainage. A regression test checks that the registers can no longer shift as well.

Do not reconnect a second client to try to recover a unsynchronized protocol. Do not send a write
until two PC-independent readings and a memory signature do not match the expected context.

The parser also distinguishes the exact RSP errors `Ehh` from hexadecimal data starting with `E`. A
memory capture whose first word was `EC220...` was wrongly refused. The package remained completely
consumed, without protocol offset. Correction and regression are present in the client for the
following processes. A JSONL client already launched does not offer a hot module reload. The boot
must be completed normally before replacing it.

### Windows Polling and JIT Breakpoint Activation

La source 2609a programme `GDBStubUpdate` every 100,000 emulated cycles. Each passage calls
`ProcessCommands(false)`, then `IsDataAvailable`, waiting with `select` and a timeout of **20
microsecondes** even when the CPU has resumed after `c`This polling is not done at every
instruction. On this Windows host, an independent measurement on a private UDP socket, without
connection to Dolphin, gives about **15,3 ms** for `select(20 µs)`, contre **1,7 µs** for
`select(0)`. The 100 samples of each mode are in
`build/dolphin-validation/gdb-select-poll-cost.json`. This explains a potential cost of several tens
of seconds per emulated second. This calculation remains an estimate, not a measure of the speed of
the game.

An emulator patch reserved for QA is prepared under `build/dolphin-validation/patched/Dolphin.exe`.
The portable original and `Dolphin-x64/Dolphin.exe` remain identical to their official footprint
during this preparation. The script rejects any other footprint, checks the uniqueness of the
instruction, and then changes a single byte to the offset `0x3BFE15`, `14 → 00`. Education at
`0x1403C0A0F` devient `mov dword ptr [rbp+0x2CC],0`. The following appeal relates to import
`WS2_32.dll`, ordinal 18 (`select`), and its error branch refers the string `select failed`. The PE
headers and the original optional checksum absent (`0`) are preserved. A static test checks these
properties and refuses to trace the output. `build/dolphin-validation/dolphin-gdb-poll-fix.json`.

This Dolphin binary modified under GPL-2.0-or-later remains private and outside the distributions of
the randomizer. Its new footprint is
`baa731a95136d50ddfe4b16e9449f66b565027f74e705e7708e531d07b49ba8e`. The preparation does not
establish its functioning: the next boot must see the speed gain and stop on breakpoint. The
verification of the delivered ISO also includes a launch with the official emulator without GDB.

The breakpoints JIT64 are conditioned by `IsDebuggingEnabled()`, which requires `[Interface]
DebugModeEnabled = True` and the absence of hardcore mode. The simple `[General] GDBPort` does not
activate this option. Adding a breakpoint via RSP invalidates the JIT cache, but does not change
this configuration. The JIT64 is therefore suitable for testing, provided that debugging is enabled
before the boot. Going to Interpret does not eliminate the cost of polling. The `[Interface]
PauseOnFocusLost` option is by default `False`.

Sources:
[JIT64](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/PowerPC/Jit64/Jit.cpp),
[configuration](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/Config/MainSettings.cpp),
[semantic Windows
select](https://learn.microsoft.com/en-us/windows/win32/api/winsock2/nf-winsock2-select).

## PAL identity and Pokémon structures

DOL original : SHA-256 `a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5`. REL
original : SHA-256 `ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b`.

The DOL instructions confirm the CK3 format used for starter captures and backup fixtures.

| Ownership | Offset objet | Corroboration native PAL |
| --- | --- | --- |
| Internal species | `+0x00`, u16 | setter `0x80121FCC`, called by selector `0x6E` |
| EXP | `+0x5C`, u32 | setter `0x80121E74`, selector `0x79` |
| Level | `+0x60`, u8 | setter `0x80121E24`, selector `0x7A` |
| Four capacities | `+0x78`, pas 4 | helper `0x8012323C`, final calculation `+0x78 + slot*4` for a non-obscur |
| Dark ID | `+0xD8`, u16 | read in the same helper |
| Jauge de purification | `+0xDC`, i32 | same helper, signed comparison with zero |

In startup creation routines, `SP+8` contains the object of 312 bytes after initialization. At
addresses `0x80134DB4` (Espeon) and `0x80134EDC` (Umbreon), `r4` already points to this object,
before it is added to the team. The copy of the first one is made by a call to `0x80134DC0`. Reading
the object before this copy allows to verify the data actually built, without rewriting them.

After creating the starters, the player root reads in u32 big endian to `0x804C8268` (`r13-0x5A58`),
getter `0x8012CFD8`. L'appel natif `0x8012E7A8(0,3,index)` find the trainer to `racine+0x70` via
`0x8012CFA0`, then the Pokémon to `dresseur+0x30+index*0x138` via `0x8012EE34`. The active team is
therefore composed of six CK3 contiguous to `racine+0xA0`. The previous u32, at `racine+0x9C`
(getter `0x8012EE68`), is used as a trainer's identifier by manufacturers: it is not **not a number
of members**. A first counter hypothesis was rejected at runtime playback. Empty locations are
verified by their zero species. Verify that the root and entire range remain in MEM1 before reading.
This string allows to read the team without looking for temporary copies in a dump of the entire
RAM.

The community names of the GC6P01 map are used to guide the search. The above instructions and
fields have been read in the exact DOL.

## Combats de boss

The table of fights is in the symbol REL 50, offset `0x1D6824`, with 566 PAL entries of `0x48`
bytes. Its end corresponds exactly to the symbol 52. The four participants begin at `+0x28`, with a
step of 8: u16 trainer identifier, then u32 controller to `+4`. The community structure Colosseum
therefore requires to take into account the additional 16 PAL bytes before the participants.

| Chef | Identifier combat | Identifier |
| --- | --- | --- |
| Bouledisco | 164 | 162 |
| Dakim | 213 | 211 |
| Venus | 328 | 326 |
| Teck | 405 | 403 |
| Helgonza | 427 | 425 |
| Jakylla | 439 | 437 |
| Nosfrat | 441 | 439 |

The native dispatcher of script functions is located in the DOL at `0x320508`, with a step of 12
bytes. Its entry 102 points to `0x80212538`. This function takes the combat identifier in `r3` and
reads the real tables of the loaded image.

A fixture can intercept the entry of this function during a normally triggered NPC fight, check the
value of `r3`, then replace only this argument with one of the above identifiers. The display and
fight then use the real boss recordings, without ROM patch. This method does not validate the
dialogs or flags of the scenario surrounding the normal encounter. A new part avoids that the dark
ones are already captured in the backup.

Source de structure :
[CMBattle](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/CMBattle.swift),
[definition of
tables](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/struct%20tables/Battles.swift).

## Changements de salle

The bootstrap fixed `r13 = 0x804CDCC0`. The room getter `0x80102A80` reads a pointer to
`0x804C8178`, dereferences its first word and reads the room ID to `+8` of this second object.
Pointers must remain in MEM1.

The script function 95, `0x801170CC`, takes `r3 = salle` and `r4 = entrée`. It writes the structure
to `0x804557F8`: previous room u32 to `+0`, next u32 to `+4`, activation u8 to `+8`, input u32 to
`+0xC`, then calls the transition engine `0x80102AA0`. Prefer a breakpoint on a natural transition,
rather than an arbitrary jump of the PC in a function with an unknown context.

Identifiers corroborated by PAL table and primary catalogue.

- `0x01`: exterior of the Service Station. `0x02`: interior.
- `0x03` : external of Phenac City ; `0x09` : boutique de Phenac City.
- `0x0F` : external of Pyrite Town ; `0x16` : boutique de Pyrite Town.
- `0x27`: Sanctuary of Samaragd. `0x385`: a variant of this sanctuary.

Do not confuse hexadecimal identifiers with decimal: room 27 decimal is `0x1B`, not `0x27`.

Source :
[XGRoom](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/Objects/data%20types/enumerable/XGRoom.swift),
[catalogue of
rooms](https://github.com/PekanMmd/Pokemon-XD-Code/blob/f2d6c4af0b6bdd78717fb41f7be7cc14aa5476a0/JSON/Colosseum/Room%20IDs.json).

## Flags: masked preparation of chest and dark

The PAL flag better is `0x80194A14`, its setter `0x80194AD0`. Their instructions decode the fields
as follows.

1. Description pointer u32 to `0x804C643C`, 8 byte input by ID.
2. The initial byte contains the group in its two high bits and the width in its six low bits. The
   bit shift is the u16 of the input to `+4`.
3. Group pointer u32 to `0x804C638C`. The group data pointer is u32 to `tableGroupes + groupe*8 +
   4`.
4. The word is `base + 4*(décalage>>5)`. Words are big endian, with bit numbering from the weak bit.
   A field can occupy two words.

The private client checks the full signatures of the beginning of the two functions and `r13` before
proposing `flag` or `set_flag`. The writings are limited to the flags of three chests and the seven
Booleans of capture of the identified bosses. They preserve the neighbouring bits and require the
expected value before modification. This prepares a fixture without CPU injection or supposition on
an SAV offset.

The table chest number 1 is in room `0x03`, Phenac City, flag 152, position `(-153.04, 32.99,
84.22)`. Number 7 is in room 27 decimals (`0x1B`), flag 158. Number 42 is in room 38 decimals
(`0x26`), flag 193. A reset is made before reloading the room, then the collection remains an action
of the player.

The 243 script points to `0x801F2EF0`. It finds the obscure metadata via the pointer at
`0x804C640C`, with a step of `0x38`. The u16 to `+0xC` and `+0x1C` of each entry are **identifiers
de drapeaux**, not states to be overwritten directly. The function puts the first to 1 and the
second to its argument `r4`.

| Dark group | Drapeau vu | Status flag |
| --- | --- | --- |
| 19 | 1184 | 2374 |
| 21 | 1186 | 2376 |
| 23 | 1188 | 2378 |
| 34 | 1199 | 2389 |
| 38 | 1203 | 2393 |
| 43 | 1208 | 2398 |
| 44 | 1209 | 2399 |

### Capture and purification independent of the state of encounter

The `+0x1C` field is not enough to decide whether a Shadow Pokémon has been captured. Its
`0x801F2E88` getter reads an eight-bit signed integer. The only direct native call to the setter, to
`0x801D69C0`, increases this integer when a value provided by an event table is larger. No global
`0=inconnu, 1=vu, 2=capturé, 3=purifié` enumeration has been established. The client leaves this
state read only.

The capture is a **separate boolean**, whose identifier is stored at `metadata+0x12`. The getter
`0x801F3344` reads this flag and sets it `0x801F33A8` in writing. `0x8008CECC`, the construction of
a Pokémon of trainer reads this better with the obscure identifier of the recording `+2` and skips
the initialization if the result is 1. `0x802187A8` appelle `0x80127454` with `r4=1` . This routine
puts the flag on `+0x16` 1 and then the one for capture `+0x12` 1. Purification is a third boolean,
stored at `metadata+0x14`, getter `0x801F34E8`, setter `0x801F354C`. The purification routine writes
it to 1 to `0x80263554`, after reading the dark identifier of the Pokémon.

| Groupe | Capture `+0x12` | Purification `+0x14` | Rencontre `+0x16` |
| --- | --- | --- | --- |
| 19 | 2144 | 1280 | 1376 |
| 21 | 2146 | 1282 | 1378 |
| 23 | 2148 | 1284 | 1380 |
| 34 | 2159 | 1295 | 1391 |
| 38 | 2163 | 1299 | 1395 |
| 43 | 2168 | 1304 | 1400 |
| 44 | 2169 | 1305 | 1401 |

The command `{"op":"shadow","id":19}` reads the five separate flags and keeps their raw values. It
checks the identifiers of the corroborated PAL line. To prepare a copy where boss 19 is again
available, `{"op":"set_flag","id":2144,"value":0,"expected":1}` only returns the capture boolean to
zero, before the construction of the fight. This does not recreate the normal course nor a
consistent backup to keep: it is a private RAM fixture, to abandon after the test. A rereading and
observation of the real fight remains necessary. Flags of purification, sight and progression are
not rewritten.

The original instruction ranges and REL lines are kept in
`analysis/generated/dolphin-runtime-references/pal-shadow-native-instructions.json`.

Sources and their fingerprints are stored locally in
`analysis/generated/dolphin-runtime-references/manifest.json`. The eleven private client tests cover
MEM1 terminals, preconditions, proofreading, fragmented packages, individual records, 2609a Ctrl-C
drainage and preservation of neighbouring bits, including when a field crosses two words, and the
separation of dark flags without deducing the capture of the raw state.
