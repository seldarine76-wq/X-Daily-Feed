# Beginner Setup Guide — Crypto Daily Feed

Follow these six stages in order. Tick each box as you go.

---

## Stage 1 — Get the code onto GitHub (using GitHub Desktop)

- [ ] Install **GitHub Desktop**: https://desktop.github.com — sign in with your GitHub account.
- [ ] **File → Add local repository** → choose your `X Daily Feed` folder.
- [ ] When it says "not a git repository", click **create a repository** → **Create repository**.
- [ ] Click **Publish repository** (top right). Untick "Keep this code private" if you want the page public → **Publish**.

Your code is now on GitHub, including the `.github` folder that runs the daily schedule.

---

## Stage 2 — Add your xAI API key as a secret

- [ ] On github.com, open your repository.
- [ ] **Settings** (repo's top menu) → **Secrets and variables → Actions**.
- [ ] **New repository secret**.
- [ ] Name: `XAI_API_KEY`  (exactly — capitals and underscore).
- [ ] Secret: paste your `xai-...` key → **Add secret**.

---

## Stage 3 — Let the daily job save its results

- [ ] Repo **Settings → Actions → General**.
- [ ] Under **Workflow permissions**, select **Read and write permissions** → **Save**.

---

## Stage 4 — Run it once to test

- [ ] Click the **Actions** tab.
- [ ] If prompted, click **"I understand my workflows, go ahead and enable them."**
- [ ] Left sidebar: **Daily crypto news scan**.
- [ ] **Run workflow** dropdown → **Run workflow** (green button).
- [ ] Wait 1–2 min, refresh. Green tick ✓ = success.
- [ ] Open `data/news.json` in your repo — you should see real headlines, not "Sample" text.

From now on it runs automatically every day at **14:00 UTC**.

---

## Stage 5 — Deploy the page on Streamlit

- [ ] Go to https://share.streamlit.io → sign in with GitHub (authorize if asked).
- [ ] **Create app → Deploy a public app from GitHub**.
- [ ] Repository: your `X Daily Feed` repo.
- [ ] Branch: `main`.
- [ ] Main file path: `streamlit_app.py`.
- [ ] **Deploy**. You'll get a public link like `your-app.streamlit.app` — bookmark it.

No API key needed on Streamlit — the page only reads the news file.

---

## Stage 6 — Daily use

- The job runs daily at 14:00 UTC and updates the page automatically.
- Open your `.streamlit.app` link each day.
- For your YouTube show, open the **"📜 Read-aloud script"** section at the bottom and copy the text.

---

## Handy extras

| Want to... | Do this |
|------------|---------|
| Run it now (any time) | Repeat Stage 4 (Run workflow) |
| Change the daily time | Edit the `cron` line in `.github/workflows/daily-scan.yml` (UTC) |
| Only trust certain X accounts | Add `"allowed_x_handles": ["handle1","handle2"]` to the `x_search` tool in `fetch_news.py` |

**If a run fails (red ✗):** it's almost always the secret name — check it's exactly `XAI_API_KEY`.

Not financial advice.
