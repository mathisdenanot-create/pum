# Calculateur de Marge PMP — PUM

Application web pour analyser les études devis PMP et calculer les prix de vente avec taux de marge.

## Installation

```bash
pip install -r requirements.txt
```

## Lancement

```bash
python app.py
```

Ouvrir le navigateur sur : http://localhost:5000

## Utilisation

1. Importer un PDF d'étude devis PMP (glisser-déposer ou clic)
2. Saisir le taux de marge à appliquer (ex : 40 %)
3. Cliquer sur **Analyser le PDF**
4. Le tableau affiche pour chaque article :
   - Référence & désignation
   - PMP/DPA et PA FR extraits du PDF
   - **Prix de base** = max(PMP/DPA, PA FR)
   - Taux de marge (modifiable par ligne)
   - Prix de vente HT calculé
   - Marge en €
5. Export CSV disponible

## Formule

```
Prix de vente HT = Prix de base ÷ (1 − taux de marge)
Marge (€)        = Prix de vente − Prix de base
```
