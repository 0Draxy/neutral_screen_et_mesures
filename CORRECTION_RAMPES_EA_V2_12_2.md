# Contrôle des rampes EA — V2.12.2

La V2.12.2 conserve les corrections de rampes introduites en V2.12.1.

## Durées utilisées

- `Rampe BE 0→max` pilote la montée BE.
- En monostable, `Rampe BE max→0` pilote la descente BE.
- En bistable, `Rampe BR 0→max` pilote la montée BR.
- `Attente entre opérations` fixe le délai demandé entre la fin de la mesure BE et le démarrage de la seconde opération.

La valeur affichée dans le QDoubleSpinBox est forcée par `interpretText()` avant utilisation.

## Séquence EA

1. Programmation de la rampe dans le générateur EA.
2. Attente minimale de 2,2 s après `SUBMIT`.
3. Relecture des tensions de départ, d'arrivée et de la durée.
4. Refus de l'essai si la relecture n'est pas conforme.
5. Armement du RP2040.
6. Vérification de la politique `FIRST_PASSAGE`.
7. Démarrage du générateur EA.

## Exemple

Pour `0 → 20 V en 20 s`, la pente est de 1 V/s. Un collage à 12 V doit être capturé vers la douzième seconde. La rampe peut être arrêtée dès que le résultat a été confirmé stable ; il n'est pas nécessaire d'attendre 20 s.
