import os

import grist_api
from dotenv import load_dotenv
from polars import DataFrame
import polars as pl

load_dotenv()


def get_api(doc_id: str):
    if "GRIST_API_KEY" not in os.environ:
        raise ValueError("provide your `GRIST_API_KEY` in .env")
    return grist_api.GristDocAPI(
        doc_id,
        api_key=os.environ["GRIST_API_KEY"],
        server="https://grist.simone-de-beauvoir.indiehosters.net",
    )


def dump_dataframes(doc_id: str, table: str, data: DataFrame):
    """
    Only normalize the 'topics' column:
    - if topics is a list -> explode
    - if topics is a comma-separated string -> split + explode
    This avoids accidental cartesian duplication when other text columns contain commas.
    """
    api = get_api(doc_id)
    df = data

    if "topics" in df.columns:
        # If topics is a string with commas, split into list
        if df.schema.get("topics") == pl.Utf8:
            if df.select(pl.col("topics").str.contains(",").any()).item():
                df = df.with_columns(
                    pl.col("topics")
                    .str.split(",")
                    .list.eval(pl.element().str.strip_chars())
                    .alias("topics")
                )

        # If topics is a list, explode into one row per topic
        if df.schema.get("topics") == pl.List(pl.Utf8) or str(df.schema.get("topics", "")).startswith("List"):
            df = df.explode("topics")

        # Clean + drop empties + avoid duplicates
        df = (
            df.with_columns(
                pl.col("topics")
                .cast(pl.Utf8, strict=False)
                .str.strip_chars()
                .alias("topics")
            )
            .filter(pl.col("topics").is_not_null() & (pl.col("topics") != ""))
            .unique()
        )

    records = df.to_dicts()

    # Keep your original list encoding (rare now, but harmless)
    for record in records:
        for k in record:
            if isinstance(record[k], list):
                record[k] = ["L"] + record[k]

    api.add_records(table, records)


def setup_grist_tables(doc_id, question_id: int):
    api = get_api(doc_id)

    table_name_answers = f"Answers_{question_id}"
    table_name_topics = f"Topics_{question_id}"
    api.call(
        "tables",
        method="post",
        json_data={
            "tables": [
                {
                    "id": table_name_topics,
                    "columns": [
                        {
                            "id": "description",
                            "fields": {
                                "label": "Label par défaut du thème",
                                "type": "Text",
                            },
                        },
                        {
                            "id": "name",
                            "fields": {
                                "label": "Nom du thème",
                                "description": "(À changer)",
                                "type": "Text",
                            },
                        },
                    ],
                },
            ]
        },
    )

    api.call(
        "tables",
        method="post",
        json_data={
            "tables": [
                {
                    "id": table_name_answers,
                    "columns": [
                        {
                            "id": "answer",
                            "fields": {"label": "Réponse", "type": "Text"},
                        },
                        {
                            "id": "session_token",
                            "fields": {
                                "label": "Id réponse (session token)",
                                "type": "Text",
                            },
                        },
                        {
                            "id": "topics",
                            "fields": {
                                "label": "Thème",
                                "type": f"Ref:{table_name_topics}",
                                "widgetOptions": '{"widget":"Reference"}',
                            },
                        },
                    ],
                }
            ]
        },
    )
    return {"topics": table_name_topics, "answers": table_name_answers}
