"""
streamlit_app.py
================
Reads data/news.json (produced daily by fetch_news.py via GitHub Actions) and
renders a clean, categorised, sentiment-tagged crypto news brief.

Deploy on Streamlit Community Cloud, main file: streamlit_app.py
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
import streamlit as st
import streamlit.components.v1 as components

# --------------------------------------------------------------------------- #
# Data source
# --------------------------------------------------------------------------- #
# To show fresh news within minutes WITHOUT waiting for a Streamlit reboot, the
# app reads news.json straight from GitHub. Set this to your repo "owner/name".
# Leave it as "" to fall back to the local file (updates only on app reboot).
GITHUB_REPO = "seldarine76-wq/X-Daily-Feed"           # 👈 e.g. "jamie/X-Daily-Feed"
GITHUB_BRANCH = "main"

DATA_PATH = Path(__file__).parent / "data" / "news.json"

# How often the open page reloads itself (seconds) and how long fetched data is
# cached. 300s = 5 minutes.
REFRESH_SECONDS = 300

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
      /* Force dark styling regardless of the viewer's browser/OS theme */
      .stApp, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: #0e1117 !important;
      }
      .stApp, .stApp p, .stApp li, .stApp span, [data-testid="stMarkdownContainer"] {
        color: #e6e6e6;
      }
      h1, h2, h3, h4, .cat-head { color: #ffffff !important; }
      [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] * { color: #9a9aa2 !important; }
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
      .summary-card {
        border: 1px solid #2c2c31; border-left: 4px solid #3ddc84;
        background: #14141a; border-radius: 12px; padding: 14px 20px;
        margin: 6px 0 20px 0;
      }
      .summary-title { font-weight: 700; font-size: 1.05rem; margin-bottom: 8px; color: #ffffff; }
      .summary-list  { margin: 0; padding-left: 1.15rem; }
      .summary-list li { margin: 5px 0; line-height: 1.45; color: #e6e6e6; }
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


def _raw_url() -> str | None:
    """GitHub raw URL for news.json, with a per-minute cache-buster to dodge the CDN."""
    if GITHUB_REPO:
        bust = int(time.time() // 60)
        return (
            f"https://raw.githubusercontent.com/{GITHUB_REPO}/{GITHUB_BRANCH}"
            f"/data/news.json?t={bust}"
        )
    return None


@st.cache_data(ttl=REFRESH_SECONDS)
def load_data() -> dict | None:
    # 1) Prefer the live copy on GitHub so the page updates without a reboot.
    url = _raw_url()
    if url:
        try:
            r = requests.get(url, timeout=10)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass  # fall back to the local file below
    # 2) Fall back to the file bundled with the app.
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

# Reload the whole page every REFRESH_SECONDS so an open tab keeps catching new data.
components.html(
    f"<script>setTimeout(() => window.parent.location.reload(), {REFRESH_SECONDS * 1000});</script>",
    height=0,
)

if st.button("🔄 Refresh now"):
    st.cache_data.clear()
    st.rerun()

data = load_data()

if data is None:
    st.warning(
        "No news yet. The first brief appears after the daily scan runs "
        "(GitHub Actions), or run `python fetch_news.py` locally to generate it."
    )
    st.stop()

# Daily summary — quick at-a-glance bullets covering everything below.
key_points = data.get("key_points") or []
if key_points:
    bullets = "".join(f"<li>{p}</li>" for p in key_points)
    st.markdown(
        f"<div class='summary-card'><div class='summary-title'>🗞️ Daily Summary</div>"
        f"<ul class='summary-list'>{bullets}</ul></div>",
        unsafe_allow_html=True,
    )

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
