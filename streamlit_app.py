"""
streamlit_app.py
================
Reads data/news.json (produced daily by fetch_news.py via GitHub Actions) and
renders a clean, categorised, sentiment-tagged crypto news brief.

Deploy on Streamlit Community Cloud, main file: streamlit_app.py
"""

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

DATA_PATH = Path(__file__).parent / "data" / "news.json"

SENTIMENT_STYLES = {
    "Bullish": {"bg": "#10331f", "fg": "#3ddc84", "border": "#1f7a45", "icon": "▲"},
    "Bearish": {"bg": "#3a1418", "fg": "#ff5c6c", "border": "#8a242e", "icon": "▼"},
    "Neutral": {"bg": "#2a2a2e", "fg": "#c7c7cc", "border": "#4a4a4f", "icon": "■"},
}

st.set_page_config(page_title="Crypto Daily Feed", page_icon="📈", layout="wide")


# --------------------------------------------------------------------------- #
# Styling
# --------------------------------------------------------------------------- #
st.markdown(
    """
    <style>
      .block-container { padding-top: 2rem; max-width: 1000px; }
      .badge {
        display: inline-block; padding: 2px 10px; border-radius: 999px;
        font-size: 0.75rem; font-weight: 700; letter-spacing: 0.03em;
        border: 1px solid; vertical-align: middle;
      }
      .story {
        border: 1px solid #2c2c31; border-radius: 12px; padding: 16px 18px;
        margin-bottom: 14px; background: #16161a;
      }
      .story h4 { margin: 0 0 6px 0; font-size: 1.12rem; line-height: 1.35; }
      .story p  { margin: 6px 0 10px 0; color: #d4d4d8; line-height: 1.55; }
      .impact   { font-size: 0.85rem; color: #9a9aa2; font-style: italic; }
      .src a    { font-size: 0.78rem; color: #6ea8fe; margin-right: 10px; text-decoration: none; }
      .cat-head { margin: 26px 0 10px 0; font-size: 1.35rem; font-weight: 700; }
      .muted    { color: #8a8a92; font-size: 0.85rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def badge(sentiment: str) -> str:
    s = SENTIMENT_STYLES.get(sentiment, SENTIMENT_STYLES["Neutral"])
    return (
        f'<span class="badge" style="background:{s["bg"]};color:{s["fg"]};'
        f'border-color:{s["border"]}">{s["icon"]} {sentiment.upper()}</span>'
    )


def load_data() -> dict | None:
    if not DATA_PATH.exists():
        return None
    try:
        return json.loads(DATA_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None


def human_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc).strftime("%A %d %B %Y, %H:%M UTC")
    except (ValueError, TypeError):
        return iso or "unknown"


# --------------------------------------------------------------------------- #
# Header
# --------------------------------------------------------------------------- #
st.title("📈 Crypto Daily Feed")
st.caption("Crypto · Macro · Geopolitics — scanned daily from X & the web by Grok (xAI)")

data = load_data()

if data is None:
    st.warning(
        "No news yet. The first brief appears after the daily scan runs "
        "(GitHub Actions), or run `python fetch_news.py` locally to generate it."
    )
    st.stop()

# Overall read
left, right = st.columns([3, 1])
with left:
    st.markdown(f"**Today's market read**  {badge(data.get('overall_sentiment', 'Neutral'))}", unsafe_allow_html=True)
    st.write(data.get("overall_summary", ""))
with right:
    st.markdown(
        f"<div class='muted'>Updated<br><b>{human_time(data.get('generated_at',''))}</b>"
        f"<br>Model: {data.get('model','')}</div>",
        unsafe_allow_html=True,
    )

st.divider()

# --------------------------------------------------------------------------- #
# Sidebar filter
# --------------------------------------------------------------------------- #
all_sentiments = ["Bullish", "Bearish", "Neutral"]
chosen = st.sidebar.multiselect("Filter by sentiment", all_sentiments, default=all_sentiments)
st.sidebar.markdown("---")
st.sidebar.caption(
    "Sentiment = likely effect on **Bitcoin / financial markets**. "
    "Not financial advice."
)

# --------------------------------------------------------------------------- #
# Stories by category
# --------------------------------------------------------------------------- #
script_lines: list[str] = []  # for the read-aloud script at the bottom

for cat in data.get("categories", []):
    items = [it for it in cat.get("items", []) if it.get("sentiment", "Neutral") in chosen]
    st.markdown(f"<div class='cat-head'>{cat['name']}</div>", unsafe_allow_html=True)

    if not items:
        st.markdown("<span class='muted'>No stories in this category today.</span>", unsafe_allow_html=True)
        continue

    script_lines.append(f"\n=== {cat['name']} ===")
    for it in items:
        sources_html = " ".join(
            f'<a href="{u}" target="_blank">source {i+1} ↗</a>'
            for i, u in enumerate(it.get("sources", []))
        )
        st.markdown(
            f"""
            <div class="story">
              <h4>{it.get('title','')} &nbsp; {badge(it.get('sentiment','Neutral'))}</h4>
              <p>{it.get('summary','')}</p>
              <div class="impact">Impact: {it.get('impact','—')}</div>
              <div class="src">{sources_html}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        script_lines.append(
            f"[{it.get('sentiment','Neutral')}] {it.get('title','')}. {it.get('summary','')}"
        )

# --------------------------------------------------------------------------- #
# Read-aloud script (copy/paste for the live show)
# --------------------------------------------------------------------------- #
st.divider()
with st.expander("📜 Read-aloud script (copy for the show)"):
    intro = (
        f"Good day everyone, here is your crypto market brief for "
        f"{human_time(data.get('generated_at',''))}. "
        f"Overall the day is looking {data.get('overall_sentiment','neutral').lower()}. "
        f"{data.get('overall_summary','')}"
    )
    st.code(intro + "\n" + "\n".join(script_lines), language="text")
