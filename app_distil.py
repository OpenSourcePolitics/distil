import marimo

__generated_with = "0.19.0"
app = marimo.App(width="medium")

with app.setup:
    import json
    from pathlib import Path
    from typing import Literal

    import altair as alt
    import marimo as mo
    import numpy as np
    import polars as pl
    from dendogram import (
        compute_depth,
        compute_hierarchy,
        compute_layout,
        cut_tree,
        dendogram_to_tree,
        to_nested_dict,
    )
    from llm import LLM
    from grist import setup_grist_tables, dump_dataframes
    from sklearn import cluster, decomposition, manifold
    import requests

    CURRENT_DIR = Path(__file__).parent
    DATA_DIR = CURRENT_DIR / "data"
    EXPORT_DIR = CURRENT_DIR / "export"
    EXPORT_DIR.mkdir(exist_ok=True)


@app.cell(hide_code=True)
def _():
    mo.md(rf"""
    # Analyse de sondages

    Ce script a pour but de créer une visualisation interactive à partir de réponses à un sondage.

    Si vous n'avez pas encore importé vos données, commencez par lancer `app_decidim_import.py`

    La documentation technique du script est disponible ici: <https://docs.k8s.osp.cat/docs/b3ddd4e9-61db-457c-9025-66e9b0e8b747/>

    ---
    """)
    return


@app.cell
def _():
    surveys = {path.name: path for path in DATA_DIR.glob("*")}
    dropdown_survey = mo.ui.dropdown(
        surveys, value=list(surveys.keys())[0], label="Choix du sondage à analyser: "
    ) 
    dropdown_survey
    return (dropdown_survey,)


@app.cell
def _(dropdown_survey):
    survey_path = Path(dropdown_survey.value)
    question_files = {
        path.name: path for path in survey_path.glob("*.csv")
    }
    dropdown_files = mo.ui.dropdown(
        question_files,
        value=list(question_files.keys())[0],
        label="choix de la question à analyser: ",
    )
    dropdown_files
    return dropdown_files, survey_path


@app.cell
def _(dropdown_files):
    raw_answers = pl.read_csv(
        dropdown_files.value, schema_overrides={"answer_id": pl.String}
    )
    return (raw_answers,)


@app.cell
def _(dropdown_files, raw_answers, survey_path):
    description_area = mo.ui.text_area(
        value="Ce sondage vise à ......................",
        label="Description du sondage: ",
    )
    question = raw_answers.columns[1]
    question_id = int(dropdown_files.value.stem[2:])
    previous_question_value = None
    if (survey_path / "questions.json").exists():
        questions = pl.read_json(survey_path / "questions.json")
        question = questions.filter(pl.col("Position") == question_id)[
            "Title"
        ].item()
        maybe_previous_question = questions.filter(
            pl.col("Position") == question_id - 1
        ).select("Title")
        previous_question_value = (
            maybe_previous_question.item()
            if len(maybe_previous_question)
            else None
        )
    question_area = mo.ui.text_area(
        value=question, label="Question du sondage à analyser"
    )
    previous_question_area = mo.ui.text_area(
        value=previous_question_value or "",
        label="Question précédente du sondage, si pertinent",
    )
    start_button = mo.ui.run_button(
        label=f"Lancer l'analyse de:  [{dropdown_files.value.name}]",
    )

    mo.vstack(
        [
            description_area,
            question_area,
            previous_question_area,
            mo.md(":warning: contenu à changer en fonction du jeu de données !)"),
            start_button,
        ]
    )
    return (
        description_area,
        previous_question_area,
        question,
        question_id,
        start_button,
    )


@app.function
def split_questions_into_opinions(df, question_column):
    """ """

    chunks = (
        (
            df.select(
                pl.col("answer_id"),
                text=pl.col(question_column)
                .str.replace_all(r"[\.!\n;]", ".")
                .str.split("."),
            )
            .explode("text")
            .with_columns(
                pl.col("text").str.strip_chars(),
                len=pl.col("text").str.strip_chars().str.len_bytes(),
            )
        )
        .filter(pl.col("text").str.len_chars() > 10)
        .with_row_index("id")
    )

    return chunks


@app.cell
def _(description_area, previous_question_area, raw_answers, start_button):
    description = description_area.value.strip()
    previous_question = previous_question_area.value.strip()
    mo.stop(
        not start_button.value,
        mo.md("Cliquer sur le boutton pour lancer l'analyse. :arrow_up: "),
    )
    opinions = split_questions_into_opinions(raw_answers, raw_answers.columns[1])
    return description, opinions, previous_question


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Représentations vectorielles

    Cette partie utilise un petit modèle d'IA (modèle d'embedding) pour créer une représentation mathématique de toutes les opinions.

    Il est nécessaire d'être connécté à internet pour cette partie.
    """)
    return


@app.cell
def _(description, previous_question, question):
    TEMPLATE = """
    {description}

    <previous_question>
    {previous_question}
    </previous_question>
    <question>
    {question}
    </question>

    <answer>
    {text}
    </answer>
    """
    llm = LLM(
        embedding_model="qwen3-embedding-8b",
        #generation_model="llama-3.1-8b-instruct",
        generation_model="mistral-small-3.2-24b-instruct-2506",
        emb_template=TEMPLATE,
        emb_args={
            "description": description,
            "previous_question": previous_question,
            "question": question,
        },
        progress_function=mo.status.progress_bar,
    )
    D = llm.emb_dim
    return D, TEMPLATE, llm


@app.cell
def _(D, llm, opinions):
    PROMPT_REWORD = """
    Voici une opinion tirée d'un sondage:

    <context>
    {description}
    </context>

    <previous_question>
    {previous_question}
    </previous_question>

    <question>
    {question}
    </question>

    <opinion>
    {input}
    </opinion>

    Invente deux opinions:
    - qui expriment clairement la même idée que l'originale
    - avec un style et un niveau de langue différent (de formel à ordinaire)
    - avec une longueur différente

    Répond directement au format json.

    <format>
    {{
        "opinions": ["opinion 1", "opinion 2"]
    }}
    </format>
    """

    opinions_to_reword = opinions.filter(pl.col("len") < 100).sample(100)
    rewordings = llm.ask_json(
        PROMPT_REWORD,
        opinions_to_reword["text"],
        progress_title="Creating rewordings of opinions to calibrate",
        timeout=2
    )
    rewording_data = (
        pl.from_dicts(rewordings)
        .with_columns(opinions_to_reword)
        .explode("opinions")
        .drop_nulls()
    )
    m_original = llm.embed(rewording_data["text"])
    m_reworded = llm.embed(rewording_data["opinions"])
    _pca = decomposition.PCA(20)
    _pca.fit(m_original - m_reworded)
    _s = np.sum(_pca.explained_variance_ratio_)
    proj_reword = np.eye(D) - _pca.components_.T @ _pca.components_
    print(f"explains {_s:.2f} of rewording noise")
    return (proj_reword,)


@app.cell
def _(llm, opinions):
    PROMPT_CHANGE_OPINION = """
    Voici une réponse à un sondage:

    <context>
    {description}
    </context>

    <previous_question>
    {previous_question}
    </previous_question>

    <question>
    {question}
    </question>

    <answer>
    {input}
    </answer>

    Rédige deux opinions:
    - la première allant clairement dans le sens de la réponse
    - la deuxième allant dans le sens opposé


    20 mots maximum, et préserve le style original.

    Répond directement au format json

    <format>
    {{
        "opinion": "",
        "inverse": "",
    }}
    </format>
    """

    opinions_to_inverse = opinions.filter(pl.col("len") < 100).sample(150)
    json_outputs = llm.ask_json(
        PROMPT_CHANGE_OPINION,
        opinions_to_inverse["text"],
        progress_title="Creating inverse opinions to calibrate",
        timeout=2,
    )
    oppositions_data = pl.DataFrame(json_outputs).drop_nulls()
    m_extracted = llm.embed(oppositions_data["opinion"])
    m_inverse = llm.embed(oppositions_data["inverse"])
    return m_extracted, m_inverse


@app.cell
def _(m_extracted, m_inverse, proj_reword):
    pca = decomposition.PCA(15)
    pca.fit((m_extracted - m_inverse) @ proj_reword)
    _s = np.sum(pca.explained_variance_ratio_)
    proj_final = proj_reword @ pca.components_.T @ pca.components_
    print(f"explains {_s:.2f} of variance")
    return (proj_final,)


@app.function
def normalize_l2(X):
    rank = len(X.shape) - 1
    return X / np.linalg.norm(X, axis=rank, keepdims=True)


@app.cell
def _(
    TEMPLATE,
    description,
    llm,
    opinions,
    previous_question,
    proj_final,
    proj_reword,
    question,
):
    inputs = [
        TEMPLATE.format(
            text=text,
            question=question,
            previous_question=previous_question,
            description=description,
        )
        for text in opinions["text"]
    ]
    m_raw = llm.embed(
        inputs,
        progress_title="Creating embeddings for all opinions",
    )
    v0 = llm.embed(
        [
            TEMPLATE.format(
                text="",
                question=question,
                previous_question=previous_question,
                description=description,
            )
        ],
    )[0]

    # if beta is bigger, more focus on conflicts of opinion.
    beta = 1
    m_reword = (m_raw - v0) @ proj_reword

    m_clean = m_reword + beta * m_reword @ proj_final
    median_norm = np.median(np.linalg.norm(m_clean, axis=0))

    m = m_clean / median_norm
    return (m,)


@app.cell
def _(m):
    agg = cluster.AgglomerativeClustering(distance_threshold=0, n_clusters=None)
    agg.fit(m)
    tree = dendogram_to_tree(agg.children_)
    return (tree,)


@app.cell
def _(opinions, tree):
    # contains all pair (id, ancestor) such that group is an ancestor of id.
    ancestry = compute_hierarchy(tree).join(opinions.select("id"), on="id")
    ancestry.schema
    return (ancestry,)


@app.cell
def _(ancestry, m, opinions, raw_answers, tree):
    stat_values = {}
    for (_i,), _g in ancestry.group_by("ancestor"):
        ids = _g["id"]
        mean_topic = m[ids].mean(0)
        mean = m[ids].mean(0)
        stat_values[_i] = {
            "cardinality": _g.join(opinions, on="id")
            .join(raw_answers, on="answer_id")
            .select(pl.col("answer_id").unique().count())
            .item(),
            "mean": mean_topic,
            "spread": np.linalg.norm(m[ids] - mean),
        }

    stats = tree.select(
        pl.col("id"),
        values=pl.col("id").replace_strict(
            stat_values,
            return_dtype=pl.Struct(
                {
                    "cardinality": pl.UInt32,
                    "mean": pl.List(pl.Float32),
                    "spread": pl.Float32,
                }
            ),
        ),
    ).unnest("values")
    return (stats,)


@app.cell
def _(stats, tree):
    threshold = 17
    tree_with_stats = tree.join(stats, on="id")
    # we find all groups that have a small enough spread, but whose parent have a not small enough spread.
    regions = (
        tree_with_stats.join(
            tree_with_stats, left_on="parent", right_on="id", suffix="_parent"
        )
        .filter(pl.col("spread_parent") >= threshold, pl.col("spread") < threshold)
        .select(id=pl.col("id"), region=pl.col("id"))
    )
    n_regions = len(regions)
    print(f"{n_regions} regions")
    mo.stop(n_regions < 7, "🧐 not enough regions. Try with a smaller threshold")
    mo.stop(n_regions > 21, "💣 too many regions. Try with a greater threshold")
    subtrees, taxonomy = cut_tree(tree, regions["region"])
    return n_regions, regions, taxonomy, threshold


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Création des noms de catégories
    """)
    return


@app.cell
def _(m, opinions):
    def find_concepts(indices, threshold=5):
        size_penalty = 1000 / (
            100 + opinions[indices].select(size=pl.col("text").str.len_chars())["size"]
        )

        v = m[indices].mean(0)

        for _ in range(2):
            scores = v.dot(m[indices].T) * size_penalty
            k = int(np.argmax(scores))
            if scores[k] < threshold:
                return
            yield opinions["text"][int(indices[k])]
            v_concept = normalize_l2(m[indices][k])
            v = v - v.dot(v_concept) * v_concept

    def create_friendly_topic_name(ids):
        concepts = list(find_concepts(ids))
        if len(concepts) == 0:
            maybe_concept = next(find_concepts(ids, threshold=0))
            return f"({maybe_concept} ?)"
        return "\n".join(concepts)
    return (create_friendly_topic_name,)


@app.cell
def _(ancestry, create_friendly_topic_name, opinions, stats):
    topics = []
    for (_id,), _data in (
        ancestry.join(opinions, on="id")
        .join(stats, left_on="ancestor", right_on="id")
        .group_by("ancestor")
    ):
        topics.append(
            {
                "id": _id,
                "topic": create_friendly_topic_name(_data["id"]),
            }
        )
    topics = pl.DataFrame(topics)
    return (topics,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Visualisation finale

    (La visualisation est exportée dans le dossier `export`)
    """)
    return


@app.cell
def _():
    def compute_coord_2d(matrix, indices=None, method: Literal["tsne", "pca"] = "tsne"):
        if indices is None:
            indices = range(0, len(matrix))

        if method == "tsne":
            reduction_model = manifold.TSNE(n_components=2, early_exaggeration=20)
        if method == "pca":
            reduction_model = decomposition.PCA(n_components=2)
        coords = reduction_model.fit_transform(matrix[indices])

        return pl.DataFrame(
            {
                "x": coords[:, 0],
                "y": coords[:, 1],
                "id": indices,
            }
        )

    def matrix_to_df(matrix):
        i_idx, j_idx = np.indices(matrix.shape)
        return pl.DataFrame(
            {
                "i": i_idx.flatten(),
                "j": j_idx.flatten(),
                "value": matrix.flatten(),
            }
        )
    return compute_coord_2d, matrix_to_df


@app.cell
def _(
    ancestry,
    compute_coord_2d,
    dropdown_files,
    dropdown_survey,
    m,
    matrix_to_df,
    n_regions,
    opinions,
    question,
    regions,
    stats,
    taxonomy,
    topics,
    tree,
):
    alt.theme.enable("carbong10")

    # Shared data
    layout = compute_layout(taxonomy)
    taxonomy_with_topics = (
        taxonomy.join(topics, on="id")
        .join(tree.select("id", "parent"), on="id")
        .join(regions, on="id", how="left")
        .join(stats, on="id")
        .select(
            pl.col("topic"),
            pl.col("id"),
            pl.col("region"),
            pl.col("cardinality"),
            topic_text=pl.format(
                "{}: {}", pl.col("id"), pl.col("topic").fill_null("")
            ),
            parent=pl.col("parent"),
            is_region=pl.col("region").is_not_null(),
        )
    )

    select = alt.selection_point(fields=["region"])

    tsne_data = compute_coord_2d(m)
    depth = compute_depth(tree)
    opinion_data = (
        tsne_data.join(opinions, on="id")
        .join(ancestry, on="id")
        .rename({"ancestor": "region"})
        .join(taxonomy_with_topics, on="region")
        .join(depth, on="id")
        .with_columns(size=1 / pl.col("depth"))
    )

    chart_cloud = (
        alt.Chart(opinion_data)
        .mark_point(strokeWidth=1)
        .encode(
            alt.X("x", axis=None),
            alt.Y("y", axis=None),
            alt.Tooltip(["text", "topic_text"]),
            alt.Size("size"),
            alt.Shape("region:N"),
            alt.Color("region:N"),
            opacity=alt.condition(select, alt.value(1), alt.value(0.3)),
        )
        .add_params(select)
    )

    # Dendrogram
    tree_data = taxonomy_with_topics.join(layout, on="id")

    paths_data = (
        taxonomy.filter(pl.col("parent").is_not_null())
        .with_columns(k=pl.lit([0, 1]))
        .explode("k")
        .with_columns(j=pl.when(pl.col("k") == 0).then("id").otherwise("parent"))
        .join(layout, left_on="j", right_on="id")
        .join(regions, on="id", how="left")
        .with_columns(is_region=pl.col("region").is_not_null())
    )

    x_max = float(layout["x"].max())
    y_max = float(layout["y"].max())

    chart_categories = alt.layer(
        alt.Chart(paths_data)
        .mark_line(interpolate="step-before", color="black")
        .encode(
            alt.X("x", axis=None, sort="ascending"),
            alt.Y("y", axis=None),
            alt.Detail("id"),
        ),
        alt.Chart(tree_data)
        .mark_point(size=200, strokeWidth=3)
        .encode(
            alt.X("x:Q", axis=None, scale=alt.Scale(domain=[-1, x_max * 2])),
            alt.Y(
                "y:Q",
                scale=alt.Scale(reverse=True, domain=[-0.5, y_max]),
                axis=None,
            ),
            alt.Tooltip(["topic_text:N", "cardinality:Q"]),
            opacity=alt.condition(select, alt.value(1), alt.value(0.3)),
            color="region:N",
            shape=alt.condition(
                alt.datum.is_region, "region:N", alt.value("square")
            ),
        )
        .add_params(select),
        alt.Chart(tree_data)
        .mark_text(dx=15, align="left", lineBreak="\n", baseline="middle")
        .encode(
            alt.X("x"),
            alt.Y("y"),
            text=alt.condition(alt.datum.is_region, "topic_text", alt.value("")),
            opacity=alt.condition(select, alt.value(1), alt.value(0.3)),
        )
        .add_params(select),
    )

    # Heatmap
    topic_data = (
        regions.join(layout, on="id")
        .join(topics, on="id")
        .join(stats, on="id")
        .sort("y")
        .with_row_index("idx")
    )

    X = normalize_l2(np.vstack(topic_data["mean"].to_numpy()))
    heatmap_data = (
        matrix_to_df(1 - X @ X.T)
        .join(
            topic_data.select("idx", "topic", "region"),
            left_on="i",
            right_on="idx",
        )
        .join(
            topic_data.select("idx", "topic", "region"),
            left_on="j",
            right_on="idx",
            suffix="_other",
        )
        .with_columns(
            h=pl.format("{}:{}", pl.col("region"), pl.col("topic")),
            v=pl.format("{}:{}", pl.col("region_other"), pl.col("topic_other")),
        )
    )

    chart_heatmap = (
        alt.Chart(heatmap_data)
        .mark_rect()
        .encode(
            alt.X(
                "h:N",
                sort=alt.EncodingSortField("i"),
                axis=alt.Axis(labelAngle=-45),
            ),
            alt.Y("v:N", sort=alt.EncodingSortField("j")),
            alt.Color("value:Q"),
            alt.Tooltip(["topic", "topic_other", "value"]),
            opacity=alt.condition(select, alt.value(1), alt.value(0.3)),
        )
        .add_params(select)
    )

    # Combine
    result = alt.vconcat(
        alt.vconcat(
            chart_cloud.properties(
                height=600,
                width=800,
                title="Espace des réponses. Cliquer sur un point pour plus de détail",
            ),
            chart_categories.properties(
                height=int(40 * n_regions),
                width=800,
                title="Catégories. Cliquer sur une catégorie pour voir les réponses correspondantes",
            ),
        ).resolve_legend(color="shared", fill="shared"),
        chart_heatmap.properties(
            height=500, width=500, title="Oppositions entre groupes d'opinion"
        ),
    ).properties(title=f"Analyse de la question:    «{question}»")

    result.save(
        EXPORT_DIR
        / f"{dropdown_survey.value.stem}-{dropdown_files.value.stem}.html"
    )
    result
    return (opinion_data,)


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    # Compte rendu et Export
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    Ci dessous, un prompt à copier-coller pour créer un résumé automatiquement par un LLM (Claude, ChatGPT ou autre)
    """)
    return


@app.cell
def _(opinion_data, stats, taxonomy, threshold, topics):
    samples_for_llm = opinion_data.group_by("region").agg(pl.col("text").sample(3))
    taxonomy_info = (
        topics.join(taxonomy, on="id")
        .join(stats, on="id")
        .join(samples_for_llm, left_on="id", right_on="region", how="left")
        .select(
            id="id",
            typical_opinion=pl.when(pl.col("spread") < threshold * 1.5).then("topic"),
            n_answers="cardinality",
            samples="text",
        )
    )

    output_for_llm = json.dumps(
        to_nested_dict(taxonomy, taxonomy_info), ensure_ascii=False
    )
    return (output_for_llm,)


@app.cell
def _(output_for_llm, previous_question, question):
    print(f"""
    Voici le résultat d'une analyse automatique d'un sondage. Créé un rapport structuré, professionnel (évite les emojis), en essayant de respecter la représentativité des opinions.
    Ajoute dans chaque partie des réponses ou extraits de réponse, et indique le nombre de répondants concernées.
    Tu dois évoquer les points de concensus et les points d'opposition.

    Remarques:
    - le champ `typical_opinion` est fourni à titre indicatif. Il peut être trompeur et ne pas refléter l'avis de tout le groupe.
    - Le nombre de répondants peut être inexact à cause d'erreurs de classifications. Arrondis grossièrement.

    <previous_question>
    {previous_question}
    </previous_question>
    <question>
    {question}
    </question>
    <data>
    {output_for_llm}
    </data>
    """)
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Export vers Grist
    """)
    return


@app.cell
def _():
    grist_doc_area = mo.ui.text(label="Grist document_id: ")
    grist_export_button = mo.ui.run_button(label="Exporter les données sur ce document Grist")
    mo.vstack([grist_doc_area, grist_export_button])
    return grist_doc_area, grist_export_button


@app.cell
def _(grist_doc_area, grist_export_button, question_id):
    mo.stop(not grist_export_button.value)
    doc_id = grist_doc_area.value
    table_names = setup_grist_tables(doc_id, question_id=question_id)
    return doc_id, table_names


@app.cell
def _(doc_id, regions, table_names, topics):
    exported_topics = (
        regions.join(topics, on="id")
        .with_row_index("topic_id", offset=1)
        .select(pl.exclude("id"))
    )
    dump_dataframes(
        doc_id,
        table_names["topics"],
        exported_topics.select(description="topic", name="topic"),
    )
    return (exported_topics,)


@app.cell
def _(doc_id, exported_topics, opinion_data, raw_answers, table_names):
    records_answers = (
        exported_topics.join(opinion_data, on="region")
        .join(raw_answers, on="answer_id")
        .group_by(session_token="answer_id", answer=raw_answers.columns[1])
        .agg(topics=pl.col("topic_id").unique())
    )
    dump_dataframes(doc_id, table_names["answers"], records_answers)
    mo.md("export terminé ✅")
    return


@app.cell(hide_code=True)
def _():
    mo.md(r"""
    ## Export manuel

    Vous pouvez exporter un échantillon de chaque catégorie si vous en avez besoin:
    """)
    return


@app.cell
def _(dropdown_region, opinion_data):
    selected_region = opinion_data.filter(
        pl.col("region") == dropdown_region.value
    ).select("answer_id", "text")
    n_sample_range = mo.ui.slider(
        3,
        len(selected_region),
        value=len(selected_region),
        label="Number of samples to export: ",
        debounce=True,
        show_value=True,
    )
    n_sample_range
    return n_sample_range, selected_region


@app.cell
def _(regions, topics):
    region_ids = {
        f"{i}: {t}": i
        for (i, t) in topics.join(regions, on="id").select("id", "topic").iter_rows()
    }
    dropdown_region = mo.ui.dropdown(
        region_ids,
        label="region to export: ",
        searchable=True,
        value=list(region_ids.keys())[0],
    )
    dropdown_region
    return (dropdown_region,)


@app.cell
def _(dropdown_region, n_sample_range, selected_region):
    {
        "topic": dropdown_region.selected_key,
        "samples": selected_region.sample(n_sample_range.value).to_dicts(),
    }
    return


if __name__ == "__main__":
    app.run()
