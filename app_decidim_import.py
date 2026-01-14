import marimo

__generated_with = "0.19.0"
app = marimo.App(width="medium")


@app.cell
def _():
    import marimo as mo
    import polars as pl
    from io import BytesIO
    from pathlib import Path
    from typing import Literal
    import json
    return BytesIO, Literal, Path, json, mo, pl


@app.cell
def _(mo):
    type_picker = mo.ui.dropdown(
        ["Decidim", "Metabase"],
        label="Importer les données depuis: ",
        value="Decidim",
    )
    type_picker
    return (type_picker,)


@app.cell
def _(mo, type_picker):
    help = None
    if type_picker.value == "Decidim":
        help = mo.md(
            "Depuis le Back-Office decidim, cliquer sur 'exporter les réponses au formulaire au format json'"
        )
    elif type_picker.value == "Metabase":
        help = mo.md(
            "Sélectionnez la base de données Metabase consolidée contenant les réponses. (C'est à dire après DBT, par la table brute). Filtrez par `questionnaire ID` puis exportez en format json"
        )
    file_picker = mo.ui.file(
        filetypes=[".json"],
        label="Séléctionnez les réponses au questionnaire",
    )

    mo.vstack([help, file_picker])
    return (file_picker,)


@app.cell
def _(Literal, Path, json, pl):
    class FormImporter:
        def __init__(self, source_type: Literal["Decidim", "Metabase"]):
            self.source_type = source_type
            self.questions: list[pl.Series] = []
            self.ids = None
            self.title = None

        def read(self, data):
            if self.source_type == "Metabase":
                self.read_metabase(data)
            elif self.source_type == "Decidim":
                self.read_decidim(data)

        def write_to_files(self, path: Path):
            path.mkdir(exist_ok=True)
            question_index = [
                {"Title": q.name, "Position": i, "TextAnswer": q.dtype == pl.String}
                for i, q in enumerate(self.questions, start=1)
            ]
            with open(path / "questions.json", "w") as f:
                json.dump(question_index, f, indent=4, ensure_ascii=False)
            for i, q in enumerate(self.questions, start=1):
                if q.dtype == pl.String:
                    exported = pl.DataFrame({"answer_id": self.ids, q.name: q})
                    exported.write_csv(path / f"q_{i}.csv")

        def read_decidim(self, data):
            raw_df = pl.read_json(data)
            self.ids = raw_df[raw_df.columns[0]]
            for c in raw_df.iter_columns():
                if c.name[0] in "123456789":
                    clean_name = ".".join(c.name.split(".")[1:])
                    self.questions.append(c.rename(clean_name))
                    if c.dtype == pl.Struct:
                        # case where the column is a group of questions. For example:

                        # "3. Votre participation au Budget participatif": {
                        #  "Avez-vous participé aux ateliers ?": ...,
                        #  "Avez-vous déposé une idée sur la plateforme ?": ...,
                        #  "Avez-vous été accompagné pour voter ?": ...
                        # }
                        for c_sub in c.struct.unnest().iter_columns():
                            new_q = c_sub.rename(clean_name + " > " + c_sub.name)
                            self.questions.append(new_q)

        def read_metabase(self, data):
            ...
            # TODO
    return (FormImporter,)


@app.cell
def _(BytesIO, FormImporter, file_picker, mo):
    importer = FormImporter("Decidim")
    bytes = BytesIO(file_picker.value[0].contents)
    importer.read(bytes)
    title_textarea = mo.ui.text_area(
        label="Nom du questionnaire pour enregistrement :", value=importer.title or ""
    )
    export_button = mo.ui.run_button(label="Exporter les données")
    mo.vstack([
        title_textarea, 
        export_button
    ])
    return export_button, importer, title_textarea


@app.cell
def _(Path, export_button, importer, mo, title_textarea):
    mo.stop(not export_button.value)
    path = Path("data") / title_textarea.value
    importer.write_to_files(path=path)
    mo.md(f"\nDonnées exportées dans `{path}` ✅")
    return (path,)


@app.cell
def _(Path, pl, title_textarea):
    pl.read_json(Path("data") / title_textarea.value / "questions.json")
    return


@app.cell
def _():
    #M_SESSION_TOKEN = {"fr": "Jeton de session", "en": "Session Token"}
    #M_ANSWER = {"fr": "Jeton de session", "en": "Session Token"}
    #M_POSITION = {"fr": "Jeton de session", "en": "Session Token"}
    #def read_metabase_format(bytes):
    #    df = pl.read_json(
    #        schema_overrides={
    #            "ID de l'utilisateur": pl.String,
    #            "": pl.String, 
    #            "Hachage IP": pl.String,
    #            "Type de question": pl.String,
    #            "Titre de la question": pl.String, 
    #            "Réponse": pl.String, 
    #            "Titre du questionnaire": pl.String, 
    #            "Position": pl.Int32, 
    #
    #            "Decidim User ID": pl.String,
    #            "": pl.String,
    #            "IP Hash": pl.String,
    #            "Question Type": pl.String, 
    #            "Question Title": pl.String,
    #            "Answer": pl.String,
    #            "Position": pl.String,
    #            "Form Title": pl.String,
    #        }
    #    )
    return


@app.cell
def _(mo, path):
    # mo.stop(not export_button.value)
    # path = Path(f"data/{title_textarea.value}")
    # path.mkdir(parents=True, exist_ok=True)
    # questions = (
    #     df.select(
    #         "Position", Type="Type de question", Titre="Titre de la question"
    #     )
    #     .unique()
    #     .sort("Position")
    # )
    # with open(path / "questions.json", "w") as f:
    #     json.dump(questions.to_dicts(), f, indent=4, ensure_ascii=False)
    # for (p, q_name), data in df.filter(
    #     pl.col("Type de question").str.ends_with("answer")
    # ).group_by("Position", "Titre de la question"):
    #     print(f"question {p}: {q_name}")
    #     exported = data.select(
    #         pl.col("Jeton de session").alias("answer_id"),
    #         pl.col("Réponse").alias(q_name),
    #     )
    #     exported.write_csv(path / f"q_{p}.csv")
    mo.md(f"\nDonnées exportées dans `{path}` ✅")
    return


if __name__ == "__main__":
    app.run()
