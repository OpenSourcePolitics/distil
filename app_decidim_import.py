import marimo

__generated_with = "0.19.0"
app = marimo.App(width="medium")

with app.setup:
    from typing import Literal


@app.cell
def _():
    import json
    from io import BytesIO
    from pathlib import Path

    import marimo as mo
    import polars as pl
    return BytesIO, Path, json, mo, pl


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
def _(Path, json, pl):
    class FormImporter:
        def __init__(self, source_type: Literal["Decidim", "Metabase"]):
            self.source_type = source_type
            self.questions: list[pl.Series] = []
            self.ids = None
            self.form_title = None
            self._col_answer_id = None
            self._col_form_title = None
            self._col_position = None
            self._col_question_title = None
            self._col_question_type = None
            self._col_answer = None

        def read(self, df):
            if self.source_type == "Metabase":
                self.read_metabase(df)
            elif self.source_type == "Decidim":
                self.read_decidim(df)

        def write_to_files(self, path: Path):
            path.mkdir(exist_ok=True)
            question_index = [
                {
                    "Title": q.name,
                    "Position": i,
                    "TextAnswer": q.dtype == pl.String,
                }
                for i, q in enumerate(self.questions, start=1)
            ]
            with open(path / "questions.json", "w") as f:
                json.dump(question_index, f, indent=4, ensure_ascii=False)
            for i, q in enumerate(self.questions, start=1):
                if q.dtype == pl.String:
                    exported = pl.DataFrame({"answer_id": self.ids, q.name: q})
                    exported.write_csv(path / f"q_{i}.csv")

        def read_decidim(self, raw_df):
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

        def read_metabase(self, raw_df):
            self.form_title = raw_df.select(
                pl.col(self._col_form_title).unique()
            ).item()
            self.ids = raw_df[self._col_answer_id].unique()
            for (q_title, q_type), group in raw_df.sort(self._col_position).group_by(
                self._col_question_title,
                self._col_question_type,
                maintain_order=True,
            ):
                is_open_question = q_type.endswith("answer")
                agg_expr = (
                    pl.col(self._col_answer).item()
                    if is_open_question
                    else self._col_answer
                )
                self.questions.append(
                    self.ids.to_frame()
                    .join(
                        group.group_by(self._col_answer_id).agg(agg_expr),
                        on=self._col_answer_id,
                        how="left",
                    )[self._col_answer]
                    .rename(q_title)
                )
    return (FormImporter,)


@app.cell
def _(BytesIO, FormImporter, file_picker, mo, pl, type_picker):
    mo.stop(len(file_picker.value) == 0)
    bytes = BytesIO(file_picker.value[0].contents)
    df = pl.read_json(bytes, infer_schema_length=1_000_000)

    importer = FormImporter(type_picker.value)

    picker_answer_id = mo.ui.dropdown(
        df.columns, label="session token (or other session id)"
    )
    picker_question_type = mo.ui.dropdown(df.columns, label="question type")
    picker_question_title = mo.ui.dropdown(df.columns, label="question title")
    picker_answer = mo.ui.dropdown(df.columns, label="answer")
    picker_form_title = mo.ui.dropdown(df.columns, label="form title")
    picker_position = mo.ui.dropdown(df.columns, label="position")
    mo.vstack(
        [
            picker_answer_id,
            picker_question_type,
            picker_question_title,
            picker_answer,
            picker_form_title,
            picker_position,
        ]
    ) if type_picker.value == "Metabase" else None
    return (
        df,
        importer,
        picker_answer,
        picker_answer_id,
        picker_form_title,
        picker_position,
        picker_question_title,
        picker_question_type,
    )


@app.cell
def _(
    df,
    importer,
    mo,
    picker_answer,
    picker_answer_id,
    picker_form_title,
    picker_position,
    picker_question_title,
    picker_question_type,
    pl,
    type_picker,
):
    if type_picker.value == "Metabase":
        importer._col_answer_id = picker_answer_id.value
        importer._col_answer = picker_answer.value
        importer._col_form_title = picker_form_title.value
        importer._col_question_type = picker_question_type.value
        importer._col_question_title = picker_question_title.value
        importer._col_position = picker_position.value
        mo.stop(
            any(
                x is None
                for x in [
                    importer._col_answer_id,
                    importer._col_answer,
                    importer._col_form_title,
                    importer._col_question_title,
                    importer._col_question_type,
                    importer._col_position,
                ]
            ),
            output=mo.md("Associer toutes les colonnes pour importer"),
        )

    importer.read(df)
    if importer.form_title is None:
        proposed_title = "mon_super_sondage"
    else:
        proposed_title = (
            pl.Series([importer.form_title]).str.replace_all(r"\W", "_").item()
        )
    title_textarea = mo.ui.text_area(
        label="Nom du questionnaire pour enregistrement :",
        value=proposed_title,
    )
    export_button = mo.ui.run_button(label="Exporter les données")
    mo.vstack([title_textarea, export_button])
    return export_button, title_textarea


@app.cell
def _(Path, export_button, importer, mo, title_textarea):
    mo.stop(not export_button.value)
    path = Path("data") / title_textarea.value
    importer.write_to_files(path=path)
    mo.md(f"\nDonnées exportées dans `{path}` ✅")
    return


@app.cell
def _(Path, pl, title_textarea):
    pl.read_json(Path("data") / title_textarea.value / "questions.json")
    return


if __name__ == "__main__":
    app.run()
