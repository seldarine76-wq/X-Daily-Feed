"""
fetch_news.py
=============
Daily crypto/macro/geopolitics news scanner for crypto traders.

Uses the xAI (Grok) Responses API with the server-side `x_search` and
`web_search` tools to scan X (Twitter) and the web for the last ~24h of news,
then categorises every story and tags it Bullish / Bearish / Neutral for
Bitcoin and financial markets.

Output is written to data/news.json, which the Streamlit app reads.

Run locally:
    export XAI_API_KEY=xai-...        # (Windows: set XAI_API_KEY=...)
    python fetch_news.py

In CI this is run by .github/workflows/daily-scan.yml once per day.
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from openai import OpenAI

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

MODEL = "grok-4.3"  # xAI flagship; see https://docs.x.ai/developers/models
OUTPUT_PATH = Path(__file__).parent / "data" / "news.json"

# Categories you asked for. Edit this list to add/remove sections — the
# Streamlit app renders whatever categories appear in the JSON.
CATEGORIES = [
    "Crypto / Bitcoin",
    "Macro / Economic",
    "Geopolitics / Major News",
]

# How far back to search on X. 1 day = the last 24h of posts.
LOOKBACK_DAYS = 1

# Max items the model should return per category (keeps the show brief).
MAX_ITEMS_PER_CATEGORY = 6


def build_prompt(categories: list[str]) -> str:
    """The instruction sent to Grok."""
    cat_lines = "\n".join(f'      - "{c}"' for c in categories)
    return f"""You are a senior markets analyst preparing a daily news brief for a
crypto trader who hosts a YouTube live show. Today is {datetime.now(timezone.utc):%A, %d %B %Y} (UTC).

TASK
Search X (Twitter) and the web for the most important news from the LAST 24 HOURS
that is relevant to someone trading Bitcoin and crypto. Prioritise high-signal
accounts, official sources, and breaking, market-moving stories. Ignore spam,
low-quality engagement-bait, price-prediction shilling, and giveaways.

Sort every story into exactly one of these categories:
{cat_lines}

For EACH story provide:
  - title: a clear, punchy headline (max ~12 words).
  - summary: 2-4 sentences written to be READ ALOUD on a live show. Plain spoken
    English, no hashtags, no emojis, no "@" handles read literally. Explain why a
    trader should care.
  - sentiment: how this is likely to affect Bitcoin / financial markets, EXACTLY
    one of: "Bullish", "Bearish", or "Neutral".
  - impact: one short clause on the likely market impact (e.g. "Supports risk-on flows").
  - sources: a list of 1-3 source URLs (X post links or article URLs) you used.

Also provide an overall market read for the day:
  - overall_sentiment: "Bullish", "Bearish", or "Neutral".
  - overall_summary: 2-3 spoken sentences summarising the day's tone for crypto.

RULES
- Return AT MOST {MAX_ITEMS_PER_CATEGORY} stories per category, most important first.
- If a category genuinely has no notable news, return an empty items list for it.
- Only include stories you actually found via search; do not invent news or URLs.

OUTPUT
Respond with ONLY a single valid JSON object, no markdown fences, no commentary,
matching exactly this shape:

{{
  "overall_sentiment": "Bullish|Bearish|Neutral",
  "overall_summary": "string",
  "categories": [
    {{
      "name": "one of the category names above",
      "items": [
        {{
          "title": "string",
          "summary": "string",
          "sentiment": "Bullish|Bearish|Neutral",
          "impact": "string",
          "sources": ["https://..."]
        }}
      ]
    }}
  ]
}}
"""


def extract_json(text: str) -> dict:
    """Robustly pull a JSON object out of the model's text output."""
    text = text.strip()
    # Strip ```json ... ``` fences if present.
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: grab everything between the first { and the last }.
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("Could not parse JSON from model output:\n" + text[:2000])


def normalise(data: dict, categories: list[str]) -> dict:
    """Validate / clean the model output and guarantee every category exists."""
    valid_sentiments = {"Bullish", "Bearish", "Neutral"}

    def fix_sentiment(s: str) -> str:
        s = (s or "").strip().capitalize()
        return s if s in valid_sentiments else "Neutral"

    by_name = {c.get("name", "").strip().lower(): c for c in data.get("categories", [])}
    out_categories = []
    for cat in categories:
        src = by_name.get(cat.strip().lower(), {})
        items = []
        for it in src.get("items", []) or []:
            items.append(
                {
                    "title": (it.get("title") or "").strip(),
                    "summary": (it.get("summary") or "").strip(),
                    "sentiment": fix_sentiment(it.get("sentiment")),
                    "impact": (it.get("impact") or "").strip(),
                    "sources": [u for u in (it.get("sources") or []) if u],
                }
            )
        out_categories.append({"name": cat, "items": items})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MODEL,
        "overall_sentiment": fix_sentiment(data.get("overall_sentiment")),
        "overall_summary": (data.get("overall_summary") or "").strip(),
        "categories": out_categories,
    }


def fetch() -> dict:
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        sys.exit("ERROR: XAI_API_KEY environment variable is not set.")

    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")

    from_date = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime(
        "%Y-%m-%d"
    )

    print(f"Calling {MODEL} with x_search (from {from_date}) + web_search ...")
    response = client.responses.create(
        model=MODEL,
        input=[{"role": "user", "content": build_prompt(CATEGORIES)}],
        tools=[
            {"type": "x_search", "from_date": from_date},
            {"type": "web_search"},
        ],
    )

    raw = response.output_text
    print(f"Received {len(raw)} chars from model. Parsing JSON ...")
    parsed = extract_json(raw)
    return normalise(parsed, CATEGORIES)


def main() -> None:
    data = fetch()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    total = sum(len(c["items"]) for c in data["categories"])
    print(f"Wrote {total} stories across {len(data['categories'])} categories -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
