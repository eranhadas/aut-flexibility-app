# aut-flexibility-app/llm_client.py  — version for openai python ≥ 1.0

import os
import json
from typing import List, Dict, Any
from openai import OpenAI   # ← new import
from dotenv import load_dotenv
load_dotenv()  # loads .env vars into the environment

# Create one reusable client; picks up OPENAI_API_KEY from the env
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# ---------------------------------------------------------------------------

def map_to_category(use_text: str, object_name: str, cats: str) -> str:
    """Return a single creativity category for one proposed use."""
    prompt = f"""
    You are a creativity evaluator. Your task is to strictly classify proposed uses of objects.

    Given:
    - Object: '{object_name}'
    - Proposed use: '{use_text}'

    Allowed creativity categories for this object are:
    {cats}

    Instructions:
    1. Determine if the proposed use is disqualified. Disqualified means:
       - Nonsensical or irrelevant to the object, mostly curse words or gibberish
       - Simply repeating the object name
       - No one can imagine it as a use (use this very rarely).

    2. If the use is disqualified, reply with exactly: Disqualified

    3. If the use is legitimate but does not fit any category, which should not be so common, reply with exactly: Uncategorized.

    4. If the use is legitimate and fits a creativity category, choose exactly one best-fitting category from the list above and reply with the category name.

    Important:
    - Only reply with a single word or phrase: either 'Disqualified', 'Uncategorized', or one exact category name from the list.
    - Do not explain. Do not add any extra words.
    - The reply must be exact and clean.

    Now, what is your classification?
    """.strip()


    try:
        resp = client.chat.completions.create(      # ← new call style
            model="gpt-4.1-nano",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You categorize uses of objects into creativity related "
                        "categories."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            max_tokens=20,
        )
        return resp.choices[0].message.content.strip()
    except Exception:
        return "Uncategorized"

# ---------------------------------------------------------------------------

def evaluate_responses(
    object_name: str, responses: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """Return {'disqualified': [...], 'used_categories': [...]} for a list of
    responses—same behaviour as the old <1.0 implementation."""
    response_texts = [r["use_text"] for r in responses]

    prompt = f"""
Given the object '{object_name}', you will be shown a list of proposed uses.

1. Identify and return a list of any disqualified responses – those that are:
   - Nonsensical or irrelevant to the object, mostly curse words or gibberish
   - Simply repeating the object name
   - No one can imagine it as a use (use this very rarely).

2. For the legitimate responses, assign each one to the most fitting category
   (e.g., 'construction', 'art', etc.).

3. Return a JSON object with:
   - 'disqualified': [list of disqualified responses]
   - 'used_categories': [list of categories that were assigned to legitimate
     responses]

Responses:
{response_texts}
""".strip()

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert in categorizing creative responses "
                        "and spotting invalid inputs."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0,
            top_p=0
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print("Evaluation error:", e)
        return {"disqualified": [], "used_categories": []}
