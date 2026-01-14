# Mise en place

0. Récupérer le code via github

<details>
    <summary>Vous n'arrivez pas à récupérer le code avec `git` ?</summary>
    Il s'agit le plus souvent d'une erreur d'authentification entre votre ordinateur et github. Demandez à n'importe quel profil technique présent près de vous, il saura vous renseigner. Dans le pire des cas, vous pouvez toujours télécharger le code en .zip, et le décomprésser au bon endroit.
</details>

1. Récupérer une clé d'authentification pour le service scaleway (`SCW_SECRET_KEY`). C'est cette clé qui permet à l'outil d'utiliser différents types d'IA.

2. Créer un fichier ".env" et y placer ce contenu:
```env
SCALEWAY_API_KEY=...
```

(En remplaçant bien sûr le "..." par le texte de la clée)

<details>
    <summary>En cas d'erreur ...</summary>
    Si la clé d'API est liée à un projet, il faut spécifier le project_id avec la variable `SCALEWAY_PROJECT_ID=...`
</details>

3. [Optionel] Récupérer une clé d'API grist et ajouter dans le même fichier `.env` la ligne:
```env
GRIST_API_KEY=...
```

avec la clé récupérée

4. Installer toutes les dépendances python avec cette commande dans le terminal, à l'emplacement du projet:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh && uv sync --frozen
```

C'est bon !

# Utilisation

Différents outils sont disponibles.

Pour les lancer, il suffit de lancer dans le terminal la commande indiquée. Une application web devrait s'ouvrir. 

Deux outils sont disponibles:

| Commande | Fonctionnalité |
| --- | --- |
| `uv run marimo run app_decidim_import` | importer un questionnaire à partir du format utilisé par décidim |
| `uv run marimo run app_distil` | analyser le questionnaire importé |

<details>
    <summary>Pour les techs</summary>
    La commande `marimo run ...` ouvre le code en tant qu'application.
    Pour ouvrir et voir le contenu du code, remplacer `marimo run` par `marimo edit`
</details>


# FAQ

## Format des données

Si vous voulez importer des données non decidim:
1. Créer un dossier dans "data"
2. Pour chaque question, ajouter un .csv qui contient deux colonnes:
  - une colonne "answer_id" qui contient un identifiant unique pour chaque réponse
  - une colonne dont le nom est le titre de la question, et dont les valeurs sont les différentes réponses.
  
  Par exemple:
  ```csv
  answer_id,Quel est votre pays préféré ?
  009019343012, France
  001829184129, Italie
  ```
  
  ⚠️ Le nom du fichier CSV est important. Il doit être `q_` + identifiant de la question + `.csv`, par exemple `q_123.csv`
