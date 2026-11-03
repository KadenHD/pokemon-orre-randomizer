# Éclipse

Icône d’application Éclipse.
Création abstraite générée avec l’outil intégré `image_gen`, incluse sous la licence
MIT du projet. Cette image ne provient pas d’une ROM.

- `icon.png` : image maîtresse transparente, conservée sans retouche.
- `icon.ico` : neuf tailles RGBA, de 16 à 256 px, avec marges transparentes.
- `provenance.json` : origine, formats et empreintes des deux fichiers.

Le fichier ICO sert à l’exécutable Windows et aux fenêtres Qt. Il est présent
dans les éditions locale et publique. L’icône Poké Ball de sélection des menus
appartient séparément au pack du jeu.

Pour régénérer le fichier ICO avec les dépendances Qt déjà utilisées par le projet :

```powershell
python scripts/build_app_icon.py
```

Prompt de l’image maîtresse :

> Use case: logo-brand. Create an original abstract Windows desktop application icon named ECLIPSE. One compact sculpted orbital knot made of two interlocking thick curved lozenges: one charcoal-black crescent with a single broad pale-gold ring marking, one muted lilac crescent with a tiny deep-red diamond inset. The two broad comma-like forms are balanced diagonally around a small central diamond-shaped opening. Their curling tapered ends form a striking unified silhouette, expressing duality, swapping and alternate outcomes. This is a purely abstract geometric emblem: no animals or characters, no faces or body parts. Crisp silver outer bevels, dark indigo recesses, enamel-like color, controlled cel-shaded shallow volume, GameCube-era console-menu craft. Chunky simple masses, restrained detail, strong readability at 32px. Center a single full icon on a square canvas with 10% clear margin and genuinely transparent background. No surrounding app tile, no text, no initials, no numbers, no watermark, no scenery, no particles, no presentation sheet or extra versions.
