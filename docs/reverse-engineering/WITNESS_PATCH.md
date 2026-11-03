# Patch témoin : Donphan devient Pikachu

Le 30 octobre 2026, une ISO séparée a été produite pour **GC6P01 PAL, révision 0**. Un seul Pokémon de dresseur est remplacé : **le cinquième Pokémon de Basile, Donphan niveau 50, devient Pikachu niveau 50**. Son identifiant de nom par défaut est également remplacé pour afficher « PIKACHU ».

## Fichiers produits

- ISO : `build/witness-pikachu/colosseum-pal-witness-pikachu.iso`
- Taille : **1 459 978 240 octets**.
- SHA-256 : `b4f2f70830b2139264f7a7d9d1f872fb4a4df081cfdfd75c6daaa85db844f2b9`
- Plan du patch : `build/witness-pikachu/witness-patch.json`
- Contrôle des données et des originaux : `build/witness-pikachu/witness-verification.json`
- Captures et événements : `build/witness-pikachu/evidence/`
- Résumé durable des vérifications : [witness-validation.json](witness-validation.json)

## Modification exacte

Le dresseur **771**, nommé BASILE en français, référence l'équipe commençant à l'enregistrement **1568**. Le slot d'indice **4**, soit l'enregistrement **1572**, n'est référencé par aucun autre dresseur de la table. Le script refuse les enregistrements partagés, les Pokémon obscurs, les surnoms personnalisés et tout `common.rel` différent du dump original validé.

| Champ de common.rel | Offset | Avant | Après |
|---|---:|---:|---:|
| Espèce, entier 16 bits big endian | `0x18998E` | 232, Donphan | 25, Pikachu |
| Nom par défaut, entier 32 bits big endian | `0x189998` | 1232 | 1025 |

Ces deux champs entraînent **deux octets effectivement différents**, aux offsets décimaux 1 612 175 et 1 612 187. Les 78 autres octets de l'enregistrement de 80 octets sont identiques. Niveau, capacités, objet tenu, sélecteur de talent, sexe, nature, EV et IV sont conservés. Pikachu garde donc volontairement les capacités de ce Donphan : **Séisme, Damoclès, Pouv.Antique et Abri**. Ce témoin vérifie le remplacement de l'espèce ; il ne cherche pas à produire une équipe équilibrée ou conforme aux capacités normalement apprises.

Le SHA-256 de `common.rel` décompressé passe de `ee2677af555dc59626f978e743235831a76cb23bae93f3fdd1060d808f749d0b` à `89a3b269bb32620fdecc52d7c47396f736cb3e72ba8b78b6f759610464ea3690`. Les **27 autres membres** de `common.fsys` sont identiques après décompression.

La reconstruction réutilise [la méthode validée sans changement de données](ROUNDTRIP.md). L'archive recompressée de 959 200 octets est placée à `0x418000`. Seuls sa nouvelle plage disque et les huit octets de son offset et de sa taille dans la FST peuvent différer de l'ISO source. Les **1 459 019 032 autres octets** sont comparés intégralement.

Le contrôle `DolphinTool verify` termine avec le code 0 et `Problems Found: No` : CRC32 `dd31d889`, SHA-1 `d51193babb015bb4f34102a423b839ea57b9e4fb`. Il émet également le diagnostic `Error creating key`, déjà observé lors du premier contrôle.

## Essai sous Dolphin

L'ISO patchée a été lancée explicitement avec **Dolphin 2609a, JIT64 SC, Direct3D 12, DSP HLE**, sans cheats, et le profil `build/witness-pikachu/dolphin-user`. La carte mémoire EUR et le SRAM proviennent de copies. Les entrées ont été effectuées avec la fenêtre de manette TAS de Dolphin, par contrôle de l'interface Windows.

Le scénario utilise **Combat rapide → Double → Très fort**. Ce mode tire séparément une équipe pour le joueur et une pour l'ordinateur. Après des adversaires Curtis, Simone, Jess puis Mélina, le jeu a attribué **l'équipe de Basile au joueur MICHAEL**, face à Mélina. La preuve en combat porte donc sur cette équipe prêtée au joueur, et non sur un combat contre le personnage Basile. Aucune table de tirage ou graine aléatoire n'a été modifiée.

| Contrôle | Observation | Capture dans evidence/ |
|---|---|---|
| Équipe modifiée | Suicune, Raikou, Entei, Galeking, **Pikachu**, Drattak ; Pikachu femelle niveau 50 | `02-patched-team-preview.png` |
| Chargement en combat | Modèle 3D de Pikachu, nom et icône corrects, **95/95 PV** | `03-pikachu-battle-model.png` |
| Capacités conservées | Séisme, Damoclès, Pouv.Antique, Abri ; commande Pouv.Antique sélectionnable | `04-pikachu-preserved-moves.png` |
| Résolution interactive | Pouv.Antique commandé contre Ninjask, puis Laser Glace de Suicune contre Hélédelle ; Pikachu est mis K.O. pendant la résolution et le menu de remplacement fonctionne | `05-turn-resolution.png` |
| Tour terminé | Raikou remplace Pikachu ; Hélédelle est K.O. puis remplacée par Feunard ; retour au menu d'attaque | `06-after-replacement.png`, `07-post-turn-command-menu.png` |

Pikachu est mis K.O. pendant ce tour ; l'exécution de Pouv.Antique n'a pas été constatée. Son animation d'attaque n'a donc pas été validée. Le remplacement d'espèce, son affichage, son chargement en combat et l'accès à ses commandes ont été observés. Les capacités sont volontairement héritées du Donphan d'origine, ce qui ne représente pas un équilibrage de l'équipe.

## Préservation et limites

Dolphin a été fermé proprement, avec un code de sortie **0**. Le contrôle complet exécuté après fermeture confirme que **l'ISO source, les 2 011 fichiers extraits et les 20 fichiers existants du profil Dolphin habituel vérifiés par le manifeste sont inchangés**. L'ISO reconstruite sans patch du premier essai conserve également son SHA-256 `3b4edc03c00f56f029d8cf47b9acbfda32f5f329a9cc9e7d3f8e603af9fc41a7`.

Les **19 tests** passent : lecteurs binaires, LZSS, réencodage FSYS, remplacement ciblé et rejet de modifications supplémentaires. Le vérificateur relit aussi les données de l'ISO finale et confirme qu'un seul enregistrement de Pokémon et ses deux seuls champs autorisés ont changé.

Le test couvre un tour interactif et le retour aux commandes, sans combat complet, parcours intégral, test sur console physique, écriture de sauvegarde en jeu, évaluation audio ou mesure de performances.

## Reproduire

Depuis la racine du projet, choisir un nouveau répertoire de sortie :

```powershell
python scripts/patch_trainer.py --source-iso 'Pokemon Colosseum (Europe) (En,Fr,De,Es,It).iso' --output-dir build/witness-pikachu-2
python scripts/prepare_dolphin_test.py --output build/witness-pikachu-2/dolphin-user
.\scripts\start_dolphin_test.ps1 -Iso build/witness-pikachu-2/colosseum-pal-witness-pikachu.iso -UserDirectory build/witness-pikachu-2/dolphin-user
python scripts/patch_trainer.py --verify-only --output-dir build/witness-pikachu-2
python -m unittest discover -s tests -v
```

Le script refuse d'écraser un répertoire de construction existant. Il lit l'ISO et l'extraction originales, puis écrit tous les résultats sous `build/`. La préparation copie la carte mémoire et le SRAM dans un profil de test isolé. Les sauvegardes d'état créées avec cette ISO doivent être utilisées avec cette même ISO : un état antérieur provenant de l'ISO sans patch pourrait restaurer les anciennes données en mémoire.
