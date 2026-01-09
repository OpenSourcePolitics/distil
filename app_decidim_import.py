import marimo

__generated_with = "0.19.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    from io import BytesIO
    from pathlib import Path
    import json
    return BytesIO, Path, json, mo, pl


@app.cell
def _(mo):
    file_picker = mo.ui.file(
        filetypes=[".csv"],
        label="Séléctionnez les réponses à un questionnaire décidim"
    )
    file_picker
    return (file_picker,)


@app.cell
def _(BytesIO, file_picker, mo, pl):
    mo.stop(not file_picker.value)
    try:
        df = pl.read_csv(
            BytesIO(file_picker.value[0].contents),
            schema={
                "ID de l'utilisateur": pl.String,
                "Jeton de session": pl.String, 
                "Hachage IP": pl.String,
                "Type de question": pl.String,
                "Titre de la question": pl.String, 
                "Réponse": pl.String, 
                "_1": pl.String,
                "_2": pl.String,
                "_3": pl.String,
                "_4": pl.String,
                "Titre du questionnaire": pl.String, 
                "_5": pl.String,
                "_6": pl.String,
                "Position": pl.Int32, 
                "_7": pl.String,
                "_8": pl.String,
            }
        )
    except Exception as e:
        mo.stop(True, mo.md("Le format du CSV est incorrect."))
    return (df,)


@app.cell
def _(df, mo, pl):
    title = df.select(
        pl.col("Titre du questionnaire")
        .str.replace_all(" ", "_")
        .str.replace_all("\W", "")
        .str.replace_all("_*$", "")
    )[0].item()
    title_textarea = mo.ui.text_area(
        label="Nom du questionnaire pour enregistrement :", value=title
    )
    export_button = mo.ui.run_button(label="Exporter les données")
    mo.vstack([
        title_textarea, 
        export_button
    ])
    return export_button, title_textarea


@app.cell
def _(Path, df, export_button, json, mo, pl, title_textarea):
    mo.stop(not export_button.value)
    path = Path(f"data/{title_textarea.value}")
    path.mkdir(parents=True, exist_ok=True)
    questions = (
        df.select(
            "Position", Type="Type de question", Titre="Titre de la question"
        )
        .unique()
        .sort("Position")
    )
    with open(path / "questions.json", "w") as f:
        json.dump(questions.to_dicts(), f, indent=4, ensure_ascii=False)
    for (p, q_name), data in df.filter(
        pl.col("Type de question").str.ends_with("answer")
    ).group_by("Position", "Titre de la question"):
        print(f"question {p}: {q_name}")
        exported = data.select(
            pl.col("Jeton de session").alias("answer_id"),
            pl.col("Réponse").alias(q_name),
        )
        exported.write_csv(path / f"q_{p}.csv")
    mo.md(f"\nDonnées exportées dans `{path}` ✅")
    return


if __name__ == "__main__":
    app.run()
