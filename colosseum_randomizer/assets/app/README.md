# Clip

Eclipse application icon. Abstract creation generated with the built-in tool `image_gen`, included
under the MIT license of the project. This image does not come from a ROM.

- `icon.png`: transparent master image, preserved without retouching.
- `icon.ico`: nine RGBA sizes, from 16 to 256 px, with transparent margins.
- `provenance.json`: origin, formats and hashes of both files.

The ICO file is used for Windows executable and Qt windows. It is present in local and public
editions. The Poké Menu Selection Ball icon belongs separately to the game pack.

To regenerate the ICO file with Qt dependencies already used by the project.

```powershell
python scripts/build_app_icon.py
```

Prompt of the master image.

> Use case: logo-brand. Create an original abstract Windows desktop application icon named ECLIPSE. One compact sculpted orbital knot made of two interlocking thick curved lozenges: one charcoal-black crescent with a single broad pale-gold ring marking, one muted lilac crescent with a tiny deep-red diamond inset. The two broad comma-like forms are balanced diagonally around a small central diamond-shaped opening. Their curling tapered ends form a striking unified silhouette, expressing duality, swapping and alternate outcomes. This is a purely abstract geometric emblem: no animals or characters, no faces or body parts. Crisp silver outer bevels, dark indigo recesses, enamel-like color, controlled cel-shaded shallow volume, GameCube-era console-menu craft. Chunky simple masses, restrained detail, strong readability at 32px. Center a single full icon on a square canvas with 10% clear margin and genuinely transparent background. No surrounding app tile, no text, no initials, no numbers, no watermark, no scenery, no particles, no presentation sheet or extra versions.
