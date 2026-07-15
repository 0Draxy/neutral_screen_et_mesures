# Neutral Screen V2.12.3 R1 — dossier d’audit

Cette branche part de `main` (V2.12.2) et contient le dossier `V2_12_3_R1_AUDIT` destiné à la vérification contradictoire de la V2.12.3 R1.

Le module `licence_manager.py` est volontairement absent du dépôt public.

## Contenu

- correctifs de la sécurité et de la surveillance de l’alimentation EA ;
- contrôle de plausibilité tension/temps ;
- bornage dynamique des rampes ;
- évolution SQLite ;
- correctif Windows des tests SQLite ;
- différences Python, UI et firmware par rapport à la V2.12.2 ;
- prompt de vérification pour Claude.

Le programme principal étant volumineux, sa différence V2.12.2 → V2.12.3 est découpée dans :

```text
main.patch.part00
main.patch.part01
main.patch.part02
main.patch.part03
```

Pour reconstituer le patch sous Windows PowerShell :

```powershell
Get-Content .\V2_12_3_R1_AUDIT\main.patch.part* -Raw | Set-Content .\main_v2_12_3.patch -NoNewline
```

Sous Linux :

```bash
cat V2_12_3_R1_AUDIT/main.patch.part* > main_v2_12_3.patch
```

Les fichiers `ui.patch` et `firmware.patch` contiennent les différences correspondantes. Les fichiers SQL, BAT et tests sont fournis intégralement.

Le pack ZIP exécutable de référence reste `neutral_screen_v2_12_3_pack_R1_correctif_windows.zip`. Cette branche sert en priorité à l’audit des changements avant essais matériels.
