# Original-bank music renderer

Build with `python scripts/build_music.py` using an installed x64 MSVC C11
toolchain and Windows SDK. An offline build may pass `--archive <path>`.
The build verifies SHA256 of the pinned AxioDL/musyx public source archive,
checks exact preimages before applying the compatibility patches, and
emits `orre_musyx.dll` plus its content/provenance manifest under `_native`.
The build never reads the private prototype directory or a game disc.

Upstream: https://github.com/AxioDL/musyx/tree/717404d77c17a95dd101bbe737d0f9549ab600e6

Upstream license: CC0-1.0; the complete notice is in `LICENSE-CC0.txt`.
The adapter and patches are maintained with this repository. The source pin
and toolchain provenance make the build reproducible from source; they do not
claim binary identity across different MSVC toolchains.

The renderer receives the user's original bank and arrangements at runtime.
Game assets and Dolphin's DSP coefficient file are not redistributed here.
The compatibility patches select DSP four-tap resampling coefficients supplied
by the user's Dolphin, preserve signed envelope/unsigned mixer arithmetic,
emulate the observed retail reverb pre-delay safely, and monitor the bounded
sample-581 host-only adaptation. A decoder-bound failure restores native audio.
No Frida, callback interception, private executable preimage, or Dolphin plugin
is used by this output path. Soundtrack equivalence still requires bounded
gameplay, music-transition, movie and lifecycle validation.

The 32kHz AUX path now follows the retail three-buffer ordering: the main mix
consumes the already processed return at `(salAuxFrame+1)%3`, while the callback
processes `(salAuxFrame+2)%3` and saves that result for the following cycle.
The previous PC path returned wet audio one 160-sample block too early. Existing
ring initialization/reset and the non-32kHz path are unchanged. The exact source
preimage is in `patches.json`; `tests/test_music_aux_ring.py` compiles the shipped
C fragment and checks impulse delay, ring wrap/reset and the unchanged alternate
rate branch. A controlled comparison against native DSP captures improved the
long-window correlation and residual, without a fitted delay or gain. It does
not establish bit-exact synthesis; the bounded residual remains documented.
