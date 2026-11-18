# HD texture sources

The application uses original author archives. They are optional external
resources, separate from this project's source license and interface pack.
The links below document provenance. The free download service uses a fixed
GitHub Release, with automatic transport-fragment assembly for XD's large ZIP.
An approved HTTPS mirror or distribution folder can still provide whole ZIPs.

| Game | Author credit | Version | Archive bytes | Selected textures |
| --- | --- | --- | ---: | ---: |
| Colosseum | Sephie (archive manifest); published by u/Bun-bun45 | V2 / 2.00 | 722,522,130 | 7,032 DDS |
| XD | mikeyX | XG/XD v1.0, PNG Texture Pack | 3,295,188,617 | 8,582 PNG |

## Original releases

- Colosseum: [author announcement](https://www.reddit.com/r/DolphinEmulator/comments/sxzxi2/),
  [original Drive archive](https://drive.google.com/file/d/1FwGSM1TJfIrAKNfy7BTrTF850JccSwkt/view).
  SHA-256: `4cac6314d8b3fed18743dc0db844b64651c3845668037912d8ed216053af0e33`.
  The archive credits Sephie; the announcement account is recorded separately.
- XD: [author thread](https://forums.dolphin-emu.org/Thread-pokemon-xg-xd-hd-texture-pack-v1-0),
  [original MEGA archive](https://mega.nz/folder/kA4WFZ7D#cd66IQr-2AM_PeYd8hFd3Q/file/QZgmWYIZ).
  Select **Pokemon XD-XG HD V1.0 PNG Texture Pack.zip**, not the Resource Pack.
  SHA-256: `56bbf26551f26b7bdb1d0d7d4a6eb7073cf4f8fef72130648bd97abde8851cf2`.

The installed selection occupies 1,609,063,880 bytes for Colosseum and
3,296,572,631 bytes for XD. Colosseum retains the author's GPU-compressed DDS
textures. Pillow decodes a source only when a custom asset requires it.

## Deterministic installation

Both archives are verified before extraction. Only Dolphin `tex1_` PNG/DDS
files are installed. Paths, file sizes and texture identities are checked;
unlisted collisions fail installation rather than silently choosing a file.
Players click **Install**; there is no ZIP import step. GitHub transport assets
remain below the service's 2 GiB per-file limit: the original Colosseum ZIP and
two binary XD fragments. Each fragment and the reassembled original XD ZIP are
verified. A fixed release tag keeps existing game folders on their selected pack.
Whole-archive mirrors and distribution folders retain the
`packs/{game}/{version}/{sha256-prefix}.zip` layout. HTTP downloads resume and
folder sources are read without modifying their archives.

Colosseum has nine duplicate names with different contents. The exact excluded
archive paths are pinned in `Pack.excluded_paths`. The selection retains the
higher-resolution character/tower texture, usable effect alpha, transparent
Pokémon artwork and a single explicit world/material/title variant for equal
sizes. These equal-size choices are application decisions, not claims about
the author's intended priority. Four DDS filenames with an extra processing annotation do not match Dolphin keys and are also ignored. The original ZIP remains unchanged.

XD's duplicate-named ` - Copy.png` is not a valid Dolphin replacement name and
is ignored, along with PSDs, notes and folders. Its valid texture names are unique.
Pack versions do not establish full coverage of every region or language.
Unchanged stock omissions retain the game's native texture; missing newly
authored custom donors block HD preparation.

Shadow Lugia's five battle materials have x4 coverage: two exact pack donors
and three authored reflection/mouth maps derived from their high-resolution
palettes. The three cinematic field models also have complete material routes.
The belly transfer uses a verified shared UV layout and fixed color calibration;
the socket and iris layers are reconstructed from the actual HD eye atlas.
Their source hashes, geometry checks, calibration and alpha policy accompany
the generated assets. These derivatives are labelled as authored resources,
not exact upstream field replacements. Native bitmaps are not enlarged.

Body and head artwork was recaptured with the complete material set, including
the shiny variant. The model manifest records each source and the native mesh.
The source ZIPs remain unchanged; custom images are generated separately.

## Pokemon portraits

The pinned Colosseum archive contains x4 portraits for all 386 base species,
including their shiny frames and all 28 Unown forms. Some native textures have
two facing directions: these use four cells in an 84x84 atlas rather than
two cells in a 42x84 atlas. The pinned XD archive does not replace the retail
Pokemon face atlases.

Orre can use the Colosseum portraits as donors for XD. The adapter matches
species and form using verified native texture identities, keeps both shiny
frames and fits the art to XD's circular frame. It records the donor's file,
hash and scale; it does not rename files blindly or replace a missing form
with another Pokemon. Castform's weather forms and Deoxys's extra XD forms
have no matching donor in this selection and keep their original portraits.
XD's HD mode requires the pinned Colosseum pack as well as XD's own pack.
The manager installs missing dependencies together; creation and launch check
both packs even when an older folder has no recorded portrait dependencies.
Both installations are shared across game folders and pinned in new manifests.

Custom Shadow Lugia portraits use separate native/HD head renders with the
actual model materials and fully red eye texture. All four captures replay
the same 86 joint matrices and use the same normalized close-up crop. Their
framing fills the native tile, with violet backgrounds: square in Colosseum
and circular in XD. The native XD shiny portrait merges seven near-identical
background shades to fit its 256-color palette; every foreground pixel,
including antialiasing, remains unchanged. The source hashes, crop, pose and
palette adjustment are recorded in `models/portrait-variants.json`.

The model, portrait and Snag List keep the same saved shiny identity. The DNA
keypad continues to use separate whole-body art, never the head portrait.

## Versioned storage and downloads

`scripts/prepare_hd_hosting.py` verifies both original ZIPs and stages a single
versioned upload tree with a SHA-256 manifest. This is private preparation;
it does not upload anything or configure a production service. Archives are
kept outside Git and application releases. Both packs total 4,017,710,747 bytes
before HTTP overhead.

The approved [free GitHub hosting](HD_HOSTING_PROPOSAL.md) serves both packs from
a separate, fixed release, with no domain or paid subscription. Its public assets
were checked byte for byte before the application download URLs were enabled.
The read-only `scripts/verify_hd_origin.py` checks HTTP transport and complete
archive identities; `scripts/prepare_hd_github.py` prepares future release assets
without publishing them.

Author credits and distribution terms remain attached to their sources.
The XD author licenses separately linked UI vectors under CC BY-NC-SA 4.0 and
lists several ESRGAN model credits; those statements do not establish a blanket
license to redistribute the complete texture ZIP. Neither archive is relicensed
under this project's MIT license. Public mirroring needs appropriate permissions.
