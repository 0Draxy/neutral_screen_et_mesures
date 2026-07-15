# Documentation IA - Projet relais RP2040 Neutral Screen V2.12.2

## Évolution majeure V2.12.2 — étalonnage et relais bistables

La V2.12.2 conserve les fonctions Neutral Screen et chronométrie, puis ajoute :

```text
- onglet Étalonnage tension entièrement présent dans le fichier .ui
- calibration ADS1115 + pont diviseur par deux points
- contrôle intermédiaire obligatoire avant activation
- historique SQLite des calibrations
- blocage des mesures si calibration absente, invalide ou expirée
- mesure monostable : collage et décollage
- mesure bistable deux bobines : basculement BE et basculement BR
- sauvegarde des RAW ADS1115 et de la calibration utilisée
```

Formule appliquée :

```text
Vbobine_mV = RAW × 0,125 × rapport + offset_mV
```

Commandes firmware de la chaîne tension :

```text
ADS?
VOLTAGE_CFG;RATIO_U6;OFFSET_MV;STABLE_US
VOLTAGE_SCAN;ARM;PICKUP;NB_INV
VOLTAGE_SCAN;ARM;DROPOUT;NB_INV
VOLTAGE_SCAN;CANCEL
COIL_HOLD;BE
COIL_HOLD;BR
COIL_HOLD;OFF
```

`COIL_HOLD;ON` est conservé comme alias historique de BE.

Câblage analogique :

```text
GP0 = SDA ADS1115
GP1 = SCL ADS1115
ADS1115 A0 = pont 39 kΩ / 3,3 kΩ sur BUS + BOBINES
ADS1115 VDD = 3,3 V
ADS1115 ADDR = GND, adresse 0x48
Sélecteur OFF / FIXE / EA à rupture avant établissement
```

La tension mémorisée correspond au premier passage complet dans la position demandée. Les rebonds ultérieurs ne remplacent jamais cette valeur ; la durée de validation sert uniquement à confirmer la stabilisation finale.

---

Ce document sert de référence pour une IA ou un professionnel qui doit analyser,
auditer, corriger ou reconstruire le projet à partir des fichiers fournis.

Fichiers attendus avec ce document :

```text
main_ihm_relais_rp2040_v2_12_2.py
licence_manager.py
ihm_relais_rp2040_28vdc_precision_v2_12_2.ui
neutral_scenarios.json
rp2040_relais_28vdc_precision_v2_12_2_ADS1115_GP26_RGB.ino
production_essais.sqlite3
chronometrie_contacts.sqlite3
build_exe_onefile_ihm_relais_rp2040_v2_12_2.bat
CABLAGE_FILS_A_FILS_V2_12_2.md
RP2040-Zero_03.jpg
```

## 1. But du projet

Le projet est un banc de test pour relais bistables/latching, piloté par une
carte RP2040-Zero et une IHM Python/PySide6.

L'objectif principal est de réaliser des essais de type Neutral Screen :

```text
- pulse bobine BE
- pulse bobine BR
- pulse simultané BE/BR
- sélection 28 Vdc / 32 Vdc par relais 5 Vdc
- lecture des contacts R1 à R4 et T1 à T4
- verdict automatique ACCEPTÉ / REFUSÉ
- enregistrement production par lot et par numéro de série
- édition des scénarios Neutral Screen
- rapport PDF par lot
- gestion SQLite de la base production
```

Architecture :

```text
Python/PySide6  : IHM, scénarios, verdicts, production, SQLite, PDF
Fichier .ui     : interface modifiable dans Qt Designer
JSON            : scénarios Neutral Screen éditables
Firmware .ino   : temps réel RP2040, pulses GPIO, lecture contacts
SQLite          : historique production par lot et SN
```

Règle critique :

```text
Les temps de pulse des MOSFET sont faits côté RP2040.
Le PC ne doit pas temporiser directement les sorties.
```

Le Python doit envoyer par exemple :

```text
PULSE_US;BE;10000
```

et le firmware RP2040 doit générer physiquement le pulse de 10000 us.

## 2. Version documentée

Version courante :

```text
V2.12.2
```

Historique fonctionnel conservé depuis V2.10.36 :

```text
- ajout des rebonds d’ouverture des contacts dans la chronométrie métier
- les rebonds d’ouverture sont gérés comme les autres rebonds :
  * affichage dans le tableau Résultats de l’onglet Chronométrie contacts
  * sauvegarde dans le détail JSON SQLite
  * export XLSX de lot
  * export PDF de lot
  * visualisation dans l’onglet Oscillogramme contacts
  * prise en compte par Zoom rebonds et par la Synthèse transfert / rebonds
- pour chaque inverseur actif, le tableau passe à 8 lignes métier :
  * Temps d'Enclenchement N (ms)
  * Temps de transfère N (ms)
  * Temps Rebond Repos Ouverture N (ms)
  * Temps Rebond Travail Fermeture N (ms)
  * Temps de Déclenchement N (ms)
  * Temps de transfère N retour (ms)
  * Temps Rebond Travail Ouverture N (ms)
  * Temps Rebond Repos Fermeture N (ms)
- pour un relais 4 inverseurs, le tableau peut donc afficher jusqu’à 32 lignes
- définitions BE / MONO ON :
  * Rebond Repos Ouverture N = première ouverture Rn -> dernière ouverture Rn
  * Rebond Travail Fermeture N = première fermeture Tn -> dernière fermeture Tn
- définitions BR / MONO OFF :
  * Rebond Travail Ouverture N = première ouverture Tn -> dernière ouverture Tn
  * Rebond Repos Fermeture N = première fermeture Rn -> dernière fermeture Rn
- les rebonds d’ouverture utilisent la même limite opérateur que les rebonds de
  fermeture : champ Sanction rebond max
- la capture firmware n’est pas changée : le RP2040 capturait déjà tous les
  fronts bruts, l’évolution est côté analyse IHM / exports / oscillogramme

- correction de l’onglet Oscillogramme contacts : le tracé n’est plus coupé
  en bas de la zone graphique, les 8 voies R1-R4/T1-T4 doivent rester visibles
- suppression de la contrainte de hauteur interne qui pouvait faire dépasser le
  canvas dans son conteneur Qt Designer et masquer T4 ou le bas du graphe
- marges de dessin adaptatives : le graphe se compacte automatiquement si la
  zone disponible est réduite
- amélioration du zoom / dézoom :
  * ajout d’un facteur de zoom réglable de x2 à x100
  * boutons ZOOM + xN et DÉZOOM xN selon le facteur choisi
  * zoom centré sur la vue courante
  * dézoom borné proprement à la capture complète
  * les curseurs A/B sont conservés pendant zoom et dézoom
- VUE COMPLÈTE remet explicitement la fenêtre de 0 µs à fin de capture
- la vue complète utilise la durée de capture prévue même si aucun front n’est
  encore présent, au lieu de retomber artificiellement sur 1 µs
```

Oscillogramme contacts conservé et amélioré :

```text
- tracé vectoriel à l’échelle temps réelle avec QPainter/QLineF
- marqueur noir sur chaque front capturé pour éviter qu’un rebond court soit
  visuellement masqué par l’arrondi pixel
- si plusieurs fronts tombent sur le même pixel, les marqueurs sont décalés
  verticalement dans la voie sans déplacer la courbe temporelle
- axe temps adapté automatiquement : affichage en µs sur les vues courtes et
  en ms sur les vues larges
- bouton ZOOM REBONDS : loupe micro-rebond
- boutons ZOOM + xN, DÉZOOM xN et VUE COMPLÈTE
- facteur N réglable de 2 à 100
- statut avec nombre de fronts visibles, span de vue et résolution µs/pixel
```

Exports dans le répertoire EXE conservés :

```text
- tous les exports et sauvegardes demandées par l'opérateur sont proposés dans
  le même répertoire que l'EXE
- en mode développement Python, le répertoire utilisé est celui du script .py
- en mode EXE PyInstaller onefile, le répertoire utilisé est :
  Path(sys.executable).parent
- le sélecteur de fichier sert uniquement à choisir le nom du fichier ; même si
  l'opérateur navigue ailleurs, le fichier final est forcé dans le dossier EXE
```

Écart inter-inverseurs conservé comme information :

```text
- l’écart premier / dernier contact attendu reste calculé et affiché
- la référence 50 µs est uniquement informative
- un écart supérieur à 50 µs ne met plus le relais en DEFAUT
- le statut IHM devient orange/informatif si cet écart dépasse 50 µs
- le verdict OK/DEFAUT est réservé aux temps, rebonds, contacts manquants et overflow
```

Fonctionnalités présentes dans cette version :

```text
- onglet verrouillé "Chronométrie contacts" intégré dans le fichier .ui et
  entièrement modifiable avec Qt Designer
- fonctionnement bistable :
  * BE sur GP14
  * BR sur GP15
  * mode automatique BE / BR avec pré-positionnement au repos avant mesure
- fonctionnement monostable :
  * commande unique sur GP14
  * GP15 non utilisé
  * mesure ON puis OFF avec maintien de bobine adapté
- capture RP2040 prioritaire des changements R1-R4/T1-T4 pendant une fenêtre
  courte, avec lecture groupée GPIO et horodatage au plus près du snapshot
- remontée qualité capture :
  * LOOP_MAX_US
  * EVENT_CAPACITY
  * DROPPED_EVENTS
  * OVERFLOW
- mesure verticale par inverseur, jusqu'à 4 inverseurs
- pour chaque inverseur actif, 8 lignes métier :
  * Temps d'Enclenchement N (ms)
  * Temps de transfère N (ms)
  * Temps Rebond Repos Ouverture N (ms)
  * Temps Rebond Travail Fermeture N (ms)
  * Temps de Déclenchement N (ms)
  * Temps de transfère N retour (ms)
  * Temps Rebond Travail Ouverture N (ms)
  * Temps Rebond Repos Fermeture N (ms)
- écart premier / dernier contact attendu affiché à titre informatif avec référence 50 µs ; cet écart ne participe pas au verdict OK/DEFAUT
- avertissement diagnostic si la scrutation dépasse CHRONO_LOOP_WARN_US
- onglet "Oscillogramme contacts" après l'onglet Chronométrie contacts :
  * reconstruction des signaux carrés 0/1 à partir de START_BITS et des
    événements bruts MEASURE_EVT
  * une trace logique par contact R1-R4/T1-T4
  * axe horizontal réellement à l'échelle du temps de capture
  * conservation des captures BE et BR après une séquence automatique, afin de
    pouvoir revoir la fermeture Travail T1-T4 même si la dernière mesure est BR
  * choix de la capture affichée : Dernière mesure, Cycle complet BE -> BR, BE, BR, Cycle complet MONO ON -> MONO OFF, MONO_ON, MONO_OFF
  * modes d’affichage : Électrique GPIO, Logique contact, Synthèse transfert / rebonds
  * rappel ancien Lot/SN depuis chronometrie_contacts.sqlite3 pour retracer les graphes enregistrés
  * marqueur vertical sur chaque front pour rendre visible un rebond même quand
    le plateau tient sur moins d'un pixel
  * zoom manuel par champs Début µs / Fin µs
  * zoom dynamique par molette souris, sélection par glissé gauche et déplacement horizontal par glissé droit
  * outil de mesure M + clic droit : flèche rouge avec delta temps en temps réel
  * bouton Vue complète pour revenir à 0 -> fin de capture
  * bouton Zoom fronts pour cadrer automatiquement de la première à la
    dernière transition capturée avec marge
  * bouton Zoom contact pour cadrer uniquement les fronts d'un contact choisi
  * bouton Zoom rebonds pour cadrer les rebonds métier des contacts attendus,
    y compris rebonds d’ouverture et rebonds de fermeture
  * en BE/MONO_ON : ouverture R1-RN et fermeture T1-TN
  * en BR/MONO_OFF : ouverture T1-TN et fermeture R1-RN
  * curseurs A/B en µs avec affichage du delta B-A en µs et ms
  * affichage de l'échelle courante en µs/pixel pour savoir si un rebond peut
    être visuellement comprimé
  * Synthèse transfert / rebonds : une seule trace composite par inverseur,
    avec niveaux REPOS / TRANSFERT / TRAVAIL et zones de rebonds ouverture / fermeture
  * pré-T0 visuel au début du graphe avec libellé T0 commande BE/BR/MONO, sans modifier les temps mesurés
  * export XLSX courbe avec points du signal carré exploitables sous tableur
    et rappel du zoom/curseurs
  * export PDF courbe avec tracé visuel de la vue zoomée et curseurs A/B
- base chronométrie séparée : chronometrie_contacts.sqlite3
- exports chronométrie XLSX et PDF au format fiche verticale par relais / SN
- exports Production et Chronométrie disponibles dans Gestion Base
- logique de lot chronométrie alignée avec Production :
  * reprise des infos si le lot existe
  * préparation du SN suivant
  * nettoyage des champs si le lot est nouveau
  * blocage BE, BR et automatique tant que les champs obligatoires manquent
- champ Production "Nombre d'inverseurs" synchronisé vers Neutral Screen
  Automatique pour ne contrôler que les contacts actifs
- script de build actuel : build_exe_onefile_ihm_relais_rp2040_v2_12_2.bat
```

Points importants de la version courante :

```text
- tri naturel des SN : 1, 2, 3... 10, 11
- distinction entre Nb essais et SN distincts
- doublons SN autorisés si un relais est mesuré plusieurs fois
- reset du SN lors d'un nouveau lot
- verrouillage de session lot jusqu'à LOT FINI
- récupération mot de passe par clé de secours
- base SQLite avec sauvegarde, restauration, fusion et nettoyage
```

Dans l'historique :

```text
Nb essais    = nombre total de lignes/mesures enregistrées
SN distincts = nombre de numéros de série différents
```

Exemple :

```text
SN 1 testé deux fois
SN 2 à SN 11 testés une fois

=> Nb essais    = 12
=> SN distincts = 11
=> Premier SN   = 1
=> Dernier SN   = 11
```

## 3. Schéma de câblage à utiliser

Le câblage officiel à jour est :

```text
CABLAGE_FILS_A_FILS_V2_12_2.md
```

Point critique corrigé :

```text
GP26 = commande du relais 5 Vdc de sélection 28 V / 32 V
GP16 = LED RGB interne WS2812 de la carte RP2040-Zero
```

Ne pas recâbler la sélection tension sur GP16.

Même si le schéma peut indiquer "RP2040 pico" par abus de langage, le montage
utilise une carte :

```text
RP2040-Zero Waveshare
```

## 4. Table de câblage officielle

### 4.1 Sorties

| GPIO RP2040 | Fonction | Détail |
|---:|---|---|
| GP14 | BE / sortie 1 | Commande gate MOSFET IRL3705N bobine BE |
| GP15 | BR / sortie 2 | Commande gate MOSFET IRL3705N bobine BR |
| GP26 | Sélection 28/32 V | Commande MOSFET du relais 5 Vdc de sélection tension |
| GP16 | LED RGB interne | WS2812 interne RP2040-Zero, ne pas utiliser pour la sélection tension |

Chaque gate MOSFET doit avoir :

```text
RP2040 GPIO -> résistance 100 ohms -> gate MOSFET
gate MOSFET -> résistance 100 kohms -> GND
source MOSFET -> GND
```

### 4.2 Entrées contacts

| Contact relais | GPIO RP2040 | Nom IHM | Couleur IHM |
|---|---:|---|---|
| R1 | GP10 | R1 | Vert |
| R2 | GP11 | R2 | Vert |
| R3 | GP6 | R3 | Vert |
| R4 | GP7 | R4 | Vert |
| T1 | GP12 | T1 | Rouge |
| T2 | GP13 | T2 | Rouge |
| T3 | GP8 | T3 | Rouge |
| T4 | GP9 | T4 | Rouge |

Les contacts sont lus avec pull-up externe :

```text
3,3 V -> résistance 10 kohms -> GPIO entrée
GPIO entrée -> contact sec -> GND
```

Logique électrique :

| État contact | Niveau GPIO | Valeur logique envoyée | LED IHM |
|---|---:|---:|---|
| Ouvert | HIGH | 0 | Éteinte |
| Fermé vers GND | LOW | 1 | Allumée |

Donc :

```text
1 = contact fermé = LED allumée
0 = contact ouvert = LED éteinte
```

### 4.3 Broches non utilisées

Les GPIO GP17 à GP25 ne sont pas utilisés dans ce montage, car ils sont peu
pratiques à câbler sur la carte RP2040-Zero.

## 5. Sélection de tension

Le banc utilise deux alimentations :

```text
Voie basse / NC : 28 Vdc
Voie haute / NO : 32 Vdc
```

La sélection 28/32 V est commandée par GP26 via un relais 5 Vdc.

Comportement attendu :

| Action | GP26 sélection | Sorties actives | Tension appliquée |
|---|---:|---|---|
| BE | Actif | GP14 | 32 Vdc / voie haute |
| BR | Actif | GP15 | 32 Vdc / voie haute |
| BEBR | Inactif | GP14 + GP15 | 28 Vdc / voie basse |

Point important :

```text
BEBR doit activer GP14 et GP15 simultanément.
```

## 6. Protection des bobines

Le schéma montre des protections bobines par diode rapide + zener.

Objectif :

```text
- protéger les MOSFET
- éviter le ralentissement excessif d'une diode seule
- conserver un relâchement suffisamment rapide pour l'essai Neutral Screen
```

Choix discutés :

```text
UF4007 + zener 12 V : plus prudent avec MOSFET 55 V en 28/32 V
UF4007 + zener 18 V : plus rapide, mais marge MOSFET plus faible
```

À vérifier physiquement :

```text
- polarité diode/zener conforme au schéma
- tension Vds max du MOSFET
- échauffement en usage répété
- temps réel de retombée à l'oscilloscope
```

## 7. Firmware RP2040

Fichier :

```text
rp2040_relais_28vdc_precision_v2_12_2_ADS1115_GP26_RGB.ino
```

Rôles :

```text
- recevoir les commandes série
- générer les pulses précis GP14 / GP15
- commander GP26 pour la sélection 28/32 V
- lire les contacts R1-R4 / T1-T4
- envoyer STATUS / CONTACT / OUTPUT
- piloter la LED RGB interne GP16
```

Constantes attendues côté firmware :

```cpp
PIN_SORTIE_1 = 14
PIN_SORTIE_2 = 15
PIN_SELECT_32V = 26
PIN_LED_RGB = 16
```

Commandes série principales :

```text
STATUS?
STOP
PAUSE
RESUME
PULSE_US;BE;DUREE_US
PULSE_US;BR;DUREE_US
PULSE_US;BEBR;DUREE_US
LED;BE
LED;BR
LED;BEBR
```

Pour Neutral Screen :

```text
BE   -> GP26 actif, GP14 pulse
BR   -> GP26 actif, GP15 pulse
BEBR -> GP26 inactif, GP14 + GP15 pulse simultané
```

Le firmware doit gérer les temps par alarmes/timers côté RP2040, pas par
temporisation PC.

## 8. Précision des pulses

Pour une demande de pulse :

```text
PULSE_US;BE;1000
```

le RP2040 doit produire un pulse d'environ 1000 us côté sortie MOSFET.

Contrôles oscilloscope recommandés :

| Test | Où mesurer |
|---|---|
| BE 1 ms | Gate ou drain MOSFET commandé par GP14 |
| BR 1 ms | Gate ou drain MOSFET commandé par GP15 |
| BEBR 1 ms | Deux voies scope sur GP14 et GP15 |
| Sélection tension | Sonde sur GP26 ou sur gate MOSFET sélection |

Pour BEBR, vérifier :

```text
- fronts GP14 et GP15 simultanés
- même durée de pulse
- GP26 inactif pendant BEBR
```

## 9. IHM Python / PySide6

Fichier :

```text
main_ihm_relais_rp2040_v2_12_2.py
```

Rôles :

```text
- charger le .ui
- gérer la connexion série
- envoyer les commandes au RP2040
- lire les états contacts
- exécuter les scénarios
- calculer ACCEPTÉ / REFUSÉ
- gérer la production par lot
- enregistrer dans SQLite
- générer les PDF
- gérer les onglets verrouillés
```

Règle UI :

```text
Ne pas renommer les objectName dans Qt Designer sans modifier le Python.
```

## 10. Onglets de l'IHM

Ordre logique des onglets :

```text
1. Production
2. Neutral Screen Automatique
3. Neutral Screen Manuel
4. Editeur Scénario Neutral
5. Gestion Base
6. Cyclage
```

Onglets protégés par mot de passe :

```text
- Neutral Screen Manuel
- Editeur Scénario Neutral
- Gestion Base
- Cyclage
```

Neutral Screen Automatique et Production restent accessibles opérateur.

## 11. Mot de passe et récupération

Mot de passe par défaut :

```text
1234
```

Stockage :

```text
production_essais.sqlite3
table settings
clé access_code
```

Clé secrète de récupération :

```text
marechal
```

Fonctionnement :

```text
1. Aller sur un onglet verrouillé
2. Quand l'IHM demande le code, saisir : marechal
3. Confirmer
4. Le mot de passe est remis à 1234
5. Les essais, lots, SN et résultats ne sont pas supprimés
```

Ce mécanisme est une récupération atelier, pas une sécurité informatique forte.

## 12. Production par lot

L'onglet Production sert à préparer un lot :

```text
- scénario pour l'essai
- numéro de lot
- désignation
- opérateur
- date du jour modifiable
```

Avant de passer au test, tous ces champs sont obligatoires.

Si un lot existe déjà dans SQLite :

```text
- l'IHM récupère scénario, désignation, opérateur, date
- l'IHM cherche le dernier SN du lot
- l'IHM prépare le SN suivant si possible
```

Si un lot n'existe pas :

```text
- le SN courant est vidé
- le premier appui sur MARCHE AUTO demandera le SN du premier relais
```

Après `LOT FINI` :

```text
- le SN courant est vidé
- la session lot est clôturée
- l'IHM revient vers Production
```

Objectif :

```text
Éviter qu'un nouveau lot hérite du SN du lot précédent.
```

## 13. Historique Production

L'historique Production doit afficher une seule ligne par lot.

Colonnes attendues :

```text
Lot | Nb essais | SN distincts | Acceptés | Refusés | Premier SN | Dernier SN | Dernier essai | Désignation
```

Règles :

```text
Nb essais = nombre total de mesures enregistrées
SN distincts = nombre de SN différents
Premier/Dernier SN = calculés en tri naturel côté Python
```

Ne pas utiliser directement `MIN(sn)` / `MAX(sn)` SQLite pour les bornes SN,
car SQLite trie les SN comme du texte :

```text
1, 10, 11, 2...
```

Le tri correct est :

```text
1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11...
```

## 14. Détail lot et PDF

Double-clic sur un lot :

```text
ouvre le détail complet du lot
```

Le détail doit afficher toutes les mesures, y compris les SN répétés.

Un doublon SN est autorisé si le même relais a été testé plusieurs fois :

```text
SN 1 à 18:02
SN 1 à 23:07
```

Dans ce cas :

```text
Nb essais = 2
SN distincts = 1
```

Le PDF doit contenir :

```text
- lot
- période d'essai au format JJ/MM/AAAA hh:mm
- désignation
- opérateur(s)
- nombre d'essais
- nombre de SN distincts
- acceptés / refusés avec pourcentage
- détail de chaque mesure
```

Le PDF ne doit pas remplacer la date d'essai par une date d'export.

## 15. Base SQLite

Fichier :

```text
production_essais.sqlite3
```

Tables principales :

```text
settings
essais
operators
```

Table `essais` :

```sql
lot TEXT
sn TEXT
designation TEXT
operateur TEXT
date TEXT
heure TEXT
scenario TEXT
resultat TEXT
details TEXT
timestamp TEXT
```

La base doit permettre :

```text
- sauvegarde
- restauration
- export CSV
- fusion/import d'une autre base
- suppression d'un lot
- recréation d'une base vide par défaut
- optimisation SQLite
```

## 16. Gestion Base

L'onglet Gestion Base est verrouillé à l'exécution, mais doit rester modifiable
dans Qt Designer.

Fonctions attendues :

```text
- rafraîchir
- sauvegarder la base
- restaurer une base
- exporter CSV
- recréer base par défaut
- fusionner/importer une autre base
- supprimer un lot
- ajouter/supprimer opérateur
- ouvrir le détail d'un lot
- créer PDF du lot
```

Table lots Gestion Base :

```text
Lot | Désignation | Date création essai | Bon / mauvais | Nb essais | SN distincts
```

Le tableau doit être triable par clic sur les en-têtes.

## 17. Neutral Screen - définitions d'état

Pour N inverseurs actifs, seuls R1..RN et T1..TN sont évalués.

Contacts hors N :

```text
- ignorés dans la décision
- grisés dans l'IHM automatique
```

Définitions :

```text
RESET_GREEN = tous les R actifs allumés ET tous les T actifs éteints
LATCH_RED   = tous les T actifs allumés ET tous les R actifs éteints
NEUTRAL     = tout autre état connu
```

Exemple pour N=2 :

| R allumés | T allumés | État |
|---:|---:|---|
| 2 | 0 | RESET_GREEN |
| 0 | 2 | LATCH_RED |
| 0 | 0 | NEUTRAL |
| 1 | 0 | NEUTRAL |
| 0 | 1 | NEUTRAL |
| 1 | 1 | NEUTRAL |
| 2 | 1 | NEUTRAL |
| 1 | 2 | NEUTRAL |
| 2 | 2 | NEUTRAL |

Cette règle correspond à la définition validée :

```text
Tout état qui n'est pas franchement RESET_GREEN ou franchement LATCH_RED
est considéré Neutral Screen.
```

## 18. Scénario norme strict

Scénario :

```text
Neutral screen norme
```

Étapes :

```text
1. BEBR 10 ms | NEUTRAL     | max 3 | si échec ACCEPT
2. BE   10 ms | LATCH_RED   | max 1 | si échec REJECT
3. BEBR 10 ms | NEUTRAL     | max 1 | si échec REJECT
4. BR   10 ms | RESET_GREEN | max 1 | si échec REJECT
```

Point important :

```text
L'étape 3 doit vérifier NEUTRAL.
Ne pas remettre check = NONE.
```

## 19. Éditeur de scénarios

Fichier :

```text
neutral_scenarios.json
```

Actions autorisées :

```text
BE
BR
BEBR
STATUS
PAUSE
STOP
```

Checks autorisés :

```text
NONE
NEUTRAL
LATCH_RED
RESET_GREEN
```

Actions en cas d'échec :

```text
REJECT
ACCEPT
CONTINUE
STOP
```

Les scénarios par défaut existent aussi dans le Python.
Si le scénario norme change, vérifier à la fois :

```text
neutral_scenarios.json
default_scenarios_data()
```

## 20. LED RGB interne

La LED RGB interne de la carte RP2040-Zero est sur :

```text
GP16
```

États voulus :

| Situation | Couleur |
|---|---|
| Boot / prêt non connecté | Jaune pâle clignotant |
| Arrêt connecté | Jaune très pâle fixe |
| Pulse BE | Rouge |
| Pulse BR | Bleu |
| Pulse BEBR | Violet |
| Sélection 32 V active | Cyan |
| Relais accepté | Vert fixe |
| Relais refusé/rejeté | Rouge fixe |
| Erreur | Orange clignotant |

Ne pas utiliser GP16 pour le relais 5 Vdc de sélection tension.

## 21. Connexion USB

Comportement attendu :

```text
- tentative de connexion automatique au RP2040 au lancement
- état connexion visible dans Production
- si USB débranché pendant Neutral Screen Automatique :
  - arrêt immédiat de l'essai
  - aucun résultat enregistré
  - retour automatique à Production
  - mémorisation du SN interrompu
  - à la relance, demander si on refait ce SN
```

## 22. UI opérateur production

Les messages opérateur doivent être gros et adaptés à un contexte production :

```text
- vérification des deux alimentations
- saisie/scanner du premier SN
- bouton TEST FINI très visible
- LOT FINI avec confirmation
```

Le bouton TEST FINI doit être validable :

```text
- à la souris
- avec la touche Entrée
- avec la barre d'espace si le focus est dessus
```

Après validation TEST FINI :

```text
- le résultat est enregistré
- le SN suivant est préparé
- l'affichage résultat redevient neutre pour le prochain relais
```

## 23. Incrémentation SN

Fonction attendue :

```text
next_sn_value()
```

Règle :

```text
Si le SN finit par un nombre, incrémenter ce nombre en conservant les zéros.
```

Exemples :

| SN courant | SN suivant |
|---|---|
| 1 | 2 |
| 9 | 10 |
| SN0099 | SN0100 |
| LOT-A-0007 | LOT-A-0008 |

Si le SN ne finit pas par une partie numérique, demander une saisie manuelle.

## 24. Nomenclature minimale

Composants principaux :

```text
- RP2040-Zero Waveshare
- 3 MOSFET IRL3705N ou équivalents adaptés
- résistances gate 100 ohms
- résistances pull-down gate 100 kohms
- résistances pull-up contacts 10 kohms
- relais 5 Vdc pour sélection 28/32 V
- diodes rapides UF4007 ou équivalent
- zeners 12 V ou 18 V selon compromis protection/vitesse
- borniers de raccordement
- alimentation 3,3 V RP2040 fournie par la carte
- alimentation 5 Vdc relais sélection
- alimentation 28 Vdc
- alimentation 32 Vdc
```

À vérifier par un professionnel :

```text
- courant des bobines
- puissance dissipée MOSFET
- marge Vds MOSFET
- sens diode/zener
- isolation et distances adaptées aux tensions utilisées
- robustesse mécanique du câblage
```

## 25. Checklist de reconstruction

Avant de modifier :

```text
1. Lire le Python, le UI, le JSON, le INO et ce MD ensemble.
2. Vérifier que le .py charge bien le .ui V2.12.2.
3. Vérifier que GP26 est bien la sélection 28/32 V.
4. Vérifier que GP16 reste la LED RGB interne.
5. Vérifier que les contacts R/T sont sur les bons GPIO.
6. Vérifier que PULSE_US est utilisé pour tous les pulses critiques.
7. Vérifier le scénario norme strict.
8. Vérifier la distinction Nb essais / SN distincts.
9. Vérifier le tri naturel des SN.
10. Vérifier les PDF de lot.
```

Tests électriques :

```text
1. Mesurer BE 1 ms sur GP14 / MOSFET BE.
2. Mesurer BR 1 ms sur GP15 / MOSFET BR.
3. Mesurer BEBR 1 ms sur GP14 + GP15.
4. Vérifier simultanéité BEBR.
5. Vérifier GP26 actif pour BE/BR.
6. Vérifier GP26 inactif pour BEBR.
7. Vérifier lecture contacts R1-R4/T1-T4.
```

Tests production :

```text
1. Créer un lot neuf.
2. Vérifier que le SN est demandé au démarrage.
3. Tester plusieurs relais.
4. Refaire volontairement un SN déjà testé.
5. Vérifier que l'IHM affiche Nb essais et SN distincts.
6. Générer le PDF.
7. Vérifier Premier SN / Dernier SN.
8. Appuyer sur LOT FINI.
9. Créer un autre lot.
10. Vérifier que l'ancien SN n'est pas repris.
```

## 26. Résumé court pour une IA

Ce projet est un banc Neutral Screen pour relais bistables.

Le RP2040-Zero pilote :

```text
GP14 = BE
GP15 = BR
GP26 = sélection 28/32 V par relais 5 Vdc
GP16 = LED RGB interne
GP10/11/6/7 = R1/R2/R3/R4
GP12/13/8/9 = T1/T2/T3/T4
```

Le Python gère :

```text
- IHM PySide6
- scénarios Neutral Screen
- verdict ACCEPTÉ / REFUSÉ
- production par lot
- SQLite
- PDF
- verrouillage opérateur
- reprise après coupure USB
```

La règle Neutral Screen est :

```text
RESET_GREEN = tous R actifs ON et tous T actifs OFF
LATCH_RED   = tous T actifs ON et tous R actifs OFF
NEUTRAL     = tout autre état connu
```

Le scénario norme strict est :

```text
BEBR NEUTRAL max 3 ACCEPT
BE   LATCH_RED max 1 REJECT
BEBR NEUTRAL max 1 REJECT
BR   RESET_GREEN max 1 REJECT
```

Ne jamais remplacer les commandes `PULSE_US;...` par une temporisation côté PC.
Les pulses critiques doivent rester côté RP2040.

## Correctif V2.12.2 - Oscilloscope

- Le bouton **VUE COMPLÈTE** force maintenant explicitement le rafraîchissement graphique.
  Correction du cas Qt où le signal `clicked(bool)` transmettait `False` au paramètre interne `update`, ce qui pouvait modifier les bornes sans redessiner immédiatement le graphique.
- Le bouton **RAPPEL LOT/SN** fonctionne maintenant en deux étapes :
  1. choix du lot dans la liste des lots enregistrés ou saisie manuelle du lot ;
  2. choix du SN uniquement parmi les SN du lot choisi ou saisie manuelle du SN ; la liste SN est triée naturellement (1, 2, 3, ... 10).
- Si plusieurs groupes existent pour le même SN (relais ou nom de test différents), une troisième confirmation propose le groupe exact à rappeler.



## Correctif V2.12.2 - Protection licence Python

- Ajout du fichier `licence_manager.py`.
- Ajout d'une protection locale au démarrage du logiciel.
- Au premier lancement, le logiciel demande un mot de passe d'activation.
- Si le mot de passe est correct, un fichier licence est créé dans le profil utilisateur Windows :

```text
%APPDATA%\RELAIS_RP2040_NEUTRAL_SCREEN\licence_relais_rp2040_neutral_screen.dat
```

- La licence est liée au PC par empreinte machine et signature HMAC.
- Une licence copiée depuis un autre PC ou modifiée manuellement est refusée.
- Le mot de passe n'est pas stocké en clair dans le code : seul son hash SHA256 est présent.
- L'appel `require_license()` est exécuté avant la création de `QApplication`, donc avant l'ouverture de l'IHM principale.
- Le script PyInstaller ajoute les imports Tkinter nécessaires à la fenêtre d'activation.
- Cette protection est une protection atelier contre copie simple, pas une sécurité informatique inviolable contre reverse engineering avancé.
---

## Correctif V2.12.2 — tension capturée avant les rebonds

La tension de collage ou de décollage n'est plus déterminée par le début de la dernière période stable.

Le firmware capture immédiatement la tension ADS1115 au premier passage complet :

- travail : tous les R ouverts et tous les T fermés ;
- repos : tous les T ouverts et tous les R fermés.

Après cette capture, les rebonds ne modifient plus la valeur. La temporisation `Validation (ms)` sert uniquement à confirmer que l'état final devient stable.

L'IHM V2.12.2 exige le firmware V2.12.2 et contrôle les indicateurs série `CAPTURE=FIRST_PASSAGE` et `VALIDATION=STABLE_AFTER_CAPTURE` avant de lancer la rampe EA.
