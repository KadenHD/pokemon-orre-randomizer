# Spinda DNA diagrams in Original and HD modes

The DNA diagram represents the specimen's saved PID. The keypad body and spot
colors use the same shiny decision. Rendering does not change the save data or
the PID generator.

The native Spinda face remains a 128x128 RGB565 texture. Its four PID bytes
control offsets truncated toward zero. The game compares complete RGB565
integers, carries horizontal overflow into the next row, and skips rows whose
starting address is outside the face. The 32x32 diagram reduces this result to
two colors. Four independent binary masks reproduce those native samples;
the tests cover all 1,024 independent spot positions.

The `dna-spinda-independent-diagrams-v2` contract adds five TObj layers per key:
a background and four masks. Including the body image, each material uses six
textures. A shared bank holds 2,051 CMPR textures at 40x40, totaling 1,640,800
bytes: one empty image, two backgrounds, and 4 x 256 x 2 spot masks. Complementary
endpoints encode a distinct Dolphin key in the first transparent block while
preserving every decoded RGBA value, including hidden RGB. This avoids a
PID-dependent fringe under linear filtering.

The native writer exposes the resolved PID and shiny status in a temporary
DOL-arena record. The bridge uses that record for both the four spot bytes and
the original normal/shiny body from `poke_body.fsys`. A ready flag distinguishes
a valid zero PID from an unavailable identity. Writers are placed after the
actual generated instruction block, including when eight samples are Spinda.
The puzzle answers remain unchanged.

Every pixel buffer has 32-byte alignment, including allocations after each
cell's descriptor records. `GXInitTexObj` encodes the address as `image >> 5`:
four-byte alignment can corrupt the rendered pixels even when a CPU hash check
passes. Tests cover all texture allocations for eight and nine samples using
that hardware encoding. Before-fix captures remain explicitly unqualified.

HD spot paint comes from the actual 512x512 Spinda material
`tex1_128x128_a1443261174f684e_4` in the Colosseum 2.00 pack. An authored ellipse
uses the native stamp's coordinate system and a crop of that HD paint. The
native bitmap is not enlarged. Bodies use their ordinary HD donors; each mask
depends on one byte rather than the complete PID.

The nine remaining ImageDesc objects for the case, screen, screws and indicators
read an immutable copy of the initial atlas. Their UVs have `u <= 0.684571`, while
artwork starts at `736/1024`. All nine illustrations use independent buffers.
One immutable-atlas key therefore maps to the actual HD UI donor, even when
Lugia's appearance changes elsewhere in the working buffer.

The existing guard still rejects a Spinda keypad without this contract. The
hologram keeps its exact native face bake; this adapter does not provide a new
512x512 face. Keypad bodies are retail artwork supplemented by the PID diagram,
rather than full-body images repainted for every PID.

Private Original/HD and normal/shiny cold-boot captures, raw PNGs and comparisons
are retained under `build/hd-coverage-validation/spinda-dna/` and the
`spinda-keypad-*-final1` directories. They use copied QA cards; the normal and
shiny controls differ only in the witness PID and native checksums. The final
production-API and immutable-case validation has a separate receipt.

The accepted European cold boot uses the actual application-created
`spinda-api-party-verified` folder. All eight Spinda bodies, their saved PID/shiny
records, the selected masks, the nine independent key images and the nine frozen
case pointers were checked in the live owned process. The raw frame is visually
clean after the alignment fix.
`build/hd-coverage-validation/spinda-dna/SPINDA_DNA_HD_ACCEPTED.json` binds the
source ISO, public HD output, raw captures and source-code hashes.
