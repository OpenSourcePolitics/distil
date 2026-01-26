# Mise en place

0. Récupérer le code via github


<details>
    <summary>Vous n'arrivez pas à récupérer le code avec `git` ?</summary>
    Il s'agit le plus souvent d'une erreur d'authentification entre votre ordinateur et github. Demandez à n'importe quel profil technique présent près de vous, il saura vous renseigner. Dans le pire des cas, vous pouvez toujours télécharger le code en .zip, et le décomprésser au bon endroit.
</details>

Lancer la commande `cp .env.example .env` pour copier la structure des variables d'environnement.

1. Récupérer une clé d'authentification pour le service scaleway (`SCW_SECRET_KEY`). C'est cette clé qui permet à l'outil d'utiliser différents types d'IA.

Copier la clé d'API key dans `.env`:
```env
SCALEWAY_API_KEY=...
```


<details>
    <summary>En cas d'erreur ...</summary>
    Si la clé d'API est liée à un projet, il faut spécifier le project_id avec la variable `SCALEWAY_PROJECT_ID=...`
</details>

2. [Optionel] Récupérer une clé d'API grist et l'ajouter dans le même fichier `.env` à la ligne:
```env
GRIST_API_KEY=...
```


3. Installer toutes les dépendances python avec cette commande dans le terminal, à l'emplacement du projet:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh && ~/.local/bin/uv sync --frozen
```

C'est bon !

# Utilisation

Lancer la commande `.venv/bin/marimo edit .` Une application web devrait s'ouvrir. 

Différents outils sont disponibles.

Pour les lancer, il suffit de lancer dans le terminal la commande indiquée. 

Deux outils sont disponibles:

| Fichier | Fonctionnalité |
| --- | --- |
| `app_decidim_import` | importer un questionnaire à partir du format utilisé par décidim |
| `app_distil` | analyser le questionnaire importé |


# FAQ

## Comment traiter un formulaire qui ne vient pas de decidim ?

Si vous voulez importer des données non decidim:
1. Créer un dossier dans "data" pour votre formulaire
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
  
  ## Comment les visualisations sont générées ?
  
  Les visualisations sont générées entièrement en python, sont interactives grace à javascript et sont exportables en HTML.
  
  C'est possible grâce au projet [VEGA](https://vega.github.io/vega/) (et son successeur, "Vega-Lite"). Ce projet définit un standard au format json pour définir des visuels. Un visuel dans le format "Vega" peut alors être utilisé dans le navigateur, peut être transformé en png ou jpg ...
 
 Pour générer les visuels "Vega" en python avec plus de facilité, la librairie [altair](https://altair-viz.github.io/) est utilisée.

Il faut noter que les visualisations avec VEGA ont un coût: elles contiennent toutes les données utilisées (dans le cas de Distil, toutes les opinions) pour pouvoir les afficher dynamiquement.

## Il y a quelque chose d'étrange avec le nombre de réponses

Distil fait la différence entre une "Réponse" et une "Opinion" ( = "Contribution").

Au début du script, chaque **réponse** est découpée en différentes **opinions** **à chaque point final et saut de ligne. En effet, une réponse peut contenir plusieurs informations différentes, qu'on veut mettre dans différentes catégories.

Dans le diagramme et dans le compte-rendu, on utilise le nombre de *réponses* qui apparaissent dans chaque catégorie.

Cela signifie que:
- si vous exportez les données dans Grist, chaque réponse est associée à plusieurs catégories.
- il peut y avoir 70% des répondants qui pensent A, et 60% qui pensent B. Ce n'est pas exclusif.
- si un répondant donne 10 opinions différentes, mais toutes dans la catégorie "A", cela ne sera comptabilisé une seule fois.

## L'application semble bloquée

Si l'application semble bloquée et que rien ne se passe, il y a probablement un bug. Pour voir le bug, il faut lancer l'application avec:

```bash
.venv/bin/marimo edit <le nom du script à lancer ici>
```

Par exemple:
```bash
.venv/bin/marimo edit app_distil.py
```

la commande "edit" lance l'application en tant que script python interactif.
