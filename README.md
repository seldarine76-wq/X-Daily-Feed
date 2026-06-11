# Crypto Daily Feed

A once-a-day news brief for crypto traders. A scheduled job asks **Grok (xAI)** to
scan **X (Twitter)** and the web for the last 24 hours of crypto, macro, and
geopolitical news, sorts it into categories, tags each story **Bullish / Bearish /
Neutral** for Bitcoin and financial markets, and writes short, read-aloud summaries.
A **Streamlit** page displays it — including a copy/paste script for your YouTube show.

## How it works

```
GitHub Actions (daily 14:00 UTC)
        │  runs fetch_news.py
        ▼
Grok 4.3 + x_search + web_search  ──►  data/news.json  ──(committed to repo)──►  Streamlit app reads & displays
```

- **`fetch_news.py`** — calls the xAI Responses API with the `x_search` and
  `web_search` server-side tools, parses the result into structured JSON.
- **`data/news.json`** — the latest brief (overwritten daily by the Action).
- **`streamlit_app.py`** — reads that JSON and renders the page.
- **`.github/workflows/daily-scan.yml`** — the daily cron job.

Your API key lives **only** as a GitHub secret. It is never deployed to the public
Streamlit page, because Streamlit just reads the committed JSON file.

---

## Setup walkthrough

### 1. Put these files in your GitHub repo

Commit everything in this folder to your repo (keep the structure):

```
.
├── .github/workflows/daily-scan.yml
├── data/news.json
├── fetch_news.py
├── streamlit_app.py
├── requirements.txt
├── .gitignore
└── .env.example
```

### 2. Add your xAI API key as a GitHub secret

In your repo: **Settings → Secrets and variables → Actions → New repository secret**

- **Name:** `XAI_API_KEY`
- **Value:** your `xai-...` key

### 3. Allow the Action to commit back to the repo

**Settings → Actions → General → Workflow permissions** → select
**"Read and write permissions"** → Save. (The workflow also declares
`permissions: contents: write`, but this repo setting must allow it.)

### 4. Run the scan once manually to test

**Actions** tab → **Daily crypto news scan** → **Run workflow**. After a minute,
check that `data/news.json` updated with real stories. From then on it runs
automatically every day at **14:00 UTC**.

> Change the time by editing the `cron` line in `daily-scan.yml`.
> `"0 14 * * *"` = 14:00 UTC. Cron is always UTC.

### 5. Deploy the page on Streamlit

1. Go to <https://share.streamlit.io> → **New app**.
2. Pick this repo/branch, set **Main file path** to `streamlit_app.py`.
3. Deploy. The page reads `data/news.json` straight from the repo — **no secrets
   needed on Streamlit.**

Each time the daily Action commits a new `news.json`, Streamlit redeploys
automatically and the page shows the fresh brief.

---

## Run locally (optional)

```bash
pip install -r requirements.txt

# generate a fresh news.json
export XAI_API_KEY=xai-your-key      # Windows: set XAI_API_KEY=xai-your-key
python fetch_news.py

# view the page
streamlit run streamlit_app.py
```

---

## Customising

| What | Where |
|------|-------|
| Categories | `CATEGORIES` list in `fetch_news.py` |
| Run time | `cron` in `.github/workflows/daily-scan.yml` |
| Stories per category | `MAX_ITEMS_PER_CATEGORY` in `fetch_news.py` |
| Lookback window | `LOOKBACK_DAYS` in `fetch_news.py` |
| Tone / instructions | `build_prompt()` in `fetch_news.py` |
| Restrict to trusted X accounts | add `"allowed_x_handles": ["...", ...]` to the `x_search` tool in `fetch_news.py` |

## Cost

Grok 4.3 is about **$1.25 / 1M input** and **$2.50 / 1M output** tokens, plus a
small per-search fee for the tools. One brief per day is a few cents at most.
New xAI accounts include promotional credits. Check current pricing at
<https://docs.x.ai/developers/pricing>.

## Notes

- Sentiment reflects likely impact on Bitcoin / financial markets. **Not financial advice.**
- Grok occasionally returns fewer stories if a quiet news day; that's expected.
- If a scan fails, the previous `news.json` stays in place, so the page never breaks.
