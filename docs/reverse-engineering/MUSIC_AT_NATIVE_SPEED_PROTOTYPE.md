# Native-speed music prototype

Status: **private prototype; bounded Europe-revision-0 runtime checks pass;
production integration remains pending**. This is not a feature of the released
application or a claim of complete soundtrack equivalence.

This follows the [initial study](MUSIC_AT_NATIVE_SPEED_STUDY.md). Scripts, copied
game images, save snapshots and review recordings remain in the ignored
`build/music-wall-clock-prototype/` directory. Production application, launcher,
ROM generation and release workflows are unchanged.

## Audio policy

- Gameplay targets 200%. Background music and musical fanfares use the audio
  clock at 100%, rather than slowing down a recording of accelerated music.
- Native effects, cries and atmosphere stay in Dolphin at game speed. This
  prototype does not make every sound effect run at 100%.
- **Prerecorded movies keep their original image and complete native soundtrack
  together at 200%.** The companion is bypassed during playback. This replaces
  the earlier proposal to keep movie audio at 100% against an accelerated image.
  A scene rendered in real time remains part of the gameplay music path.
- Every QA instance has physical output forced to zero at command-line priority.
  Review recordings capture audio before that final mute.

## Private implementation

Colosseum uses an original-bank MusyX PC renderer pinned to
`717404d77c17a95dd101bbe737d0f9549ab600e6`. Native sequence handles are correlated
with resource fingerprints. A gain hook suppresses only corresponding music
groups while native sequencing, completion checks and game scripts continue.
The renderer now uses the game's six native reverb parameters and original DSP
four-tap sample-rate coefficient tables instead of a generic sinc filter.
The private compatibility path also follows the DSP's signed-envelope and
unsigned-mixer arithmetic. It reproduces the observed retail reverb pre-delay
pointer behavior safely, without reproducing the original out-of-object write.

XD decodes Nintendo DSP ADPCM music streams at their individual source rates.
Only SDK stream handles identified as music or musical fanfares are suppressed.
The streamed cry archive stays native. Already-started fanfares finish at 100%
after their accelerated native counterpart ends; retired handles leave the mute
list without holding up game scripts.

Both gain hooks require an enable flag and fresh heartbeat in a private 64-byte
mailbox. Expiration restores native music. Launches without the companion retain
native audio. Colosseum restores original pause gains rather than forcing a
constant volume over game fades.

The final mix experiment hooks the actual Cubeb output callback in an owned
Dolphin process. The callback pulls companion PCM through a bounded FIFO and
records the native-effects-plus-music result before device mute. It does not
combine independently recorded files afterward. Its 32 kHz producer follows the
output consumer cursor, with 80 ms of nominal queue lead and a 65,536-frame
capacity. Fixed -6 dB master gain reserves headroom. Teardown disables the
consumer before the producer stops, preventing an underrun during the final
native-gain restoration wait.

This callback hook is tied to the checked Dolphin executable and machine-code
preimage. It is research instrumentation, not a supported public Dolphin plugin
or production packaging solution.

## Observed results

Runtime tests use Europe revision 0 of both games, independent Dolphin profiles
and copied memory cards. Existing Dolphin sessions are never attached to or
controlled. Source movies, models, textures and save formats remain unchanged.

| Measurement | Colosseum | XD |
| --- | ---: | ---: |
| Earlier stable native-speed reference | 59.94 retraces/s | 59.94 retraces/s |
| Earlier stable double-speed timing test | 119.81 retraces/s | 119.88 retraces/s |
| Final captured gameplay run, measured average | 119.69 retraces/s | 115.89 retraces/s |
| Companion production rate | 32,000 PCM frames/s | 32,000 PCM frames/s |
| Final gameplay mix, missing FIFO frames | 0 | 0 |
| Final gameplay mix, saturated samples | 0 | 0 |
| Final gameplay mix, peak absolute PCM value | 20,554 | 22,811 |

Retraces are timing counters, not a claim of 60 distinct rendered frames per
second. XD does not sustain exactly 200% throughout this instrumented video run.
Earlier envelope comparisons between 100% and 200% runs favored the 1x music
hypothesis in both games (correlations 0.960 and 0.958). That establishes timing
for those excerpts, not complete soundtrack fidelity.

Captured gameplay includes menus, Colosseum exploration and a playable Miror B
battle, plus XD's simulator battle, victory and return to the laboratory. Native
cry resource `stm_se_nakigoe_archive.fsys` remains outside the mute list. XD's
recorded fanfare continues after native completion without delaying the game.

A separate check of the exported XD battle excerpt compares six seconds of the
actual captured mix with the original `stm_bgm_B_virtual.fsys` stream at 0.5x,
1x and 2x. Subtracting the separately captured native PCM from the fixed-gain
mix isolates the companion contribution that actually reached the callback.
Its waveform correlation is 0.994 at 1x and 0.087 at 2x. This confirms normal
music speed for that battle excerpt; effects and cries remain at game speed.

During checked prerecorded intervals, companion PCM is zero, native suppression
is off and captured output equals half the native callback PCM within one half
of an integer quantization step. The factor of one half is the fixed master
headroom gain. Movie resources and embedded timing are not rewritten or
independently time-stretched. Long attract-mode recordings cover about 45 seconds
of Colosseum movie playback and 65 seconds of XD playback at the double-speed
target. Their checked interiors contain 2,136,000 and 3,078,240 paired native/mix
PCM frames respectively. One interrupted final callback leaves 481 unpaired raw
frames at shutdown in the Colosseum recording; they are excluded from comparison.

Twenty focused checks cover musical timing, heartbeat fallback, natural one-shot
completion, loop joins, fanfare lifecycle, movie state 3, released movie slots and
corrupt movie-table bounds, counter rollover, pause, and music-phase restoration.
These complement real recordings; they do not replace listening or a complete
scene/region matrix.

## Fidelity investigation

The earlier apparent Colosseum volume deficit was measured using raw RMS. Native
DSP depop accumulators retain a DC residual below their ramp threshold, whereas
the PC renderer drains it. The original reverb amplifies that constant component.
Observed native studio values and output means account for the large offset;
raw RMS therefore does not isolate musical loudness. Runtime checks also ruled
out the suspected mono/stereo mismatch: the observed game actually used stereo.

With exact 20 ms analysis windows and centered AC measurements, the checked title
segments differ by less than 0.3 dB. Short-window envelope correlations exceed
0.98, while the longer 20-second window remains around 0.89. No artificial gain,
EQ, or tempo correction was added to conceal that difference. These measurements
explain the earlier loudness inference; they do not prove bit-identical synthesis
or perceptual equivalence across the complete soundtrack.

Independent decoding matches 186 of 187 observed native DSP ADPCM histories. One
snapshot differs and remains an observation limit. Comparing the corrected dry
mixer with native DSP depop output gives 187 checks within one PCM unit. Native
envelope arithmetic and the verified retail pre-delay compatibility path are now
enabled in this private prototype, superseding the earlier disabled A/B candidate.

Retail sample 581 declares loop start `0xffffffff` and loop length 1, rejected by
the PC renderer. Only the host bank copy changes that entry to one-shot; ROM bytes
remain intact. An extended profile examines all 78 arrangements: two intentionally
remain native-only, and 76 render for up to their first five minutes, totaling
13,586 seconds. `windycity_song` reads this sample and reaches decoded position 4,338
of 9,745, with no out-of-range request during this bounded profile. This does not
prove every later loop or branch. The helper now aborts to native fallback if the
adapted sample would run beyond its original length.

## Live speed changes, pause and state loads

Separate real-callback recordings exercise 100% -> 200% -> pause -> resume ->
100%, followed by saving and loading a state in the same owned test process.
Private loopback controller input supplies hotkeys without controlling another
Dolphin window. Once pause is detected, musical source frames stop advancing.
Music resumes at its previous position, independently of the emulation target.

The first lifecycle captures restarted music after a timeline rollback. The
follow-up `colo-restore-mix-200` and `xd-restore-mix-200` recordings supersede that
behavior. The private helper associates its own musical history with observed VI
positions. XD restores its decoded stream cursor; Colosseum reconstructs the
synthesizer by replaying its own render/control journal, without copying internal
engine pointers or heap state. A focused Colosseum checkpoint test reproduces
the expected future PCM exactly, including reverb. A separate test reloads the
same XD loop checkpoint twice.

During reconstruction, the companion callback is intentionally held and its
heartbeat remains live. The observed Colosseum reconstruction takes about 0.30
seconds; XD cursor restoration is below the report's millisecond clock precision.
This is a brief music interruption on state load, not continuous playback through
the load. The normal queue still adds 80 ms of nominal lead. Both final recordings
report zero missing FIFO frames, zero helper failures and nonsaturating mixed
peaks of 15,071 and 22,641 PCM units respectively. Both restore the exact requested
observed VI and report that music did not restart.

This only establishes history restoration for the exercised backward loads in the
same process. Forward loads, states from another session, reset, VI reuse across
branches, and long sessions require an explicit production checkpoint identity
and bounded storage/reconstruction policy. They are not certified by these tests.

## Review recordings and integration gates

Private `review-full-mix/` exports use the actual callback mix. Their manifest
records source runs and timing. Video dumps are mapped through observed retrace
counters; audio has no tempo or pitch processing. Speakers remain muted during
recording.

Older exports in `review/` are explicitly **music-only**. They omit native effects
and movie audio and must not be presented as final-mix recordings. A failed XD
capture with zero callback frames is excluded; a standalone rerun supplies the
final XD gameplay evidence.

The exercised music-speed, movie-bypass, mixing, pause and backward-load paths
can inform the launcher mockups. Public integration still requires supported
output/buffering instead of private process instrumentation, a Dolphin compatibility
policy, production checkpoint handling, remaining region checks, and broader
loop/fade and scene coverage. No claim is made that every soundtrack branch or
emulator build has passed. The private callback instrumentation must not be
shipped as-is.

Local evidence includes `protected-originals.json`, `final-mix-validation.json`,
`dsp-src-fidelity.json`, `bank-sentinel-study.json`, `bank-extended-study.json`,
`native-decoder-validation.json`, `native-dry-mix-validation.json`,
`audio-gate-summary.json`, `timing-analysis.json`, per-run reports and review
manifests. Local paths and game-derived content stay excluded from Git.

## Next UI review

Three visual proposals cover play-folder creation, globally installed HD packs
pinned to versions validated for each Orre release, and a per-folder launcher.
They are design proposals, not screenshots of shipped features. Generated
play-folder filenames remain in English. The proposals distinguish normal-speed
gameplay music from accelerated native picture-plus-soundtrack playback. Their
review does not waive the production integration gates above.
