# Capture des tensions au premier passage — V2.12.2

## Définition appliquée

### Tension de collage

La tension est mémorisée au premier instant où tous les inverseurs sont en position travail :

```text
R1..Rn ouverts ET T1..Tn fermés
```

### Tension de décollage ou retour BR

La tension est mémorisée au premier instant où tous les inverseurs sont en position repos :

```text
T1..Tn ouverts ET R1..Rn fermés
```

## Traitement des rebonds

Lors du premier passage complet, le RP2040 mémorise immédiatement :

- la tension ADS1115 corrigée ;
- la valeur RAW ADS1115 ;
- l'instant en microsecondes.

Si un contact rebondit ensuite, seule la temporisation de validation stable repart à zéro. La tension, le RAW et l'instant du premier passage restent verrouillés.

Lorsque la position complète reste stable pendant la durée réglée dans l'IHM, le résultat est confirmé avec la valeur du premier passage.

## Exemple en montée

```text
12,000 V : tous les contacts atteignent pour la première fois la position travail
12,004 V : rebond, un contact T se rouvre
12,030 V : tous les contacts reviennent en position travail
12,033 V : stabilité confirmée
```

Résultat enregistré :

```text
12,000 V
```

## Exemple en descente

```text
12,020 V : tous les contacts atteignent pour la première fois la position repos
12,015 V : rebond, un contact R se rouvre
11,990 V : tous les contacts reviennent en position repos
11,987 V : stabilité confirmée
```

Résultat enregistré :

```text
12,020 V
```

## Portée

La logique est identique pour :

- chaque inverseur individuel ;
- la ligne GLOBAL, correspondant au dernier inverseur nécessaire pour obtenir la position complète ;
- le collage BE monostable ;
- le décollage BE monostable ;
- le basculement BE bistable ;
- le retour BR bistable.
