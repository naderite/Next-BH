# Application habitation Next-BH

Le service FastAPI propose un espace web de suivi de dossiers habitation et une API. LangGraph conserve la révision et le point de reprise de chaque dossier dans SQLite. Le catalogue Chroma contient des passages synthétiques versionnés. La génération cite les extraits sélectionnés par produit. Une approbation déclenche uniquement une réponse simulée. Un refus ou un rejet clôture le dossier.

## Démarrage local avec Python 3.12

Depuis la racine du dépôt sous PowerShell.

```powershell
py -3.12 -m venv .venv-housing
$housingPython = ".venv-housing/Scripts/python.exe"
& $housingPython -m pip install -r mvp/requirements.txt
& $housingPython -m mvp.catalog
& $housingPython -m uvicorn mvp.app:app --host 127.0.0.1 --port 8012 --workers 1
```

Sous Linux ou macOS, créer l’environnement avec `python3.12 -m venv .venv-housing` et utiliser `.venv-housing/bin/python` pour les mêmes commandes. Ouvrir [l’espace de travail](http://127.0.0.1:8012/) ou [la documentation de l’API](http://127.0.0.1:8012/docs).

Créer un dossier, préparer la prochaine action, puis approuver ou rejeter le brouillon. Conserver l’identifiant pour rouvrir le dossier dans un autre navigateur. L’historique conserve les décisions, les passages cités et les résultats simulés. Par défaut les données locales sont sous `data/`. `NEXT_BH_STATE` et `NEXT_BH_EVIDENCE` permettent de choisir la base d’état et le répertoire du catalogue. Exécuter un seul processus pour une base d’état donnée. Le service local utilise un nom de réviseur saisi dans le formulaire.

## P1 · Catalogue

`python -m mvp.catalog` matérialise les entrées de `mvp/catalog.json` dans Chroma et publie un manifeste comprenant la version, le SHA-256 et le nom de la collection. Au démarrage, le service compare la collection et son manifeste au catalogue de la version déployée. La recherche par produit est exacte. Le scénario « Catalogue incomplet » permet de vérifier l’abstention quand le passage requis manque. Une révision approuvée après un changement du catalogue est bloquée si elle cite une ancienne version.

## P2 · Politique entraînée

Le moteur utilise une politique de règles par défaut. Pour utiliser MaskablePPO, installer les dépendances dans le même environnement et entraîner un modèle local. Le simulateur et le service partagent les mêmes actions, masques et transitions.

```powershell
& $housingPython -m pip install torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
& $housingPython -m pip install -r mvp/policy-requirements.txt
& $housingPython -m mvp.train_policy --output data/housing-policy/seed-42.zip --seed 42 --steps 4096
$env:NEXT_BH_POLICY = "data/housing-policy/seed-42.zip"
$env:NEXT_BH_POLICY_SHA256 = (Get-FileHash $env:NEXT_BH_POLICY -Algorithm SHA256).Hash.ToLowerInvariant()
& $housingPython -m uvicorn mvp.app:app --host 127.0.0.1 --port 8012 --workers 1
```

Utiliser uniquement un modèle issu d’un entraînement de confiance. Le service vérifie son empreinte et le contrat d’observation. Chaque décision trace le modèle utilisé et les actions autorisées. Le rapport JSON compare le modèle à une politique de règles et à un choix aléatoire parmi les actions autorisées. Les trois politiques rejouent les mêmes scénarios synthétiques avec des graines d’évaluation distinctes de l’entraînement. Ce premier benchmark mesure ces scénarios et ne permet pas d’estimer des résultats commerciaux réels.

## Vérification

```powershell
& $housingPython -m pip install httpx==0.28.1
& $housingPython -m unittest -v mvp.test_housing
```

Suite du produit dans [BH-20](https://maiteai.atlassian.net/browse/BH-20). Les étapes restantes comprennent le catalogue assureur autorisé, le passage du rédacteur à un LLM évalué, l’évaluation de la politique sur des scénarios plus variés, l’historique des entraînements dans MLflow et le déploiement partagé avec comptes de réviseurs.
