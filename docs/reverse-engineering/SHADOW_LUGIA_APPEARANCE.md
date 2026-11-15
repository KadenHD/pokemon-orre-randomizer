# Shadow Lugia appearance in both games

The appearance policy uses the actual Pokemon's species, Shadow provenance,
saved PID/owner and purification state. It does not infer Shadow status from
species249 or from another Lugia's saved personality.

| Specimen | Default | Keep Shadow appearance enabled |
| --- | --- | --- |
| Shadow Lugia | XD dark model | XD dark model |
| Shiny Shadow Lugia | Custom white body and dark belly | Same custom model |
| Purified Lugia | Ordinary Lugia | XD dark model |
| Purified shiny Lugia | Ordinary pink shiny Lugia | Custom white body and dark belly |
| Lugia that was never Shadow | Ordinary Lugia, including its pink shiny palette | Unchanged |

The advanced boolean `keep_shadow_lugia_after_purification` is false in both
presets and on import of older signed profiles. It changes display resources
only. Purification, the National Ribbon, moves, stats, saved personality and
trainer identity remain native.

## Colosseum

`postgame_lugia_model.py` retains its historical module name but also serves
randomized Shadow Lugia. Full Pokemon records require a genuine nonzero Shadow
ID. A separate ordinary-model marker prevents an ordinary Lugia with a matching
PID from falling through to reduced-record matching. Capture and targeting
views which omit Shadow fields match saved identities only among Lugia Shadow
IDs in the final encounter table.

The Snag List receives the actual selected ID and purified gauge sentinel in
its temporary display object. Opening the list and browsing with the D-pad use
separate native constructors; both retain the selected specimen's saved PID,
owner and appearance policy. The DNA analyzer tags only an identified Shadow
sample, with its saved personality, owner and purified state. The keypad parser
chooses one of four bounded native texture variants using the same identity
and option; it does not alter the puzzle's species comparisons or answers.

The analyzer retains its original blue hologram tint. The keypad uses complete
Pokemon images from `poke_body.fsys`, with the native normal/shiny variants and
all Unown forms, rather than cropped battle portraits. Its bevel and comparison
keys remain native. Spinda keeps its pre-rendered full-body image; a separate
32px inset shows the resolved PID's spot mask. The inset does not claim to alter
the fixed spots on that body image. The 3D hologram uses the actual PID pattern.

## XD

XD already maps any true Shadow Lugia to its dark model index417. The custom
shiny resource follows that individual model request's native shiny flag;
another Lugia's identity is not a fallback for that request. Separate virtual
normal/shiny face keys prevent the portrait cache from sharing the two variants.

Only display-specific calls receive the optional purified-provenance rule.
The shared gameplay Shadow predicates remain unchanged. The Snag List retains
provenance on a temporary copy when needed. Authored XD001 scenes still use
their original Shadow73 identity, while Gateon's randomized Shadow encounter
uses Shadow30 and its own saved identity. Ordinary companions and dancers do
not acquire the dark model merely because their species is Lugia.

## Validation

Executable PowerPC tests cover normal/shiny, generated/unseen, before/after
purification and both option states, including never-Shadow negative cases and
PID collisions. Native call windows and archive composition are checked on all
three regional originals. Optional local-ROM tests do not turn static regional
coverage into a claim of three full native playthroughs. Private Dolphin runs
use copied QA cards, a dedicated controller and a silent backend, and retain
source hashes and screenshots separately from the public source archive.
