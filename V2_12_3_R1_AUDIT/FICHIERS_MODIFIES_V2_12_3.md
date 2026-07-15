# Fichiers modifiés — Neutral Screen V2.12.3

## Révision R1 après essai Windows

Par rapport au premier ZIP V2.12.3 transmis, **un seul fichier de code a changé** :

- `test_securite_ea_plausibilite_v2_12_3.py` : fermeture explicite des connexions SQLite temporaires avec `contextlib.closing`, afin d'éviter `WinError 32` lors de la suppression du dossier temporaire sous Windows.

Le programme principal, le `.ui`, le firmware et les bases de référence sont strictement inchangés dans cette révision R1.

## Fichiers à transmettre en priorité à Claude

### Modifications fonctionnelles

1. `main_ihm_relais_rp2040_v2_12_3.py`
   - logique fermée des réponses SCPI ;
   - surveillance périodique de l’état générateur ;
   - arrêt EA commandé et confirmé ;
   - alerte d’arrêt non confirmé ;
   - limite dynamique de durée de rampe ;
   - contrôle de plausibilité tension/temps ;
   - remise à zéro des verdicts propres à chaque essai ;
   - migrations SQLite et exports ;
   - correction de l'export PDF afin de ne plus tronquer les colonnes au-delà de la neuvième ;
   - suppression du bouton caché `TEST FINI` ;
   - intégration du bouton Production `Recharger base`.

2. `ihm_relais_rp2040_28vdc_precision_v2_12_3.ui`
   - ajout de `pushButton_prod_reload_base` ;
   - titre V2.12.3 ;
   - texte de l’information de rampe mis à jour.

3. `chronometrie_contacts.sqlite3`
   - base vide de référence migrée avec les nouvelles colonnes de plausibilité et d’arrêt EA.

4. `SCHEMA_SQLITE_V2_12_3.sql`
   - schéma complet des deux bases avec les nouvelles colonnes.

5. `test_securite_ea_plausibilite_v2_12_3.py`
   - tests des réponses SCPI vides ;
   - tests de confirmation d’arrêt ;
   - tests des limites dynamiques ;
   - tests de plausibilité et de remise à zéro entre essais ;
   - test de migration V2.12.2 idempotente et d’enregistrement SQLite ;
   - test PDF dense à 14 colonnes.

6. `build_exe_onefile_ihm_relais_rp2040_v2_12_3.bat`
   - noms V2.12.3 et fichiers supplémentaires copiés dans `dist`.

### Fichier de preuve d'exécution

- `FINAL_TEST_OUTPUT_V2_12_3.txt` : sortie brute du dernier passage des tests logiciels. Ce fichier est une trace, pas une preuve matérielle.

### Modifications de version ou de traçabilité, sans changement fonctionnel matériel

7. `rp2040_relais_28vdc_precision_v2_12_3_ADS1115_GP26_RGB.ino`
   - numéro V2.12.3 et trame HELLO `V2_12_3` uniquement ;
   - logique `FIRST_PASSAGE` identique à la V2.12.2.

8. `neutral_scenarios.json`
   - champ `version` passé à `2.12.3` ; scénarios inchangés.

9. `test_capture_premier_passage_v2_12_3.py`
   - noms de fichiers et version adaptés ; logique de test inchangée.

10. Documentation V2.12.3
    - `README_PACK_V2_12_3.md` ;
    - `CHANGELOG_V2_12_3.md` ;
    - `CORRECTION_SECURITE_EA_PLAUSIBILITE_V2_12_3.md` ;
    - `CORRECTION_RAMPES_EA_V2_12_3.md` ;
    - `CORRECTION_CAPTURE_PREMIER_PASSAGE_V2_12_3.md` ;
    - `CAHIER_DES_CHARGES_AUDIT_IA_NEUTRAL_SCREEN_V2_12_3.md` ;
    - `SOFTWARE_TESTS_V2_12_3.txt` ;
    - `VALIDATION_V2_12_3.txt`.

## Fichiers inchangés par rapport au pack précédent

- `licence_manager.py` ;
- `requirements.txt` ;
- `production_essais.sqlite3` : base vide, schéma Production inchangé ;
- `schema_cablage_initial.jpg` ;
- `RP2040-Zero_03.jpg`.

Les documents de câblage et d’étalonnage ont seulement été renommés V2.12.3 et complétés par la mention qu’aucune modification matérielle n’est imposée par cette évolution.
