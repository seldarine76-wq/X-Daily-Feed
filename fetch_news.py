"""
fetch_news.py
=============
Daily crypto/macro/geopolitics news scanner for crypto traders.

Uses the xAI (Grok) Responses API with the server-side `x_search` and
`web_search` tools to scan X (Twitter) and the web for the last ~24h of news,
then categorises every story and tags it Bullish / Bearish / Neutral for
Bitcoin and financial markets.

It runs ONE dedicated search per category so every section (crypto, macro,
geopolitics) always gets its own search pass and reliably gets populated.

Output is written to data/news.json, which the Streamlit app reads.

Run locally:
    export XAI_API_KEY=xai-...        # (Windows: set XAI_API_KEY=...)
    python fetch_news.py
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

# Each category gets its own search pass. The "guidance" tells Grok exactly what
# to hunt for in that section. Edit/add/remove freely — the Streamlit app renders
# whatever categories end up in the JSON.
CATEGORY_GUIDANCE: dict[str, str] = {
    "Crypto / Bitcoin": (
        "Bitcoin and major crypto. Look for price-moving news: spot ETF flows, "
        "SEC/regulatory actions, exchange or stablecoin news, protocol upgrades, "
        "large liquidations, on-chain or whale moves, and notable institutional "
        "buys/sells."
    ),
    "Macro / Economic": (
        "Market-moving macro and economics. ALWAYS surface any scheduled US economic "
        "data released today or due today (CPI, PPI, PCE, NFP/jobs, GDP, retail "
        "sales, ISM). Also cover Federal Reserve and major central-bank decisions or "
        "speeches, interest rates, bond yields, and the US dollar (DXY). There is "
        "almost always a relevant macro story on any given trading day."
    ),
    "Geopolitics / Major News": (
        "Major world events that move risk assets. Look for wars and military "
        "escalations, elections and major political shifts, sanctions, tariffs and "
        "trade disputes, energy/oil shocks, and any black-swan headlines. There is "
        "almost always at least one market-relevant geopolitical story each day."
    ),
}
CATEGORIES = list(CATEGORY_GUIDANCE.keys())

LOOKBACK_DAYS = 1            # how far back x_search looks (1 = last 24h)
MAX_ITEMS_PER_CATEGORY = 6   # most-important-first cap per section
MAX_RETRIES = 2             # retry a category search this many times on failure

# To restrict X results to handles you trust, uncomment and fill this list (max 20).
# It is applied to every category search.
ALLOWED_X_HANDLES: list[str] | None = None
# ALLOWED_X_HANDLES = ["WatcherGuru", "DeItaone", "FirstSquawk", "unusual_whales"]


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
VALID_SENTIMENTS = {"Bullish", "Bearish", "Neutral"}


def extract_json(text: str):
    """Robustly pull a JSON value (object or array) out of model text output."""
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fallback: grab the widest {...} or [...] span.
    candidates = []
    for open_c, close_c in (("{", "}"), ("[", "]")):
        s, e = text.find(open_c), text.rfind(close_c)
        if s != -1 and e != -1 and e > s:
            candidates.append(text[s : e + 1])
    for c in sorted(candidates, key=len, reverse=True):
        try:
            return json.loads(c)
        except json.JSONDecodeError:
            continue
    raise ValueError("Could not parse JSON from model output:\n" + text[:2000])


def fix_sentiment(s) -> str:
    s = (s or "").strip().capitalize()
    return s if s in VALID_SENTIMENTS else "Neutral"


def clean_items(raw_items) -> list[dict]:
    items = []
    for it in (raw_items or [])[:MAX_ITEMS_PER_CATEGORY]:
        if not isinstance(it, dict):
            continue
        title = (it.get("title") or "").strip()
        if not title:
            continue
        items.append(
            {
                "title": title,
                "summary": (it.get("summary") or "").strip(),
                "sentiment": fix_sentiment(it.get("sentiment")),
                "impact": (it.get("impact") or "").strip(),
                "sources": [u for u in (it.get("sources") or []) if u],
            }
        )
    return items


# Shared rules so sentiment reflects the LIKELY FORWARD move, not recent momentum.
SENTIMENT_RULES = """How to assign sentiment (likely FORWARD effect on Bitcoin / financial markets):
- Judge the probable NEXT move, not what price has already done. Do NOT mark
  something Bearish just because price recently fell, or Bullish just because it rose.
- Price at or testing a SUPPORT or RESISTANCE level is NEUTRAL until it resolves:
  a confirmed hold or bounce off support is Bullish; a confirmed break below is
  Bearish (and the reverse at resistance).
- Oversold, capitulation, or washed-out conditions are often Neutral-to-Bullish.
- Use Bullish or Bearish only for a clear directional catalyst or a confirmed
  technical move. When the outcome hinges on an unresolved level or an upcoming
  event, use Neutral."""


def build_category_prompt(category: str, guidance: str) -> str:
    today = datetime.now(timezone.utc)
    return f"""You are a senior markets analyst building the "{category}" section of a daily
news brief for a crypto trader who hosts a YouTube live show.
Today is {today:%A, %d %B %Y} (UTC).

Search X (Twitter) AND the web for the most IMPORTANT and most-discussed news from
the LAST 24 HOURS that fits this section:

  {guidance}

Return the top {MAX_ITEMS_PER_CATEGORY} stories, most important first. Only return
fewer if there genuinely is less news. Do NOT pad with trivia, price-prediction
shilling, giveaways, or engagement-bait. Only include stories you actually found
via search — never invent news or URLs.

For each story give:
  - title: a clear, punchy headline (max ~12 words).
  - summary: 2-4 sentences written to be READ ALOUD on a live show. Plain spoken
    English, no hashtags, no emojis, no "@" handles. Say why a trader should care.
  - sentiment: EXACTLY one of "Bullish", "Bearish", or "Neutral", following the rules below.
  - impact: one short clause on the likely market impact.
  - sources: a list of 1-3 source URLs you used.

{SENTIMENT_RULES}

Respond with ONLY a JSON array (no markdown fences, no commentary), shaped exactly:
[
  {{"title": "...", "summary": "...", "sentiment": "Bullish|Bearish|Neutral",
    "impact": "...", "sources": ["https://..."]}}
]
If there is truly no relevant news, return [].
"""


def x_search_tool(from_date: str) -> dict:
    tool = {"type": "x_search", "from_date": from_date}
    if ALLOWED_X_HANDLES:
        tool["allowed_x_handles"] = ALLOWED_X_HANDLES[:20]
    return tool


def fetch_category(client: OpenAI, category: str, guidance: str, from_date: str) -> list[dict]:
    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            print(f"  [{category}] search attempt {attempt} ...")
            response = client.responses.create(
                model=MODEL,
                input=[{"role": "user", "content": build_category_prompt(category, guidance)}],
                tools=[x_search_tool(from_date), {"type": "web_search"}],
            )
            items = clean_items(extract_json(response.output_text))
            print(f"  [{category}] found {len(items)} stories.")
            return items
        except Exception as e:  # noqa: BLE001 - we want to retry on any failure
            last_err = e
            print(f"  [{category}] attempt {attempt} failed: {e}")
    print(f"  [{category}] giving up after {MAX_RETRIES} attempts ({last_err}).")
    return []


def synthesize_overall(client: OpenAI, categories: list[dict]) -> dict:
    """Write the 'market read', a bullet summary, and overall sentiment (no search)."""
    headlines = []
    titles = []
    sentiments = []
    for cat in categories:
        for it in cat["items"]:
            headlines.append(f"- ({it['sentiment']}) [{cat['name']}] {it['title']}")
            titles.append(it["title"])
            sentiments.append(it["sentiment"])

    # Heuristic fallbacks if the model call fails.
    bull, bear = sentiments.count("Bullish"), sentiments.count("Bearish")
    fallback_sent = "Bullish" if bull > bear else "Bearish" if bear > bull else "Neutral"
    fallback_points = titles[:5]

    if not headlines:
        return {"overall_sentiment": "Neutral", "overall_summary": "", "key_points": []}

    prompt = (
        "Here are today's market headlines for a crypto trader:\n"
        + "\n".join(headlines)
        + "\n\n"
        + SENTIMENT_RULES
        + "\n\nWrite a daily market read. Respond with ONLY JSON matching:\n"
        '{"overall_sentiment": "Bullish|Bearish|Neutral", '
        '"overall_summary": "2-3 spoken sentences summarising the day\'s tone for crypto, to be read aloud", '
        '"key_points": ["3 to 5 very short bullet points, max ~12 words each, '
        'covering the most important takeaways across all categories"]}'
    )
    try:
        resp = client.responses.create(model=MODEL, input=[{"role": "user", "content": prompt}])
        data = extract_json(resp.output_text)
        points = [str(p).strip() for p in (data.get("key_points") or []) if str(p).strip()][:5]
        return {
            "overall_sentiment": fix_sentiment(data.get("overall_sentiment")) or fallback_sent,
            "overall_summary": (data.get("overall_summary") or "").strip(),
            "key_points": points or fallback_points,
        }
    except Exception as e:  # noqa: BLE001
        print(f"  [overall] synthesis failed, using heuristic: {e}")
        return {"overall_sentiment": fallback_sent, "overall_summary": "", "key_points": fallback_points}


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def build() -> dict:
    api_key = os.getenv("XAI_API_KEY")
    if not api_key:
        sys.exit("ERROR: XAI_API_KEY environment variable is not set.")

    client = OpenAI(api_key=api_key, base_url="https://api.x.ai/v1")
    from_date = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%d")

    print(f"Scanning {len(CATEGORIES)} categories with x_search (from {from_date}) + web_search ...")
    categories = []
    for name, guidance in CATEGORY_GUIDANCE.items():
        categories.append({"name": name, "items": fetch_category(client, name, guidance, from_date)})

    overall = synthesize_overall(client, categories)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "model": MODEL,
        "overall_sentiment": overall["overall_sentiment"],
        "overall_summary": overall["overall_summary"],
        "key_points": overall.get("key_points", []),
        "categories": categories,
    }


def already_updated_today() -> bool:
    """True if news.json already holds a brief generated today (UTC)."""
    if not OUTPUT_PATH.exists():
        return False
    try:
        existing = json.loads(OUTPUT_PATH.read_text(encoding="utf-8"))
        stamp = (existing.get("generated_at") or "")[:10]
        return stamp == datetime.now(timezone.utc).strftime("%Y-%m-%d")
    except (json.JSONDecodeError, OSError):
        return False


def main() -> None:
    force = os.getenv("FORCE", "").lower() in ("1", "true", "yes")
    if not force and already_updated_today():
        print("news.json already updated today — skipping (set FORCE=1 to override).")
        return
    data = build()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    total = sum(len(c["items"]) for c in data["categories"])
    print(f"Wrote {total} stories across {len(data['categories'])} categories -> {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
