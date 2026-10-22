# Pronos du jour

Site personnel qui publie chaque matin les paris « value » sur 18 championnats de football européens.

## Comment ça marche
1. **Données** : résultats et cotes de [football-data.co.uk](https://www.football-data.co.uk) (gratuit, sans clé), 3 saisons.
2. **Modèle** : Poisson / Dixon-Coles par championnat : force d'attaque et de défense de chaque équipe, avantage du terrain, matchs récents pondérés plus fort.
3. **Sélection** : probabilité « juste » tirée du consensus des bookmakers (cote moyenne, marge retirée) ; pari retenu quand un bookmaker nommé offre une cote au moins 2 % au-dessus (proba ≥ 25 %, cote ≤ 5). Le modèle de Poisson seul perdait 5 à 13 % en backtest, il sert donc d'analyse (buts attendus, score probable) et d'indice de confiance.
   Résultats (`python research.py`, lancé via l'onglet Actions → « Réglage du modèle ») : environ +4 % par pari sur ~200 paris/an, sur les deux dernières saisons. Échantillon trop petit pour être une preuve.
4. **Mise** : quart de Kelly, plafonnée à 3 % de la bankroll.
5. **Backtest** : la stratégie est rejouée sur les 12 derniers mois (sans regarder le futur) et le résultat est affiché sur la page.

## Lancer en local
```
python build.py            # génère docs/index.html et docs/picks.json
python build.py --no-backtest
```
Aucune dépendance : Python 3.10+ suffit.

## Journal des paris
Chaque pari proposé est enregistré dans `docs/journal.json` (avec la cote du jour), puis réglé automatiquement avec le vrai score : c'est le vrai bilan du site, affiché sur la page.

## Autres sports (The Odds API)
1. Créer une clé gratuite sur https://the-odds-api.com (500 requêtes/mois).
2. Dans le dépôt : Settings → Secrets and variables → Actions → New repository secret, nom `ODDS_API_KEY`.
3. Le site ajoute alors chaque jour jusqu'à 6 compétitions actives (NBA, NHL, NFL, tennis, MLB, MMA…), même stratégie de consensus. Environ 200 à 400 requêtes par mois ; le script s'arrête avant d'épuiser le quota.
Pas de backtest pour ces sports (l'historique des cotes est payant) : seul le journal dira si ça marche.

## Mise en ligne (gratuite)
1. Pousser ce dossier dans un dépôt GitHub.
2. Settings → Pages → « Deploy from a branch » → `main` / `docs`.
3. Le workflow `.github/workflows/daily.yml` régénère la page tous les jours à 6h UTC (lancement manuel possible dans l'onglet Actions).

## Avertissement
Les paris comportent un risque de perte. Aucun modèle ne garantit des gains ; les bookmakers limitent souvent les comptes gagnants.
