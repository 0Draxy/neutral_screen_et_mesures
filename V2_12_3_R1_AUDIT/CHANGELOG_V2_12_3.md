# Changelog — Neutral Screen V2.12.3

## Sécurité EA

- `SYST:ERR?` vide ou en timeout devient une erreur.
- `FUNC:GEN:WAVE:STAT?` vide ou non `RUN` provoque l’arrêt de l’essai.
- L’état générateur est vérifié périodiquement pendant la rampe.
- La fin de mesure et l’arrêt opérateur commandent `STOP`, `OUTP OFF`, `VOLT 0`.
- L’arrêt est confirmé par : état générateur arrêté, `OUTP?` à OFF, `MEAS:VOLT?` ≤ 0,200 V et file SCPI claire.
- En cas d’échec, l’IHM affiche `ARRÊT EA NON CONFIRMÉ — COUPER MANUELLEMENT L’ALIMENTATION`.

## Rampes EA

- Pente minimale conservée : `0,000725 × 200 V = 0,145 V/s`.
- Durée maximale dynamique : `Vmax / 0,145`.
- La limite est arrondie vers le bas à la résolution des champs afin qu’une valeur acceptée par l’IHM ne soit pas rejetée ensuite par le contrôle de pente.

## Plausibilité métrologique

- Comparaison du `T_US` capturé avec le temps théorique correspondant à la tension ADS1115.
- Tolérance : `max(0,750 s ; 10 % de la durée demandée)` afin d’absorber le décalage entre armement RP2040 et départ physique EA.
- Classement : `OK`, `INCOHERENT` ou `NON_VERIFIE`.
- Aucune modification des valeurs officielles `RAW`, `MV` ou `T_US`.
- Les verdicts de plausibilité, de sécurité et d'arrêt sont réinitialisés au début de chaque essai afin d'éviter toute contamination par l'essai précédent.

## SQLite et exports

Ajout des champs :

- statuts de plausibilité PICKUP/DROPOUT ;
- temps théoriques et écarts temporels ;
- JSON complet de plausibilité ;
- arrêt EA confirmé ;
- état final sortie/générateur ;
- tension finale EA ;
- détail de confirmation d’arrêt.

Les migrations sont idempotentes et conservent les anciennes bases.

L'export PDF accepte désormais toutes les colonnes demandées : l'ancienne largeur fixe limitée à neuf colonnes a été remplacée par un calcul dynamique, avec passage en paysage pour les tableaux denses.

## Interface

- ajout du bouton `Recharger base` dans Production ;
- affichage de la durée maximale de rampe selon `Vmax` ;
- suppression du bouton caché `TEST FINI` et des raccourcis globaux redondants ;
- conservation de la fenêtre modale `TEST FINI` avec validation souris, Espace et Entrée.

## Firmware

Aucune modification fonctionnelle de la logique temps réel ou `FIRST_PASSAGE`. Seuls le nom de version et la trame HELLO passent en V2.12.3.

## Correctif de révision du pack R1

- fermeture explicite des trois connexions SQLite temporaires du test `test_securite_ea_plausibilite_v2_12_3.py` ;
- suppression de l'erreur Windows `WinError 32` lors du nettoyage de `TemporaryDirectory` ;
- aucune modification fonctionnelle du logiciel, de l'interface ou du firmware.
