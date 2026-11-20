# Le rôle de Gemma dans le pilote Next-BH

**Gemma choisit les passages du catalogue à citer pour expliquer une recommandation.** FastAPI fournit le produit candidat et Python assemble le brouillon à partir des passages vérifiés. Dans la démonstration locale du 20 novembre 2026, les 24 cas synthétiques ont donné le résultat attendu avec le sélecteur déterministe de la CI. La recette avec le modèle Gemma et la notation humaine restent à réaliser.

## Quel modèle est prévu ?

Gemma 3n E4B est un modèle de langage préentraîné de Google, conçu pour l’exécution locale. E4B désigne la variante à environ quatre milliards de paramètres effectifs. Next-BH utilise le modèle tel qu’il est distribué dans Ollama sous le nom `gemma3n:e4b`. Pour ce pilote, l’entrée et la sortie sont textuelles. [Présentation du modèle par Google](https://developers.googleblog.com/en/introducing-gemma-3n-developer-guide/), [variante distribuée par Ollama](https://ollama.com/library/gemma3n:e4b)

Ollama sert le modèle sur une adresse locale `127.0.0.1`. Avant de lancer la recette, le pilote vérifie dans `/api/tags` que le nom et l’empreinte correspondent à la version attendue. Il consigne l’empreinte et la version d’Ollama pour que les résultats puissent être rattachés au modèle testé. [Configuration du modèle](../scripts/staging_inputs.py#L185), [préparation de la recette](STAGING_SETUP.md)

## De l’opportunité au brouillon

1. **FastAPI sélectionne le candidat.** La route `GET /recommend_pm/` renvoie le profil de l’entreprise synthétique et un produit candidat.
2. **Chroma récupère les passages.** La recherche filtre le catalogue fictif sur le produit exact. Python vérifie que les passages récupérés couvrent tous les besoins déclarés. Un besoin non précisé ou un catalogue insuffisant produit une note interne avant l’appel au modèle.
3. **Gemma choisit les citations.** LangChain lui transmet le produit, le profil, les besoins et les extraits admissibles. Le modèle doit renvoyer un objet JSON contenant les identifiants des passages choisis.
4. **Python contrôle et assemble.** Le code vérifie le format JSON, l’appartenance des identifiants aux extraits proposés, l’absence de doublons et la couverture de chaque besoin. Une sélection invalide produit une note interne. Avec une sélection valide, le brouillon cite les extraits mot pour mot et conserve la révision du catalogue, le document et l’emplacement de chaque source.
5. **Le tableau de bord affiche le brouillon.** Un réviseur peut consulter les sources puis approuver ou rejeter le brouillon. La décision reste interne au pilote, qui a enregistré zéro envoi client lors de l’exécution locale.

[Orchestration du pilote](../scripts/run_staging_recommendations.py), [consigne à Gemma et contrôles Python](../agent/utils/grounded_recommendation.py), [relecture dans le tableau de bord](STAGING_PILOT.md#run-and-review)

### Exemple à montrer dans le tableau de bord

Dans `CLEAR-01`, une entreprise fictive de logistique utilise ses propres utilitaires pour les livraisons. FastAPI propose **Synthetic Fleet Cover**. Le passage `fleet-vehicles` (Flottes 1.1) étaye le besoin déclaré. Une réponse valide du modèle pour ce cas serait `{"source_ids":["fleet-vehicles"]}`. Dans la démo, cette sélection provient du sélecteur de CI. Le brouillon invite à vérifier l’adéquation du produit lors d’un échange. [Cas synthétiques](../scripts/fixtures/wave3-opportunities.json), [catalogue fictif](../scripts/fixtures/wave3-catalog.json)

## Ce que les deux exécutions permettent de vérifier

| Exécution | Ce qu’elle vérifie | État |
| --- | --- | --- |
| Démonstration locale en mode `--ci` | Un sélecteur déterministe fournit les identifiants à la place de Gemma. FastAPI, Chroma, les contrôles Python et l’enregistrement dans MongoDB sont exécutés. Les trois parcours sont visibles dans le tableau de bord. | 24 résultats attendus sur 24 le 20 novembre 2026. Huit recommandations, huit demandes de clarification et huit cas de documentation insuffisante. |
| Recette avec `gemma3n:e4b` | Le même parcours est exécuté avec le modèle local. Pour les cas admissibles, on observe si Gemma renvoie des identifiants valides et choisit des extraits qui couvrent tous les besoins. | À réaliser sur un hôte capable de charger le modèle et d’exécuter le pilote. |
| Revue humaine | Le réviseur évalue l’adéquation du produit ou de l’abstention, la fidélité aux sources et l’utilisabilité de chaque brouillon ou note. | À consigner pour les 24 cas, avec trois totaux distincts sur 48. |

Pour la recette, lancer le pilote avec le catalogue approuvé et l’empreinte du modèle, puis relever le commit, la version d’Ollama, les deux empreintes et le résultat de chaque cas. Dans le tableau de bord, vérifier les citations de `CLEAR-01`, les notes de `AMBIG-01` et `NOFIT-08`, puis la persistance d’une approbation et d’un rejet après actualisation. [Procédure de recette](STAGING_PILOT.md#run-and-review), [grille de revue](STAGING_EVALUATION.md#human-scoring), [preuve CI](https://github.com/naderite/Next-BH/actions/runs/44643141739/attempts/2), [suivi BH-16](https://maiteai.atlassian.net/browse/BH-16)
