# MVP Enhancements & Ops Checklist

Scope: Tier-1 “Bring-Your-Own-Sheet” MVP running on Streamlit + Railway Postgres + background jobs that populate Game/summary tables.
Goal: keep it light, fast, and cheap while adding durability and polish.

⸻

Quick UX Wins (low effort, high impact)
	•	Sticky jump nav (mobile) — Add a compact nav (“Scores | Picks | Survivors | Insights”) using st.container() pinned at top (Streamlit can’t do native sticky, but placing this block above content mimics it and shortens scroll).
	•	Collapse long lists — Wherever you enumerate “Picked by: A, B, C…”, wrap with st.expander("Picked by 23 players") to cut egress and scroll.
	•	Status chips — In “Live Scores,” add small text chips (Live/Final/Not started). Your render_live_scores_widget likely knows the game state—surface it.
	•	Consistency on team labels — Use full team name in charts, abbreviations in tables; point both to a central team dictionary (load_team_data() already exists).
	•	Freshness cues — You already have last_updates in render_footer(). Mirror a tiny “Last updated: xx:yy” at the top of the page near Scores.
	•	Share snapshot — Add a small “Save PNG” for the stacked bar & donut via Plotly’s config={'toImageButtonOptions': ...} to increase virality.

Why important: Quality-of-life now; keeps pages readable as leagues/players expand.

⸻

Performance & Cost
	•	Cache data reads — Wrap expensive reads with st.cache_data (safe for pure data) and resources (DB engine) with st.cache_resource.

```
@st.cache_resource
def get_db():
    from api.database import SessionLocal
    return SessionLocal()

@st.cache_data(ttl=60)  # 60s default; lower during live windows if needed
def get_summary_cached(season: int):
    from app.dashboard_data import get_summary_data
    return get_summary_data(season)

@st.cache_data(ttl=60)
def get_meme_stats_cached(season: int):
    from app.dashboard_data import get_meme_stats
    return get_meme_stats(season)
```

Then use these in main() in place of direct calls.

	•	Lazy render heavy sections — Use st.tabs() (you already do) + early returns to avoid building all charts if not visible (Streamlit still executes, but you can guard costly work).
	•	Trim Plotly annotations — In render_weekly_picks_chart, you annotate segments with Count >= 10. Consider top-3 per week only; lots of text kills mobile FPS.
	•	Correct color map — Current color_discrete_map is built from zip(df_sorted["Team"], df_sorted["Color"]) which may include duplicates and inconsistent mapping. Build once from team_data:

```
color_map = {t: d.get("color", "#666") 
             for t, d in load_team_data()["teams"].items()}
fig = px.bar(..., color_discrete_map=color_map)
```

	•	Compression & CDN — Put Cloudflare free tier in front; enable Brotli. Streamlit static assets benefit a lot.
	•	Game-window polling — Drive refresh cadence via a small constant (e.g., 15–30s during live; 5–10 min otherwise). If you expose API routes, backoff with jitter.

Why important: Keeps Railway egress/runtimes low; prevents “sticky” charts under load.

⸻

Data Pipeline (resilience, idempotency)
	•	Idempotent ingest — Ensure each pick row has a stable source_row_hash or (player, week, team) key; UPSERT to avoid dupes if the job reruns.
	•	Derived tables — Maintain precomputed weekly aggregates (picks per team), survivors, and meme stats in separate tables or materialized views. Your UI should read only from these aggregates.
	•	Single team dictionary — Centralize {abbr, city, nickname, logo_url, colors, bye_week} so charts/tables never diverge.
	•	Timestamps — Store last_ingested_at and last_scores_update_at server-side; you’re already passing last_updates—standardize UTC in DB and format in UI.

Why important: Enables consistent, fast reads; reduces runtime joins/aggregation in the UI.

⸻

Observability (MVP-friendly)
	•	Structured logs in UI layer — Add a small helper to log section timings and sizes:

```
import time, json

class SectionTimer:
    def __init__(self, name): self.name, self.t = name, time.time()
    def end(self, extra=None):
        ms = int((time.time()-self.t)*1000)
        print(json.dumps({"section": self.name, "ms": ms, **(extra or {})}))
```
Usage:
```
t = SectionTimer("weekly_picks_chart")
render_weekly_picks_chart(summary)
t.end()
```

	•	Job health counters — In your worker, log ingest.success, ingest.fail, scores.success, scores.fail counts per hour.
	•	Lightweight metrics endpoint (if you run a FastAPI backend): /healthz, /metricsz with last update times.

Why important: Tells you where time/egress goes, without full APM.

⸻

Robust Edge Cases to Cover
	•	Duplicate / late picks — Lock by kickoff and mark late edits with a badge.
	•	Rebuys (multiple lives) — Support an optional life_id dimension for pools that allow re-entries.
	•	Bye weeks / postponed / neutral sites — Read schedule once; don’t rely on parsing opponent strings.
	•	Name conflicts — Normalize player names (trim, casefold); consider an internal player_id if the Sheet contains duplicates.
	•	Invalid teams — Validate team codes against the dictionary at ingest; flag rows to a “quarantine” table for the commissioner.

Why important: Prevents silent data drift and keeps dashboards trustworthy.

⸻

Product Ideas That Fit “Lightweight”
	•	Chaos Meter — Expected vs actual eliminated (based on closing line). Small KPI card per week.
	•	Pick Equity Heatmap — Remaining entrants × remaining teams; highlights contrarian leverage.
	•	Spectator Mode — If a user is eliminated, feature “Team of Doom,” “Graveyard,” and weekly chaos up top to retain engagement.
	•	Weekly recap email — Static PNGs of the 2–3 top cards (Plotly export) + link back.

Why important: Boosts stickiness without heavy engineering.

⸻

Security & Keys
	•	Server-side secrets only — You already use dotenv; ensure API keys never hit the client. Offer a thin server proxy for external APIs.
	•	Row-level privacy — The public dashboard should never show emails/PII from Sheets. Keep public tables clean.
	•	CORS/Rate limits — If you expose FastAPI endpoints, restrict origins to your domain and add modest per-IP rate limits.
	•	“Not a gambling operator” disclaimer — Simple footer text (you already have a footer) to clarify you don’t handle entries/payouts.

Why important: Prevents accidental key exposure & keeps you on safe ground.

⸻

Make It Feel “Live” (without being heavy)
	•	SSE for scores (optional) — If you control a FastAPI service, use Server-Sent Events to push score deltas; Streamlit can read via requests in a background thread or poll an endpoint that merges deltas.
	•	Stale-while-revalidate — Show current values immediately; refresh in background; update the “Last updated” chip on success.
	•	Stop updating finals — Once a game hits Final, stop polling that game’s ID for the rest of the session.

Why important: Real-time feel, minimal compute.

⸻

Code-Level Suggestions (based on app/main.py)
	1.	DB sessions: close reliably
```
try:
    db = SessionLocal()
    render_live_scores_widget(db, SEASON, current_week)
except Exception:
    st.info("🏈 Live scores will appear once data is populated")
finally:
    try: db.close()
    except: pass
```

	2.	Current week discovery
Your query pulls the max week with any games in Game. Consider preferring max week that is ongoing or most recent final. You can also override via query param (?week=3) for debugging.
	3.	Cache expensive reads
Replace:
```
summary = get_summary_data(SEASON)
meme_stats = get_meme_stats(SEASON)
```
with cached wrappers (see “Performance & Cost”).

	4.	Color map correctness (Plotly)
Build a unique color map from team_data once (see snippet above). Avoid per-frame zip() which may map duplicates inconsistently.
	5.	Guard empty data more ergonomically
In render_weekly_picks_chart, you show a long info block if no data. Add a hint button to open your template sheet or “Refresh now” link to a worker status page.
	6.	Player search ergonomics
	•	When there are many matches, st.selectbox is fine, but add a format_func that includes the team last picked or status for clarity.
	•	Consider st.cache_data for search_players (it likely queries a static index per week).
	7.	Meme stats copy
The tone is fun (✅). Consider adding small tooltips (via st.caption) that clarify definitions (“road win”, “underdog by X pts”) so newcomers understand.

⸻

Example: Adding “Last Updated” at Top
```
def render_last_updated_chip(last_updates):
    # Prefer scores timestamp if present, else ingest
    ts = last_updates.get("update_scores") or last_updates.get("ingest_sheet")
    label = ts.strftime("%m/%d %H:%M") if ts else "—"
    st.caption(f"🕒 Last updated: {label} (UTC)")

# In main(), right after title:

render_last_updated_chip(summary.get("last_updates", {}))
```

⸻

Example: Collapsing Long Name Lists
```
def render_pickers_list(title: str, names: list[str]):
    count = len(names)
    if count == 0:
        st.caption("No pickers")
        return
    with st.expander(f"{title} — {count} players"):
        st.write(", ".join(names))
```
Use in any section that prints large “Picked by:” lists.

⸻

Example: Central Team Color Map
```
def get_team_color_map():
    td = load_team_data()["teams"]
    return {team: td[team].get("color", "#666666") for team in td}

# in render_weekly_picks_chart(...)

color_map = get_team_color_map()
fig = px.bar(..., color_discrete_map=color_map)
```


⸻

Rollout Order (fastest wins first)
	1.	Cache data (st.cache_data / st.cache_resource)
	2.	Collapse long lists, add top freshness chip, correct Plotly color map
	3.	Smarter week detection + better DB session closing
	4.	Job idempotency & timestamps (DB)
	5.	Optional SSE / smarter polling if you feel latency during games

⸻

TL;DR

Your Streamlit MVP is already clean and thoughtful. The biggest immediate ROI will come from caching reads, collapsing long lists, adding freshness cues at the top, and tightening the color map + annotations. Those changes alone will make it feel more professional, cut egress, and keep the UI snappy during game spikes—without complicating your architecture.

If you want, I can turn any two of the code-level items above into exact diffs against your repo (e.g., add caching + color map fix).