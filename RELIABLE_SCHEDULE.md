# Reliable daily trigger (external scheduler)

GitHub's built-in `schedule:` cron is "best-effort" and sometimes skips runs
entirely. To make the daily scan fire on time every day, we trigger it from a
free external scheduler (cron-job.org) that calls GitHub's API. Your workflow
already allows this via its `workflow_dispatch` trigger — no code changes needed.

The GitHub `schedule:` lines stay in place as a free backup. If the external
trigger fires first, the scheduled run simply sees today's data and skips.

---

## Step 1 — Create a GitHub access token (so the scheduler is allowed to start the job)

1. On github.com: click your avatar (top-right) → **Settings**.
2. Bottom of the left menu → **Developer settings**.
3. **Personal access tokens → Fine-grained tokens** → **Generate new token**.
4. Fill in:
   - **Token name:** `cron trigger`
   - **Expiration:** 1 year (or your choice — you'll just regenerate it later).
   - **Resource owner:** your own account.
   - **Repository access:** **Only select repositories** → choose **X-Daily-Feed**.
   - **Permissions:** expand **Repository permissions**, find **Actions**, set it to
     **Read and write**. (Metadata → Read-only is added automatically; that's fine.)
5. **Generate token** and **copy it now** (starts with `github_pat_...`). GitHub
   shows it only once. Keep it somewhere safe for the next step.

This token can ONLY start Actions on this one repo, and you can revoke it anytime
from the same page.

---

## Step 2 — Create the scheduled trigger on cron-job.org

1. Sign up free at <https://cron-job.org> and verify your email.
2. **Account settings → Timezone:** set it to **UTC** (so the time below is exact).
3. **Create cronjob** and set:

   - **Title:** `Daily crypto scan`
   - **URL:**
     ```
     https://api.github.com/repos/OWNER/X-Daily-Feed/actions/workflows/daily-scan.yml/dispatches
     ```
     Replace `OWNER` with your GitHub username (the same `owner/name` you put in
     `streamlit_app.py`).
   - **Schedule:** every day at **12:00** (since timezone is UTC).

4. Open the cronjob's **Advanced** settings:

   - **Request method:** `POST`
   - **Headers** (add each as a key / value pair):

     | Key | Value |
     |-----|-------|
     | `Accept` | `application/vnd.github+json` |
     | `Authorization` | `Bearer github_pat_...` (paste your token) |
     | `X-GitHub-Api-Version` | `2022-11-28` |
     | `User-Agent` | `cron-job` |

   - **Request body** (also called "POST data"):
     ```
     {"ref":"main"}
     ```

5. **Save** and make sure the job is **enabled**.

---

## Step 3 — Test it

- On cron-job.org, use **Run now** (or **Test run**).
- A successful call returns HTTP **204** (no content) — that's normal for this API.
- Go to your repo's **Actions** tab: within a few seconds you should see a new
  **Daily crypto news scan** run, triggered manually/by API. It will fetch fresh
  news and update the page.

If you get **401/403**: re-check the `Authorization` header (must be `Bearer ` +
your token) and that the token has **Actions: Read and write** on this repo, and
that the `User-Agent` header is present (GitHub rejects requests without one).

---

## Notes

- Keep the daily scan at ~12:00; if both the external trigger and GitHub's own
  schedule happen to fire, the second one skips automatically (no duplicate work,
  no wasted API credits).
- The keep-awake job is separate and still runs as before.
- When your token expires (in ~1 year) the trigger will start failing — just
  generate a new fine-grained token and update the `Authorization` header.
