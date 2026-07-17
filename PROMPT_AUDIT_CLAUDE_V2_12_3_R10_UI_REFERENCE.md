# Audit Claude — Neutral Screen V2.12.3 R10

Analyse intégralement la branche GitHub `v2.12.3-r10-ui-reference` du dépôt `0Draxy/neutral_screen_et_mesures`.

## Mission

Réaliser un audit technique croisé du Python PySide6, du fichier Qt Designer, du firmware RP2040, du protocole série, des règles SQLite, des exports Excel/PDF et du BAT PyInstaller.

Ne modifie aucun fichier pendant l’audit. Ne considère pas les affirmations des README comme des preuves : vérifie l’implémentation réelle.

## Fichier UI de référence obligatoire

Le fichier officiel est :

`ihm_relais_rp2040_28vdc_precision_v2_12_3.ui`

Il provient du fichier utilisateur `ihm_relais_rp2040_28vdc_precision_v2_12_3(2).ui` et remplace toutes les anciennes versions de l’interface.

Contrôler notamment :

- titre de fenêtre : `Cycleur - Neutral Screen - V2.12.3 R10 - (Par O.MARECHAL)` ;
- nom du premier onglet : `Production` ;
- titre interne du premier onglet : `Neutral Screen - Cycleur - Mesures` ;
- sous-titre/version : `V 2.12.3 R10` ;
- conservation des tailles, positions, espacements et styles définis dans Qt Designer ;
- absence de reconstruction de l’IHM à partir d’un ancien `.ui` ;
- correspondance exacte entre tous les `objectName` utilisés par le Python et ceux du `.ui` ;
- détection des widgets dupliqués ou non connectés, notamment les contrôles de connexion de l’onglet Production.

## Fonctions critiques à vérifier

### Capture temporelle

- La logique `FIRST_PASSAGE` doit conserver la première transition complète détectée.
- Les rebonds ultérieurs ne doivent jamais remplacer la tension, le RAW ADS ou le temps capturé.
- Les rebonds doivent seulement intervenir dans la validation de stabilité.
- Vérifier les mesures d’enclenchement, transfert, rebond travail, déclenchement, transfert retour et rebond repos pour 1 à 4 inverseurs.

### Mesure de tension collage/décollage

- Vérifier les rampes BE et BR séparées.
- Bistable : la valeur de montée BE est utilisée pour BE et la valeur de montée BR pour BR.
- Monostable : la première rampe est la montée BE et la seconde la descente BE.
- Les réglages doivent être sauvegardés, rechargés puis figés au démarrage de l’essai.
- Vérifier la mesure globale et la mesure individuelle de chaque inverseur.
- En cas de contact manquant : global BE = `Vmax`, global BR bistable = `Vmax`, décollage monostable = `0 V`.
- Si le premier passage global existe mais que la stabilité échoue, conserver la vraie capture et produire un défaut de stabilité.

### Bouton MESURER TOUT

Le cycle combiné doit être entièrement automatique avec l’alimentation EA comme seule alimentation des bobines :

1. passage EA en distant ;
2. mesure des tensions par rampes ;
3. sauvegarde des tensions ;
4. arrêt du générateur de rampe ;
5. réglage EA à la valeur distincte `Tension chrono` ;
6. contrôle de la tension réelle avec `MEAS:VOLT?` ;
7. lancement de la chronométrie par GP14/GP15 ;
8. sauvegarde combinée ;
9. `OUTP OFF`, consigne 0 V et confirmation d’arrêt.

Il ne doit exister aucun message demandant à l’opérateur de commuter manuellement de EA vers FIXE.

L’alimentation fixe 28/32 V est réservée au Neutral Screen et ne doit pas être raccordée pendant `MESURER TOUT`. Vérifier que GP26 reste dans l’état d’isolement prévu pendant le mode EA.

### Voyants contacts de l’onglet collage/décollage

- Vérifier qu’il s’agit de vrais cercles graphiques et non du caractère Unicode `●`.
- Vérifier le diamètre, l’arrondi, les couleurs actif/inactif et l’absence de chevauchement avec le titre du groupe.
- Vérifier que le Python ne réécrit pas une taille incompatible avec celle du `.ui`.

### Exports

Tous les exports Excel/PDF concernés doivent présenter les résultats combinés.

Feuille/section 1 :

- Tension d’Enclenchement globale ;
- Tension de Rappel globale ;
- les six temps demandés pour chaque inverseur utilisé, dans l’ordre défini.

Feuille/section 2 :

- tensions globales ;
- tensions d’enclenchement et de rappel individuelles pour chaque inverseur utilisé ;
- les six temps de chronométrie par inverseur.

Vérifier les noms, l’ordre, les unités, les valeurs manquantes, les relais à 1–4 inverseurs et la cohérence entre SQLite, Excel et PDF.

### Étalonnage tension et SQLite

- Identifier précisément la table et les colonnes de conservation des étalonnages ADS1115.
- Vérifier la sélection de l’étalonnage actif.
- Vérifier la traçabilité de l’étalonnage utilisé dans chaque mesure.
- Vérifier les migrations automatiques de base existante, notamment `chrono_supply_v`.
- Vérifier qu’une base de référence vide ne peut pas écraser la base utilisateur.

### EA-PSI et sécurité

- Vérifier les commandes SCPI, réponses vides, timeouts et états d’erreur.
- Vérifier le prépositionnement, la pente minimale, la plausibilité des mesures et les contrôles de tension.
- Vérifier que l’arrêt de sécurité est confirmé et ne se contente pas d’envoyer une commande sans contrôle.
- Vérifier tous les chemins d’exception, annulation, fermeture de l’application et perte de communication.

### Firmware et protocole série

- Vérifier l’accord exact entre les commandes émises par le Python et leur parsing dans le firmware.
- Vérifier le mode chronométrie alimenté par EA sans action indésirable sur GP26.
- Vérifier les commandes BE, BR, OFF, ADS et les réponses attendues.
- Rechercher les erreurs de découpage de trames, dépassements, blocages et temporisations.

### Construction Windows

- Vérifier que le BAT commence directement par `@echo off` et ne contient pas de BOM UTF-8.
- Vérifier les fichiers obligatoires, les tests lancés et la commande PyInstaller.
- Vérifier que le nom de l’EXE correspond à R10.
- Le fichier privé `licence_manager.py` n’est volontairement pas publié sur GitHub. Ne pas demander son contenu et ne pas proposer de le committer. Pour un test local uniquement, utiliser éventuellement un stub minimal hors dépôt.

## Format de réponse obligatoire

1. Résumé exécutif.
2. Tableau des anomalies triées : `CRITIQUE`, `MAJEURE`, `MINEURE`, `INFORMATION`.
3. Pour chaque constat : fichier, lignes exactes, preuve, conséquence et correctif minimal proposé.
4. Tableau de conformité de toutes les exigences ci-dessus.
5. Liste des tests réellement exécutés et de leurs résultats.
6. Séparer explicitement :
   - `Certain par lecture du code` ;
   - `Confirmé par test logiciel` ;
   - `À vérifier sur Windows` ;
   - `À vérifier sur matériel` ;
   - `À vérifier métrologiquement`.
7. Ne jamais annoncer une précision matérielle ou une sécurité électrique comme validée uniquement par le code.
8. Signaler les faux positifs possibles et vérifier le contexte complet avant de conclure.
