# Isolation et statut de fermeture des essais Dolphin

Recherche du 31 octobre 2026. Le binaire local porte l’étiquette UI Dolphin
2609a. Les sources officielles du tag 2609a ont été récupérées au commit
`409881c34357d0f105fd473167d15ab0bd9c1628`, avec leurs SHA-256 dans le manifeste
local `build/dolphin-validation/references-isolation/manifest.json`. Le binaire
est empreinté séparément à chaque essai ; cette recherche ne prétend pas établir
une équivalence de compilation entre le binaire et les sources.

## Ce que le code établit

L’option `-u`/`--user` est déclarée par
[CommandLineParse.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/UICommon/CommandLineParse.cpp).
Dans [Main.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/DolphinQt/Main.cpp),
`SetUserDirectory` reçoit ce chemin avant l’initialisation des configurations et
de `Settings`. Le répertoire explicite est prioritaire sur les mécanismes de
repli Windows. Le fichier `portable.txt` impose un repli dans `User/` à côté de
l’exécutable lorsqu’aucun chemin explicite n’est fourni.
[UICommon.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/UICommon/UICommon.cpp)

`Settings::GetQSettings` place `Qt.ini` sous le répertoire de configuration
issu du chemin utilisateur.
[Settings.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/DolphinQt/Settings.cpp)
Les chemins reconstruits par Dolphin placent le SRAM GameCube dans son
répertoire GC utilisateur ; la configuration de démarrage emploie ce chemin.
[FileUtil.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Common/FileUtil.cpp),
[ConfigManager.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/ConfigManager.cpp)

Un chemin de carte mémoire indiqué dans un INI peut toutefois viser un fichier
externe au profil. L’argument `-u` seul ne remplace donc pas la vérification des
chemins configurés.

La fin normale de `MainWindow::OnStopComplete`, lorsqu’une sortie est demandée,
appelle `QGuiApplication::exit(0)`.
[MainWindow.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/DolphinQt/MainWindow.cpp)
`Main.cpp` renvoie le résultat de la boucle Qt ; certains échecs de démarrage
produisent explicitement 1. Ces observations statiques ne suffisent pas à
expliquer le statut 1 de l’ancien lanceur après une session jouée.

## Corrections du dispositif de validation

`scripts/run_dolphin_validation.py` lance directement une liste d’arguments par
`subprocess.Popen`, sans shell intermédiaire. Il inscrit le PID, les arguments,
les chemins et le statut `running` dans un rapport JSON, puis le véritable
`return_code` du processus et son équivalent hexadécimal à sa fermeture.
Les lecteurs peuvent suivre les mises à jour atomiques du JSON. Les captures
stdout/stderr restent dans deux fichiers associés ; un fichier existant est
refusé. Le statut du moniteur est distinct du code natif consigné.

Le lanceur exige une copie de Dolphin avec `portable.txt`, un profil préparé et
un rapport situés sous `build/`. Les liens symboliques, jonctions et fichiers
liés matériellement sont refusés pour les cibles de validation. Les chemins
modifiables connus des INI de configuration et de jeu doivent rester dans le
profil de l’essai. Les sections Gecko natives à lignes sans affectation sont
acceptées sans autoriser des redirections externes de carte mémoire.

L’image de jeu, l’exécutable et les fichiers protégés supplémentaires sont
empreintés avant et après. Le profil personnel entier est inventorié, au-delà
des seuls dossiers Config/GC. Aucun arrêt automatique ni restauration forcée de
fichier personnel n’est effectué. Les résultats d’une session interrompue ne
sont pas présentés comme un audit final. Les empreintes prouvent une stabilité
des fichiers surveillés sur l’intervalle, pas l’absence de toute activité du
système ni le bon fonctionnement de chaque scénario du jeu.

`scripts/start_dolphin_test.ps1` délègue désormais à ce moniteur. Il utilise par
défaut la copie `build/dolphin-validation/portable/Dolphin.exe`, accepte un chemin
de copie explicite, et renvoie le statut du moniteur. Le code du processus natif
se lit dans le rapport JSON. Aucun émulateur n’est inclus dans les distributions.

Exemple, après préparation de la copie portable et du profil de test :

```powershell
python scripts/run_dolphin_validation.py --emulator build/dolphin-validation/portable/Dolphin.exe --iso build/v05-qa/unchanged.iso --profile build/dolphin-validation/profiles/baseline-empty --report build/dolphin-validation/baseline-empty-run.json
```

Choisir un nom de rapport neuf à chaque répétition. L’option `--protect-file`
peut être répétée pour ajouter les images originales et l’installation originale
de Dolphin à l’audit, en plus de l’image montée et du clone déjà surveillés.
`--debugger` ouvre les panneaux du débogueur lorsque le scénario l’exige.

## Première observation contrôlée

Sur une ISO strictement identique à l’originale, un profil vide et D3D12, le
processus observé PID 30268 s’est terminé avec le code natif **0** après fermeture
par l’interface. Le moniteur a confirmé les fichiers protégés inchangés et les
**46 fichiers du profil personnel inchangés**. Preuve locale :
`build/dolphin-validation/baseline-empty-run.json`.

Cette observation ne reproduit pas l’ancien statut 1 et n’en établit pas la
cause rétroactivement. Les essais avec carte copiée et image randomisée sont
consignés dans leurs rapports distincts et dans le compte rendu de validation
principal.

## Événements Windows et comparaison des contextes

Une lecture ciblée des événements Application Error / Windows Error Reporting
pour `Dolphin.exe` sur les 48 heures précédentes a trouvé de véritables rapports
`APPCRASH`, absents du journal texte Dolphin. Le fichier privé
`build/dolphin-validation/dolphin-windows-errors.json` conserve les 12 événements
filtrés, SHA-256
`a2fd75282984acc9efb184c0e83daf8d80251ea969dacfec20c2ca74dc113e81`.

| Heure locale le 31 octobre | Processus et chemin | Module et exception |
| --- | --- | --- |
| 11:37:32 à 11:37:35 | PID 10276 (`0x2824`), `Dolphin-x64/Dolphin.exe` | `ntdll.dll`, `0xc0000008` |
| 11:45:43 | Même PID et même chemin | `XInputUap.dll`, `0xc0000005`, offset `0x22c7` |

Ces horaires concordent avec l’ancienne session à carte copiée, dont le journal
Dolphin avait été créé à 11:37:32. L’ancien lanceur n’enregistrait pas le PID ;
le lien exact avec son code 1 reste donc une corrélation temporelle. Les rapports
Windows établissent une anomalie native de Dolphin dans ces modules ; ils ne
démontrent pas que les données randomisées ou la sauvegarde en sont la cause.
Sans pile d’appels retenue, le module fautif ne suffit pas à désigner une cause
racine dans Dolphin, dans Windows ou dans un pilote.

Le clone de test lancé ensuite dans le contexte bureau hors AppContainer, PID
8140, chargeait `C:\WINDOWS\SYSTEM32\DINPUT8.dll` et
`C:\WINDOWS\SYSTEM32\xinput1_4.dll`. `XInputUap.dll` ne figurait pas dans cet
inventaire ciblé. Preuve locale :
`build/dolphin-validation/host-input-modules.json`. Cette différence fournit une
piste d’environnement vérifiable ; elle ne prouve pas, à elle seule, une
résolution du plantage de fermeture.

Dans les sources épinglées, le backend Win32 initialise XInput globalement, même
si la manette sélectionnée utilise DInput. Sa désinitialisation libère la DLL.
Aucune clé INI de désactivation de ce backend n’est présente dans les fonctions
inspectées ; écrire une option inventée ne constituerait pas une correction.
[Win32.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/InputCommon/ControllerInterface/Win32/Win32.cpp),
[XInput.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/InputCommon/ControllerInterface/XInput/XInput.cpp)
Les quatre sources du contrôleur sont conservées avec leurs empreintes dans
`references-isolation/controller-manifest.json`, sous le dossier local de QA.

Pour les essais avec débogueur, lancer le moniteur Dolphin et son client GDB
dans le même contexte bureau hors AppContainer évite le blocage de boucle locale
observé dans le conteneur. Aucune exemption réseau AppContainer ni autre réglage
Windows n’a été changé. Le lancement de débogage resté bloqué dans le conteneur
a été arrêté explicitement comme essai diagnostique abandonné ; son statut
`0xffffffff` ne doit pas être compté comme un test de fermeture normale.

La correction vérifiable du dispositif est donc un lancement isolé et identifié,
avec canaux stdout/stderr valides, surveillance complète des originaux, contexte
de débogage cohérent et codes natifs enregistrés. Les fermetures réelles suivantes
sur image vierge et image randomisée restent les observations décisives pour
juger de la stabilité du contexte retenu.

## Savestates pendant un arrêt GDB

Une sauvegarde d’état demandée dans l’interface appelle `State::SaveAs`, puis
`Core::RunOnCPUThread`. Lorsque le cœur est démarré, cette opération met la
sérialisation en attente sur le thread CPU.
[State.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/State.cpp#L458),
[Core.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/Core.cpp#L767)

Le thread CPU arrêté par GDB attend dans `ProcessCommands(true)` ; il ne vide
pas cette file pendant cette attente. En déduction du code, une sauvegarde
peut rester en suspens jusqu’à la reprise par le client GDB. La consultation des
métadonnées de savestates prend aussi un verrou qui attend la fin des tâches de
sauvegarde, ce qui peut bloquer temporairement l’interface. Pour les fixtures,
créer l’état avant le dialogue du PNJ, ou lors d’une pause ordinaire, puis
installer les points d’arrêt.
[CPU.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/HW/CPU.cpp#L145),
[State.cpp](https://github.com/dolphin-emu/dolphin/blob/409881c34357d0f105fd473167d15ab0bd9c1628/Source/Core/Core/State.cpp#L562)

## Clôture des fixtures privées

Le helper local `build/dolphin-validation/finalize_validation.py` refuse toute
correction si un processus Dolphin tourne encore ou si le contrôle s’exécute
dans AppContainer. Il compare les empreintes initiales des 2011 fichiers du jeu,
2691 fichiers de l’installation originale, 46 fichiers personnels et deux images
sources. Il ne restaure jamais de fichier personnel.

Après arrêt des essais, son option `--apply` conserve une copie du binaire et
des INI de test, rétablit le seul clone officiel, puis désactive GDB, le mode
débogueur et les cheats des profils privés. Un nouvel essai sans débogueur doit
ensuite se terminer normalement, puis un audit sans `--apply` clôture la
vérification. Les états construits pour les fixtures restent dans les dossiers
privés de QA.

## Contrôles automatiques

Neuf tests ciblés passent dans `tests/test_dolphin_validation.py` : transmission
exacte des chemins avec espaces sans shell, code natif non nul, empreintes de
tout le profil, détection de modification ou disparition d’un fichier, refus des
chemins externes et des liens matériels, absence de remplacement d’un rapport,
et contrôle des chemins de carte dans les INI spécifiques au jeu.

Cinq tests privés du finaliseur couvrent le refus d’un processus actif, la
restauration limitée au clone, le blocage si un original a changé, le refus
d’écraser un rapport et l’absence de correction en mode audit seul. Ces tests
utilisent des fichiers temporaires et des inventaires simulés.
