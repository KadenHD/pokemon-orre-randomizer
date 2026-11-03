# Version 0.16 : retrouver les réglages et relire sa configuration

Le moteur reste `details-and-progression-v15`. Les **82 paramètres, dont
57 booléens dans quinze catégories**, leurs valeurs et les domaines de tirage
ne changent pas. La version de l’application passe à 0.16.0 ; le schéma de
profil reste 1.

## Recherche des réglages

En mode Avancé, **Rechercher un réglage…** porte sur les libellés, aides,
catégories et choix traduits dans la langue courante. Les accents sont ignorés ; des synonymes usuels,
comme les termes shiny/chromatique, facilitent la recherche.

Les résultats sont temporaires : un clic ou Entrée ouvre la catégorie du réglage,
le fait défiler dans la zone visible et lui donne le focus. Le formulaire normal
reprend ensuite sa place. Cette action ne change aucune valeur et n’invalide pas
un aperçu dont la configuration reste identique. La recherche ne porte pas sur
les noms des Pokémon de l’aperçu, qui gardent leurs propres champs de recherche.

## Rétablir les valeurs conseillées d’une catégorie

Le bouton **Valeurs conseillées** concerne la catégorie courante et utilise
les valeurs de **Pokémon + capacités**, c’est-à-dire `Options.recommended()`. Cette référence ne reprend
pas le dernier profil importé ni les valeurs du mode Copie à l’identique.

Seuls les champs de cette catégorie sont rétablis. La seed, les chemins, les
autres catégories et la langue restent conservés. Les changements effectifs
invalident l’aperçu ; le moteur doit alors le recalculer avec ces valeurs.
Les contraintes entre catégories restent vérifiées normalement.

## Récapitulatif avant création

Le volet **Réglages appliqués** à l’étape Créer distingue les règles qui seront
appliquées des valeurs simplement mémorisées. Il décrit notamment les choix manuels de starters, contraintes,
statuts chromatiques, niveaux et multiplicateurs actifs. Par exemple, une valeur
d’EXP différente de ×1 est effective, tandis que les trois facteurs de courbe
ne le sont que lorsque la difficulté progressive est activée.

Le résumé ne révèle pas les espèces tirées par la seed. Les starters choisis
manuellement peuvent être nommés puisqu’ils ont été explicitement sélectionnés.
L’aperçu complet reste une action séparée. Le message d’annulation est simplifié
en « Annulation… ». L’ouverture du volet fait défiler la page juste assez pour
montrer les premières lignes de détail, en gardant l’action de création visible.

## Compatibilité des profils et du moteur

Les profils v0.15 conservent leurs 82 champs et leurs valeurs, y compris les
starters manuels, la courbe, l’EXP et la jauge obscure. Leur version, empreinte,
identité de jeu, types de valeurs et liste exacte de champs restent contrôlés.
Un champ manquant ou inconnu n’est pas ignoré. Le réexport porte la version
de l’application courante et le même identifiant de moteur.

Les tests utilisent un profil exporté par l’archive publique v0.15 conservée,
avec les huit ajouts v0.15 non neutres. Les anciens profils v0.14 et antérieurs
gardent leurs règles de migration précédentes.

La régression compare les configurations recommandée et combinée aux preuves
v0.15 dans les trois régions, avec la même ROM, seed et les mêmes options.
Les six ensembles d’offsets, tailles et empreintes de payload correspondent.
Les trois ISO combinées v0.15 sont ensuite comparées intégralement à la source
et au plan de patch courant : tous les octets correspondent. Aucune nouvelle image ISO
n’est écrite par ce contrôle.

Les 39 fichiers du moteur et lecteurs concernés sont aussi identiques aux
sources v0.15 archivées. Le changement de navigation et de métadonnée de version
ne modifie donc pas ces résultats. Les preuves sont privées dans
`build/v16-validation/regression-result.json` ; les trois images originales et
les 46 fichiers du profil Dolphin personnel restent inchangés pendant cet essai.

## Validation automatisée de l’interface

La suite complète exécute **449 tests**, avec deux cas explicitement ignorés.
Les tests de recherche et de récapitulatif couvrent la navigation au clavier,
le focus et le défilement vers un résultat, la remise à zéro limitée à la catégorie,
la conservation de la seed et des autres valeurs, les règles inactives et
l’absence de révélation des tirages aléatoires.

Les deux exécutables v0.16 ont été construits dans des dossiers de staging neufs,
sans reconstruire le codec Rust ni modifier les distributions précédentes.
Leur diagnostic embarqué, exécuté hors écran avec préférences et chemins
temporaires privés, parcourt **168 états par édition**, soit **336 états** :

| Contrôle par édition | États |
| --- | ---: |
| Navigation existante | 48 |
| Dialogues d’exclusion | 24 |
| Options chromatiques | 60 |
| Aperçus synthétiques | 24 |
| Recherche, catégorie et récapitulatif v0.16 | 12 |

Les douze nouveaux états correspondent aux six langues et aux deux tailles
de fenêtre (1040 × 800 et 680 × 540). Les 156 états antérieurs restent comparables
aux diagnostics v0.15. Les deux éditions vérifient aussi leur codec Rust,
l’icône de l’application et leurs ressources respectives : pack local présent,
ressources du jeu absentes de l’édition publique.

Ces diagnostics n’ouvrent aucune ROM ni préférence personnelle et ne lancent
pas Dolphin. Après la revue visuelle, trois fichiers de présentation ont été
ajustés : compteur de résultats, largeur du nom de catégorie, formulation et
défilement du récapitulatif. Les tests ciblés et les douze contrôles de mise en
page dans les six langues aux deux tailles passent avec ces ajustements. Les
deux exécutables finaux repassent leurs 336 états de diagnostic au total. Le
premier staging, les applications v0.15 et les 50 anciens ZIP sont conservés.

La revue visible sous Windows confirme qu’Entrée rejoint le réglage trouvé,
que la remise à zéro des chromatiques conserve la seed et l’EXP à ×2, et que
le récapitulatif conserve ces valeurs en japonais. La version finale affiche
le compteur corrigé, le nom complet de la catégorie et les premières lignes
du volet dès son ouverture. Ce contrôle de présentation s’arrête avant la
création d’une nouvelle ROM. Les preuves privées sont dans
`build/v16-validation/suite/full-source.log`,
`build/v16-frozen-final/staging-validation.json` et `build/v16-runtime/ui-final/`.

## Nouveaux essais QOL dans Dolphin

Les cinq étapes ont été observées dans chacune des trois régions, soit **15
étapes validées sous Dolphin**. Ces essais complètent les observations de combat
en Europe consignées pour la v0.15. [Bilan v0.15](DESKTOP_V15.md)

Les essais utilisent les images combinées de la matrice v0.15, dont le contrôle
binaire ci-dessus confirme la concordance avec le moteur courant. La seed est
`feature-v15-validation-1`, avec **EXP ×2 et jauge ×3**. Les rapports de chaque
image et l’agrégat privé détaillent les autres options et les empreintes.

| Image | Identité | Début du SHA-256 |
| --- | --- | --- |
| USA | `GC6E01` | `8006d9ba6db9ffb0` |
| Japon | `GC6J01` | `90e1570f628c825a` |
| Europe | `GC6P01` | `e03d4da870d5d5a3` |

| Observation native | USA | Japon | Europe |
| --- | --- | --- | --- |
| Marche avec jauge 1 → 0, plancher à zéro et compteur 256 → 0 | Observé | Observé | Observé |
| Libération à la Relique avec réserve 499 → 0, EXP 57 820 → 58 319 et niveau 35 conservé | Observé | Observé | Observé |
| Purification finale avec ruban national, drapeau natif 0 → 1 et total 25 → 26 | Observé | Observé | Observé |
| EXP normale ×2 en combat et niveau 35 → 36 | Gain 673 → 1 346, total 58 319 → 59 665 | Gain 448 → 896, total 58 319 → 59 215 | Gain 448 → 896, total 58 319 → 59 215 |
| EXP ×2 effectivement ajoutée à la réserve du partenaire obscur | 12 313 → 13 659 (+1 346) | 12 313 → 13 209 (+896) | 12 313 → 13 209 (+896) |

La Relique transfère **499 points une seule fois**, à la valeur exacte de la
réserve. La marche observe le delta natif −0,5, multiplié en −1,5. Le jeu
applique ensuite le plancher à zéro et réinitialise le compteur. Les gains
natifs de combat sont relevés dans chaque région avant application du facteur.

Les trois sessions se sont fermées normalement avec un code retour de 0.
L’agrégat `build/v16-runtime/result.json` associe chaque étape à sa capture et à
son empreinte. Après les trois fermetures, `build/v16-runtime/final-preservation.json`
confirme par SHA-256 l’intégrité des **18 fichiers protégés**, dont les **six ROM
ISO et RVZ originales**, ainsi que celle des **46 fichiers du profil Dolphin
personnel**, sauvegardes comprises.

### Préparation et portée des observations

Les essais reprennent sur de **nouvelles cartes préparées hors ligne**. Le
premier Pokémon est Lanturn niveau 35, avec EXP 57 820, réserve 499, jauge 1
et compteur de marche 255. Le total initial de purifications est 25. Tortank
niveau 33 commence avec une réserve de 12 313 et une jauge de 800. Les PV
restaurés proviennent de la guérison native observée dans l’essai Europe
antérieur.

Les PID, IV, EV, capacités et statistiques stockées sont hérités des fixtures
précédentes. Le relevé japonais `fixture-stat-comparison.json` associe les
statistiques initiales de Lanturn et Tortank aux tables d’origine. Le parcours
valide les mécanismes ciblés avec une équipe préexistante. L’acquisition de
cette équipe, les 25 purifications initiales, l’équilibrage et une partie
complète du scénario restent hors de son périmètre.

Les dialogues, choix, déplacements et KO sont réalisés par les commandes du jeu.
Les captures relèvent les arguments, les registres et les changements produits
par les fonctions natives. Dans chaque région, le bridge intervient une fois
pour rejoindre la salle de combat à partir d’une vraie transition de porte.
Après contrôle de l’état initial, il ajuste uniquement la destination et son
argument `r3`. L’audit conserve les destinations et chaque demande du bridge.
La lecture des registres flottants se limite à PS0 dans le protocole RSP utilisé.

Les autres multiplicateurs relèvent des contrôles automatisés. Le témoin de
refus au seuil natif d’EXP obscure figure dans le bilan v0.15. Les preuves,
cartes, captures et audits sont conservés dans le dossier privé `build/v16-runtime/`.

## Distribution Windows

L’édition locale utilise le pack de présentation extrait dans ce projet.
L’édition publique comprend le code source et l’application Windows sans ce
pack. Les archives ne contiennent aucune ROM, sauvegarde ni copie de Dolphin.
Les deux éditions utilisent les exécutables validés et le même codec Rust.
