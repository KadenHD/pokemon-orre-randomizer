# Shiny model coverage

The 2026-11-23 read-only audit covers the Europe, USA and Japan revision-0
originals of both games. It found no missing shiny field conversion among
the 386 base species on any disc. It does not mean every species was replayed
individually on the GPU or in every story scene.

## Retail resources

| Check | Colosseum, per region | XD, per region |
| --- | ---: | ---: |
| Base species, normal/shiny field-model pairs | 386 | 386 |
| Extra Unown letters and sampled Spinda PIDs | 36 | 36 |
| Parsed PKX resources, including non-Pokemon assets | 527 | 602 |
| Decoded portrait atlases | 418 | 423 |
| Normal/shiny whole-body DNA pairs | 413 | Not used by XD |

All base portraits are present. All decoded Colosseum DNA pairs differ between
normal and shiny. Field checks use the production loader, including dedicated
retail rare-model archives and the native palette recipes. Unown checks cover
all 28 letters; Spinda checks sample eight PID extremes, not every possible
spot pattern. No source ROM hash changed. RVZ inputs were converted one at a
time into disposable private images.

Some original assets intentionally share colors. The three stock Castform
weather portrait atlases have identical normal/shiny cells, and XD's stock
Shadow Lugia portrait has no separate shiny colors. Those are not gaps in the
current generated game: the authored resources below replace their selected
identities. A neutral palette recipe alone is also not proof of a missing shiny
variant: some species use a separate rare-model archive.

## Authored resources and HD

- Shadow Lugia has eight authenticated portraits: both games, normal/shiny,
  native/x4. Colosseum uses square framing and XD uses round framing. Its DNA
  artwork uses separate complete-body captures in native and x4 resolutions,
  with a black contour and the same registered pose.
- Castform's modern shiny Sunny, Rainy and Snowy forms use separately registered
  native resources and x4 artwork. Each regional catalogue verifies 20 material
  images and three portrait atlases. Legacy retail-source atlases keep their
  original colors and identities.
- The ordinary HD portrait catalogue covers all 386 species and 28 Unown
  letters through 413 atlases. Nine additional reviewed atlases supply the
  weather forms in both games and XD's three other Deoxys forms. Custom Shadow
  Lugia and modern shiny weather resources have their own contracts.

The audit passes the current files through the production portrait, DNA-body
and Castform x4 validators, and authenticates 66 model/artwork files against
their bundled provenance records. Registration verifies hashes, dimensions,
pack source pins and the native/x4 relationship. Texture coverage is described
separately in [HD coverage](HD_COVERAGE.md); these are not new polygon models.

The targeted shiny/artwork suite passes 110 tests. Earlier live
checks of the authored forms remain documented in [HD coverage](HD_COVERAGE.md)
and [validation scope](VALIDATION.md). The exhaustive six-disc pass here is an
offline resource audit, not 2,316 individual in-game encounters.

Private JSON reports and source hashes are retained under
`build/v206-validation/` and excluded from public source archives. They contain
no claim that every camera, animation or full campaign has been replayed.
