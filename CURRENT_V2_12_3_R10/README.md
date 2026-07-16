# Neutral Screen V2.12.3 R10 — référence courante

Cette branche contient la version **V2.12.3 R10** destinée à l’audit et à la poursuite du développement.

## Référence UI officielle

Le fichier reconstruit :

`ihm_relais_rp2040_28vdc_precision_v2_12_3.ui`

provient du dernier fichier Qt Designer fourni et validé par l’utilisateur. Il doit être utilisé comme base obligatoire pour toute modification ultérieure.

Repères visibles contrôlés :

- premier onglet : **Production** ;
- titre principal : **Neutral Screen - Cycleur - Mesures** ;
- version affichée : **V 2.12.3 R10** ;
- titre de fenêtre : **Cycleur - Neutral Screen - V2.12.3 R10 - (Par O.MARECHAL)**.

## Reconstruction de la R10

Les patches lisibles de ce dossier transforment les fichiers V2.12.2 déjà présents à la racine du dépôt en fichiers R10 :

```bash
python CURRENT_V2_12_3_R10/apply_r10.py
```

Sous Windows, lancer cette commande dans **Git Bash**, car le script utilise l’outil standard `patch`.

Le script :

1. reconstruit le Python principal, le `.ui` et le firmware R10 ;
2. contrôle leurs SHA-256 ;
3. installe à la racine le BAT, les tests, le schéma SQLite et les autres fichiers de support ;
4. crée les deux bases SQLite `REFERENCE_VIDE` sans toucher aux bases utilisateur ;
5. prépare les dossiers `DOCUMENTATION` et `AUDIT_R10`.

Fichiers principaux produits :

- `main_ihm_relais_rp2040_v2_12_3.py` ;
- `ihm_relais_rp2040_28vdc_precision_v2_12_3.ui` ;
- `rp2040_relais_28vdc_precision_v2_12_3_ADS1115_GP26_RGB.ino`.

## Licence

`licence_manager.py` n’est volontairement pas publié dans ce dépôt public. Il ne doit pas être ajouté à cette branche. Un auditeur peut employer un stub local temporaire uniquement pour charger l’IHM, sans le committer et sans modifier la protection dans le code livré.

## Limite de validation

Les tests logiciels ne constituent pas une validation métrologique ou matérielle. La précision de tension et le comportement réel de l’EA, de l’ADS1115, du RP2040 et des relais doivent être contrôlés sur le moyen physique.
