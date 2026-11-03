# Application de bureau v0.1 — validation locale

Session Windows du 30 octobre 2026. Python 3.12.2, PySide6/Qt 6.11.2,
PyInstaller 6.22.3. La préparation locale ne publie rien sur Internet.

## Moteur et sécurité

58 tests unitaires et intégrations locales passent, dont les tests précédents du
moteur. Les tests Qt couvrent les règles par défaut, les erreurs récupérables et
une fenêtre 680 × 540. Les tests du pipeline couvrent les sorties existantes, les
alias de source, les seeds UTF-8, les échecs de conversion, l'annulation et la
détection d'un octet corrompu hors des plages modifiées. Sans le dump local, les
tests d'intégration du jeu sont explicitement ignorés.

ISO → ISO avec la seed historique de test et trois options activées :

```
source  1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9
sortie  e37dae3666fae8323cb9f9c55c679c170053c96430d0d22fe2c6057e3aeea941
```

La sortie est identique octet pour octet à la v3 déjà essayée sous Dolphin. Les
1 459 978 240 octets sont comparés à la source plus les remplacements exacts attendus.
Le hash source est recalculé à la fin. Aucune extraction `game/` n'est nécessaire.

## Parcours Windows réel

L'application Qt a été ouverte et pilotée avec le sélecteur de fichiers natif,
sur la RVZ locale vierge ; une sortie RVZ distincte a été créée avec le même moteur
et toutes les options. La fenêtre reste réactive pendant le worker et affiche le
succès et le chemin à 100 %. Temps de traitement observé : 34,7 secondes.

```
RVZ source  e7f23723e6dc28dd1660ed38a993102f9b0980b669a3c4c69f9e8b483ac4712b
RVZ sortie  65c80f187615a934fe6167d7c6e3795f807ee1b4f3fd61c2e0782d304ca22952
ISO sortie  e37dae3666fae8323cb9f9c55c679c170053c96430d0d22fe2c6057e3aeea941
```

La RVZ produite a été redécompressée et son ISO comparée par SHA-256 à l'ISO
vérifiée avant compression. La source RVZ est intacte. Les conversions utilisent
un profil DolphinTool temporaire, sans option de suppression des données.

## Distribution et limites

Le build produit un dossier avec DLL Qt remplaçables, le code source MIT, les
licences et les sources exactes des bibliothèques Qt. Les sources du projet sont
choisies par liste positive, excluant ROM, données extraites, captures du jeu,
sauvegardes et émulateur. Les archives et les étapes finales de démarrage du
binaire sont contrôlées localement avant livraison.

Le binaire autonome corrigé a ensuite créé une ISO complète depuis la ROM vierge,
avec le SHA-256 de sortie `e37dae3666fae8323cb9f9c55c679c170053c96430d0d22fe2c6057e3aeea941`.
L'interface affiche le succès à 100 % et la source est intacte. Le build assainit
son PATH pour empêcher l'inclusion de DLL ICU incompatibles provenant d'autres
outils du poste. Les plugins Qt sont limités aux composants nécessaires à cette
interface ; le clavier virtuel, QML, PDF et les plugins d'image inutilisés sont exclus.

Le ZIP des sources a été décompressé dans un dossier temporaire sans `game/` :
58 tests se terminent avec succès, dont 4 intégrations ignorées faute de ROM.
Les deux ZIP passent le contrôle d'intégrité, d'empreinte et d'absence de ROM ou
d'émulateur. Un wheel Python installable a également été construit sans inclure
de données du jeu. Les preuves locales sont conservées dans `build/desktop-*`.

Seul le PAL GC6P01 révision 0 et son hash exact sont pris en charge. L'application
n'a pas été testée sur un autre PC, macOS ou Linux. La création d'une image et les
invariants techniques ne constituent pas une validation de l'équilibrage ou d'une
partie complète. Les essais Dolphin précédents sont dans le rapport v3.
