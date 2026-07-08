# OhioRoadWatch

A weekend-build portfolio project: an agentic AI system that watches live Ohio
highway conditions using ODOT's official OHGO public API — camera snapshots
classified by an NVIDIA NIM-hosted vision-language model, incidents indexed
for semantic search, a LangGraph agent you can ask questions, and a simple
hazard-alert checker.

Built against the real OHGO Public API schema (publicapi.ohgo.com/docs), not
a scrape of the map site. Runs entirely on free tiers: OHGO's public API and
NVIDIA NIM's hosted inference (build.nvidia.com), no credit card needed for
either.

## Architecture

```
OHGO API (cameras + incidents)
        |
   ingest.py            -- polls the API, stores rows + snapshot images in SQLite
        |
  classify.py            -- NVIDIA NIM vision model labels each snapshot (clear/wet/snow/fog/etc.)
        |
 vector_store.py          -- embeds incidents + camera conditions into a local Chroma index
        |            \
   agent.py           alerts.py
 (LangGraph +      (checks watch-listed
  ChatNVIDIA tools,  routes for hazards,
  Q&A over the      logs/prints alerts)
  live data)
        |
 dashboard.py (Streamlit: camera grid + chat)

run_pipeline.py ties ingest -> classify -> index -> alerts into one loop
```

## What you need (and what it costs)

Everything below runs on your own machine — no cloud account, no hosted
database, nothing else to provision.

| Piece | Cost |
| --- | --- |
| OHGO public API | Free (registration only) |
| SQLite (`db.py`) | Free — local file |
| Chroma (`vector_store.py`) | Free — local, no server |
| Streamlit (`dashboard.py`) | Free — runs locally |
| NVIDIA NIM (`classify.py`, `agent.py`) | **Free** — no credit card, ~40 requests/minute shared rate limit |

With NVIDIA NIM this project has **no recurring API cost** at all, even left
running continuously. The one real constraint is the shared ~40 req/min rate
limit across your key — `ingest.py` paces classify calls (`CLASSIFY_DELAY_SECONDS`,
default 1.6s) to stay under it. If you add more cameras or a shorter poll
interval and start seeing 429 errors, raise that delay or reduce camera count
per poll.

Two things worth knowing about the free tier:
- NVIDIA's terms position it for development/testing/evaluation, not
  guaranteed production SLAs — fine for a portfolio/demo project.
- The specific free-tier model catalog can change over time; if
  `meta/llama-3.2-11b-vision-instruct` or `meta/llama-3.1-70b-instruct` ever
  get deprecated, swap the model name in `.env` (`NIM_VISION_MODEL` /
  `NIM_AGENT_MODEL`) — everything else stays the same.

A VPS (~$5-6/month) is only needed if you want a public link instead of a
localhost demo — not required to build or demo this project.

## Setup (do this first)

1. **Get an OHGO API key** (free, ~2 minutes): register at
   https://publicapi.ohgo.com/accounts/registration, then grab your key from
   your account page. This is ODOT's own developer portal — separate from the
   ohgo.com map site.
2. **Get an NVIDIA NIM API key** (free, no credit card, ~2 minutes): sign up
   at https://build.nvidia.com, then generate a key (prefixed `nvapi-`) from
   your profile menu.
3. Copy `.env.example` to `.env` and fill in both keys.
4. Install dependencies:
   ```bash
   python -m venv venv && source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```
5. Sanity-check the API connections:
   ```bash
   python -c "from ohgo_client import OhgoClient; c = OhgoClient(); print(len(c.get_cameras(region='akron')), 'cameras found near Akron')"
   python -c "from classify import classify_image_bytes; import requests; img = requests.get('https://upload.wikimedia.org/wikipedia/commons/thumb/d/dd/Gfp-wisconsin-madison-the-nature-boardwalk.jpg/2560px-Gfp-wisconsin-madison-the-nature-boardwalk.jpg').content; print(classify_image_bytes(img))"
   ```

## Alerts & notifications

`alerts.py` checks your watch-listed routes/keywords (`WATCH_ROUTES` in
`.env`) against the latest camera classifications and current incidents, and
fires a **desktop notification** (via `plyer`) that includes the road name
and direction, e.g.:

> ⚠️ Road hazard
> I-76 Eastbound near Kent — snow, low visibility

A few behaviors worth knowing:

- **Notifies once per event, not every poll cycle.** Each hazard/incident is
  tracked by an id, so an ongoing snow condition or open incident won't spam
  you every 5 minutes — you're notified when it starts, and again if it
  clears and something new appears.
- **Cleared incidents drop out automatically.** OHGO's incidents endpoint
  reflects live state, so anything no longer returned by the API is treated
  as resolved and removed from the local database.
- **Everything is also logged** to `data/alerts.log`, regardless of whether
  you've already been notified — so you still get a full written history.
- **Platform notes:** desktop notifications work out of the box on Windows
  and macOS. On Linux, `plyer` needs a notification daemon (`notify-send`)
  available — if notifications silently don't appear, check that's installed;
  everything else (log file, console output) still works either way.

If you later want alerts even when you're away from the machine (not just a
desktop popup), swap `send_desktop_notification()` in `alerts.py` for a Slack
webhook or email call — the dedup logic and message content stay the same.

## Weekend build plan

**Day 1 — data + vision**
- Morning: confirm `ohgo_client.py` pulls cameras/incidents for your region
  (defaults to `akron`, since you're in Kent — swap `OHGO_REGION` or set
  `OHGO_RADIUS="41.1537,-81.3579,20"` in `.env` to widen/narrow it).
- Afternoon: run `python ingest.py` a few times, watch `data/roadwatch.db`
  and `data/images/` fill up. Tune `classify.py`'s prompt/labels if the
  classifications look off for your cameras (night-time shots, PTZ cameras,
  etc. can be noisy).

**Day 2 — agent, search, dashboard**
- Morning: run `python vector_store.py` (add a small `if __name__` block, or
  call `index_incidents()` / `index_camera_conditions()` from a shell) to
  confirm indexing works, then try `python agent.py` and ask it a few
  questions.
- Afternoon: `streamlit run dashboard.py` for the live camera grid + chat UI.
  Wire up `run_pipeline.py` as a background loop (`python run_pipeline.py`)
  so the dashboard has fresh data while you demo it.
- Wrap-up: write a short README section (or a LinkedIn/portfolio post) on
  what it does, and capture a GIF of the dashboard for your portfolio.

## Stretch goals (if you have more time later)

- Distill `classify.py`'s VLM labels into a tiny supervised CNN and export it
  to ONNX — a nice callback to your NeuroGolf small-model work, and it turns
  a per-image API call into a sub-millisecond local inference.
- Add the `weather-sensor-sites` endpoint (RWIS road sensors — surface temp,
  visibility, precipitation) as another agent tool for a fuller picture than
  cameras alone.
- Swap the console/log alert in `alerts.py` for a real notification channel
  (Slack webhook, email) once you're comfortable with the core loop.
- Deploy `run_pipeline.py` + `dashboard.py` to a small always-on box (or a
  free-tier cloud VM) so it's a live demo link, not just local.

## Notes on the API

- Auth: send your key as `Authorization: APIKEY <key>` (handled in
  `ohgo_client.py`).
- Region filter accepts: akron, cincinnati, cleveland, columbus, dayton,
  toledo, central-ohio, ne-ohio, nw-ohio, se-ohio, sw-ohio.
- Camera snapshot images refresh every ~5 seconds server-side; polling every
  5 minutes (default `POLL_INTERVAL_SECONDS`) is plenty for a conditions
  monitor and keeps you well within any rate limits.
- ODOT's rolling video retention is 72 hours and separate from this API —
  this project only uses live still snapshots, not recorded video.
