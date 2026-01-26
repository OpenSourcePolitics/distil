import datetime
import json
import time
from concurrent.futures import ThreadPoolExecutor, wait
from functools import cache
from json.decoder import JSONDecodeError
from os import environ
from pathlib import Path
from typing import Sequence

import numpy as np
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

APIKEY_VAR_NAME = "SCALEWAY_API_KEY"

if APIKEY_VAR_NAME not in environ:
    with open(".env", "a") as f:
        f.write(f"{APIKEY_VAR_NAME}=")
    raise ImportError(f"Please specify `{APIKEY_VAR_NAME} indside .env")
elif environ[APIKEY_VAR_NAME] == "":
    raise ImportError(f"Please specify `{APIKEY_VAR_NAME} indside .env")


EXTRA_HEADERS = {
    "HTTP-Referer": "https://opensourcepolitics.eu",
    "X-Title": "OpenSourcePolitics",
}


class LLM:
    def __init__(
        self,
        embedding_model: str,
        generation_model: str,
        emb_template: str,
        emb_args: dict = {},
        temperature: float = 0.3,
        progress_function=lambda x, **kwargs: x,
        n_threads=5,
        log_path="logs",
    ):
        if "SCALEWAY_PROJECT_ID" in environ:
            project_id = environ["SCALEWAY_PROJECT_ID"]
            base_url = f"https://api.scaleway.ai/{project_id}/v1"
        else:
            base_url = "https://api.scaleway.ai/v1"
        self.client = OpenAI(
            base_url=base_url,
            api_key=environ[APIKEY_VAR_NAME],
        )
        self.emb_model_name = embedding_model
        self.gen_model_name = generation_model
        self.gen_temp = temperature
        self.prompt_args = emb_args
        self.progress_function = progress_function
        self.n_threads = n_threads
        self.emb_dim = self.embed_batch(("",)).shape[1]
        self.log_path = Path(log_path)
        self.log_path.mkdir(exist_ok=True)

    @cache
    def embed_batch(self, inputs: tuple[str]):
        """
        Embed a batch of strings using an embedding model.
        A batch is typically ~100 tweets in size. If the input contains too much text, the API can throw an error.
        The result is cached to avoid recomputing it multiple times in the same session.
        Args:
            input: the texts to embed.
            model_name: the model to use (`provider/model_name`)
        """
        embedding = self.client.embeddings.create(
            extra_headers=EXTRA_HEADERS,
            model=self.emb_model_name,
            input=inputs,
            encoding_format="float",
        )
        return np.array([x.embedding for x in embedding.data], dtype=np.float64)

    def embed(
        self,
        inputs: Sequence[str],
        progress_title="Embedding input text",
    ):
        """
        Embed an arbitrary number of  texts using the provided model.
        Args:
            inputs: the texts to embed
            model_name: the model to use (`provider/model_name`)
            status_function: a function to show progress like `tqdm` of `marimo.status.progress_bar`
            status_function_title: the title to use for the status function
        """
        results = []
        for i_batch in self.progress_function(
            range(0, len(inputs), 100), total=len(inputs), title=progress_title
        ):
            batch = tuple(inputs[i_batch : i_batch + 100])
            mat = self.embed_batch(batch)
            results.append(mat)

        # the embedding model already does the normalization step
        # raw_matrix = preprocessing.normalize(raw_matrix, "l2")
        return np.vstack(results)

    def ask_json_single(self, prompt: str, input: str, log_file=None):
        messages = [
            {
                "role": "system",
                "content": "You are a helpful assistant who only can write JSON output. Follow the format indicated in the <format> tags. Start by the token: {",
            },
            {"role": "user", "content": prompt.format(input=input, **self.prompt_args)},
        ]
        completion = self.client.chat.completions.create(
            extra_headers=EXTRA_HEADERS,
            extra_body={},
            model=self.gen_model_name,
            messages=messages,
            temperature=self.gen_temp,
        )
        out = completion.choices[0].message.content
        assert out is not None
        decoded = None
        try:
            decoded = json.loads(out)
        except JSONDecodeError:
            print(f"LLM returned invalid json. See {self.log_path}/{log_file}")
        if log_file is not None:
            validation_emoji = "🚫" if decoded is None else "✅"
            with open(self.log_path / log_file, "a") as f:
                f.write("\n======= INPUT: =============\n")
                f.write(input)
                f.write(f"\n======= RESPONSE ({validation_emoji}): =====\n")
                f.write(out)
                f.write("\n@@@@@@@@@@@@@@@@@@@@@@@@@@@@@\n")
        return decoded

    def ask_json(
        self, prompt, inputs: Sequence[str], progress_title=None, timeout_warning=2
    ):
        """
        Ask the LLM to process a sequence of inputs and return JSON responses.
        Uses a thread pool to parallelize requests and logs interactions to a file.
        Args:
            prompt: the prompt template to use. The argument `{input}` will be replaced with the input.
            inputs: the list of texts to process
            progress_title: the title to use for the progress function
            timeout_warning: if we need to wait more than this value to get
                a response form the API, print a warning
        """
        json_outputs = []
        logfile = datetime.datetime.now().isoformat() + ".txt"
        with open(self.log_path / logfile, "w") as f:
            f.write("====== PROMPT: =======")
            formated_prompt = prompt.format(input="{input}", **self.prompt_args)
            f.write("\n\t".join(formated_prompt.split("\n")))
            
        for i in self.progress_function(
            range(0, len(inputs), self.n_threads),
            title=progress_title,
            total=len(inputs),
        ):
            with ThreadPoolExecutor(max_workers=self.n_threads) as executor:
                futures = [
                    executor.submit(self.ask_json_single, prompt, text, logfile)
                    for text in inputs[i : i + self.n_threads]
                ]
                done, not_done = wait(futures, timeout=timeout_warning)
                if not_done:
                    print(f"[Warning] API call takes longer than {timeout_warning}s")
                for future in futures:
                    try:
                        result = future.result()
                    except TimeoutError:
                        result = None
                    json_outputs.append(result)

        return json_outputs
