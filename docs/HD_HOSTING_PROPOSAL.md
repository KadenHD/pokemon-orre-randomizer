# Free HD download hosting

Status: approved and deployed on November 18, 2026. The public repository and
frozen release are available, and full public-download SHA-256 verification
passed before their URLs were enabled in the application. No paid service,
cloud account or domain was created.

## Service

Use the separate public repository [KadenHD/pokemon-orre-hd-packs](https://github.com/KadenHD/pokemon-orre-hd-packs),
with the fixed release [packs-2026-11-18](https://github.com/KadenHD/pokemon-orre-hd-packs/releases/tag/packs-2026-11-18).
This requires no purchased domain or hosting subscription.
GitHub's [Free plan](https://github.com/pricing) includes public repositories.
The application's own releases stay in `pokemon-orre-randomizer`, so a texture
release cannot replace the latest application release used by the updater.

GitHub documents a limit below 2 GiB for each release asset and no limit on the
total release size or bandwidth. These are the published service quotas, not a
promise about future platform policy. See [GitHub release quotas](https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases#storage-and-bandwidth-quotas).

## Release assets

| Asset | Bytes | Purpose |
| --- | ---: | --- |
| `colosseum-2.00-4cac6314d8b3.zip` | 722,522,130 | Unchanged Colosseum author ZIP |
| `xd-1.0-56bbf26551f2.zip.001` | 1,900,000,000 | First binary fragment of the XD author ZIP |
| `xd-1.0-56bbf26551f2.zip.002` | 1,395,188,617 | Remaining bytes of the XD author ZIP |

The three assets total **4,017,710,747 bytes**, approximately 4.02 GB. The review
bundle is `build/v2-completion/hosting/github-packs/`, with `manifest.json` and
`SHA256SUMS`. Each fragment is below 2 GiB. Concatenating the XD fragments gives
the original ZIP byte for byte; the archive is not repacked or modified.

Original complete SHA-256 values:

- Colosseum 2.00: `4cac6314d8b3fed18743dc0db844b64651c3845668037912d8ed216053af0e33`.
- XD 1.0: `56bbf26551f26b7bdb1d0d7d4a6eb7073cf4f8fef72130648bd97abde8851cf2`.

## What the player does

The player clicks Install. Orre downloads Colosseum as one ZIP, and XD as two
transport fragments written directly into one ZIP temporary file. Each fragment
and the final original ZIP are checked before extraction. Interrupted downloads
resume inside the correct fragment; earlier verified fragments are retained.
There are no manual file selections, split/join commands or extra fragment copies
in the player's download cache. Archives are removed after successful installation.
XD's HD portraits also require Colosseum's pack; both installations remain shared
across all game folders.

Each application release pins exact asset URLs, sizes, fragment checksums and
original archive checksums. It never downloads a moving `latest` pack release.
Old assets remain available while released game folders reference them. Existing
assets are never overwritten, and an application update does not duplicate the
same upstream pack. No ROM, save or seed is uploaded to the download service.

The application also retains its original distribution-folder format for private
use: complete author ZIPs under `packs/{game}/{version}/{sha256-prefix}.zip`.
A normal HTTPS mirror of that layout remains compatible. These are alternatives
to the GitHub transport, not a required manual installation step.

## Cost

The service uses a public GitHub repository and release assets: **no hosting
subscription and no domain purchase**. No payment service or metered cloud bucket
is introduced. Application EXE/ZIP downloads continue to use their existing GitHub
release workflow. GitHub's published release quotas support the three prepared
assets without changing the author's ZIP contents.

## Verification and deployment

1. Obtain the user's approval for this separate public repository and the three
   prepared release assets, as requested before any production hosting.
2. Retain original author credits and appropriate redistribution permissions.
   The [source and rights notes](HD_SOURCES.md) remain attached. The packs are not
   relicensed under the application's MIT code license.
3. Publish the verified files and manifest to the fixed tag. A pre-existing asset
   with a different checksum must cause an abort, not an overwrite.
4. Check the public endpoints using the read-only verifier:

   ```powershell
   python scripts/verify_hd_origin.py --github-manifest build/v2-completion/hosting/github-packs/manifest.json --full-sha256 --report hd-release-verification.json
   ```

   This checks HEAD sizes, initial/final byte ranges, each asset's full SHA-256,
   and the complete reconstructed ZIP SHA-256. The verification streams data and
   does not store another archive copy. Without `--full-sha256`, it checks the
   HTTP transport only and makes no full-integrity claim.
5. Configure the approved fixed release URLs in the catalog. Rehearse interruption,
   continuation, installation and repair using a clean application cache, then
   rebuild and verify the Windows application and launcher from those exact inputs.

## Deployment record

The repository, reviewed files and fixed URLs were approved before publication.
GitHub received all three archives/fragments with their expected SHA-256 values.
The read-only public verifier then streamed each asset and checked both original
ZIP identities, HEAD sizes and byte ranges. The application pins these verified
URLs; it never follows a moving latest pack release.

The real application client also installed both XD dependencies into an isolated
cache, selecting 8,582 XD textures and 7,032 Colosseum textures. An interrupted
Colosseum transfer retained 10 MiB and resumed at that exact offset. A repeated
installation performed no download, and completed ZIPs were removed from the
download cache.

The same review and verification steps apply before publishing a newer pack.
Local preparation and protocol tests do not publish files or spend money.
