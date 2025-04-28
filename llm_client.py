# aut-flexibility-app/llm_client.py  — version for openai‑python ≥ 1.0

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
        Given the object '{object_name}', given this proposed use: '{use_text}'.


1. Identify whether it is a disqualified respons – that is:
   - Nonsensical or irrelevant
   - Simply repeating the object name
   - Not a possible use

2. For the legitimate responses, assign it to the most fitting category
   (e.g., 'construction', 'art', etc.).
   """
    )

    try:
        resp = client.chat.completions.create(      # ← new call style
            model="gpt-3.5-turbo",
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
   - Nonsensical or irrelevant
   - Simply repeating the object name
   - Not a possible use

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
            model="gpt-3.5-turbo",
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
            temperature=0.3,
        )
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print("Evaluation error:", e)
        return {"disqualified": [], "used_categories": []}
