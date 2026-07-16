# Neutral Screen V2.12.3 R10 — pack propre

Cette version reprend obligatoirement le dernier `.ui` utilisateur validé.

## Correction R10

Les huit indicateurs R1 à R4 et T1 à T4 de l’onglet Collage / Décollage ne sont plus des caractères Unicode `●`. Ils sont dessinés comme de vrais ronds CSS de 18 × 18 px, avec un positionnement régulier sous le titre du groupe.

## Construction

Lancer `build_exe_onefile_ihm_relais_rp2040_v2_12_3_R10.bat` après reconstruction et installation des fichiers de support par `CURRENT_V2_12_3_R10/apply_r10.py`.

L’exécutable est créé dans `dist\neutral_screen_v2_12_3_R10.exe`.

Le firmware est inchangé par rapport à la R8/R9. Les bases portant le suffixe `REFERENCE_VIDE` ne doivent jamais remplacer les bases utilisateur.
