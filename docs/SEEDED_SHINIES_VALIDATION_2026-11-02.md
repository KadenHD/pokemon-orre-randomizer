# Statuts chromatiques liés à la seed — 2 novembre 2026

La v0.11.0 utilise le moteur `seeded-shiny-status-v12`. Le test à 25 % et seed
`seeded-preview-1` prévoit Galekid chromatique et Héricendre ordinaire pour les
deux starters. Les 54 lignes d’aperçu reprennent les décisions du patch et leurs
portraits natifs, sans recalcul indépendant. Cette seed donne 17 chromatiques
sur ces 54 lignes ; le taux est une probabilité par clé, pas un quota.

L’ISO privée de test porte le SHA-256
`e8696b3c7fbb235ed8535e32e8bd9ea0e1309a33dfd69bf5e563f99859031372`.
La lecture complète de l’image reconstruite est vérifiée. L’ISO vierge reste
au SHA-256 `1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9`.

## Contrôles automatisés

La suite locale exécute 342 tests : 340 réussis et deux ignorés. Les tests du
patch exécutent ses instructions PowerPC avec un générateur natif simulé pour
vérifier les arguments, les propriétaires, les registres préservés, les bornes
de tables et les branches. Ils ne sont pas présentés comme une exécution Dolphin.
La compatibilité du mode natif avec le code conservé de la v0.10.1 est vérifiée
octet par octet pour 0 %, 25 % et 100 %, avec et sans correctif de capacités de
cadeau. Le profil signé conservé de la v0.10 est importé avec la liaison à la seed
désactivée.

## Exécution native contrôlée sous Dolphin

Deux démarrages indépendants utilisent l’ISO exacte et des profils privés sans
carte personnelle ni savestate. Les tables REL et la section DOL chargées sont
comparées aux données de l’ISO avant les appels. Le joueur, ses caches et les
groupes de flags sont des fixtures dans une zone RAM distincte ; aucun fichier de
sauvegarde personnel n’est utilisé.

À chaque démarrage, le vrai constructeur `0x801FE824` traite 81 enregistrements
sélectionnés : les 48 groupes d’obscurs et 33 emplacements ordinaires, dont deux
de même espèce avec des statuts opposés. Il traverse le trampoline de sauvegarde
d’index et le wrapper de production. Les 81 statuts correspondent aux décisions
encodées. Les six véritables routines de génération de starters et cadeaux
correspondent également à l’aperçu. Le point d’observation suit le stockage du
PID et le checksum, avant les callbacks d’acquisition ; le propriétaire fourni
au générateur est relevé pour calculer le critère canonique.

Le deuxième démarrage ajoute 17 appels au RNG natif avant ces essais. Les statuts
restent identiques alors que les PID peuvent varier. Pour le groupe obscur 21,
le test prépare uniquement son flag de rencontre dans le registre RAM isolé :
la branche native `0x801FEC68` restitue le PID mémorisé et contourne le wrapper de
génération. Ce contrôle ne remplace pas une capture jouée ni une sauvegarde/relecture.

Les essais complets de 5 510 constructeurs ont dépassé la limite du harnais :
le rejet natif doit aussi respecter nature et genre. Il est exclu des résultats
réussis ; les deux lots ciblés donnent une couverture bornée et vérifiable. Ces
échantillons choisis ne mesurent pas statistiquement un taux d’apparition.

Les processus CPU sont arrêtés volontairement après les appels synthétiques
(code de diagnostic `0xEE01`). Aucune fermeture normale ni partie jouée n’est
revendiquée pour ces sessions. Les moniteurs confirment la conservation des
originaux protégés et du profil Dolphin personnel ; le débogage des profils QA
est désactivé après chaque essai. Les preuves détaillées restent privées dans
`build/seeded-shinies-2026-11-02/`.
