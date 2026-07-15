# Correctif du test SQLite sous Windows — V2.12.3

## Symptôme

Le BAT s'arrêtait pendant `test_securite_ea_plausibilite_v2_12_3.py` avec :

```text
PermissionError: [WinError 32] ... chronometrie_contacts.sqlite3
```

## Cause

Dans la bibliothèque standard Python, le bloc :

```python
with sqlite3.connect(db) as con:
    ...
```

valide ou annule la transaction à la sortie du bloc, mais **ne ferme pas la connexion SQLite**.

Le test tentait ensuite de supprimer immédiatement le dossier temporaire alors que Windows conservait encore le fichier SQLite ouvert. Linux autorise généralement la suppression d'un fichier encore ouvert, ce qui avait masqué ce défaut du test.

## Correction

Les trois connexions temporaires du test utilisent désormais :

```python
from contextlib import closing

with closing(sqlite3.connect(db)) as con:
    ...
```

La connexion est donc fermée avant la suppression du dossier temporaire.

## Portée

- aucun changement du programme principal ;
- aucun changement du firmware ;
- aucun changement du fichier `.ui` ;
- aucun changement des bases de référence ;
- seul le script de test Windows a été corrigé.

L'avertissement Qt `QFontDatabase: Cannot find font directory` n'est pas la cause de l'arrêt. Il est non bloquant pendant le test hors écran.
