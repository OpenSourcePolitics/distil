import os

import grist_api
from dotenv import load_dotenv
from polars import DataFrame

doc_id = "x63smxa6Gw5uzcgRuxdVqJ"
load_dotenv()


def get_api(doc_id_: str):
    if "GRIST_API_KEY" not in os.environ:
        raise ValueError("provide your `GRIST_API_KEY` in .env")
    return grist_api.GristDocAPI(
        doc_id,
        api_key=os.environ["GRIST_API_KEY"],
        server="https://grist.simone-de-beauvoir.indiehosters.net",
    )


def dump_dataframes(doc_id: str, table: str, data: DataFrame):
    api = get_api(doc_id)
    records = data.to_dicts()
    for record in records:
        for k in record:
            if isinstance(record[k], list):
                # to follow grist format
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
                                "label": "Thèmes",
                                "type": f"RefList:{table_name_topics}",
                                "widgetOptions": '{"widget":"Reference"}',
                            },
                        },
                    ],
                }
            ]
        },
    )
    return {"topics": table_name_topics, "answers": table_name_answers}
