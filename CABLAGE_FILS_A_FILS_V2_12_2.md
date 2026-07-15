# Câblage fils à fils — Neutral Screen V2.12.2

## 1. Objet de l’évolution

La V2.12.2 ajoute la mesure automatique de la **tension de collage** et de la **tension de décollage** d’un relais monostable de 1 à 4 inverseurs.

La rampe 0 → Vmax ou Vmax → 0 est générée par l’alimentation **EA-PSI 9200-04 T**. Le RP2040 surveille simultanément les contacts et mesure localement la tension réelle avec un **ADS1115**.

Le montage 28/32 V existant reste utilisé pour les essais Neutral Screen. Un sélecteur de source empêche de relier l’alimentation fixe et l’alimentation EA en parallèle.

---

## 2. Composants à ajouter

| Quantité | Composant | Valeur / exigence |
|---:|---|---|
| 1 | Module ADS1115 | 16 bits, I²C, adresse 0x48, alimentation 3,3 V |
| 1 | Résistance RHAUT | 39 kΩ, 0,1 %, 0,25 W minimum |
| 1 | Résistance RBAS | 3,3 kΩ, 0,1 %, 0,25 W minimum |
| 1 | Résistance série ADC | 1 kΩ, 1 % |
| 1 | Condensateur filtre | 10 nF, 50 V minimum |
| 2 | Diodes Schottky de clamp | BAT54 ou équivalent faible capacité |
| 1 | Sélecteur de source | 3 positions **OFF / FIXE / EA**, rupture avant établissement, ≥ 40 Vdc et ≥ 1 A |
| 1 | Fusible sortie EA | 0,5 A maximum conseillé, à adapter au relais et au câblage |

Le module ADS1115 doit être alimenté en **3,3 V**, pas en 5 V, pour conserver des niveaux I²C compatibles avec le RP2040.

---

## 3. Affectation des nouvelles broches RP2040-Zero

| Broche RP2040-Zero | Fonction V2.12.2 | Raccordement |
|---:|---|---|
| GP0 | I²C0 SDA | ADS1115 SDA |
| GP1 | I²C0 SCL | ADS1115 SCL |
| 3V3 | Alimentation logique | ADS1115 VDD |
| GND | Référence logique et puissance | ADS1115 GND et masse commune |

Les broches existantes ne changent pas :

| Broche | Fonction existante |
|---:|---|
| GP14 | MOSFET bobine monostable / BE |
| GP15 | MOSFET BR, inutilisé pendant la mesure monostable collage/décollage |
| GP26 | Sélection fixe 28/32 V, maintenue inactive en mode alimentation EA |
| GP10, GP11, GP6, GP7 | R1, R2, R3, R4 |
| GP12, GP13, GP8, GP9 | T1, T2, T3, T4 |
| GP16 | LED RGB interne WS2812 |

---

## 4. Câblage ADS1115 fils à fils

### 4.1 Liaison I²C

```text
RP2040 3V3  -------------------------- ADS1115 VDD
RP2040 GND  -------------------------- ADS1115 GND
RP2040 GP0  -------------------------- ADS1115 SDA
RP2040 GP1  -------------------------- ADS1115 SCL
ADS1115 ADDR -------------------------- GND       (adresse 0x48)
ADS1115 ALERT/RDY --------------------- non connecté
ADS1115 A1/A2/A3 ---------------------- non connectés
```

La plupart des modules ADS1115 possèdent déjà des résistances de pull-up I²C. Si le module n’en possède pas :

```text
SDA -> 4,7 kΩ -> 3V3
SCL -> 4,7 kΩ -> 3V3
```

Ne pas ajouter de pull-up vers 5 V.

### 4.2 Pont diviseur de tension

Le point mesuré est le **bus positif de bobine après le sélecteur OFF/FIXE/EA**.

```text
BUS + BOBINE
    |
    +---- RHAUT 39 kΩ 0,1 % ----o---- RBAS 3,3 kΩ 0,1 % ---- GND
                                |
                                +---- 1 kΩ ---- ADS1115 A0
                                                 |
                                                 +---- 10 nF ---- GND
```

Rapport nominal :

```text
K = (39 000 + 3 300) / 3 300 = 12,8181818
```

Valeurs obtenues :

| Tension bus bobine | Tension théorique sur A0 |
|---:|---:|
| 30 V | 2,340 V |
| 36 V | 2,808 V |
| 40 V | 3,120 V |

Le logiciel utilise par défaut le facteur **12,818182**.

### 4.3 Clamp de protection A0

```text
D1 BAT54 : anode sur ADS1115 A0, cathode sur 3V3
D2 BAT54 : anode sur GND, cathode sur ADS1115 A0
```

Vérifier la polarité réelle des diodes avant mise sous tension. Les références doubles de type BAT54S n’ont pas toutes le même brochage selon le boîtier ; contrôler la fiche technique du composant réellement monté.

---

## 5. Sélection de source d’alimentation

### 5.1 Sélecteur obligatoire

Installer un sélecteur **OFF / FIXE / EA** à rupture avant établissement.

```text
Sortie du relais de sélection 28/32 V ---- position FIXE du sélecteur
EA + via fusible -------------------------- position EA du sélecteur
Commun du sélecteur ----------------------- BUS + BOBINE
Position OFF ------------------------------ aucune source raccordée
```

Le sélecteur doit empêcher physiquement la mise en parallèle des deux sources.

### 5.2 Masses

```text
EA - --------------------------------------+ 
Alimentation fixe - ------------------------+---- GND PUISSANCE COMMUN
Source MOSFET IRL3705N ---------------------+
RP2040 GND ---------------------------------+
ADS1115 GND --------------------------------+
```

Cette masse commune est nécessaire parce que l’ADS1115 mesure la tension par rapport au GND du RP2040.

### 5.3 Bobine et MOSFET existants

```text
BUS + BOBINE --------------------------- borne + bobine monostable
borne - bobine ------------------------- drain MOSFET GP14
source MOSFET -------------------------- GND puissance
RP2040 GP14 -- 100 Ω ------------------- gate MOSFET
Gate MOSFET -- 100 kΩ ------------------ GND
```

La protection rapide diode + zener existante reste raccordée directement aux bornes de la bobine.

---

## 6. Schéma fonctionnel complet

```text
                    +---------------- Alimentation fixe 28/32 V
                    |
                    |     +----------- EA-PSI + -- fusible
                    |     |
                 [ Sélecteur OFF / FIXE / EA ]
                              |
                              +---------------------- BUS + BOBINE
                              |                           |
                              |                           +---- bobine ---- drain MOSFET
                              |                                           source ---- GND
                              |
                              +-- 39 kΩ --o-- 3,3 kΩ -- GND
                                          |
                                          +-- 1 kΩ -- ADS1115 A0
                                                        |
RP2040 GP0 --------------------------------------------- SDA
RP2040 GP1 --------------------------------------------- SCL
RP2040 3V3 --------------------------------------------- VDD
RP2040 GND --------------------------------------------- GND
```

---

## 7. Contrôles avant la première mesure

1. Mettre le sélecteur sur **OFF**.
2. Vérifier à l’ohmmètre qu’il n’existe aucune continuité entre la sortie positive EA et la sortie positive fixe.
3. Alimenter uniquement le RP2040 et vérifier la détection ADS1115 avec la commande `ADS?`.
4. Appliquer 5 V, 15 V puis 30 V depuis l’EA, sans relais, et comparer la valeur ADS à un multimètre étalonné.
5. Ajuster le rapport diviseur dans l’IHM si nécessaire.
6. Vérifier que GP14 maintient correctement le MOSFET passant pendant toute la rampe.
7. Vérifier que GP15 reste inactif.
8. Vérifier qu’en mode EA, GP26 ne peut pas raccorder la source fixe au bus bobine.
9. Faire un premier essai avec une limite de courant basse et un relais non critique.

---

## 8. Calcul de correction du rapport diviseur

Après une mesure stable avec un multimètre de référence :

```text
nouveau rapport = ancien rapport × tension multimètre / tension affichée ADS
```

Exemple :

```text
ancien rapport = 12,818182
multimètre      = 30,000 V
ADS affiché     = 29,910 V
nouveau rapport = 12,818182 × 30,000 / 29,910 = 12,85675
```

Contrôler ensuite au minimum trois points : 5 V, 15 V et 30 V.

---

## 9. Définition des résultats

Pour un relais monostable à N inverseurs :

### Collage

Pour chaque inverseur `n` :

```text
Rn ouvert ET Tn fermé pendant la durée de validation stable
```

Le résultat global est obtenu lorsque tous les inverseurs actifs satisfont simultanément cet état.

### Décollage

Pour chaque inverseur `n` :

```text
Rn fermé ET Tn ouvert pendant la durée de validation stable
```

Le résultat global est obtenu lorsque tous les inverseurs actifs satisfont simultanément cet état.

La tension enregistrée est celle du **premier passage complet dans la position demandée**. Les rebonds ultérieurs ne remplacent pas cette valeur ; la validation stable confirme seulement que le transfert se termine correctement.

---

## 10. Précision visée

Avec le pont 39 kΩ / 3,3 kΩ et le calibre ADS1115 ±4,096 V :

```text
1 bit ADS = 125 µV sur A0
1 bit ramené au bus bobine ≈ 1,60 mV
```

La précision réelle dépend davantage de l’étalonnage, du bruit, du délai de conversion ADS et de la rampe réelle de l’alimentation.

Objectif de qualification après étalonnage et contrôle matériel :

| Rampe 0 → 30 V | Incertitude pratique visée |
|---:|---:|
| 1 s | environ ±0,08 V |
| 2 s | environ ±0,06 V |
| 3 s | environ ±0,05 V |

Ces valeurs sont des objectifs de conception. Elles doivent être confirmées sur le moyen réel avec un multimètre ou un enregistreur de référence avant d’être utilisées comme incertitudes officielles.

---

# Complément V2.12.2 — étalonnage et relais bistable

L’onglet d’étalonnage ne demande aucun composant supplémentaire par rapport au câblage ADS1115 déjà décrit.

Le même canal A0 mesure le BUS + BOBINES dans les deux cas :

```text
Monostable : GP14/BE uniquement
Bistable 2 bobines : GP14/BE ou GP15/BR, jamais les deux pendant une rampe
```

Le firmware V2.12.2 commande :

```text
COIL_HOLD;BE  -> GP14 actif
COIL_HOLD;BR  -> GP15 actif
COIL_HOLD;OFF -> GP14 et GP15 inactifs
```

Pour l’étalonnage, laisser les bobines déconnectées et raccorder le multimètre de référence entre BUS + BOBINES et GND commun.

---

## V2.12.2 — absence de modification matérielle

La correction de capture au premier passage est entièrement logicielle. Aucun fil, composant, canal ADS1115 ni raccordement EA n'est modifié par rapport à la V2.12.1.
