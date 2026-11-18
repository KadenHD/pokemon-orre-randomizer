# Source-built native-speed music companion

Status: **enabled for the checked Windows/Europe revision-0 profiles after
bounded native-reference, actual Windows mix, movie and recovery validation**.
The earlier private callback hook is not part of this implementation.

## Integration contract

`native_music_resources.prepare_music_assets(source, destination, game_id=...)`
creates or verifies a shared source-specific cache. It reads ISO/GCM directly;
RVZ uses the existing lossless converter in a temporary directory. Publication
is atomic and cancellation leaves no published partial cache. Manifests contain
resource sizes and SHA256 hashes, without source-machine paths. Colosseum keeps
its original bank and arrangement archives. XD selects only `stm_bgm_` and
`stm_me_` archives; cry, effect and movie archives remain native.

`play_music.MusicSession(process, assets_dir, metadata, dolphin_dir).start()`
returns the session immediately. `process` must be the live `subprocess.Popen`
child owned by the launcher. The companion never discovers, attaches to, closes
or terminates other Dolphin processes. `stop()` requests shutdown and joins its
worker; `active` and `error` report status. Errors restore the native gain lease
and leave Dolphin running. With the companion enabled, the launcher configures
native Dolphin volume 50 and the companion uses the shared
`native_music_volume.NATIVE_MUSIC_OUTPUT_GAIN=0.5`. This reserves equal headroom
on both branches, preserving their ratio; native-only launch volume remains100.
It reads the exact owned
Dolphin's Windows session volume, mute and channel gains and applies them to
its PCM, without changing any Windows volume. An ambiguous session restores
native audio. The companion's own Windows volume preference still applies.
Earlier unity-gain QA runs remain explicit historical controls. Their measured
action peak, before the existing common Windows-session attenuation, justified
the common half-gain reserve. No Windows volume is changed to obtain headroom.

The host verifies fixed addresses against the exact supported retail profile,
checks dynamic arena bounds, the running game ID/revision, mailbox signature
and installed gain-hook branches. Reads stay within MEM1. Writes are limited
to the enable, heartbeat and requested mask fields; XD additionally writes its
selected stream IDs. Colosseum's saved faders, applied mask, native counters
and mailbox signature remain native-owned.

Before opening WaveOut, the companion resolves the Core Audio default render
endpoint with role `eConsole`, matching the checked Cubeb backend. It compares
that IMMDevice ID with WinMM's `DRV_QUERYFUNCTIONINSTANCEID` result. The mapper
is used only when it matches; otherwise an explicitly matching WinMM device is
selected. The actual opened WinMM device ID is checked again before any PCM is
submitted. Missing/unidentifiable routing restores native audio. A changed default
endpoint is detected once per second and also restores native audio. These are
read-only queries; [Microsoft's endpoint API](https://learn.microsoft.com/en-us/windows/win32/api/mmdeviceapi/nf-mmdeviceapi-immdeviceenumerator-getdefaultaudioendpoint)
and [WaveOut device-message API](https://learn.microsoft.com/en-us/windows/win32/api/mmeapi/nf-mmeapi-waveoutmessage)
define the underlying contracts.

## Output and clocks

The 32kHz stereo PCM queue uses supported Windows WaveOut calls with four 20ms
buffers. Completed buffers drive production, so the source music clock does not
depend on the emulation multiplier. Buffer/header lifetime extends through
reset and unprepare. No global or output-device volume setting is changed.

The installed executable's embedded version is **2609b**, SHA256
`7d686bbe88539a0373ec2f0c29d6a810263ecd23a06ace89df9ed02101f3a2a2`.
The official [2609b CubebStream source](https://github.com/dolphin-emu/dolphin/blob/2609b/Source/Core/AudioCommon/CubebStream.cpp#L219-L231)
passes `volume / 100.0f` to Cubeb. Its pinned
[Cubeb WASAPI implementation](https://github.com/mozilla/cubeb/blob/54217bca3f3e0cd53c073690a23dd25d83557909/src/cubeb_wasapi.cpp#L969-L991)
multiplies PCM samples by that value directly in the software-volume branch;
integer PCM truncates the fractional result. Therefore the checked source maps
Dolphin volume 50 to linear gain 0.5, without a nonlinear loudness curve. These
files and the Cubeb pin are identical in official tags 2609a and 2609b. This is
source evidence tied to the executable's declared version, rather than a measured
post-volume waveform or final-system-mixer validation.

Colosseum uses an independently source-built original-bank MusyX renderer. XD
uses a bounded C Nintendo DSP ADPCM decoder and each stream's original sample
rate. Fanfares may finish on the music clock after their native handle retires;
retired handles leave the mute list and game scripts continue normally. Native
effects, cries and atmosphere follow the emulation speed.

The native bridge independently bypasses suppression during prerecorded movies.
Host movie detection also clears queued companion PCM and disables its lease.
The movie picture and complete native soundtrack therefore share Dolphin's
clock. Real-time scenes continue through the gameplay music path.

## Build and redistribution

`python scripts/build_music.py` downloads the AxioDL/musyx source commit
`717404d77c17a95dd101bbe737d0f9549ab600e6`, verifies its pinned archive SHA256,
applies exact-preimage compatibility patches, and uses installed x64 MSVC/SDK
tools. `--archive <path>` supports an already downloaded verified source archive.
The output includes ABI-checked `orre_musyx.dll` and a content/provenance JSON.
The runtime checks that manifest before loading the library. No private DLL,
Frida dependency, native callback preimage or game asset is a build input.

Capability validation additionally requires the checked source-archive, commit,
compatibility-patch and adapter digests. A missing, stale or corrupt renderer
does not enable the option. The manifest's binary digest is checked independently;
binary identity across different compiler toolchains is not required.

CC0 terms and provenance are in `licenses/music`. Native source details are in
`native/music/README.md`. Repeated builds using the checked installed toolchain
produced identical DLL hashes; binary identity across toolchains is not claimed.

## Observed checks

The source-built renderer matched the private renderer's PCM exactly for 32,000
Colosseum title frames and 1,949,696 XD battle source frames at 31,874Hz. This is
a bounded regression comparison, not complete native soundtrack equivalence.
A source-built Colosseum journal reconstruction reproduced 16,000 subsequent
PCM frames exactly, including the checked reverb phase.

An actual WaveOut zero-PCM smoke completed 2,560 frames. A follow-up resolved the
actual eConsole endpoint, verified its matching WinMM output and completed another
2,560 zero-PCM frames. Separate fresh-bridge
game copies and isolated profiles exercised live MEM1 ownership, selective native
gain suppression, host synthesis/stream playback and the actual WaveOut consumer.
Both native outputs were forced to zero at command-line priority. A QA wrapper
measured host PCM and submitted zeros at the final WaveOut call. Colosseum reached
nonzero title music and native movie-bypass transitions; XD reached
`stm_bgm_open_roll.fsys`. Both sessions closed without a helper error. Only those
owned child processes were terminated; source discs and user profiles were not
written. These checks establish host integration, **not an audible final mix**.

Local reports are under the ignored `build/native-host-smoke/` directory.
Automated checks in `tests/test_play_music.py` cover cache integrity/cancellation,
ADPCM arithmetic, individual-rate resampling, loop interpolation, one-shot and
fanfare completion, same-session phase restoration, lease ownership, output
buffer lifetime, clock rollover, pause detection and failure cleanup.

## Historical component checks and limits

The following component observations predate the consented actual Windows mix
captures described below. Their original boundaries and gains remain explicit.

### Version 2 game-folder integration checks

Fresh generated Colosseum and XD game folders loaded the pinned full HD packs
with 99 and 239 custom overlay images respectively. The owned, muted Dolphin
runs observed no companion error. Colosseum reached title, field/map and Miror B
music; XD's separate simulator-battle run observed 20 seconds of battle music.
The last steady 10 seconds of that XD run advanced 0.999821 source-music seconds
per wall second while the game ran at about 199.2% (PAL 50 VI/s base).
The longest HD loading stall also triggered the documented 200 ms pause gate;
the soundtrack is not uninterrupted across those stalls.

Peak observed Dolphin working sets were approximately 1.1 GiB for Colosseum
and 1.4 GiB for the XD capture path; the XD battle run without frame dumping
peaked at 989 MiB. These are bounded scene observations, not a memory ceiling
for every area or graphics setting. Original ROM/card hashes remained unchanged.
Both outputs were physically silent: command-line native mute and zeros
submitted to the final WaveOut consumer, with host PCM recorded beforehand.
This checks the companion, not the audible final Windows mix.

Local evidence: `build/game-folder-validation/hd-runtime-02-*/report.json` and
`build/game-folder-validation/hd-xd-battle-host-01/analysis.json`.

### Additional source-built component captures

Separate owned Dolphin 2609b processes exercised the actual source-built
`MusicSession`, real WaveOut buffer consumption and new generated game folders.
Native output stayed muted at command-line priority; the host recorded its
production WaveOut input and submitted zeros. Read-only QA instrumentation
captured the unchanged native Cubeb callback output before the configured zero
gain. It did not replace the renderer, mix the companion inside Dolphin, rewrite
callback samples, or add a production dependency on process instrumentation.

Two six-second XD simulator-battle host excerpts, from 100% and 200% game
scenarios, correlate above 0.99999999 with the original decoded stream at normal
speed. The double-speed reference correlates below 0.069. Each stereo channel's
observed headroom multiplier is approximately 0.5000001 after accounting for the
game's own music gain. This establishes timing, channel routing and host gain
for those excerpts; both comparisons use the checked original-bank decoder and
do not independently prove complete native ADPCM fidelity.

A separate real helper-stop run restored native title audio while Dolphin kept
running: the lease stayed zero and native centered RMS increased from 0.116 to
1,891 PCM units. Its unadjusted six-second native/reference waveform correlation
was 0.444. Short-window phase offsets exposed a small clock difference. Official
[AudioInterface.cpp](https://github.com/dolphin-emu/dolphin/blob/2609b/Source/Core/Core/HW/AudioInterface.cpp#L348-L356)
and [Mixer.h](https://github.com/dolphin-emu/dolphin/blob/2609b/Source/Core/AudioCommon/Mixer.h#L59-L60)
use 108,000,000 / 3,372 = 32,028.46975 Hz for the GameCube AI path, a ratio of
1,125 / 1,124 against the host's nominal 32kHz renderer. An **analysis-only**
time-scale fit of 1.0009 raised the checked native/reference correlation to
0.99823, consistent with that clock difference. That initial analysis changed
no runtime code. The later fixed-ratio correction is described below; neither
comparison is a bit-exact or final-device-mix claim.

The owned lifecycle run observed approximately 50.002 -> 100.011 -> pause 0 ->
resume 99.674 -> 49.999 VI/s, corresponding to PAL 100%/200% targets. Musical
source phase advanced approximately one second per second in the running title
segments and remained exactly stationary in the checked pause interior. The
native streamed cry with sound ID 838 remained outside music suppression. Its
observed handle lifetime changed from 2.063 to 1.031 seconds. Centered-AC envelope
comparison favored the double-speed hypothesis (0.947 versus 0.784 at normal
speed); raw waveform matching did not establish phase-identical synthesis.

The original XD victory stream contains 3.9035 seconds of audio. Its accelerated
native handle retired after approximately 1.968 seconds. Eighty-eight checked
host output blocks remained nonzero afterward; the host lifecycle ended about
1.969 seconds after native retirement and the game continued to the laboratory.
Control timestamps include buffer/polling granularity and are not exact audio
duration measurements.

Eight movie-interior checks cover both games at 100% and 200%, totaling 871,680
native callback frames. The native soundtrack remained nonzero, the companion
lease was disabled, and no host voice or PCM packet was produced in those
trimmed interiors. This supports the native bypass path; it does not replace a
new capture of the final combined audiovisual output. One setup run produced no
callback frames and is explicitly excluded. Incomplete shutdown suffix records
are excluded from paired analyses. All useful runs reported no helper error and
preserved original ROM/card hashes; each owned process and instrumentation
session was closed.

A separate Windows process-tree loopback pilot captured only its owned test
process and descendants. An 8,000-unit synthetic tone, muted solely through that
process's verified audio session, became essentially silence in the capture
(peak one PCM unit). The prior mute state was restored successfully. No unrelated
session or device volume was changed. This demonstrates that this capture
boundary does not expose the desired combined signal before the session mute.
Only physical output endpoints were available; no virtual endpoint was installed.
Consequently these are **separate pre-device component recordings, not an
observed final Windows mix**. Recombining them cannot remove that evidence limit.

Local scripts, protected-source manifests, per-run reports, raw component
recordings, rate comparisons and the consolidated `component-validation.json`
remain under the ignored `build/game-folder-validation/native-final-mix/`.
REA read-only capture observations include
`ev_e2317d1b939a783e379902a57a9f34fd1f0621b08bc1a70069142e07294cd4ce`
and `ev_bcfc6a304707aa2388aa5106bcb114960d4bc6409c834a7f0eb3c2a211ae7c6b`;
each script separately checks the known callback preimage. Source identity is
bound locally to the executable SHA256 recorded above; the instrumentation
provider itself does not authenticate the complete executable artifact.

### Read-only routing audit and state lifecycle follow-up

A fresh read-only Core Audio/PnP audit found two active render endpoints,
both unmuted at master scalar 1.0, with five and one nonexpired sessions.
No already-silent, unused output or usable virtual render endpoint was found.
The audit changed no volume, default device or application routing. The primary
[Microsoft loopback documentation](https://learn.microsoft.com/en-us/windows/win32/coreaudio/loopback-recording)
describes endpoint mix capture; its
[reference-stream documentation](https://learn.microsoft.com/en-us/windows-hardware/drivers/audio/windows-11-apis-for-audio-processing-objects#reference-loopback-stream)
describes the pre-endpoint-volume tap. Neither establishes an isolated silent
output on this machine. No nonzero final-output pilot was started.

Two further owned, double-muted source-built runs observed an actual private
save-slot load and a reset in each game at the 200% target. XD's native VI count
returned from 1626 to 1210, then from 1693 to zero. Colosseum returned from 1475
to 1062, then from 1494 to zero; its host journal reconstructions took about
31 ms and 15 ms. Both helpers continued without an error, source ROM/card
hashes remained unchanged, and all owned processes closed. An earlier XD setup
attempt ended before completing the commands and is excluded. Those runtime
observations preceded the clock correction below. Receipts are `current-route-audit.json` and
`state-validation.json` in the same private evidence directory. These are
bounded early same-session state checks, with the documented queue lead and
polling granularity; they do not prove arbitrary state restoration or a final
Windows mix.

### Fixed GameCube DAC clock correction

The exact source-defined ratio `1125/1124`, without a fitted rate, raises the
same six-second native XD title comparison from 0.44445158 to 0.99985312.
Offline output from the corrected, source-built `MusicState` correlates at
0.99984780 with that native callback excerpt. This supports correcting the
0.088968% clock difference, approximately 1.53956 cents, when reproducing the
GameCube's native 100% tempo/pitch. It is independent of game speed and does
not apply to native effects or movies. The common native DAC path supports
the same clock ratio for MusyX synthesis and XD streams; the measured waveform
comparison here covers XD title music only.

XD stream cursors now include that fixed clock ratio. Colosseum keeps the
original 32kHz synthesizer and applies a rational streaming interpolation to
its output, retaining at most two source frames and an integer fractional
phase. The existing synthesis journal reconstructs that phase and lookahead.
Two actual source-built MusyX reconstructions reproduced 16,000 output frames
byte-for-byte from a checkpoint with fractional phase 638. Four added tests
cover packet continuity, measured sine pitch, fractional stream rewind and
synthesizer-journal restoration; all 41 audio/bridge tests pass. Receipts are
`fixed-native-clock-comparison.json` and `clock-reconstruction.json` in the
private evidence directory. The earlier nominal-clock gameplay captures remain
historical component evidence; the corrected playback still needs a new final
Windows mix and listening validation.

## Actual Windows mix checks, 17 November 2026

With explicit consent, bounded owned-process-tree loopback recordings captured
the real Windows mix while a separate watchdog temporarily muted the physical
endpoint. A kill-on-close job contained Dolphin and the capture child; all audio
children closed before the watchdog restored the original mute state. No master
or session volume, default device, driver or unrelated process was changed.
Original ROM/card hashes remained unchanged. Raw recordings retain the endpoint's
eight float32 channels at 44,100Hz. The six non-front channels were exactly zero
in these runs, permitting an unchanged-level FL/FR video preview. This is an
observed Windows process-tree mix, rather than recombined component recordings;
downstream physical listening and endpoint processing remain outside the check.

The native-format pilot qualified the expected 440Hz tone and level. Earlier
stereo pilots had capture-format downmix attenuation and are excluded from gain
qualification. A separate integration fault was corrected: the companion now
follows its owned Dolphin's read-only session gain/mute/channel values. The
observed Dolphin session preference was 0.11, while the companion's session was
1.0. No preference was reset or inversely compensated. The current common output
reserve is 0.5 on both Dolphin and companion; older unity runs remain labelled
controls. The unity XD action peak would exceed full scale before that existing
session attenuation. With the common reserve, the observed peak was 0.078107,
approximately 0.7101 before the known 0.11 preference. This is bounded headroom
evidence; attenuation cannot repair clipping already inside synthesis.

| Checked scenario | Observed result | Coverage limit |
| --- | --- | --- |
| Colosseum Miror B/field to dungeon, current half gain | 45 seconds, no helper error; final-mix/host correlation 0.99916 / 0.99856, gain 1.00024 / 1.00023 | Output integration, not native synthesizer equivalence |
| XD battle, cry, victory, laboratory, current half gain | Battle 99.16 VI/s and 1.00004 music seconds/wall second; victory 99.95 VI/s and 0.99933 music seconds/wall second | PAL target 200%; setup ran faster and is excluded |
| Pause, private save/load, reset, helper stop, both games | Checked pause interiors exactly silent; backward VI loads and reset to zero observed; native audio returned with lease zero and no host packets | Recent same-session states only |
| Startup video sequences, both games, native100 versus game200 | Matching VI durations and pictures; fixed double-speed audio hypothesis strongly preferred | The Pokemon Company and Genius Sonority logos, not a narrative cinematic |

The streamed XD cry 838 belongs to the native cry archive, uses SDK ID 2, and
never enters the selected music mute list. Raw `unknown-xd-resource` observer
diagnostics are retained: the music-only cache intentionally excludes that cry
archive, and the native archive/header identifies it independently. The original
cry's observed lifetime changes from 2.063 to 1.031 seconds. The victory host
stream continues at native speed after the accelerated native handle retires.
No clipping samples or capture discontinuities were observed in the accepted
final action/field recordings; this does not establish every effect or scene.

Startup-video comparisons include both embedded THP audio and native scripted
music behind a video. Fixed 2x waveform correlations for the two sequences were
0.9971 / 0.9896 in Colosseum and 0.7727 / 0.9954 in XD, exceeding the corresponding
1x hypotheses. The first XD sequence retains a larger residual. Image comparisons
use matching VI fractions without optimized image search; duration ratios are
approximately 2.00. Colosseum's source-confirmed THP display/audio counters also
support the checked progression. Screenshot timing has recorded acquisition
bounds, so these observations support relative picture/sound pace, rather than
frame-exact absolute A/V latency. No narrative opening was reached in these
bounded runs. Retail code uses the same native movie path for the Colosseum
opening, but extending the result to that unplayed scene is an inference.

Native render screenshots and the same captured Windows mix produce short
variable-frame-rate MP4 witnesses, approximately 12 frames/s. They are not
50/60fps game recordings. No loudness normalization or reconstructed mix is used.
Current half-gain witnesses are `colosseum-final-reserve-video-02` and
`xd-final-action-reserve-video-02`; scene timestamps, hashes and ffprobe output
are preserved with their raw eight-channel sources in the private evidence
directory. Lifecycle clips contain long native-fallback phases and must not be
described throughout as companion music at native speed.

### Historical Colosseum title comparison discrepancy

The integrated exact-preimage AUX correction restores the retail three-buffer
return order at 32kHz: consume processed slot +1, process/store slot +2. The old
PC branch mixed the new result one 160-sample block early. A controlled offline
A/B, with unchanged banks, clock, gain and one shared attack origin, improved
the 16-second correlation from 0.7993 to 0.9336 and the late ten seconds from
0.8461 to 0.9973. Public compiled-C impulse/wrap/reset tests protect this patch.

A fresh strict-native100 Windows reference initially appeared to leave a
fidelity gate open. Against the corrected renderer at fixed gain 0.11,
the title's 1.8-second attack has channel correlations 0.9945 / 0.9951, envelope
correlation 0.99991 and level errors -0.047 / -0.043dB. The following checked
4-to-12-second passage has correlations 0.9009 / 0.8707, envelope correlation
0.7469 and level errors -0.876 / -1.214dB. There is no later realignment, fitted
rate or free gain. The offline recipe is a fresh title start, without the full
retail command/reverb history; the evidence therefore establishes a residual,
not its cause or bit-exact synthesis. The investigation below identified the
additional native title effect in this comparison and resolved that blocker.

Private receipts include `final-mix-scenarios.json`, `movie-rate-comparison.json`,
per-run `audio-guard-closed.json` / `video-mux-receipt.json`, and
`build/v2-three-points/colosseum-fidelity-review/fresh-windows-100/`.
The full consolidated suite passed 1,201 tests in 132 modules: 1,198 passed and
three Windows symlink-privilege tests skipped. This is software verification,
not listening approval or complete soundtrack/cinematic coverage.

## Completion checks, 18 November 2026

An independent audit localized the apparent title discrepancy to a sudden,
mostly centered additional signal at six seconds. Retail title code starts
sound `0x46e` / 1134 at animation frame 180 and stops it at frame 199. The PAL
sound table identifies it as an effect, FX 948 in a separate bank. A fresh real
companion capture observed its SE flag, live SDK handle and onset exactly 300
VI after title start, while only the BGM volume group was suppressed. The effect
remained native, as required. The old comparison had matched native **music plus
effects** against an offline **music-only** rendering.

An existing, protected native DSP music-only reference resolves that mismatch
without another synthesis patch. With the same AUX-corrected renderer, banks,
fixed clock and fixed gain, the 4-to-20-second title passage has correlations
0.996613 / 0.996937, envelope correlation 0.999668 and level errors
-0.0106 / -0.0308dB. The later 25-to-35-second passage has correlations
0.99717 / 0.99748 and envelope correlation 0.99910. The historical reference
excluded its FX master and restored it; the new runs changed no such gain.
All original measurements are retained with this corrected interpretation.

The fresh observed companion mix also follows the fresh native reference before
the effect: correlations 0.99914 / 0.99922 on the attack and approximately
0.99961 on the 2-to-4-second passage. With the effect included, total level is
within -0.019dB of the known common gain. The two boots' effect attacks differ by
about 40ms relative to the locked musical origin; no later alignment is applied
to hide that difference. This supports the checked musical fidelity and native
effect preservation, rather than claiming bit-exact synthesis.

A targeted ownership fix excludes sound-effect rows before mapping sequence
owners. Effect handles and sequence public IDs occupy separate domains and can
have the same numeric value; an effect must not overwrite the matching BGM
owner. A synthetic regression reproduces that collision. This is separate from
the resolved comparison discrepancy and does not change the synthesizer DLL.

### Longer prerecorded scenes and relative timing

Colosseum's narrative `openingdemo.thp` was reached through normal New Game,
confirmation and name selection using only the isolated controller and a copied
QA card. XD's long `movie_auto_demo` was reached by leaving the title idle.
Private states saved at the video starts provided identical inputs for short
100%/200% comparisons; source ROMs, cards and saved states stayed unchanged.
The XD scene is a promotional montage, not a continuous narrative opening.
XD's `opening_event` narrative is a real-time scene and is outside this THP
comparison. Gameplay music retains its normal-speed treatment in real-time
scenes; the prerecorded-video path leaves the complete soundtrack native.

Both paired video captures emitted zero companion PCM and kept the native lease
disabled. Matching VI/display-frame pictures show the same scenes at the two
rates. Colosseum display progression was approximately 2.010 times the reference;
XD's matched-VI progression was 1.99936 times the reference. Fixed 2x audio
hypotheses give correlations 0.94736 for the Colosseum narrative excerpt and
0.99876 for the XD montage, versus approximately 0.121 / 0.110 for 1x. The
Colosseum native video/audio counters remain separated by zero, one or two
pipeline frames. This extends the earlier startup-logo checks to long video
paths with both scripted music/effects and embedded movie sound. It supports
relative picture/sound pace; screenshot acquisition and native pipeline bounds
do not establish frame-exact absolute synchronization at the physical device.

WaveOut's measured outstanding queue is bounded to 80ms in the checked current
output implementation. The calculation accounts for buffers discarded by
`clear`: cumulative submitted-minus-played counts alone also include discarded
frames and must not be presented as queue latency. The approximately 40ms
relative effect/music attack observation is consistent with this queue bound.
Pause detection still uses the documented 200ms VI-stall threshold. No physical
listening or output-to-ear latency measurement was performed.

A controlled routing-query failure exercised the real helper cleanup against
a live Dolphin: the actual endpoint stayed unchanged, but the QA output factory
reported a mismatch. The native lease became zero within 16ms after detection,
host submissions stopped, and five seconds of native audio remained nonzero
while VI progressed. No Windows default, volume or route was changed. This
validates the query-failure/recovery path, not a physical device-unplug trial.
Native endpoint selection and owned-session checks remain fail-closed.

All accepted new runs restored the original endpoint mute after closing their
owned audio children, retained all eight raw float channels and observed zero
full-scale samples. The six non-front channels were exactly zero. Short VFR
screenshots-plus-audio witnesses use the same observed Windows mix without
loudness normalization; their roughly 12fps cadence and timing bounds are
recorded. Private proof is under `build/v2-completion/audio/`, including
`completion-analysis.json` and the movie comparison boards; the independent
causal audit is `build/v2-completion/audio-independent/FINAL_AUDIO_CAUSE.json`.
The focused audio/bridge/compiled-C suite passes 51 tests.

## Validated scope and practical limits

The option reports `production_validated=True` only for Windows, GC6P01/GXXP01
revision 0 and the verified renderer recipe. The runtime observations use
Dolphin 2609b, Cubeb and a matching WaveOut endpoint. Other regions/revisions,
unverified renderer provenance and unidentifiable audio routing are refused.
Validation covers the described source references, real mix, gameplay timing,
effects/fanfare transitions, headroom, recent-state lifecycle, representative
prerecorded scenes and controlled route failure. It is not an assertion that
every soundtrack branch, state file or physical audio device was exercised.

Pause detection follows a 200ms VI stall threshold and flushes queued output;
it is not a direct Dolphin pause notification. The queue adds up to 80ms lead.
Colosseum reconstruction uses a bounded 120 seconds of source rendering and
30,000 control operations; recent VI lookups are bounded to 6,000 checkpoints.
XD stores bounded recent cursor checkpoints and a bounded decoded-stream cache.
Unknown/unavailable checkpoints and observed large forward discontinuities
restore native audio. The host cannot identify every forward load, reset or
VI reuse from the counter alone. Persistent cross-session checkpoint identity,
long-session reconstruction, every music/fade/loop branch and arbitrary state
files remain outside the checked scope. Unknown checkpoints restore native
audio. The bounded technical checks now support enabling the option for the
verified profiles; physical listening, arbitrary states and exhaustive scene
coverage are disclosed limits rather than claims inferred from those checks.
