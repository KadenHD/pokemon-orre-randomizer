# EXP et purification accélérée : contrats natifs régionaux

Les deux réglages sont indépendants et valent **×1 par défaut**. À ×1 tous les
deux, le patch renvoie les octets reçus sans ajouter de section ni modifier le
jeu. Ces options ne réécrivent aucune sauvegarde.

## Effet des réglages

**EXP des combats ×0,25 à ×5** multiplie le gain final de chaque bénéficiaire,
après les bonus natifs d’objet et de propriétaire. Le résultat est arrondi à
l’entier le plus proche, avec un minimum de 1 pour un gain initialement positif.
Le même réglage concerne l’EXP mise en réserve pour un Pokémon obscur lorsque
le jeu l’autorise ; cette réserve n’est pas remultipliée à sa libération.
L’EXP initiale des starters, le niveau de départ et les Super Bonbons gardent
leur traitement d’origine. Les montées de niveau et l’affichage du gain utilisent
la valeur modifiée dans le parcours natif.

**Diminution de la jauge obscure ×1 à ×10** multiplie uniquement les variations
négatives calculées par la routine native de progression de la purification.
Les augmentations de jauge ne sont pas accélérées. Les effets de la nature et
des objets sont calculés avant ce multiplicateur ; le jeu conserve ensuite son
plancher à zéro. L’option ne purifie pas automatiquement un Pokémon et ne
déverrouille aucune scène, Relique ou récompense.

## Qualification des exécutables

Les noms et la lecture du parcours USA proviennent des sources primaires du
[projet de décompilation Colosseum](https://github.com/dougchansan/pkmn-colosseum/tree/ad02df4900c623d16d02b9a8ddd9c53ea0cd3db2),
notamment `pokemon_range_8011F77C.c` et `fight_range_80211A00.c`. Cette source
sert à interpréter les instructions ; elle n’est pas exécutée ni compilée par
l’application.

Les fonctions sont retrouvées séparément dans les trois DOL originaux par une
recherche de leur séquence complète, avec normalisation des appels et adresses
relocalisés. Chaque recherche a un résultat unique dans une section de code.
Le patch de production vérifie ensuite l’empreinte **non normalisée de toute la
fonction**, l’instruction remplacée et l’identité exacte du DOL d’origine.
Il ne calcule pas les adresses régionales à partir d’un décalage commun.

| Région | Fonction EXP | Instruction EXP ciblée | Fonction de jauge | Instruction de jauge ciblée |
| --- | --- | --- | --- | --- |
| Europe `GC6P01` | `0x80227DF4` | `0x80228150` | `0x80123A84` | `0x80123CE0` |
| USA `GC6E01` | `0x802232F4` | `0x80223650` | `0x8011F910` | `0x8011FB6C` |
| Japon `GC6J01` | `0x8021EA8C` | `0x8021EDE8` | `0x8011D0C8` | `0x8011D324` |

Le point EXP précède la séparation entre le gain normal et la mise en réserve
obscure. Le point de jauge remplace l’addition de la variation à la jauge,
juste avant le plancher natif à zéro. Les instructions déplacées sont rejouées
et l’exécution reprend à l’instruction suivante, sans modifier le registre de
retour. Les registres encore nécessaires au parcours natif sont conservés.

Le calcul entier d’EXP utilise un dénominateur de 10 000. Un plafond défensif
de 65 535 avant multiplication évite tout dépassement du calcul sur 32 bits.
Il dépasse les gains natifs admissibles : les 413 lignes d’espèces de chaque
région ont un rendement d’EXP maximal de 255 ; même au niveau 100 avec trois
bonus successifs de ×1,5, le gain par bénéficiaire reste inférieur à 12 295.
Les statistiques randomisées ne modifient pas ce rendement.

Le code ajouté utilise la section `text2` déjà réservée par les patchs de
capacités des cadeaux et de chromatiques, ou crée cette même réservation si
elle est absente. La garde de l’arène est étendue en conséquence. L’empreinte
des fonctions, l’ancienne réservation et la liste exacte des plages modifiables
doivent correspondre avant d’écrire les nouveaux octets.

## Vérifications et limites

Les tests exécutent les instructions PowerPC produites dans un décodeur
indépendant : 189 combinaisons de gains/taux/régions et 72 combinaisons de
jauges/variations/multiplicateurs/régions, avec contrôle du retour, des registres,
de l’arrondi, du minimum et du plancher natif. Les trois exécutables originaux
font aussi l’objet de contrôles de répétabilité, de composition avec les patchs
existants et de rejet d’instructions ou d’en-têtes altérés.

### Observations réelles dans Dolphin Europe

L’ISO combinée Europe a été jouée avec **EXP ×2 et jauge ×3**, sur une copie
de carte de test isolée du profil personnel. Les arrêts sur instructions natives
ont permis de comparer les valeurs avant et après les blocs ajoutés, puis après
les écritures du jeu dans les enregistrements Pokémon :

| Témoin | Valeur native et résultat observé |
| --- | --- |
| Réduction de jauge en combat, Lanturn | Variation −0,5 devenue −1,5 ; jauge entière **6 650 → 6 500** |
| Réduction de jauge en combat, Tortank | Variation −0,75 devenue −2,25 ; jauge entière **800 → 575** |
| EXP, Lanturn encore trop obscur | Gain **673 → 1 346** dans le bloc ; le seuil natif refuse ensuite la mise en réserve, qui reste à **0** |
| EXP, Tortank prêt à recevoir sa réserve | Gain **673 → 1 346** ; réserve réellement écrite par le jeu **12 313 → 13 659**, soit **+1 346** |

Le témoin Lanturn rejeté ne compte donc pas comme un gain appliqué. Celui de
Tortank prouve l’ajout réel d’EXP en réserve. Les captures contrôlent les
registres encore utilisés et le lien de retour ; les fichiers Pokémon bruts
avant/après ne diffèrent que dans la jauge ou la réserve attendue. Le débogueur
expose la moitié PS0 des registres flottants, pas les moitiés paired-single PS1.
Aucune capture ne force un PC, une jauge, une EXP, un résultat de combat ou une
récompense. Deux passages de porte réels utilisent un raccourci de navigation
déclaré et gardé vers Pyrite ; destination et argument natif sont redirigés
ensemble, sans sauter à une instruction de combat.

Les cartes de test contiennent une progression synthétique héritée des essais
de cadeaux. Une incohérence de ces données a été corrigée dans de **nouvelles**
cartes v3 : six Pokémon de l’équipe avaient une jauge positive mais leur drapeau
global indiquait une purification. Douze bits ont été ajustés en conservant le
total de 25, sans modifier les Pokémon, l’EXP, les jauges, le scénario ou les
anciens emplacements de sauvegarde. Le premier témoin Tortank provient de
l’ancienne carte ; le témoin Lanturn de jauge et les deux témoins EXP proviennent
du nouvel essai cohérent. Ce changement de fixture n’est pas un correctif du
patch de production et ne prouve pas 25 purifications jouées.

La guérison des six Pokémon a aussi été effectuée auprès de l’infirmière native
dans l’essai Europe. Des cartes USA/Japon distinctes ont ensuite reçu uniquement
les trois octets de PV restaurés observés dans cette guérison, pour préparer
d’éventuels essais. Cette préparation hors ligne ne constitue pas une guérison
jouée ni une validation QOL sur ces deux régions.

Les deux processus Dolphin Europe se sont fermés normalement. Les empreintes
avant/après des fichiers protégés, des ROM originales et du profil Dolphin
personnel sont identiques. Les gardes de l’outil de test ont également refusé
les demandes hors contrat ; ces refus et les erreurs de lecture sont conservés
séparément des captures réussies.

### Limites restantes

**Les nouveaux parcours QOL USA et Japon n’ont pas été joués dans cet essai.**
Leurs contrats natifs, la matrice de données et les instructions PowerPC sont
qualifiés séparément ; cela ne remplace pas une observation régionale réelle.
Aucune montée de niveau d’un Pokémon normal, libération de réserve lors de la
purification finale, diminution déclenchée par la marche ou branche du plancher
de jauge à zéro n’a été observée ici. Les autres multiplicateurs restent couverts
par les contrôles automatisés. Aucune partie complète ni validation de
l’équilibrage n’est revendiquée.

Les rapports de création antérieurs gardent leur indication initiale de
validation à effectuer. L’agrégat privé daté `build/v15-runtime/result.json`
décrit les observations ultérieures et leurs limites, sans réécrire ces rapports.

Les listings, les empreintes de recherche et le clone source épinglé restent
privés dans `build/qol-v15/`. Les captures, cartes et moniteurs de cette exécution
restent dans `build/v15-runtime/`. Les données du jeu ne sont pas distribuées.

### Suivi distinct en v0.16

Les [notes de validation v0.16](DESKTOP_V16.md) consignent les observations
supplémentaires USA/Japon et l’état du nouvel essai Europe. Elles distinguent
chaque étape réellement jouée, les préconditions synthétiques et les limites du
bridge. Elles complètent ce compte rendu historique sans élargir sa portée.
