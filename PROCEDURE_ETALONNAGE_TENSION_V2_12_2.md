# Procédure d’étalonnage tension — V2.12.2

## Conditions préalables

- ADS1115 alimenté en 3,3 V ;
- pont diviseur 39 kΩ / 3,3 kΩ raccordé au BUS + BOBINES ;
- condensateur 10 nF entre A0 et GND ;
- RP2040 connecté ;
- alimentation EA connectée ;
- sélecteur physique sur EA ;
- aucun relais nécessaire pendant l’étalonnage ;
- multimètre de référence raccordé directement au BUS + BOBINES.

## Point bas

1. Mettre la sortie EA à 0 V.
2. Lire la tension réelle au multimètre.
3. Saisir cette valeur dans `Point bas`.
4. Cliquer sur `CAPTURER POINT BAS`.
5. Vérifier qu’un RAW apparaît.

## Point haut

1. Régler l’EA vers 30 V.
2. Lire la tension réelle au multimètre.
3. Saisir cette valeur dans `Point haut`.
4. Cliquer sur `CAPTURER POINT HAUT`.

## Contrôle intermédiaire

1. Régler l’EA vers 15 V.
2. Lire la tension réelle au multimètre.
3. Saisir cette valeur dans `Contrôle intermédiaire`.
4. Cliquer sur `CAPTURER CONTRÔLE`.

## Calcul et activation

1. Renseigner opérateur, multimètre et date.
2. Régler la tolérance, 0,050 V par défaut.
3. Cliquer sur `CALCULER`.
4. Vérifier le rapport, l’offset et l’erreur de contrôle.
5. Si le statut est conforme, cliquer sur `ENREGISTRER ET ACTIVER`.
6. Vérifier dans l’historique la ligne `ACTIVE VALIDE`.

## Règles de sécurité logicielle

- sans point intermédiaire : activation refusée ;
- erreur supérieure à la tolérance : activation refusée ;
- calibration expirée : mesure officielle bloquée ;
- calibration invalidée : mesure officielle bloquée ;
- la consigne EA ne doit jamais être saisie à la place de la valeur réellement lue au multimètre.

---

## Remarque V2.12.2 sur la validation des contacts

Le réglage `Validation (ms)` ne décale pas la tension de collage ou de décollage. La tension est verrouillée au premier passage complet des contacts. Cette durée confirme seulement que la position finale se stabilise après les rebonds.
