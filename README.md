# Pokémon Orre Randomizer

Application de bureau open source pour randomiser les jeux Pokémon de la région
de Rhode (Orre en anglais). L’accueil propose **Pokémon Colosseum**, compatible
avec les ROM vierges Europe, USA ou Japon en ISO et RVZ. **Pokémon XD** y est
annoncé comme prochain jeu. Le traitement se fait sur votre ordinateur, avec une
nouvelle image enregistrée à côté de la ROM d’origine ou à l’emplacement choisi.

## Utiliser l'application

Sous Windows 10/11 x64, extraire **tout** le ZIP Windows disponible dans **Releases**,
puis ouvrir `OrreRandomizer.exe` et choisir **Pokémon Colosseum**. Conserver le dossier
`_internal` à côté de l’exécutable. Python n’est pas nécessaire pour cette version.

L’icône **Éclipse**, fournie en tailles 16 à 256 px, est intégrée à l’exécutable et
aux fenêtres de l’outil. Elle est incluse dans les deux éditions.

La langue de l'interface suit automatiquement le système : **français, anglais,
allemand, espagnol, italien ou japonais**, avec repli sur l'anglais pour les autres
langues. Le sélecteur en haut de la fenêtre propose **Système**, **Français**,
**English**, **Deutsch**, **Español**, **Italiano** et **日本語**, même sans ROM chargée.
Le changement est immédiat, conserve le formulaire et reste mémorisé au prochain
lancement. Il s'applique aussi aux descriptions, erreurs et messages de progression.
Ce réglage ne change pas la langue du jeu ni les données randomisées.
Les noms des pierres évolutives suivent la langue choisie dans le jeu. La ROM
européenne conserve ses cinq traductions natives ; la ROM USA conserve l’anglais
et la ROM japonaise le japonais. Choisir une langue dans l’outil ne traduit pas
le jeu. Les trois révisions exactes acceptées sont indiquées ci-dessous.
Les dialogues ajoutés pour Adelbert suivent aussi la langue choisie dans le jeu :
français, anglais, allemand, espagnol ou italien en Europe, anglais aux USA,
japonais au Japon, indépendamment des six langues
proposées par l’interface de l’outil.

Le parcours **ROM → Réglages → Créer** montre une étape à la fois. Le mode
**Simple** propose trois points de départ :

| Choix | Effet |
| --- | --- |
| **Pokémon + capacités** | Remplace les Pokémon avec une puissance proche de l’original ; randomise aussi les capacités, les apprentissages par niveau, les CT et les objets des coffres et boutiques. |
| **Pokémon seuls** | Remplace les Pokémon sans équilibrer leur puissance ; conserve les capacités, les apprentissages, les CT et les objets, sauf les pierres ajoutées en boutique. |
| **Copie à l’identique** | Crée une nouvelle ROM sans randomisation, avec conversion ISO/RVZ possible. |

Les deux modes randomisés concernent les dresseurs, les obscurs, les starters et les
cadeaux. Ils adaptent les évolutions à Colosseum, vendent les pierres à Phénacit et
Pyrite et évitent les familles d’obscurs en double. Le mode **Avancé** permet de
modifier chaque option ; revenir en Simple conserve ces réglages personnalisés.

L’étape Réglages sépare **Configuration** et **Aperçu des Pokémon**. La seed reste
visible dans les deux vues ; le menu **Profils** permet d’importer ou d’exporter
les réglages. En Avancé, les catégories s’affichent à gauche si la fenêtre est assez
grande, sinon dans un sélecteur au-dessus du formulaire. Seul le contenu actif défile.
La molette ne modifie une valeur numérique ou une liste de choix qu’après lui avoir
donné le focus ; ailleurs, elle fait défiler le formulaire.

En Avancé, **Rechercher un réglage…** retrouve les réglages dans les libellés,
aides, catégories et choix affichés dans la langue courante, sans tenir compte des accents. Choisir
un résultat ouvre sa catégorie et place le focus sur le champ ; la recherche ne
modifie aucun réglage. **Valeurs conseillées** rétablit cette seule catégorie
selon le mode **Pokémon + capacités**. La seed, les chemins
et les autres catégories sont conservés.

Par défaut, les deux starters sont des **formes de base de familles à trois stades**,
avec deux évolutions successives disponibles dans Colosseum. Dans **Avancé →
Starters et cadeaux**, **Stade des starters** propose Tous les stades, Forme de
base, Première évolution ou Évolution finale. **Familles à trois stades uniquement**
est indépendant de ce choix et peut être désactivé. Les starters d’origine
conservés restent inchangés, comme les niveaux de départ. Trois stades signifient
deux évolutions : Bulbizarre → Herbizarre → Florizarre. Les branches d’Évoli ne
comptent pas comme des évolutions successives.

Les listes **Premier starter** et **Second starter** permettent aussi de choisir
une espèce par son nom ou son numéro national du Pokédex. **Tirage avec la seed**
laisse le moteur choisir ; il est possible de fixer un seul Pokémon. Un choix
manuel remplace les filtres de stade, de famille à trois stades et de puissance
individuelle pour ce starter. Les exclusions, générations autorisées, règles sur
les légendaires et contraintes du duo restent obligatoires. Pour conserver Noctali
ou Mentali d’origine, décocher son remplacement ; le choix manuel correspondant
est alors ignoré.

Dans **Avancé → Starters et cadeaux**, **Rendre les cadeaux événementiels accessibles**
permet de recevoir les cadeaux de Pikachu et Celebi auprès d’Adelbert, près de la
Relique Sacrée. L’option est activée dans les deux préréglages randomisés et désactivée
dans Copie à l’identique. Par défaut, le cadeau de Pikachu demande **10 obscurs purifiés**
et est reçu au **niveau 30** ; celui de Celebi demande **25 purifications**, au **niveau 45**.
Les deux seuils et les deux niveaux se règlent séparément. Les espèces et statuts
chromatiques correspondent à l’aperçu ; chaque cadeau ne peut être reçu qu’une fois
par sauvegarde.

Adelbert devient disponible après toutes les scènes d’introduction à la purification,
y compris le suivi dans sa maison après le combat contre Skrub. Son apparition dans
la maison et au sanctuaire est exclusive : un seul Adelbert est présent à la fois.
Même avec un seuil de zéro purification, ces scènes doivent être terminées.

Dans **Avancé → Pokémon autorisés**, les listes **Pokémon exclus** et **Types
d’origine exclus** permettent de retirer des espèces des tirages. La recherche
accepte un nom ou un numéro du Pokédex ; une case cochée signifie « exclu ».
Ces filtres concernent tous les remplacements, y compris les starters, les cadeaux
et les obscurs. Ils utilisent les types du jeu d’origine, même si les types sont
randomisés. Exclure une espèce n’exclut pas le reste de sa famille.

Dans **Avancé → Dresseurs**, **Types des équipes non obscures** propose un type
commun tiré au hasard ou le type commun d’origine lorsqu’il existe et reste
admissible. Les Pokémon obscurs gardent leur tirage et ne suivent pas le thème.
Les équipes qui partagent les mêmes enregistrements dans le jeu partagent aussi
leur thème. Le remplacement des Pokémon non obscurs doit être activé.

**Adversaires non obscurs au stade final** impose des formes sans évolution à
partir du niveau choisi (40 par défaut). Le seuil utilise les niveaux après
les multiplicateurs et les bonus des boss. Sans remplacement aléatoire des
espèces, les adversaires évoluent dans leur propre famille ; sinon, le tirage
utilise les formes finales autorisées. Les obscurs, starters et cadeaux ne sont
pas concernés. Les exclusions restent obligatoires ; si aucun tirage ne respecte
les contraintes, la création s’arrête sans produire de ROM.

Ces trois ajouts sont désactivés par défaut. Le mode **Copie à l’identique** reste
sans modification. Les profils 0.5 à 0.8 sont importés en conservant les anciens
tirages et sans activer les nouvelles règles.

Dans **Avancé → Niveaux et capture**, **Difficulté progressive** remplace le
multiplicateur global par trois valeurs selon le **niveau d’origine** de
l’adversaire : 1–35, 36–50 et 51–100. Chaque valeur va de ×0,5 à ×2. Les bonus
des boss sont appliqués ensuite, puis le filtre de stade final utilise ce niveau
modifié. Ces plages ne désignent pas des chapitres du scénario. Starters et
cadeaux gardent leur propre niveau.

**Expérience gagnée ×** règle le gain en combat de ×0,25 à ×5, par pas de 0,25.
**Vitesse de purification ×** règle la diminution de la jauge obscure de ×1 à
×10. Ces deux options valent **×1 par défaut**. La seconde ne remplace pas la
purification finale à la Relique. Leurs contrats natifs et l’état de validation
sont décrits dans [les notes v0.15](docs/DESKTOP_V15.md).

Dans **Avancé → Chromatiques**, **Personnaliser les shinies** active un taux de
**0 à 100 %** pour les nouveaux Pokémon des dresseurs, obscurs, starters et cadeaux
identifiés. **0 % : aucun ; 100 % : tous**. Décoché, le jeu conserve son comportement
d’origine, y compris ses restrictions sur les starters et cadeaux. Les deux
préréglages randomisés de l’interface activent un taux de **5 % lié à la seed**.

Avec **Lier les chromatiques à la seed**, coché par défaut, la seed fixe le statut
de chaque starter, cadeau, obscur et emplacement de dresseur. L’aperçu des starters,
obscurs et cadeaux montre les statuts exacts pour une **nouvelle partie**, même
en dessous de 100 %, avec les vrais portraits normaux ou chromatiques de la ROM
et une petite étoile rouge près du nom des Pokémon chromatiques. Deux rencontres de la même espèce peuvent avoir des
statuts différents. Le taux est une probabilité par rencontre, sans quota imposé
sur les Pokémon affichés.

Décocher cette nouvelle option conserve le tirage en jeu au taux choisi ; aux
taux intermédiaires, l’aperçu indique alors que le statut sera décidé en jeu.
Nature, genre, IV et PID complet restent générés par le jeu dans les deux modes.
Un obscur garde son statut après capture et purification ; un Pokémon déjà
généré ne fait pas l’objet d’un nouveau tirage. Une sauvegarde existante peut donc
contenir des Pokémon différents de l’aperçu d’une nouvelle partie.

Les profils 0.5 à 0.10.1 sont importés avec la liaison à la seed désactivée pour
conserver leurs sorties antérieures ; les profils antérieurs à 0.10 gardent aussi
la personnalisation des shinies désactivée. La liaison n’a aucun effet tant que
**Personnaliser les shinies** est décoché. [Détails techniques](docs/SHINIES.md).

Dans **Aperçu des Pokémon**, **Calculer l’aperçu** utilise la ROM, la seed et les
réglages actuels, avec le même moteur que la création et sans enregistrer de nouvelle
ROM. Les onglets **Starters · 2**, **Obscurs · 48** et **Cadeaux · 4** partagent ce
calcul : portraits, noms et niveaux disponibles. Les deux listes comparent les
espèces d’origine aux remplaçants, avec une recherche et un compteur de lignes.
Avant le calcul, un « ? » indique un remplaçant à tirer. Un starter conservé
ou choisi manuellement peut déjà être nommé.
Les cadeaux accessibles auprès d’Adelbert affichent le donneur et leur seuil de
purifications. Sans l’option d’accès, les cadeaux événementiels restent signalés
comme tels et gardent leurs conditions d’origine. Après un changement de seed ou d’options, **Actualiser l’aperçu** devient
disponible. Des portraits défilent pendant le calcul, qui reste annulable. **✓ Aperçu à jour**
remplace le bouton tant que la configuration est identique. Les portraits sont
lus dans la ROM sélectionnée et ne sont pas téléchargés.

Si le tirage conserve des familles en double avec la règle d’unicité entre
starters, obscurs et cadeaux, l’onglet **Doublons** indique les Pokémon concernés.

Cliquez sur **Fiche du Pokémon** sous un starter, ou sur une ligne de rencontre.
La fiche regroupe le résumé, les capacités et les évolutions en trois onglets.
Les propriétés décrivent les
données finales de cette partie, y compris les types ou évolutions modifiés.
Un obscur doit être purifié avant de pouvoir évoluer. Les noms et les conditions
sont présentés dans la langue de l’outil ; un talent possible ne constitue pas
une prédiction du talent individuel que le jeu attribuera.

Pour une RVZ, DolphinTool décompresse une seule ISO temporaire par fenêtre.
Changer seulement la seed ou les options réutilise cette ISO après vérification
des empreintes de la source, de l’ISO et de l’outil. Le cache est supprimé à la
fermeture de la fenêtre, lors d’un changement de ROM ou d’outil, ou après une erreur.

La création peut réutiliser les modifications calculées par l’aperçu après avoir
vérifié les empreintes de la ROM, la seed et les réglages. Le rapport indique si
le calcul a été réutilisé. La sortie est toujours vérifiée intégralement.

Les boutons **Musique** et **Sons** sont indépendants et activés au premier
lancement lorsque le pack audio est présent. Les préférences de langue et de son sont mémorisées séparément
des profils. La construction locale embarque les images et sons exportés : aucun
cache préalable ni téléchargement n’est nécessaire. L’archive publique conserve
les cadres et contrôles dessinés par l’application, sans ressources du jeu.
Les deux éditions démarrent sans ROM et utilisent le même moteur et les mêmes profils.

1. Sélectionner ou déposer sa ROM ISO/RVZ vierge.
2. Saisir une seed et choisir les règles, ou importer un profil depuis le menu de l’en-tête.
3. Choisir un nouveau fichier de sortie ISO ou RVZ, puis créer la ROM.
4. Après vérification, ouvrir cette nouvelle image dans Dolphin et commencer une
   nouvelle partie pour obtenir les starters et les rencontres randomisés.

Pour lire ou produire une **RVZ**, sélectionner `DolphinTool.exe` fourni avec votre
installation de [Dolphin](https://dolphin-emu.org/download/). Le traitement ISO → ISO
fonctionne sans DolphinTool. L'application ne lance pas l'émulateur et ne touche
pas aux sauvegardes ni au profil Dolphin existant.

Le champ DolphinTool apparaît à l’étape ROM pour une source `.rvz`, et à l’étape
Créer pour une sortie RVZ. Les deux champs partagent le même chemin.
Le format de sortie proposé suit celui de la ROM sélectionnée : ISO → ISO, RVZ → RVZ.
Vous pouvez ensuite choisir l’autre format.

Le volet **Réglages appliqués** de l’étape **Créer** récapitule les règles
qui seront effectivement appliquées :
choix manuels, contraintes actives, taux et multiplicateurs. Une option mémorisée
mais désactivée par son interrupteur principal n’est pas annoncée comme appliquée.
Ce récapitulatif ne révèle pas les Pokémon qui seront tirés par la seed ; l’aperçu
reste une action distincte.

Un rapport `nom-de-la-ROM.iso.json` (ou `.rvz.json`) contient la seed exacte, les
options, les versions et les empreintes SHA-256. Garder ce rapport pour reproduire
la partie. Même source, seed, options et version du moteur : même ISO ; les octets
de compression RVZ peuvent dépendre de la version de DolphinTool.

Dans **Profils → Reprendre depuis un rapport…**, sélectionnez ce fichier JSON
pour charger sa seed et ses réglages. La ROM et la destination déjà sélectionnées
sont conservées. L’application compare la ROM sélectionnée à celle du rapport.

Un journal **`nom-de-la-ROM.iso.html`** ou **`.rvz.html`** accompagne aussi la
sortie. Il présente les starters, obscurs, cadeaux, équipes, évolutions et CT dans
des sections repliées pour éviter les spoilers. **Ouvrir le journal** est proposé
après création. Il utilise la langue courante de l’interface ; en CLI,
`--journal-language fr|en|de|es|it|ja` la choisit explicitement, avec le français
par défaut. Ce fichier se lit hors ligne, sans images ni scripts externes, et ne
reprend pas les chemins de la ROM source ou de destination. Une sortie, un rapport
ou un journal existant n’est jamais remplacé.

Les boutons **Importer un profil…** et **Exporter le profil…** échangent un petit
fichier JSON contenant la seed, les 83 réglages, la version du moteur et l’identité
de la ROM compatible. Aucun chemin personnel ni donnée du jeu n’y figure.
L’import conserve les chemins source et destination déjà choisis. Les profils des
v0.5 et v0.6 restent acceptés : la nouvelle correction des noms de pierres y est
désactivée pour conserver les sorties d’origine.
Les profils 0.5 à 0.12 sont importés avec l’accès aux cadeaux événementiels désactivé
pour conserver leurs tirages et les conditions d’obtention précédentes. Les profils
0.11 et 0.12 conservent aussi leur choix de statuts chromatiques liés à la seed.
L'empreinte du contenu est vérifiée ; celle-ci
détecte une modification accidentelle, sans constituer une signature d’auteur.
Un fichier existant n’est jamais remplacé lors de l’export.
Les profils jusqu’à la v0.14 importent les huit nouveaux réglages v0.15 avec les
starters sur **Tirage avec la seed**, la courbe désactivée et les multiplicateurs à ×1.

## Compatibilité

Trois versions **révision 0**, images complètes de 1 459 978 240 octets une fois
décompressées. Le SHA-256 complet doit correspondre à l’en-tête régional :

| Région | Identifiant | SHA-256 de l’ISO vierge |
| --- | --- | --- |
| Europe, cinq langues | `GC6P01` | `1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9` |
| USA, anglais | `GC6E01` | `78c4074429fa598b97bfac296bf8e0f7e93f5cb6d8679f8d2653ca902820f6c5` |
| Japon, japonais | `GC6J01` | `17c284ab2592083b91d33229ea03384ccdd397eab5db5d3a6ddf5b1f9685368f` |

Les données, adresses natives, boutiques, capacités et patchs chromatiques sont
sélectionnés par empreinte pour chaque région. La v0.16 importe les profils
v0.15 sans changer leurs 82 réglages ; le moteur reste `details-and-progression-v15`.
Les profils v0.14 gardent les nouveaux réglages neutres lors de leur import.
Les profils de réglages peuvent
être utilisés avec les trois ROM. Pour reproduire exactement une image, conserver
aussi sa région d’origine et le rapport de création.

[Validation des trois régions et limites](docs/REGIONAL_COMPATIBILITY_2026-11-03.md).
[Cadeaux USA/Japon : acquisition, dialogues, sauvegarde et rechargement](docs/REGIONAL_GIFTS_DOLPHIN_2026-11-03.md).
[Nouveautés v0.15 et validation des trois régions](docs/DESKTOP_V15.md).
[Navigation et validation v0.16](docs/DESKTOP_V16.md).

Les autres révisions, ROM déjà randomisées, images tronquées ou dont les
données ont été supprimées sont refusées. Aucune ROM, BIOS, sauvegarde ni installation
Dolphin n’est fournie. Le pack visuel et sonore de cette construction locale est
exporté de la ROM locale fournie dans ce projet ; il permet d’utiliser l’interface sans fournir de ROM.

Prévoir environ **1,5 Gio** libres pour ISO → ISO, **2,8 Gio** pour RVZ → ISO et
jusqu'à **5,6 Gio** pour RVZ → RVZ. Les fichiers temporaires sont supprimés après
réussite, erreur ou annulation normale ; une fermeture forcée du processus peut
laisser un dossier `.colosseum-*` à retirer manuellement après arrêt de l'application.
L’aperçu RVZ peut aussi conserver environ **1,5 Gio** dans le dossier temporaire
du système tant que sa fenêtre reste ouverte. L’annulation est contrôlée pendant
la recompression LZSS, dans les codecs Rust et Python ; elle n’attend plus la fin
d’un membre compressé. Les conversions DolphinTool sont également surveillées
et arrêtées en cas d’annulation.

## Règles

**83 paramètres, dont 58 cases à cocher**, sont répartis en quinze catégories.
Dans les deux préréglages randomisés, l’option **Éviter les familles en double dans
l’histoire** coordonne les starters, les obscurs et les cadeaux. Les Pokémon
conservés ou choisis manuellement et les contraintes strictes gardent la priorité.
Le rapport de création indique les doublons restants. Les profils antérieurs
à la v0.18 importent cette option désactivée pour reproduire leur tirage.
Chaque changement possède son propre réglage :

- **Noms des pierres** : ajouter les espaces manquants dans les cinq traductions
  natives, sans changer les objets ni les autres textes. Le mode Copie à l’identique garde les
  noms d’origine.
- **Dresseurs** : Pokémon ordinaires, Pokémon obscurs et familles obscures uniques.
  Avec tout activé : 3 355 Pokémon chez 817 dresseurs, dont les 48 groupes obscurs.
- **Starters et dons** : une case pour chacun de Noctali, Mentali, Posipi, Ho-Oh,
  Celebi et Pikachu événementiel.
  Les niveaux d’origine sont conservés et l’EXP des starters est adaptée. Activer
  l’accès aux cadeaux événementiels ajoute les deux récompenses d’Adelbert, avec
  leurs seuils de purification et niveaux de réception configurables.
  Les contraintes du duo sont indépendantes : puissance proche entre eux, familles
  différentes et aucun type partagé. Le stade et le filtre de familles à trois
  stades se règlent séparément ; le choix manuel d’une espèce est aussi disponible.
  Les espèces sans préévolution, même sans évolution, sont des formes de base.
  Un starter non randomisé reste intact et contraint le choix de son partenaire.
- **Capacités** : attaques des dresseurs, des starters et des dons ; apprentissages
  par niveau. Choix cohérent ou chaos ; attaque offensive et du même type,
  absence de doublons, exclusion de Destruction/Explosion et des K.O. en un coup.
  Charge Noire et les marqueurs spéciaux du jeu sont préservés.
- **CT** : mélanger les 50 capacités natives avec leurs descriptions ; conserver
  les compatibilités, suivre les types, tout autoriser ou tirer au hasard.
  Garantir une CT offensive compatible lors d'une réécriture. Les huit CS sont
  conservées. Cela ne donne pas automatiquement l'objet CT au joueur.
- **Boss** : renforcer les Pokémon non obscurs de sept chefs identifiés et leurs
  variantes ; éviter les doublons de famille modifiables dans leurs équipes.
  Le nombre de Pokémon est conservé. Les obscurs suivent leur tirage global,
  avec trois réglages supplémentaires : statut légendaire libre/conservé/exclu,
  puissance globale/proche/libre et total natif minimal. Ces règles concernent
  sept groupes obscurs identifiés et synchronisent toutes leurs réapparitions.
  Elles ne changent ni niveaux ni capture. Les familles restent distinctes à
  l’échelle des 48 obscurs lorsque cette protection est activée.
- **Espèces autorisées** : générations I, II et III, légendaires/fabuleux,
  remplacements de puissance comparable. Cette sélection filtrée exclut Munja
  pour éviter les blocages liés à Garde Mystik.
- **Talents, statistiques et types** : trois randomisations indépendantes ;
  cohérence par famille pour les types/talents, conservation facultative du total
  des statistiques. La mécanique particulière de Munja reste protégée.
- **Objets tenus** : remplacer les objets déjà présents chez les adversaires,
  avec une sélection limitée aux objets de combat si souhaité.
- **Objets trouvés** : randomiser les objets ordinaires de 38 coffres admissibles,
  avec valeur comparable et conservation des Balls si souhaité. Les objets clés,
  Flûtes du Temps, pierres, quantités et positions sont protégés. Les récompenses
  scriptées des personnages restent d'origine.
- **Difficulté et capture** : niveaux des adversaires ×0,5 à ×2 ; taux de capture
  obscurs ×0,25 à ×5 et minimum configurable entre 0 et 255. La difficulté
  progressive propose trois multiplicateurs au lieu du multiplicateur global.
  EXP des combats ×0,25 à ×5 et vitesse de diminution de la jauge obscure ×1 à ×10,
  avec ×1 par défaut pour les deux.
- **Évolutions** : échanges simples ; échanges avec objet ; Coquiperl ; Évoli vers
  Mentali/Noctali ; beauté de Barpau. Chaque catégorie peut rester d'origine.
  Onix évolue en Steelix à une montée de niveau dès le niveau 40 si les échanges
  avec objet sont adaptés. Les obscurs doivent être purifiés avant d'évoluer.
- **Boutiques** : une case pour Phénacit et une pour Pyrite. Ajouter les six pierres
  à 2 100 chacune tout en conservant le stock. Le prix de la Pierre Lune suit ces
  options automatiquement. Une évolution adaptée utilisant une pierre exige qu'au
  moins une boutique reste activée, pour éviter de bloquer cette évolution.
  Six stocks identifiés peuvent être randomisés séparément, avec conservation
  facultative des soins. Les devises spéciales, autres listes et pierres restent
  protégées.
- **Chromatiques** : personnalisation facultative du taux de 0 à 100 %, avec
  liaison à la seed cochée par défaut ou tirage en jeu si elle est décochée.
  Les statuts fixés par la seed sont visibles dans l’aperçu d’une nouvelle partie.

« Réglages conseillés » active les espèces, les quatre randomisations de
capacités en mode cohérent, la puissance comparable, les protections, les
évolutions accessibles et les boutiques. Il ajoute les CT selon les types,
les coffres, les stocks avec soins conservés et la variété des boss.
Il impose aussi des starters de familles différentes, sans type commun et de
puissance proche entre eux. Les deux préréglages randomisés commencent avec des
formes de base de familles à trois stades ; ces deux filtres restent modifiables.
Les obscurs de boss suivent par défaut les filtres et l’équilibrage globaux ;
leur statut légendaire d’origine n’est pas imposé.
Types, talents, statistiques, objets tenus et renforcement des boss restent
optionnels ; niveaux et capture restent à ×1.
« Tout désactiver » produit une copie
vérifiée, identique à l'ISO originale, sans recomprimer les archives inutiles.
La règle de familles uniques ne s'applique que si les obscurs sont randomisés.
Les 48 groupes restent synchronisés et toutes les formes évolutives sont éligibles.

Le graphe des familles est conservé. Le détail des 15 changements d'évolution est
dans [le rapport v3](docs/reverse-engineering/RANDOMIZER_V3.md).
L'intégrité binaire est vérifiée à chaque création. Le
[rapport Dolphin du 31 octobre 2026](docs/DOLPHIN_VALIDATION_2026-10-31.md)
consigne les contrôles fonctionnels des starters, de la purification, des CT,
de l'évolution d'Onix, d'un achat, d'un coffre et de la capture d'un obscur, ainsi
que l'état des essais de boss et de conservation. Les essais utilisent des
copies préparées ; ils ne certifient ni une partie complète, ni l'équilibrage,
ni le fonctionnement sur console physique. Les essais précédents restent
documentés dans [les recherches](RESEARCH.md).

Les contrôles complémentaires, les deux éditions et les commandes de diagnostic
sont décrits dans [la préparation des distributions](docs/RELEASE.md).

## Lancer depuis les sources

Python 3.12 ou plus récent :

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e .
python -m colosseum_randomizer
```

Dans ce projet, ouvrir l’exécutable sous `dist/windows/OrreRandomizer-<version>/`
pour lancer l'interface sans terminal. Le raccourci local `Ouvrir Colosseum Randomizer.lnk`
pointe vers cet exécutable. `lancer-randomizer.ps1` reste disponible et ouvre en priorité
l'exécutable construit dans une fenêtre visible ; en cas d'erreur, le diagnostic reste affiché.
Pour utiliser la même fonction sans interface :

```powershell
python -m colosseum_randomizer.cli original.iso nouvelle-partie.iso --seed ma-seed
python -m colosseum_randomizer.cli original.rvz nouvelle-partie.rvz --seed ma-seed --dolphin-tool C:\Dolphin\DolphinTool.exe
python -m colosseum_randomizer.cli original.iso partie-partagee.iso --profile ma-partie.json
python -m colosseum_randomizer.cli original.iso duo.iso --seed ma-seed --starter-umbreon-species 94 --starter-espeon-species 208 --journal-language en
```

Chaque règle possède aussi `--nom-de-regle` et `--no-nom-de-regle` en CLI, par exemple
`--no-starter-umbreon --no-gift-hooh --no-evolve-beauty`. `--help` liste tous les
paramètres. En CLI, les nouveaux changements restent désactivés par défaut pour
conserver les anciens usages ; ajouter par exemple :

```powershell
python -m colosseum_randomizer.cli original.iso chaos.iso --seed ma-seed --randomize-trainer-moves --randomize-starter-moves --randomize-gift-moves --randomize-learnsets --moves-mode balanced --balance-species
```

L'orchestration utilise la bibliothèque standard Python ; Qt sert à l'interface.
Le binaire Windows inclut un codec LZSS Rust accéléré. Depuis les sources, le codec
Python fonctionne sans Rust ; pour activer l'accélération avec un outil Rust installé :

```powershell
python scripts/build_native.py
```

Les encodages Python et Rust produisent les mêmes octets, avec décodeurs et tests
croisés. Aucun dossier `game/` extrait n'est requis pour créer une ROM. Le rapport
indique le codec utilisé et les temps par étape. Les mesures locales sont dans
[la validation v0.2](docs/DESKTOP_V02.md). Les nouveaux réglages et leurs limites
sont décrits dans [la validation v0.3](docs/DESKTOP_V03.md) et
[la validation v0.4](docs/DESKTOP_V04.md). Les fiches, starters manuels, courbe,
EXP, purification et contrôles de la v0.15 sont dans [les notes v0.15](docs/DESKTOP_V15.md).

## Développer et distribuer

[Contribution et construction Windows](CONTRIBUTING.md), [licence MIT](LICENSE),
[notices des dépendances](THIRD_PARTY_NOTICES.md), [validation locale](docs/DESKTOP_VALIDATION.md).
Les ZIP de distribution utilisent une liste explicite de fichiers autorisés pour
exclure les données du jeu. Aucun dépôt ou binaire n'est publié automatiquement.
