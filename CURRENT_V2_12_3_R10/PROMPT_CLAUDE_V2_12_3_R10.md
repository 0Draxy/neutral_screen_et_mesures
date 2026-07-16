# Audit Claude — Neutral Screen V2.12.3 R10

Tu dois auditer **Neutral Screen V2.12.3 R10** depuis la branche GitHub :

- dépôt : `0Draxy/neutral_screen_et_mesures`
- branche : `v2.12.3-r10-ui-reference`

Commence par lire `CURRENT_V2_12_3_R10/README.md`, puis exécute depuis la racine du dépôt :

```bash
python CURRENT_V2_12_3_R10/apply_r10.py
```

Sous Windows, exécute cette commande dans **Git Bash**, car le script utilise l’outil standard `patch`.

Cette commande reconstruit les trois fichiers principaux R10 depuis les sources V2.12.2 et les patches versionnés, contrôle leurs SHA-256, installe à la racine le BAT et les tests R10, puis crée les bases SQLite `REFERENCE_VIDE`. N’audite pas les anciens fichiers V2.12.2 comme s’ils étaient la cible R10.

## Fichiers cibles principaux

- `main_ihm_relais_rp2040_v2_12_3.py`
- `ihm_relais_rp2040_28vdc_precision_v2_12_3.ui`
- `rp2040_relais_28vdc_precision_v2_12_3_ADS1115_GP26_RGB.ino`
- `build_exe_onefile_ihm_relais_rp2040_v2_12_3_R10.bat`
- `SCHEMA_SQLITE_V2_12_3.sql`
- les tests `test_*R10.py` et les tests de non-régression installés à la racine

## Vérifications obligatoires

1. Confirmer que le `.ui` utilisateur est la référence officielle et que ses positions, tailles, espacements, textes et `objectName` sont conservés.
2. Vérifier que le premier onglet affiche : onglet `Production`, titre `Neutral Screen - Cycleur - Mesures`, version `V 2.12.3 R10`.
3. Vérifier que les voyants R1 à R4 et T1 à T4 de l’onglet collage/décollage sont de vrais cercles graphiques de 18 × 18 px, sans caractère de police et sans chevauchement du titre.
4. Vérifier que `MESURER TOUT` utilise uniquement l’alimentation EA, sans demande de passage `EA → FIXE`, avec une tension de chronométrie distincte, mémorisée et figée au début du cycle. GP26 ne doit pas activer la source fixe pendant ce mode.
5. Vérifier que les rampes BE et BR utilisent leurs réglages indépendants : bistable, rampe BE pour l’enclenchement et rampe BR pour le rappel ; monostable, montée BE pour l’enclenchement et descente BE selon le réglage de rappel/décollage.
6. Vérifier la règle `FIRST_PASSAGE` : la première tension complète, son `RAW` et son `T_US` restent figés ; les rebonds servent uniquement à la validation de stabilité et ne remplacent jamais la capture.
7. Vérifier les valeurs globales de remplacement en cas de contacts manquants : `Vmax` pour l’enclenchement, `Vmax` pour le rappel bistable, `0 V` pour le décollage monostable, tout en conservant les tensions individuelles réellement capturées.
8. Vérifier que les exports Excel et PDF contiennent une synthèse globale et un détail des tensions par inverseur, avec les six temps de chronométrie pour 1 à 4 inverseurs.
9. Vérifier la persistance des étalonnages dans `chronometrie_contacts.sqlite3`, table `calibrations_tension_ads1115`, ainsi que la traçabilité de l’étalonnage actif dans les mesures enregistrées.
10. Vérifier que le BAT R10 est en UTF-8 sans BOM et qu’il lance uniquement les tests correspondant à R10.
11. `licence_manager.py` est volontairement absent du dépôt public. Pour exécuter localement l’IHM, créer seulement un stub temporaire non commité. Ne jamais contourner ni supprimer la protection de licence dans le code livré.
12. Classer toute conclusion sur la précision, les timings réels, l’EA, l’ADS1115 ou le RP2040 comme **à vérifier sur matériel**. Le code seul ne démontre pas une précision de ±0,05 V.
13. Vérifier la correspondance complète entre les `objectName` recherchés par le Python et ceux présents dans le `.ui`.
14. Vérifier les séquences d’arrêt de sécurité EA : `OUTP OFF`, consigne à 0 V, lecture de confirmation et gestion des réponses SCPI vides ou tardives.
15. Vérifier l’absence de régression sur les fonctions Neutral Screen, chronométrie, oscilloscope, base SQLite, production, PDF et Excel.
16. Exécuter les tests logiciels disponibles. Signaler distinctement les tests impossibles faute de matériel, de PySide6, de compilateur Arduino ou de fichier privé de licence.
17. Vérifier que les bases `REFERENCE_VIDE` ne peuvent pas écraser les bases utilisateur et que le BAT les range dans `dist\BASES_REFERENCE_VIDES`.

## Forme attendue du rapport

Pour chaque constat : citer le fichier et les lignes précises, classer le constat **certain**, **probable**, **à vérifier sur matériel** ou **non démontré**, expliquer l’impact réel et proposer un correctif concret uniquement lorsqu’il est nécessaire.

Terminer par :

1. erreurs bloquantes ;
2. erreurs importantes ;
3. améliorations mineures ;
4. tests complémentaires ;
5. conclusion **GO / GO sous réserves / NO-GO**.
