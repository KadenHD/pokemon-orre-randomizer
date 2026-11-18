# Music at native speed during fast-forward

Study date: 2026-11-16. Status: feasibility investigation, not a shipped feature.
No launcher, interface, randomization setting or generated ROM was changed during
this initial study. The [follow-up prototype](MUSIC_AT_NATIVE_SPEED_PROTOTYPE.md)
uses separate experimental copies and records the subsequent runtime results.

## Decision

Use a host-side music player driven by the game's music events. Its output
clock must follow the host audio device, independently of Dolphin's emulation
speed. Keep sound effects and cries in Dolphin.

This initial study establishes an implementation direction. Read-only observation
of both games succeeded. Subsequent prototype recordings exercise selective native
music suppression, host playback, real mixed output, movie bypass, speed changes,
pause and backward state loads together. See the follow-up for exact scope and
remaining production gates; the full transition/region matrix is not certified.

## Observed resources

The local Europe revision-0 originals were inspected without writing to them.
Do not interpret arrangement/archive counts as counts of unique background
songs: the containers also contain silence, fanfares and other musical cues.

| Game | Observed native resources | Consequence |
| --- | --- | --- |
| Colosseum | 78 arrangements in `bgm_archive.fsys`, 612,140 decoded bytes in total. `snd_music.samp` is 3,659,136 bytes. Project, pool and sample-directory resources are in `common.fsys`. | Render the MusyX sequences with their original instruments; a collection of sampled waveforms is not the soundtrack. |
| XD | 107 `stm_bgm_*.fsys` archives, 161,216,672 bytes in total. Each has an `I_SF` header and a DSP-ADPCM payload. 78 have the loop flag set. | Decode and stream the original audio, honoring each header's rate and loop metadata. |
| XD residual sequences | `null_bgm_song` and `wind_atmos_loop_song` remain in its small `bgm_archive.fsys`. | A stream-only implementation does not cover all audio paths. |

XD's observed stream rates range from 30,672 to 32,115 Hz. Hardcoding 32 kHz
would alter playback speed. PCM16 expansion of all 107 streams would consume
556,315,176 bytes before resampling; decoding on demand avoids an unnecessary
full-WAV cache. All observed loop ends fit inside the declared sample counts.
This validates metadata bounds, not the audible quality of all loop joins.

The app's existing three menu WAV files are menu assets, not a complete
in-game soundtrack or a music-event bridge.

## Native observation points

The two adjacent sound-ID getters were matched from local US symbol references
to the original US, Europe and Japan DOLs. Each match uses a unique 64-byte
instruction context, masking inter-function branch displacements, small-data
offsets and `lis` immediates. The actual getter must still be exactly
`lwz r3, displacement(r13); blr`. The initial r13 value is read from the DOL's
`lis r13; ori r13,r13` setup. These are derived static matches, not six runtime
playthroughs or verified patch sites.

| Game ID | Current music getter | Current music ID word | VI retrace word |
| --- | --- | --- | --- |
| GC6E01 | `0x801653C4` | `0x8047B0AC` | `0x8047A84C` |
| GC6P01 | `0x80169738` | `0x804C855C` | `0x804C7CFC` |
| GC6J01 | `0x8016249C` | `0x8046675C` | `0x80465F14` |
| GXXE01 | `0x80183168` | `0x804EB4D4` | `0x804EAC54` |
| GXXP01 | `0x80184A18` | `0x80525ABC` | `0x80525234` |
| GXXJ01 | `0x8017E7A8` | `0x804C89C4` | `0x804C8144` |

The corresponding original DOL SHA-256 values and raw getter bytes are retained
in the private static report. Future code must verify target identity and exact
call windows before installing anything; it must never use this table blindly.

REA opened and identified the original Colosseum DOL. Its deeper read operation
was unavailable: this Windows provider does not support GameCube DOL analysis,
and Ghidra was not configured. REA was closed without changing its setup.
The observations below use direct DOL parsing and Dolphin's shared memory,
not a claimed successful REA decompilation.

## Controlled runtime observations

Four owned Dolphin instances were run sequentially, each for 18 wall seconds,
using fresh profiles, no cheats, no imported saves, both memory-card slots
disabled and the Null graphics backend. Audio used `No audio output`, zero
volume and mute settings. Only these owned PIDs were terminated afterward.
No existing Dolphin instance was attached to or controlled.

The Windows `dolphin-emu.<owned PID>` mapping was opened with `FILE_MAP_READ`.
The expected six-byte game ID was checked before sampling MEM1. No memory
writes, input automation or native code patches were used.

| Original | Target speed | Observed VI retraces per wall second |
| --- | --- | --- |
| Colosseum Europe | 100% | 49.896 |
| Colosseum Europe | 200% | 99.925 |
| XD Europe | 100% | 50.046 |
| XD Europe | 200% | 100.050 |

The measured ratios were 2.0027 and 1.9992 respectively. This confirms the
controlled emulation-speed change and the read-only observation path.

Colosseum's 200% run exposed music IDs 1130 and 1233 after startup. The short
XD runs remained in its introduction, so a separate 60-second observation at
200% was made. That run exposed IDs 1506 and 8, at 100.020 VI retraces per wall
second. Those IDs were not attributed to archive names by guesswork. The
short 100% runs only exposed ID 0; do not claim they validated audible tracks.

Input ROM sizes and modification times were unchanged. No user's save was
loaded or changed. No music or other test audio was played through speakers.

These observations do not demonstrate that native music can already be muted
without muting sound effects, or that external music has played in sync with
a complete game session.

## Why the simpler alternatives do not satisfy the goal

### Dolphin pitch preservation

The current mixer can preserve playback pitch, but its queue management can
discard granules to catch up. It does not expose an independent, continuous
background-music clock. Processing the final mixed output also cannot separate
music from cries or effects after they have been mixed together.

### Changing only the in-game sequence tempo

Both sound libraries expose sequence-speed controls, but Colosseum's sequences
and XD's prerecorded streams require different handling. Tempo compensation
alone does not address sample pitch, envelopes, effects/reverb timing and
variable speed. A fixed half-speed patch would also be incorrect at 100% or
on a machine that cannot sustain 200%.

A ROM running inside an emulator does not automatically know the host's real
elapsed time or its achieved speed. A speed-dependent native solution would
need a host bridge too, while modifying more of the original audio engine.

### Playing a soundtrack based only on the current room

This misses battles, scene-specific music, repeated starts of the same track,
temporary music, silence, fades and restoration of a previous track. Polling
the current music ID is useful for discovery, but cannot identify every event.

## Proposed implementation boundary

1. **Prepare local audio resources.** Read them from the user's own game image.
   Use a versioned, shared music cache keyed by game/resource hashes and decoder
   version, independently of the HD texture cache. Do not require an internet
   soundtrack download or duplicate the soundtrack for every seed.
2. **Capture music lifecycle events.** Add a narrowly scoped, versioned native
   event mailbox for play, stop, restart, pause/resume, gain/fade and resource
   selection. A sequence counter must preserve same-ID restarts and short
   events. Distinguish background, temporary music and effect slots explicitly.
   Validate stream and sequencer paths separately in XD.
3. **Run the host player at native rate.** In Colosseum, use an original-bank
   MusyX renderer or a validated offline render cache. In XD, decode the native
   DSP streams at their own rates. The audio device clock owns musical time;
   Dolphin's VI counter is only an observation/pause signal, never the music
   playback clock. Speed changes must not restart the track or double its rate.
4. **Suppress only the native audible music contribution.** Keep native music
   sequencing, status queries and completion waits alive. Do not replace all
   sound with mute, stop native sequences to silence them, or change script
   return values. Selective gain control must preserve native fades and leave
   cries, effects and atmosphere intact. This has not yet been validated.
5. **Keep ordinary launches functional.** Enable native suppression only after
   a compatible host player is ready. On missing data, helper failure or an
   expired heartbeat, restore the native music path rather than leaving silence
   or interfering with gameplay. Direct Dolphin launches still need normal
   audio without requiring the companion process.
6. **Preserve identity and game content.** No change to models, shinies, seed,
   gameplay or save format is required for this approach. Any experimental
   telemetry patch must be made in a separate output, never a user's existing
   image. The original opening movie files remain untouched.

The candidate Colosseum renderer is AxioDL MusyX commit
`717404d77c17a95dd101bbe737d0f9549ab600e6`. Its PC API supports immutable raw
group validation and output of an explicitly requested number of PCM frames,
without a device or wall-clock dependency inside the renderer. The host can
therefore control its clock. The checked revision's license file is CC0-1.0;
this does not change the ownership of game audio resources. No library was
installed, vendored or compiled into this application during the initial study.
The follow-up private prototype builds this renderer separately; see
[the prototype results](MUSIC_AT_NATIVE_SPEED_PROTOTYPE.md).

## Required validation before launcher integration

- Build an isolated music bridge prototype first, leaving the production
  launcher and UI unchanged.
- Compare at 100% against native Colosseum playback: instruments, balance,
  reverb, intro and loop joins. SDK API availability is not proof of fidelity.
- Validate XD decoding and loops at the observed nonuniform source rates.
- Record 100% -> 200% -> 100% while one track continues. Measure musical time
  and listen to the captured audio afterward; do not infer success from pitch.
- Cover field -> battle -> victory -> field, defeat/reload, pause/resume,
  repeated plays, silence, fades, fanfares, menus and the postgame quest.
- Confirm that selective suppression leaves effects and cries audible, and
  that all native waits and story progression still complete normally.
- Handle save-state load/reset even when the music ID is unchanged. Detect
  timeline rollback; current-ID polling alone cannot restore musical position.
- Treat prerecorded-movie audio separately. The chosen policy now keeps both
  the original image and its complete native soundtrack at 200%, bypassing the
  companion during playback. Do not retain movie audio at 100% against a 200%
  image. See the [prototype results](MUSIC_AT_NATIVE_SPEED_PROTOTYPE.md) for the
  observed scope and outstanding fidelity gates.
- Test missing resources, helper exit and lost contact. Check restoration of
  the current native gain rather than forcing a fixed volume over game fades.
- Run real scenes on each supported region before publishing those hooks.
  Only Europe revision-0 startup was observed dynamically in this study.

## Evidence and primary references

Private, ignored artifacts are in `build/music-wall-clock-study/`:
`audit.py`, `static-audit.json`, `observe.py`, `runtime-observations.json` and
the individual read-only observations. They are research helpers, not product
code. They contain no extracted complete soundtrack or additional ISO copy.

- [Dolphin mixer and catch-up queue](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/AudioCommon/Mixer.cpp)
- [Dolphin audio setting descriptions](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/DolphinQt/Settings/AudioPane.cpp)
- [Dolphin MEM1 allocation](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Core/HW/Memmap.cpp)
- [Dolphin Windows mapping names](https://github.com/dolphin-emu/dolphin/blob/master/Source/Core/Common/MemArenaWin.cpp)
- [MusyX PC API at the studied revision](https://github.com/AxioDL/musyx/blob/717404d77c17a95dd101bbe737d0f9549ab600e6/include/musyx/pc.h)
- [MusyX sequence implementation](https://github.com/AxioDL/musyx/blob/717404d77c17a95dd101bbe737d0f9549ab600e6/src/musyx/runtime/seq.c)
- [MusyX license](https://github.com/AxioDL/musyx/blob/717404d77c17a95dd101bbe737d0f9549ab600e6/LICENSE)
- [vgmstream's XD ISH/ISD metadata reader](https://github.com/vgmstream/vgmstream/blob/24ffd6ce3e1f34fdebf9f5316d18ad2e162838ce/src/meta/ish_isd.c)
- Local symbol references: `dougchansan/pkmn-colosseum` US map and its XD US
  reference map, checked against the original DOL bytes. Source reconstructions
  and historical campaign names were not accepted as runtime proof.
