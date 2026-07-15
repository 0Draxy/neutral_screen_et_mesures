# Pack Neutral Screen V2.12.2

## Objet

Cette version corrige la logique de mesure des tensions de collage et de décollage :

- la tension est capturée au **premier passage complet** de tous les inverseurs dans la position demandée ;
- les rebonds ultérieurs ne remplacent jamais cette tension ;
- la durée « Validation (ms) » confirme seulement que la position finale devient stable.

La correction s'applique aux deux fonctionnements :

- monostable : montée BE pour le collage, descente BE pour le décollage ;
- bistable : montée BE pour le basculement travail, montée BR pour le retour repos.

## Fichiers principaux

- `main_ihm_relais_rp2040_v2_12_2.py` : IHM PySide6 et contrôle EA.
- `ihm_relais_rp2040_28vdc_precision_v2_12_2.ui` : interface Qt Designer.
- `rp2040_relais_28vdc_precision_v2_12_2_ADS1115_GP26_RGB.ino` : firmware RP2040 obligatoire.
- `licence_manager.py` : sécurité licence, identique aux versions précédentes.
- `neutral_scenarios.json` : scénarios Neutral Screen.
- `build_exe_onefile_ihm_relais_rp2040_v2_12_2.bat` : construction EXE Windows onefile.
- `CORRECTION_CAPTURE_PREMIER_PASSAGE_V2_12_2.md` : logique détaillée.
- `CORRECTION_RAMPES_EA_V2_12_2.md` : programmation et contrôle des rampes EA.

## Installation

```text
py -3 -m pip install -r requirements.txt
py -3 main_ihm_relais_rp2040_v2_12_2.py
```

Téléverser impérativement le firmware V2.12.2 sur le RP2040. L'IHM refuse de démarrer une rampe tension si le RP2040 ne confirme pas :

```text
CAPTURE=FIRST_PASSAGE
VALIDATION=STABLE_AFTER_CAPTURE
```

## Licence

La protection licence est conservée. Si le PC a déjà été activé avec le même identifiant de licence, aucune nouvelle activation ne sera demandée.

## Construction EXE

Lancer :

```text
build_exe_onefile_ihm_relais_rp2040_v2_12_2.bat
```

Le fichier est créé dans `dist\neutral_screen_v2_12_2.exe`.

## Validation

Les contrôles logiciels sont décrits dans :

- `SOFTWARE_TESTS_V2_12_2.txt`
- `VALIDATION_V2_12_2.txt`

La validation matérielle doit être réalisée avec le RP2040, l'ADS1115, l'alimentation EA et un relais réel.
