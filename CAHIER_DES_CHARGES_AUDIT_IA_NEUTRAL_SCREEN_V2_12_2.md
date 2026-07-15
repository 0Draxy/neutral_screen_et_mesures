# Cahier des charges et plan d’audit IA — Neutral Screen V2.12.2

**Date de préparation : 15/07/2026**  
**Cible auditée : pack Neutral Screen V2.12.2**  
**Auteur du moyen indiqué dans l’IHM : O. MARECHAL**

## 0. Mission confiée à l’IA auditrice

Analyser intégralement et conjointement les fichiers Python, Qt Designer, firmware RP2040, JSON et SQLite. L’objectif n’est pas de confirmer les affirmations du pack, mais de déterminer si l’implémentation respecte réellement toutes les exigences ci-dessous, sans régression sur les fonctions historiques.

L’audit doit impérativement :

1. citer le fichier et les lignes concernées pour chaque constat ;
2. distinguer **certain**, **probable**, **à vérifier sur matériel** et **non démontré** ;
3. rechercher les erreurs de logique, de séquencement, de temporisation, de parsing série, de concurrence Qt/timers, de sécurité électrique, de persistance SQLite et d’export ;
4. vérifier les correspondances entre les `objectName` du `.ui` et les recherches `findChild/get_widget` du Python ;
5. vérifier que le firmware et l’IHM utilisent le même protocole série ;
6. vérifier que les valeurs enregistrées en base et exportées correspondent aux valeurs réellement capturées ;
7. ne jamais considérer un test simulé comme une validation matérielle ou métrologique ;
8. proposer un correctif minimal et testable pour chaque défaut confirmé.

### Format de retour demandé

Pour chaque défaut :

```text
Sévérité : BLOQUANT / MAJEUR / MOYEN / MINEUR
Statut : CERTAIN / PROBABLE / À VÉRIFIER MATÉRIEL
Fichier + lignes :
Fonction concernée :
Scénario de reproduction :
Résultat actuel :
Résultat attendu :
Risque :
Correction recommandée :
Test de non-régression :
```

Terminer par un verdict séparé pour :

```text
- architecture générale
- firmware temps réel
- communication série RP2040
- pilotage alimentation EA
- chaîne ADS1115 et calibration
- logique collage/décollage
- Neutral Screen automatique
- chronométrie et rebonds
- oscillogramme
- bases SQLite et exports
- licence et construction EXE
- validation matérielle restante
```

## 1. Fichiers à analyser

Fichiers fonctionnels principaux :

```text
main_ihm_relais_rp2040_v2_12_2.py
ihm_relais_rp2040_28vdc_precision_v2_12_2.ui
rp2040_relais_28vdc_precision_v2_12_2_ADS1115_GP26_RGB.ino
neutral_scenarios.json
licence_manager.py
requirements.txt
build_exe_onefile_ihm_relais_rp2040_v2_12_2.bat
```

Bases de référence vides fournies pour l’audit :

```text
production_essais.sqlite3
chronometrie_contacts.sqlite3
SCHEMA_SQLITE_V2_12_2.sql
```

Ces deux bases sont normalement créées automatiquement au premier lancement. Les fichiers fournis ici sont **vides de données utilisateur** et servent uniquement à rendre les schémas immédiatement auditables.

### Empreintes SHA-256 du dossier d’audit

- `main_ihm_relais_rp2040_v2_12_2.py` — `baf411eecda1d57922bd400ce544a6f1d3517b0e8517a3a1068e22eece3c6e2a`
- `ihm_relais_rp2040_28vdc_precision_v2_12_2.ui` — `321ef3143ace6dea7d6c0faf73f084a48e81e14a370a884d0c7c72c7b9313422`
- `rp2040_relais_28vdc_precision_v2_12_2_ADS1115_GP26_RGB.ino` — `5dd4900298e39613fa0b9f376a7240d322b58697e4bc952d815e3aad3c6bb4ae`
- `licence_manager.py` — `03fcb4f4bd55d56a43d76176edf743f5b40dc3cbe7ce547e3a70379c11cf9357`
- `neutral_scenarios.json` — `dd90f6135cbd1ff87cb68d90e7e3b6e52939abafe5ce2a2e278d7c93a151a2b6`
- `requirements.txt` — `3d0adf0b72928962dca12b0d1f6598d961f46e739b6d40e04e2350bf89b18871`
- `build_exe_onefile_ihm_relais_rp2040_v2_12_2.bat` — `c3c222298c8bf6dc8d5bfb41b94715f32c5c4bd9a257401c7cfcec6342f6afb8`
- `production_essais.sqlite3` — `927730d15b4c371bfabbd77926580229f0cc868ac4051be81b29ad91fc09db06`
- `chronometrie_contacts.sqlite3` — `38b8f6a9c3cd48f62a58f6ee3af18e066aab495a01443bf7912aa0a8966f9f67`
- `SCHEMA_SQLITE_V2_12_2.sql` — `163f0b2c7ade500eba744e164aeeb7c7f0c2babcb86566618b9ea3a46d1d75b3`

## 2. Ordre de priorité des références

En cas de contradiction :

1. les exigences du présent cahier des charges décrivent le comportement voulu ;
2. le `.ino`, le `.py`, le `.ui`, le JSON et les schémas SQLite montrent le comportement réellement livré ;
3. les autres fichiers Markdown du pack décrivent l’intention mais ne constituent pas une preuve d’implémentation ;
4. les fichiers `SOFTWARE_TESTS` et `VALIDATION` prouvent seulement les contrôles qu’ils décrivent explicitement.

L’IA auditrice doit signaler toute contradiction entre le comportement voulu et le code.

## 3. Architecture et responsabilités non négociables

### 3.1 Répartition des rôles

```text
Python/PySide6 : IHM, validation opérateur, scénarios, verdicts, SQLite, PDF/XLSX/CSV, pilotage SCPI EA.
Fichier .ui    : structure visuelle modifiable dans Qt Designer.
RP2040         : génération des fronts et pulses, cyclage temps réel, acquisition rapide des contacts, ADS1115.
JSON           : scénarios Neutral Screen éditables.
SQLite         : production, chronométrie, tensions et étalonnages.
```

### 3.2 Règle temps réel critique

Le PC ne doit jamais produire lui-même la durée électrique d’un pulse critique. Le Python convertit les paramètres en microsecondes puis envoie une commande complète ; le RP2040 génère le pulse avec ses alarmes matérielles.

Exemples obligatoires :

```text
START_US;MONO;ON_US;OFF_US;SET_US;RESET_US;CYCLES
START_US;BISTABLE;ON_US;OFF_US;SET_US;RESET_US;CYCLES
PULSE_US;BE;DUREE_US
PULSE_US;BR;DUREE_US
PULSE_US;BEBR;DUREE_US
```

Une temporisation Qt ou Python ne doit pas remplacer la durée du pulse physique.

### 3.3 Arrêt de sécurité

Tout arrêt utilisateur, timeout, erreur série, perte du RP2040, erreur ADS ou erreur EA pendant une mesure tension doit tenter de réaliser les opérations suivantes :

```text
VOLTAGE_SCAN;CANCEL
COIL_HOLD;OFF
FUNC:GEN:WAVE:STAT STOP
OUTP OFF
VOLT 0
```

Le programme ne doit pas laisser BE, BR ou l’alimentation EA actifs après une erreur.

## 4. Câblage officiel et conventions logiques

### 4.1 Sorties RP2040

| Fonction | GPIO | Règle |
|---|---:|---|
| Bobine BE / monostable | GP14 | MOSFET avec résistance de grille 100 Ω et pull-down 100 kΩ |
| Bobine BR | GP15 | MOSFET avec résistance de grille 100 Ω et pull-down 100 kΩ |
| Sélection 28/32 V | GP26 | commande MOSFET du relais auxiliaire de sélection |
| LED RGB interne WS2812 | GP16 | exclusivement LED d’état, jamais sélection tension |

### 4.2 Entrées contacts

| Contact | GPIO |
|---|---:|
| R1 | GP10 |
| R2 | GP11 |
| R3 | GP6 |
| R4 | GP7 |
| T1 | GP12 |
| T2 | GP13 |
| T3 | GP8 |
| T4 | GP9 |

Câblage de chaque entrée :

```text
3,3 V → résistance 10 kΩ → GPIO → contact sec → GND
```

Convention électrique :

```text
GPIO LOW  = contact fermé
GPIO HIGH = contact ouvert
```

Le firmware peut convertir cette convention en bits internes « fermé = 1 », mais cette conversion doit être cohérente partout.

### 4.3 ADS1115

```text
ADS1115 VDD  → 3,3 V RP2040
ADS1115 GND  → GND commun
ADS1115 SDA  → GP0
ADS1115 SCL  → GP1
ADS1115 ADDR → GND, adresse 0x48
ADS1115 A0   → sortie du pont diviseur
A1/A2/A3     → non utilisés dans cette version
```

Pont officiel :

```text
BUS + BOBINES → 39 kΩ → point M → 3,3 kΩ → GND
point M → 1 kΩ → A0
A0 → 10 nF → GND
```

Rapport nominal :

```text
(39 kΩ + 3,3 kΩ) / 3,3 kΩ = 12,8181818
```

A0 mesure le BUS positif par rapport au GND. L’acceptation métrologique à ±0,05 V autour de 12 V exige une comparaison réelle avec un voltmètre directement aux bornes de BE puis BR.

### 4.4 Source EA et sources fixes

La source EA ne doit jamais être mise en parallèle avec les alimentations fixes. La sélection physique attendue est à rupture avant établissement :

```text
OFF / FIXE / EA → BUS + BOBINES
EA− → GND commun
```

Pendant une mesure tension :

```text
GP26 reste en sélection basse ; la source réelle est l’EA par le sélecteur physique.
BE et BR ne doivent jamais être activées simultanément.
```

## 5. Protocole RP2040 à contrôler

### 5.1 Cyclage et pulses

```text
START_US;MONO;...
START_US;BISTABLE;...
STOP
PAUSE
RESUME
STATUS?
PULSE_US;BE;...
PULSE_US;BR;...
PULSE_US;BEBR;...
```

Limites firmware annoncées :

```text
Durées générales : 1 µs à 4 294 967 295 000 µs environ.
Capture chronométrie : 1 000 à 100 000 µs.
Capacité événements chronométrie : 192 événements.
Échantillonnage contacts hors capture : 250 µs.
ADS1115 : mode continu A0, PGA ±4,096 V, 860 SPS, lecture environ toutes les 1 200 µs.
```

### 5.2 Mesures contacts

```text
MEASURE_CONTACTS;BE;CAPTURE_US;PULSE_US;NB_INV
MEASURE_CONTACTS;BR;CAPTURE_US;PULSE_US;NB_INV
MEASURE_MONO;ON;CAPTURE_US;HOLD_US;NB_INV
MEASURE_MONO;OFF;CAPTURE_US;HOLD_US;NB_INV
```

La capture doit remonter au minimum :

```text
START_BITS, END_BITS, événements horodatés, LOOP_MAX_US,
EVENT_CAPACITY, DROPPED_EVENTS, OVERFLOW.
```

### 5.3 Mesures tension

```text
VOLTAGE_CFG;RATIO_U6;OFFSET_MV;STABLE_US
VOLTAGE_SCAN;ARM;PICKUP;NB_INV
VOLTAGE_SCAN;ARM;DROPOUT;NB_INV
VOLTAGE_SCAN;CANCEL
COIL_HOLD;BE
COIL_HOLD;BR
COIL_HOLD;OFF
ADS?
```

Le firmware V2.12.2 doit confirmer :

```text
CAPTURE=FIRST_PASSAGE
VALIDATION=STABLE_AFTER_CAPTURE
```

L’IHM doit refuser un ancien firmware qui ne confirme pas ces deux politiques.

## 6. États contacts communs

Pour N inverseurs actifs, seuls R1..RN et T1..TN sont évalués. Les autres sont ignorés dans le verdict et grisés dans l’IHM.

```text
RESET_GREEN = tous les R actifs fermés ET tous les T actifs ouverts
LATCH_RED   = tous les T actifs fermés ET tous les R actifs ouverts
NEUTRAL     = tout autre état entièrement connu
```

Un contact inconnu ou une communication absente ne doit pas être transformé artificiellement en NEUTRAL ou en résultat acceptable.

## 7. Onglet 1 — Production

### Finalité

Préparer le contexte de production avant l’essai automatique.

### Champs obligatoires

```text
Scénario
Lot
Désignation
Nombre d’inverseurs : 1 à 4
Opérateur
Date
```

### Règles

- le contexte doit être enregistré dans SQLite ;
- lorsqu’un lot existant est saisi, reprendre ses informations et rechercher son dernier SN ;
- préparer le SN suivant uniquement si le suffixe numérique est incrémentable ;
- conserver les zéros à gauche : `SN0099 → SN0100` ;
- ne jamais reprendre le SN d’un lot précédent dans un nouveau lot ;
- `LOT FINI` clôt la session, vide le SN et revient vers Production ;
- la connexion RP2040 doit être visible et une tentative automatique est attendue au lancement ;
- l’historique affiche une ligne par lot, mais le détail conserve toutes les mesures, y compris les SN répétés ;
- distinguer strictement **nombre d’essais** et **nombre de SN distincts** ;
- les bornes SN doivent être calculées avec un tri naturel, jamais avec `MIN(sn)/MAX(sn)` texte SQLite ;
- le PDF doit utiliser les dates d’essai enregistrées, pas la date d’export.

### Contrôles à demander à l’audit

- cohérence de l’incrémentation SN ;
- comportement lot neuf / lot existant / lot fini ;
- absence de double enregistrement ;
- reprise après interruption USB ;
- exactitude des agrégats et du tri naturel ;
- sauvegarde des détails JSON sans perte.

## 8. Onglet 2 — Neutral Screen Automatique

### Finalité

Exécuter un scénario JSON sur un relais de production et produire un verdict final.

### Règles opérateur

- lot, désignation, opérateur, date, scénario et SN doivent être valides avant départ ;
- le nombre d’inverseurs vient du contexte Production ;
- les pulses particuliers peuvent remplacer les valeurs du scénario uniquement lorsque l’option correspondante est activée ;
- les pulses sont exécutés par `PULSE_US` côté RP2040 ;
- l’IHM doit afficher l’étape, la tentative, l’état des contacts et le verdict ;
- `TEST FINI` doit fonctionner à la souris, Entrée et espace lorsqu’il a le focus ;
- après `TEST FINI`, enregistrer le résultat, préparer le SN suivant et remettre l’affichage dans un état neutre ;
- `LOT FINI` nécessite une confirmation et ne doit pas conserver le dernier SN ;
- en cas de perte USB : arrêt immédiat, aucun résultat partiel enregistré, retour Production et proposition de refaire le SN interrompu ;
- un refus de communication ou un état inconnu ne doit jamais devenir ACCEPTÉ.

### Scénario normatif obligatoire

```text
1. BEBR 10 ms | vérifier NEUTRAL     | maximum 3 essais | si échec : ACCEPT
2. BE   10 ms | vérifier LATCH_RED   | maximum 1 essai  | si échec : REJECT
3. BEBR 10 ms | vérifier NEUTRAL     | maximum 1 essai  | si échec : REJECT
4. BR   10 ms | vérifier RESET_GREEN | maximum 1 essai  | si échec : REJECT
```

L’étape 3 doit impérativement garder `check = NEUTRAL`.

## 9. Onglet 3 — Neutral Screen Manuel

### Finalité

Commander individuellement BE, BR ou BEBR et observer les contacts.

### Règles

- onglet protégé par mot de passe ;
- durée BE, BR et BEBR réglable avec unité explicite ;
- BE et BR utilisent la sélection haute 32 V ;
- BEBR utilise la sélection basse 28 V ;
- le relais de sélection doit avoir 20 ms d’établissement avant pulse et 20 ms de retombée après un pulse voie haute ;
- le pulse doit rester côté RP2040 ;
- STOP doit interrompre la séquence et mettre les sorties à zéro ;
- l’état réel des sorties et des huit contacts doit rester visible.

L’audit doit vérifier qu’aucun chemin Python n’active directement une sortie pendant une durée calculée côté PC.

## 10. Onglet 4 — Éditeur Scénario Neutral

### Données autorisées

Actions :

```text
BE, BR, BEBR, STATUS, PAUSE, STOP
```

Checks :

```text
NONE, NEUTRAL, LATCH_RED, RESET_GREEN
```

Actions sur échec :

```text
REJECT, ACCEPT, CONTINUE, STOP
```

### Règles

- création, duplication, suppression, import, export et réordonnancement des étapes ;
- validation stricte des valeurs, durées, tentatives et noms ;
- sauvegarde atomique autant que possible pour éviter un JSON tronqué ;
- synchronisation des scénarios par défaut entre `neutral_scenarios.json` et `default_scenarios_data()` ;
- toute modification doit être immédiatement visible dans Production et Automatique ;
- ne pas perdre les scénarios utilisateur lors d’une mise à jour ou d’une erreur de chargement sans sauvegarde préalable.

## 11. Onglet 5 — Gestion Base

### Cibles

```text
production_essais.sqlite3
chronometrie_contacts.sqlite3
```

### Fonctions attendues

```text
Rafraîchir
Sauvegarder
Restaurer
Exporter CSV
Exporter XLSX
Exporter PDF
VACUUM / optimiser
Recréer une base vide
Fusionner/importer une autre base
Ajouter/supprimer un opérateur
Afficher/exporter/supprimer un lot
```

### Restrictions

- onglet protégé ;
- sauvegarde de sécurité avant restauration, fusion, suppression ou recréation ;
- restauration et fusion doivent vérifier le schéma source ;
- aucune confusion entre la base Production et la base Chronométrie ;
- suppression de lot confirmée explicitement ;
- les doublons SN restent autorisés ;
- les tables de tensions et d’étalonnage sont dans `chronometrie_contacts.sqlite3` ;
- les exports doivent représenter fidèlement les données de la cible sélectionnée.

## 12. Onglet 6 — Cyclage

### Modes

```text
Monostable
Bistable 2 bobines
```

### Paramètres

```text
Temps ON
Temps OFF
Impulsion SET/BE
Impulsion RESET/BR
Nombre de cycles
Unités µs, ms, s, min ou h selon les champs proposés
```

### Commande attendue

Le Python convertit toutes les durées en microsecondes et envoie une seule commande `START_US`. Le RP2040 gère ensuite la machine d’état et les échéances en `uint64_t`.

### Fonctions

```text
Démarrer
Pause
Reprendre
Arrêt
STATUS?
```

### Restrictions

- aucune accumulation d’erreur volontaire par `sleep()` côté PC ;
- pause/reprise conserve correctement le temps restant ;
- STOP met immédiatement GP14 et GP15 à zéro ;
- un cycle déclaré terminé correspond exactement à la définition du mode ;
- les durées très longues ne doivent pas provoquer d’overflow signé ou de conversion float imprécise ;
- l’IHM doit refuser les valeurs hors plage avant envoi ;
- les contacts restent surveillés sans ralentir la machine temps réel.

## 13. Onglet 7 — Chronométrie contacts

### Modes de mesure

Bistable :

```text
BE : enlèvement repos → travail
BR : retour travail → repos
BE/BR automatique : prépositionnement puis séquence complète
```

Monostable :

```text
ON  : activation BE et passage repos → travail
OFF : relâchement BE et retour travail → repos
AUTO : ON puis OFF
```

### Paramètres

```text
Lot, date, relais, ambiance, nom du test, SN
Type relais
Nombre d’inverseurs 1 à 4
Fenêtre de capture 1 à 100 ms
Pulse/maintien 1 à 100 ms dans l’IHM actuelle
Sanction temps max
Sanction rebond max
```

### Mesures métier par inverseur

```text
1. Temps d’enclenchement
2. Temps de transfert aller
3. Rebond repos à l’ouverture
4. Rebond travail à la fermeture
5. Temps de déclenchement
6. Temps de transfert retour
7. Rebond travail à l’ouverture
8. Rebond repos à la fermeture
```

Pour quatre inverseurs : jusqu’à 32 lignes métier.

### Définitions temporelles

BE / MONO ON :

```text
Enclenchement              = T0 commande → fermeture travail pertinente
Transfert aller            = ouverture R → fermeture T
Rebond repos ouverture     = première ouverture R → dernière ouverture R
Rebond travail fermeture   = première fermeture T → dernière fermeture T
```

BR / MONO OFF :

```text
Déclenchement              = T0 commande/relâchement → fermeture repos pertinente
Transfert retour           = ouverture T → fermeture R
Rebond travail ouverture   = première ouverture T → dernière ouverture T
Rebond repos fermeture     = première fermeture R → dernière fermeture R
```

L’audit doit vérifier les définitions exactes appliquées par l’analyse des événements, en particulier les cas avec plusieurs rebonds et des contacts déjà dans l’état cible au début.

### Qualité de capture

- `OVERFLOW` signifie que le tampon d’événements a débordé ; le résultat ne doit pas être déclaré OK ;
- `DROPPED_EVENTS` doit être visible et sauvegardé ;
- `LOOP_MAX_US` doit être conservé pour diagnostiquer la résolution réelle ;
- l’écart premier/dernier inverseur et la référence 50 µs sont informatifs uniquement ; dépasser 50 µs ne doit plus provoquer un défaut ;
- les sanctions portent sur temps, rebonds, contacts manquants et overflow.

### Persistance et exports

- sauvegarde dans `mesures_chrono_contacts` ;
- `details_json` et `events_json` doivent permettre de reconstruire le résultat ;
- export lot XLSX et PDF ;
- un même SN peut avoir plusieurs mesures à des heures différentes.

## 14. Onglet 8 — Oscillogramme contacts

### Modes d’affichage

```text
Électrique GPIO
Logique contact
Synthèse transfert / rebonds
```

### Fonctions obligatoires

```text
Vue complète
Zoom fronts
Zoom contact
Zoom rebonds
Zoom + / dézoom avec facteur 2 à 100
Fenêtre temporelle manuelle
Curseurs A et B avec delta
Chargement d’un ancien lot puis choix du SN
Export XLSX et PDF
```

### Restrictions visuelles

- les huit voies R1–R4/T1–T4 restent visibles ;
- aucun tracé ne doit être coupé en bas ;
- le bouton Vue complète doit modifier les bornes et déclencher immédiatement le redessin ;
- les fronts courts doivent rester visibles grâce aux marqueurs même s’ils tombent sur le même pixel ;
- l’axe utilise µs ou ms selon la largeur de vue ;
- le zoom est centré, borné à la capture et conserve les curseurs ;
- le rappel historique doit choisir d’abord le lot, puis le SN du lot ;
- les SN répétés doivent rester distinguables par leur horodatage ou mesure.

## 15. Onglet 9 — Tensions collage / décollage

### 15.1 Identification et prérequis

Champs obligatoires :

```text
Lot
Relais/désignation
SN
Nom du test
Date
Ambiance
Type : monostable ou bistable 2 bobines
Nombre d’inverseurs : 1 à 4
```

Prérequis bloquants :

```text
RP2040 connecté
EA connectée sur un autre port COM
ADS1115 opérationnel
Étalonnage actif, valide et non expiré
Position initiale des contacts connue et conforme
Firmware confirmant FIRST_PASSAGE / STABLE_AFTER_CAPTURE
```

### 15.2 Paramètres IHM actuels

```text
Vmax                   : 0,100 à 40,000 V, défaut 30,000 V
Rampe BE montée        : 0,300 à 300,000 s, défaut 3,000 s
Rampe retour BE/BR     : 0,300 à 300,000 s, défaut 3,000 s
Attente interphase     : 3,000 à 120,000 s, défaut 3,000 s
Limite courant         : 0,001 à 4,000 A, défaut 0,200 A
Validation stable      : 1 à 50 ms, défaut 3 ms
Nombre d’inverseurs    : 1 à 4
```

La valeur en cours de saisie dans chaque `QDoubleSpinBox` doit être validée par `interpretText()` avant lecture.

### 15.3 Pilotage EA

Commandes de base déjà utilisées :

```text
SYST:LOCK 1
SYST:LOC
OUTP ON / OFF
VOLT x
CURR x
MEAS:VOLT?
MEAS:CURR?
```

Rampe interne arbitraire :

```text
FUNC:GEN:SEL VOLTAGE
FUNC:GEN:WAVE:LEVEL n
FUNC:GEN:WAVE:IND 5 → tension départ
FUNC:GEN:WAVE:IND 6 → tension arrivée
FUNC:GEN:WAVE:IND 7 → durée
FUNC:GEN:WAVE:SUBMIT
attente minimale 2,2 s sans nouvelle commande
relecture départ, arrivée et durée
armement RP2040
OUTP ON
FUNC:GEN:WAVE:STAT RUN
contrôle de l’état RUN
```

Avant chaque programmation : vider la file d’erreurs SCPI. Après `SUBMIT` : lire `SYST:ERR?` et refuser l’essai si l’EA signale une erreur.

Tolérances de relecture actuellement attendues :

```text
Départ/arrivée : ±0,010 V
Durée          : max(0,010 s ; 0,2 % de la durée demandée)
```

La classe impose pour l’EA-PSI 9200-04 T une pente minimale de `0,145 V/s`. L’audit doit vérifier la validité de cette hypothèse, la cohérence avec l’UI autorisant jusqu’à 300 s, et le comportement près des limites.

### 15.4 Séquence monostable

Collage :

```text
1. EA à 0 V, sortie coupée.
2. Vérifier repos : R fermés, T ouverts.
3. Maintenir BE active.
4. Armer VSCAN PICKUP.
5. Démarrer rampe 0 → Vmax pendant la durée montée BE.
6. Capturer la tension de collage au premier passage complet travail.
7. Confirmer ensuite la stabilité sans remplacer la tension capturée.
```

Décollage dans un cycle :

```text
1. Conserver BE active et maintenir Vmax.
2. Attendre exactement le délai interphase demandé, en tenant compte du temps de préparation EA.
3. Armer VSCAN DROPOUT.
4. Démarrer rampe Vmax → 0 pendant la durée descente BE.
5. Capturer la tension de décollage au premier passage complet repos.
6. Confirmer ensuite la stabilité sans remplacer la tension capturée.
7. Couper BE, générateur, sortie EA et revenir à 0 V.
```

Mesure décollage seule : préconditionner le monostable à Vmax avec BE active avant la descente.

### 15.5 Séquence bistable deux bobines

Basculement BE :

```text
1. Prépositionner au repos par BR à Vmax.
2. Couper BR, sortie EA, revenir à 0 V.
3. Vérifier repos.
4. Maintenir BE active.
5. Rampe 0 → Vmax.
6. Capturer le premier passage complet travail.
7. Couper BE.
```

Retour BR :

```text
1. Prépositionner au travail par BE si la mesure BR est lancée seule.
2. Couper BE, sortie EA, revenir à 0 V.
3. Vérifier travail.
4. Maintenir BR active.
5. Rampe 0 → Vmax avec la durée BR saisie dans le second champ.
6. Capturer le premier passage complet repos.
7. Couper BR et remettre l’EA à 0 V.
```

Dans un cycle BE+BR, le délai interphase commence après la fin validée de BE. La seconde rampe ne doit pas commencer avant la cible temporelle demandée ; le temps réel doit être enregistré dans `interphase_actual_s`.

### 15.6 Définition officielle des tensions

#### Tension de collage / basculement BE

```text
Tension nécessaire pour obtenir la fermeture de tous les contacts travail.
Mesure au premier instant où, pour tous les inverseurs actifs :
R ouverts ET T fermés.
```

#### Tension de décollage / retour BR

```text
Tension pour laquelle on obtient la fermeture de tous les contacts repos.
Mesure au premier instant où, pour tous les inverseurs actifs :
T ouverts ET R fermés.
```

### 15.7 Règle fondamentale sur les rebonds

La tension, le RAW et l’instant sont verrouillés au **premier passage complet**. Les rebonds ultérieurs ne doivent jamais les modifier.

```text
Premier passage complet → capturer MV, RAW, T_US une fois.
Rebond hors position     → remettre uniquement le compteur de stabilité à zéro.
Retour dans la position  → recommencer uniquement la validation stable.
Stabilité atteinte       → valider la capture initiale.
```

Exemple collage :

```text
12,000 V : premier passage complet travail → valeur verrouillée
12,004 V : rebond
12,030 V : retour travail
12,033 V : stabilité confirmée
Résultat obligatoire : 12,000 V
```

Exemple décollage :

```text
12,020 V : premier passage complet repos → valeur verrouillée
12,015 V : rebond
11,990 V : retour repos
11,987 V : stabilité confirmée
Résultat obligatoire : 12,020 V
```

Cette règle s’applique à chaque inverseur et à la ligne `GLOBAL`. `GLOBAL` correspond au premier instant où tous les inverseurs actifs sont simultanément dans la position cible.

### 15.8 Cohérence temps/tension à auditer

Pour une rampe 0 → 20 V en 20 s :

```text
pente = 1 V/s
collage à 12 V attendu vers t ≈ 12 s
```

Pour une descente 20 → 0 V en 20 s :

```text
décollage à 12 V attendu vers t ≈ 8 s
```

L’audit doit vérifier :

- que `T_US` démarre au véritable armement RP2040 et reste synchronisé avec le départ EA ;
- que le délai entre l’armement et `RUN` n’introduit pas un décalage significatif ;
- que le calcul `effective_ramp_s` ne masque pas une incohérence ;
- qu’un résultat `19,8 V à t≈12 s` ou `12 V à t≈19,8 s` est signalé comme incohérent plutôt que sauvegardé sans alerte ;
- que les valeurs par inverseur et GLOBAL proviennent bien de la trame finale FIRST_PASSAGE ;
- que la fin de rampe ou le dernier échantillon ADS ne remplace jamais la capture.

### 15.9 Persistance et export

Chaque mesure doit enregistrer :

```text
métadonnées lot/SN/type
Vmax, durées demandées, attente demandée et réelle
limite courant, validation stable
politique FIRST_PASSAGE / STABLE_AFTER_CAPTURE
rapport et offset de calibration
ID/date/erreur de calibration
RAW et tensions par inverseur et GLOBAL
T_US par inverseur et GLOBAL
durées de rampes reconstituées
relectures EA
résultat et timestamp
```

Les exports XLSX/PDF doivent conserver ces éléments essentiels, au minimum la calibration, les durées, les tensions GLOBAL et par inverseur, le type de relais et la politique de capture.

## 16. Onglet 10 — Étalonnage tension

### Finalité

Déterminer une conversion traçable entre RAW ADS1115 et tension du BUS, puis interdire les mesures officielles si la calibration n’est pas valide.

### Paramètres actuels

```text
Validité             : 1 à 3650 jours, défaut 365
Tolérance contrôle   : 0,001 à 1,000 V, défaut ±0,050 V
Point bas réel       : 0 à 5 V, défaut 0 V
Point haut réel      : 1 à 40 V, défaut 30 V
Point contrôle réel  : 0,1 à 40 V, défaut 15 V
```

### Procédure obligatoire

1. renseigner opérateur, référence du multimètre et date ;
2. stabiliser le point bas, saisir la tension multimètre et capturer un RAW frais ;
3. stabiliser le point haut, saisir la tension multimètre et capturer un RAW frais ;
4. stabiliser un point intermédiaire indépendant, saisir sa tension et capturer un RAW frais ;
5. calculer rapport et offset ;
6. refuser l’activation si le point de contrôle dépasse la tolérance ;
7. une seule calibration peut être active ;
8. une calibration expirée ou invalidée bloque les mesures tension.

### Calcul attendu

```text
slope_mV_par_count = (Vhaut − Vbas) × 1000 / (RAWh − RAWb)
rapport             = slope_mV_par_count / 0,125
Offset_mV           = Vbas × 1000 − RAWb × 0,125 × rapport
Vcalculée           = RAW × 0,125 × rapport / 1000 + Offset_mV / 1000
```

Le firmware reçoit le rapport en millionièmes et l’offset en mV.

### Restrictions

- chaque bouton Capture doit demander une trame `ADS?` fraîche ;
- les anciens RAW affichés ne doivent pas être utilisés par erreur ;
- point haut > point bas + 1 V ;
- RAW haut > RAW bas ;
- rapport firmware admis : 1 à 100 ;
- offset firmware admis : −500 à +500 mV ;
- activation impossible sans point intermédiaire conforme ;
- l’historique doit distinguer ACTIVE VALIDE, EXPIRÉE et INVALIDÉE ;
- invalidation ne doit pas effacer l’historique ;
- une mesure sauvegardée doit conserver la calibration utilisée même si une nouvelle calibration devient active.

## 17. SQLite — schémas et règles

### 17.1 Base Production

Tables :

```text
settings
operators
essais
```

La table `essais` conserve notamment lot, SN, désignation, nombre d’inverseurs, opérateur, date, heure, scénario, résultat, détails JSON et timestamp.

### 17.2 Base Chronométrie

Tables :

```text
mesures_chrono_contacts
calibrations_tension_ads1115
mesures_tension_fonctionnement
```

Le schéma exact est fourni dans `SCHEMA_SQLITE_V2_12_2.sql`.

### 17.3 Règles communes

- journal WAL et `synchronous=NORMAL` sont utilisés dans l’application ;
- les migrations doivent être idempotentes ;
- une ancienne base ne doit pas perdre ses données ;
- une base partiellement migrée doit produire une erreur explicite ;
- les champs JSON doivent rester valides ;
- les sauvegardes/restaurations doivent gérer correctement les fichiers WAL/SHM ou utiliser l’API backup SQLite ;
- l’absence de clé étrangère explicite entre mesure tension et calibration doit être examinée ;
- l’audit doit rechercher les incohérences entre schéma créé, migrations et colonnes utilisées dans les INSERT/SELECT/export.

## 18. Exports et emplacement des fichiers

Pour les exports demandés par l’opérateur :

```text
Mode Python : dossier du script.
EXE onefile : dossier de l’exécutable, Path(sys.executable).parent.
```

Même si l’opérateur navigue dans un autre dossier, le fichier final est normalement forcé dans le dossier de l’EXE. L’audit doit vérifier que cette règle est réellement appliquée à tous les exports concernés et qu’aucun nom invalide ou écrasement silencieux n’est possible.

## 19. Verrouillage et licence

### Onglets accessibles sans mot de passe

```text
Production
Neutral Screen Automatique
```

### Onglets protégés

```text
Neutral Screen Manuel
Éditeur Scénario Neutral
Gestion Base
Cyclage
Chronométrie contacts
Oscillogramme contacts
Tensions collage / décollage
Étalonnage tension
```

Mot de passe initial atelier : `1234`.  
Mot de récupération : `marechal`, qui remet uniquement le mot de passe à `1234` sans supprimer les essais.

Ce verrouillage d’onglets n’est pas une sécurité informatique forte.

La protection licence est exécutée avant l’ouverture de l’IHM par `require_license()`. Une activation existante sur le même PC peut être réutilisée. L’audit doit vérifier :

- absence de contournement involontaire au démarrage ;
- inclusion de `licence_manager.py` dans l’EXE onefile ;
- comportement clair en cas de fichier de licence absent, corrompu ou déplacé ;
- absence d’impact de la licence sur les bases d’essais.

## 20. LED RGB interne

| Situation | État attendu |
|---|---|
| Boot / non connecté | jaune pâle clignotant |
| Connecté / arrêt | jaune très pâle fixe |
| Pulse BE | rouge |
| Pulse BR | bleu |
| Pulse BEBR | violet |
| Sélection 32 V | cyan |
| Accepté | vert fixe |
| Refusé | rouge fixe |
| Erreur | orange clignotant |

La LED ne doit jamais retarder une capture ou un pulse critique.

## 21. Tests logiciels minimum à reproduire

### Statique et démarrage

```text
python -m py_compile main_ihm...py licence_manager.py
validation XML du .ui
validation JSON
chargement Qt hors écran
initialisation complète de l’IHM hors écran
```

### Correspondance UI/Python

- tous les `get_widget` obligatoires existent et ont la classe attendue ;
- aucun `objectName` dupliqué critique ;
- tous les signaux ne sont connectés qu’une fois ;
- aucune création dynamique de remplacement ne masque un widget absent dans le `.ui`.

### RP2040 simulé

- trames série fragmentées en plusieurs lectures ;
- plusieurs lignes reçues dans un même paquet ;
- caractères invalides et ligne trop longue ;
- déconnexion au milieu d’une mesure ;
- anciennes versions firmware ;
- overflow événements ;
- timeout sans résultat.

### Capture premier passage

```text
Collage : 12,000 V → rebond → stabilité à 12,033 V → résultat 12,000 V.
Décollage : 12,020 V → rebond → stabilité à 11,987 V → résultat 12,020 V.
Plusieurs rebonds successifs.
Rebond plus long que la validation.
Passage individuel avant le passage GLOBAL.
Contact inconnu ou incohérent.
```

### EA simulée

- rampe 0→20 V en 20 s relue exactement ;
- durée saisie encore en édition ;
- erreur SCPI après SUBMIT ;
- relecture départ/fin/durée hors tolérance ;
- état générateur non RUN ;
- déconnexion EA ;
- deuxième rampe BR utilisant bien le second champ ;
- attente interphase réelle ≥ attente demandée ;
- arrêt pendant la phase d’attente et pendant RUN.

### SQLite

- création des deux bases ;
- migration depuis une ancienne version ;
- insertion/relecture/export d’un résultat complet ;
- doublon SN autorisé ;
- sauvegarde/restauration avec WAL ;
- fusion et suppression avec sauvegarde préalable ;
- calibration active unique et expiration.

### Tests matériels obligatoires avant validation finale

1. oscilloscope sur GP14, GP15 et GP26 pour pulses BE/BR/BEBR ;
2. contrôle des huit entrées contacts ;
3. comparaison ADS1115, valeur IHM et multimètre au BUS à 0, 12, 15, 20 et 30 V ;
4. comparaison de la valeur A0 corrigée avec la tension réelle aux bornes de BE puis BR ;
5. mesure réelle d’une rampe 0→20 V en 20 s ;
6. vérification collage vers 12 V à environ 12 s ;
7. vérification décollage 20→0 V vers 12 V à environ 8 s ;
8. rebonds provoqués ou observés : confirmer que la première tension reste verrouillée ;
9. coupure USB RP2040, déconnexion EA et arrêt d’urgence ;
10. répétabilité sur plusieurs cycles et plusieurs relais.

## 22. Points explicitement non validés dans le pack

À la date du présent document :

```text
- pas de compilation Arduino réelle dans l’environnement de génération ;
- pas de test physique du firmware sur RP2040 ;
- pas de test physique ADS1115 ;
- pas de test physique des rampes EA ;
- pas de validation métrologique ±0,05 V ;
- pas de validation oscilloscope de la simultanéité BEBR ;
- pas de validation électrique des protections bobines/MOSFET ;
- pas de preuve matérielle que l’erreur BE proche de Vmax est supprimée.
```

Le pack ne doit donc pas être déclaré « parfait », « validé matériellement » ou « validé métrologiquement » sur la seule base des tests logiciels.

## 23. Questions prioritaires à poser à l’auditeur

1. La synchronisation `VSCAN BEGIN → démarrage EA RUN` permet-elle d’associer correctement `T_US` et tension réelle ?
2. La capture utilise-t-elle un échantillon ADS suffisamment proche du front contact pour tenir ±0,05 V avec les rampes prévues ?
3. La logique FIRST_PASSAGE est-elle correcte pour chaque inverseur et GLOBAL dans tous les cas de rebond ?
4. Un contact passant brièvement dans l’état cible puis n’y revenant jamais peut-il conduire à une capture ancienne validée beaucoup plus tard ? Est-ce conforme à la définition métier ?
5. La durée stable confirme-t-elle la fin réelle des rebonds sans écraser la première tension ?
6. Les rampes EA sont-elles correctement construites pour la PSI 9200-04 T et la pente minimale codée est-elle justifiée ?
7. L’attente interphase demandée correspond-elle à l’intervalle métier attendu ou inclut-elle les 2,2 s de préparation EA ?
8. Les arrêts et exceptions coupent-ils toujours les deux bobines et l’EA ?
9. Le résultat `OK` des mesures tension est-il trop permissif lorsqu’une seule phase est présente ou lorsqu’une incohérence temps/tension existe ?
10. Les bases, migrations, exports et sauvegardes sont-ils sans perte et cohérents entre les deux fichiers SQLite ?
11. Le gros fichier Python monolithique présente-t-il des connexions de signaux multiples, états résiduels ou races de timers ?
12. Les tests fournis sont-ils indépendants de l’implémentation ou reproduisent-ils seulement la même logique ?

## 24. Critère de conclusion

Un verdict « travail parfait » n’est acceptable que si :

```text
- aucun défaut bloquant ou majeur n’est identifié ;
- les exigences de chaque onglet sont reliées à une implémentation vérifiable ;
- les tests logiciels couvrent les erreurs et pas seulement le chemin nominal ;
- le firmware compile pour la vraie carte ;
- les essais matériels et métrologiques passent ;
- la valeur tension reste dans ±0,05 V autour de la référence sur BE et BR ;
- les rampes et délais sont mesurés réellement ;
- la sécurité laisse toutes les sorties à zéro après chaque erreur.
```

Sans ces preuves, la conclusion correcte est : **logiciel prêt pour validation matérielle**, et non **moyen validé**.
