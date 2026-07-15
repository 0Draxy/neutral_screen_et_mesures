# Neutral Screen V2.12.2 — capture avant rebonds

## Correction principale

La V2.12.1 attendait qu'un état contact reste stable puis conservait le début de la dernière période stable. En présence de rebonds, cette logique pouvait déplacer la tension mesurée vers une valeur plus haute en montée ou plus basse en descente.

La V2.12.2 mémorise désormais définitivement la première tension correspondant à l'état complet demandé :

- collage / BE : tous les R ouverts et tous les T fermés ;
- décollage monostable : tous les T ouverts et tous les R fermés ;
- retour BR bistable : tous les T ouverts et tous les R fermés.

La validation stable reste active mais ne modifie plus la tension capturée.

## Sécurité de compatibilité

L'IHM vérifie les champs de la trame d'armement RP2040 :

```text
CAPTURE=FIRST_PASSAGE
VALIDATION=STABLE_AFTER_CAPTURE
```

Une ancienne version du firmware est refusée avant le démarrage de la rampe EA.

## Trames ajoutées

Le firmware envoie une trame au premier passage :

```text
VSCAN;FIRST;MODE=PICKUP;INV=GLOBAL;MV=12000;RAW=...;T_US=...
```

Le résultat confirmé conserve exactement cette valeur :

```text
VSCAN;RESULT;MODE=PICKUP;CAPTURE=FIRST_PASSAGE;VALIDATION=STABLE_AFTER_CAPTURE;GLOBAL_MV=12000;...
```

## Fichiers techniques modifiés

- `main_ihm_relais_rp2040_v2_12_2.py`
- `ihm_relais_rp2040_28vdc_precision_v2_12_2.ui`
- `rp2040_relais_28vdc_precision_v2_12_2_ADS1115_GP26_RGB.ino`
- `build_exe_onefile_ihm_relais_rp2040_v2_12_2.bat`
- `neutral_scenarios.json` : numéro de version uniquement.

## Traçabilité

La base SQLite et l'export XLSX enregistrent désormais :

```text
capture_policy = FIRST_PASSAGE
validation_policy = STABLE_AFTER_CAPTURE
```

Le rapport PDF indique dans son titre que la capture est réalisée au premier passage.

## Éléments conservés

- pilotage EA et contrôle des durées de rampe V2.12.1 ;
- étalonnage ADS1115 ;
- sécurité licence ;
- câblage matériel ;
- chronométrie et Neutral Screen automatique.
