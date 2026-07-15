# Sécurité EA et contrôle de plausibilité — V2.12.3

## 1. Logique fermée

Les requêtes critiques suivantes doivent produire une réponse non vide :

```text
SYST:ERR?
FUNC:GEN:WAVE:STAT?
OUTP?
MEAS:VOLT?
```

Toute absence de réponse ou tout timeout provoque un échec.

## 2. Arrêt confirmé

Le logiciel envoie :

```text
FUNC:GEN:WAVE:STAT STOP
OUTP OFF
VOLT 0
```

Puis vérifie :

- générateur `STOP`, `OFF`, `IDLE` ou `0` ;
- sortie `OFF` ou `0` ;
- tension mesurée absolue ≤ 0,200 V ;
- `SYST:ERR?` avec code 0.

Deux tentatives sont réalisées. Un échec déclenche une alerte bloquante demandant une coupure manuelle.

Cette confirmation logicielle ne remplace pas le sélecteur physique `OFF / FIXE / EA`.

## 3. Plausibilité tension/temps

Pour une rampe linéaire :

```text
fraction = (Vmesurée - Vdépart) / (Vfin - Vdépart)
t_théorique = durée × fraction
écart = T_US / 1 000 000 - t_théorique
```

Tolérance volontairement large :

```text
max(0,750 s ; 10 % de la durée)
```

Cette tolérance tient compte du fait que `T_US` commence à l’armement RP2040, avant le départ physique de l’EA.

Le contrôle classe la mesure, mais ne modifie jamais :

- `GLOBAL_MV` ;
- `GLOBAL_RAW` ;
- `GLOBAL_T_US` ;
- les valeurs individuelles des inverseurs.

## 4. Indépendance entre essais

Au début de chaque nouvel essai, le logiciel remet explicitement à zéro :

- les statuts de plausibilité PICKUP/DROPOUT ;
- le résultat prioritaire éventuel (`INCOHERENT` ou `ARRET_EA_NON_CONFIRME`) ;
- l'état de confirmation d'arrêt EA.

Cette remise à zéro empêche qu'un défaut de l'essai précédent soit enregistré sur le relais suivant.

## 5. Traçabilité des exports

Les nouvelles informations de plausibilité et d'arrêt EA sont ajoutées à SQLite et aux exports. Le générateur PDF calcule désormais une largeur pour chaque colonne et passe en paysage lorsque le tableau dépasse neuf colonnes ; aucune colonne supplémentaire ne doit être silencieusement supprimée.
