Survivor Pool Dashboard — Dev Spec (v0.1)

Goal: a cheap-to-run, single-page web app that auto-ingests weekly picks from Google Sheets, fetches live NFL scores on a schedule, determines who “survived,” and renders fun, sharable visuals.

This document is written so you can hand it to a coding assistant (Claude Code) and start building immediately.

⸻

0) High-level architecture (low cost)
	•	Frontend: Single-page app using Streamlit (fastest) or Next.js/React (more control). One page only.
	•	Backend / jobs: Lightweight worker (Python) + scheduled cron.
	•	Storage: Postgres (e.g., Supabase/Railway free tier).
	•	Hosting options (pick one):
	•	All-in-one container on Railway/Fly.io (runs web + cron inside one service) — simplest.
	•	Static frontend (Cloudflare Pages / Vercel) + serverless job (Cloudflare Workers Cron / GitHub Actions cron) + Supabase.
	•	Secrets: .env for API keys, Sheet ID, DB URL.

⸻

1) Google Sheet ingestion

Assumptions from the sheet screenshot:
	•	Sheet name: Picks
	•	Columns:
	•	Col A: Name (player display name; unique per player)
	•	Cols B..Z: Week 1, Week 2, … (cell values: NFL team abbreviations, e.g., WAS, BAL, PHI, DEN, ARI, LAR, BUF, SEA, TB, IND, KC, GB, DAL, CIN etc.)
	•	Values may be blank for future weeks or if user hasn’t picked yet.

Pull rules:
	•	Daily refresh (morning, e.g., 07:00 PT) to backfill any late adds/edits.
	•	No overwrite of locked picks (see §4 “Locking & validation”).
	•	Read via Google Sheets API using a Service Account with read-only access to the spreadsheet.

Config needed:

GOOGLE_SHEETS_SPREADSHEET_ID=<...>   # the survivor pool sheet
GOOGLE_SHEETS_PICKS_RANGE=Picks!A1:Z5000
GOOGLE_SERVICE_ACCOUNT_JSON_BASE64=<base64 of credentials JSON>  # easier for env


⸻

2) NFL data provider (pluggable)

Implement a ScoreProvider interface so we can swap sources:

class ScoreProvider(Protocol):
    def get_schedule_and_scores(self, season:int, week:int) -> list[Game]  # includes kickoff, teams, home/away, status, winner
    def get_current_week(self, season:int) -> int

Initial adapters (use any one that’s easiest for you):
	•	ESPN public JSON endpoints (free; unofficial; light scraping; handle changes gently).
	•	The Odds API / MySportsFeeds / SportsdataIO (have free tiers/trials; keys go in .env).

Polling schedule (PT):
	•	Sundays: hourly 10:00 → 21:00
	•	Mon/Thu: once at 21:00 (after game ends)
	•	On run: fetch scores for the current NFL week and update DB.

Config:

NFL_SEASON=2025
SCORES_PROVIDER=espn  # or sportsdataio / mysportsfeeds / oddsapi
SCORES_API_KEY=<optional>


⸻

3) Database schema (Postgres)

-- people playing
create table players (
  player_id serial primary key,
  display_name text unique not null
);

-- raw picks as typed in the sheet (one row per player-week)
create table picks (
  pick_id serial primary key,
  player_id int references players(player_id),
  season int not null,
  week int not null,
  team_abbr text,             -- e.g., 'BUF'
  source text not null default 'google_sheets',  -- provenance
  picked_at timestamptz not null default now(),
  unique(player_id, season, week)
);

-- canonical NFL games
create table games (
  game_id text primary key,   -- provider-native id or concat season/week/home/away
  season int not null,
  week int not null,
  kickoff timestamptz not null,
  home_team text not null,
  away_team text not null,
  status text not null,       -- 'pre','in','final'
  home_score int,
  away_score int,
  winner_abbr text            -- null until final
);

-- results of picks evaluated against final winners
create table pick_results (
  pick_id int primary key references picks(pick_id) on delete cascade,
  game_id text references games(game_id),
  is_valid boolean not null default true,  -- e.g., duplicate-team violation
  is_locked boolean not null default false,
  survived boolean                         -- null until game final; true/false afterwards
);

-- to prevent duplicate-team picks across the season
create unique index if not exists uniq_player_team_season
  on picks(player_id, season, team_abbr)
  where team_abbr is not null;

Note: the partial unique index enforces “no team twice” automatically once a team exists for that player+season (nulls don’t conflict).

⸻

4) Locking & validation
	•	Lock rule: A player’s pick becomes locked at kickoff of that team’s game. Before kickoff, the pick can change (we re-ingest Sheet; last value before kickoff wins).
	•	For each ingestion:
	•	Resolve (season, week, team_abbr) → game_id via the games table.
	•	If now ≥ kickoff for that team’s game, set is_locked=true and do not update team_abbr on future ingestions.
	•	If a player changes to a different team before kickoff, update picks.team_abbr and re-validate uniqueness.
	•	No same team twice: enforced by the partial unique index (above). If violated on ingest, set pick_results.is_valid=false and flag on UI.

⸻

5) Backfill Weeks 1–2 (one-time)
	•	Run a Backfill job:
	1.	Fetch official week 1 & 2 schedules and finals.
	2.	Ingest Sheet for weeks 1 & 2 (create picks).
	3.	Mark each pick’s game_id, set is_locked=true, and compute survived = (team_abbr == winner_abbr).
	•	Store an audit row (or just log) with counts.

⸻

6) Ingestion workers (cron)

Implement two job types:
	1.	Sheet Ingest (daily + pre-games on Sun morning):
	•	Read the range.
	•	Upsert players and upsert picks (current season, all visible week columns).
	•	Respect locking logic.
	•	Re-compute pick_results.is_valid (dup-team) after upsert.
	2.	Scores Updater (cron schedule above):
	•	For current week:
	•	Upsert games (kickoff/status/scores/winner).
	•	For any games.status='final', set pick_results.survived for linked picks.

Suggested schedules (UTC in infra; below are PT intentions):
	•	Sheet Ingest: 07:00 PT daily; 09:30 PT Sundays as a second run.
	•	Scores Updater: hourly on Sundays 10→21 PT; 21:00 PT Mon/Thu.

⸻

7) API surface (if using React/Next.js; Streamlit can read DB directly)
	•	GET /api/summary?season=2025&week=3
	•	Returns counts per team (for stacked bar), total remaining players, total entrants.
	•	GET /api/player?name=Brent%20Rossin&season=2025
	•	Current pick (with lock status) + prior weeks.
	•	GET /api/memes?season=2025&week=3
	•	“Dumbest picks” (largest negative margin), “Big Balls” (won as underdogs), etc.

Keep responses small & cacheable (e.g., 30–60s CDN cache).

⸻

8) Visuals (MVP)
	1.	Stacked bar by week (team-colored stacks)
	•	X-axis: Week.
	•	For each week, a stacked bar of team counts.
	•	Color: primary team color.
	•	Label: overlay team logo centered on each stack (fallback: team abbreviation).
	•	Data shape:

[
  {"week":3, "team":"BUF", "count":112},
  {"week":3, "team":"KC", "count":27},
  ...
]


	•	Implementation tips:
	•	In React: Recharts BarChart with stacked Bar by team; use Cell with team color map.
	•	In Streamlit: compute SVG with pillow/cairosvg, or Altair layered bars + image marks.

	2.	Donut (remaining %)
	•	Center text: 65% (and x / y under it).
	•	Numbers: remaining = players who have never had survived=false (i.e., not eliminated).
	•	Render simple count + percentage.
	3.	Meme stats (tables or cards)
	•	Dumbest picks (season-to-date): sort final games by negative point differential for picked team; show top 3 with opponent & spread.
	•	Dumbest (last week): same filter week = current_week - 1.
	•	Big Balls: winners where the picked team closed as underdog (needs betting line; optional v1).
	•	v0 heuristic if no odds: underdog ≈ road team beating winning home favorite? (Mark “experimental”)
	•	v1: integrate closing lines via odds provider.

Provide a team map (abbr → full name, color, logo URL). Put static assets in /public/logos/<abbr>.png.
Start with these abbreviations present in the sheet: WAS, BAL, PHI, DEN, ARI, LAR, BUF, SEA, TB, IND, KC, GB, DAL, CIN. Add the full league list later.

Example color mapping (seed):

{
  "ARI": "#97233F",
  "ATL": "#A71930",
  "BAL": "#241773",
  "BUF": "#00338D",
  "CAR": "#0085CA",
  "CHI": "#0B162A",
  "CIN": "#FB4F14",
  "CLE": "#311D00",
  "DAL": "#003594",
  "DEN": "#FB4F14",
  "DET": "#0076B6",
  "GB":  "#203731",
  "HOU":"#03202F",
  "IND":"#002C5F",
  "JAX":"#006778",
  "KC": "#E31837",
  "LAC":"#0080C6",
  "LAR":"#003594",
  "LV": "#000000",
  "MIA":"#008E97",
  "MIN":"#4F2683",
  "NE": "#002244",
  "NO": "#D3BC8D",
  "NYG":"#0B2265",
  "NYJ":"#125740",
  "PHI":"#004C54",
  "PIT":"#FFB612",
  "SF": "#AA0000",
  "SEA":"#002244",
  "TB": "#D50A0A",
  "TEN":"#0C2340",
  "WAS":"#5A1414"
}


⸻

9) Business logic details
	•	Elimination / still alive:
	•	A player is eliminated once any pick_results.survived=false in the season.
	•	Remaining = players with no survived=false.
	•	Multiple entries per person? Not in v0; display_name is unique. (Extend with an entry_id later.)
	•	Edge cases:
	•	Blank or typo team abbreviations → mark pick invalid; surface in UI badge.
	•	Postponements / ties: if no winner, leave survived=null until status is final.
	•	If Sheet renames a player, keep the old players.display_name and add a mapping table aliases(player_id, alias_text) (optional).

⸻

10) Minimal UX (single page)

Sections, top → bottom:
	1.	Header: “Survivor 2025 — Live Dashboard”
	2.	Donut: Remaining players (remaining / total, percentage)
	3.	Stacked bar: Weekly picks distribution
	4.	Search box: “Find a player” → card shows current pick (lock status), and a table of their past picks (✅ survived / ❌ eliminated)
	5.	Meme stats: “Dumbest picks (Szn)”, “Dumbest (Last Wk)”, “Big Balls (Underdog wins)”
	6.	Footer: data refresh time + disclaimer

Performance: Cache JSON for 30–60s; at <500 concurrent viewers this is fine on any free tier.

⸻

11) Security & reliability (lightweight)
	•	Service account is read-only to that single Sheet.
	•	Store only display names; no emails/PII.
	•	Validate Sheet inputs (uppercase, 2–4 letters).
	•	Rate-limit score fetches; exponential backoff; write idempotently (upserts).
	•	Wrap cron tasks with logging, and store last success timestamp in a meta table.

⸻

12) Project structure

survivor-dashboard/
  app/                      # Streamlit or Next.js
  api/                      # (if React) FastAPI or Next API routes
  jobs/
    ingest_sheet.py
    update_scores.py
    backfill_weeks.py
  db/
    migrations.sql
    seed_team_map.json
  public/logos/             # team logos by abbr
  .env.example
  README.md


⸻

13) Contracts & pseudocode

Sheet ingest (pseudocode):

rows = sheets.get_range(SPREADSHEET_ID, PICKS_RANGE)
header = rows[0]  # ["Name","Week 1","Week 2", ...]
week_cols = [(i, parse_week_num(header[i])) for i in range(1, len(header)) if header[i].startswith("Week")]

for r in rows[1:]:
    name = r[0].strip()
    if not name: continue
    player_id = upsert_player(name)

    for col_idx, week in week_cols:
        team = (r[col_idx] or "").strip().upper() or None
        upsert_pick(player_id, SEASON, week, team)  # respect locking inside

Update scores (pseudocode):

wk = provider.get_current_week(SEASON)
games = provider.get_schedule_and_scores(SEASON, wk)
upsert_games(games)

# attach game_id to picks + compute survived
for p in picks_for_week(SEASON, wk):
    g = find_game_by_team_week(games, p.team_abbr)  # i.e., team_abbr is home or away
    link_pick_to_game(p, g.game_id)
    lock_if_now_ge_kickoff(p, g.kickoff)

    if g.status == "final":
        set_survived(p, p.team_abbr == g.winner_abbr)


⸻

14) Acceptance checklist (MVP)
	•	Backfill weeks 1–2 and compute survived results.
	•	Daily Sheet ingest creates/updates picks but never changes locked picks.
	•	Sunday hourly + Mon/Thu 21:00 PT score updates transition in-progress → final and compute survive results.
	•	Stacked bar reflects current counts by team for each week.
	•	Donut shows remaining / total and percentage.
	•	Search shows a player’s current pick (with lock status) and history with ✅/❌.
	•	Duplicate-team rule enforced and surfaced if violated.
	•	Page shows “Last updated” timestamps for ingest and scores.

⸻

15) Local dev quickstart

# 1) Python env
uv venv && source .venv/bin/activate  # or pipx/poetry
pip install fastapi uvicorn pydantic google-api-python-client \
            google-auth google-auth-oauthlib google-auth-httplib2 \
            psycopg2-binary sqlalchemy python-dotenv requests

# 2) Run Postgres locally (docker ok) and apply migrations.sql

# 3) Put .env from .env.example

# 4) Seed team colors/logos
python -c "import json; print('ok')"  # (placeholder)

# 5) Test jobs
python jobs/backfill_weeks.py
python jobs/ingest_sheet.py
python jobs/update_scores.py

# 6) Start UI
streamlit run app/main.py
# or: uvicorn api.main:app --reload (for React/Next to consume)


⸻

16) Nice-to-have (post-MVP)
	•	Support multiple entries per person (add entry_id).
	•	Odds integration for real underdog classification.
	•	Small admin panel to override a pick (in case of sheet typo).
	•	Export CSVs and image snapshots of charts.
	•	Simple “what-if” EV simulator (future).

⸻

17) What you need from the commissioner (inputs)
	•	Google Sheet ID and read-only sharing with the service account.
	•	Confirmation on:
	•	Team abbreviations used (stick to standard NFL).
	•	If any participants have multiple entries.
	•	Total starting entrants (for donut baseline if some hadn’t picked yet in W1).

⸻

18) Definition of Done (v0)
	•	Deployed URL publicly viewable.
	•	Jobs run on the specified schedule and update within ≤5 minutes of each cron run.
	•	Data for Weeks 1–3 visible; donut, stacked bar, player search, and meme stats render without errors.
	•	README has runbook (how to re-seed, rotate keys, change sheet range).

⸻

Appendix A — Minimal API response examples

/api/summary

{
  "season": 2025,
  "weeks": [
    {"week":1, "teams":[["BAL",31],["KC",22],["BUF",18],["ARI",5]]},
    {"week":2, "teams":[["PHI",27],["DAL",26],["DEN",18]]},
    {"week":3, "teams":[["BUF",112],["KC",27],["GB",9]]}
  ],
  "entrants_total": 225,
  "entrants_remaining": 146,
  "updated_at": "2025-09-18T21:05:00Z"
}

/api/player?name=Brent%20Rossin

{
  "player":"Brent Rossin",
  "season":2025,
  "picks":[
    {"week":1,"team":"DEN","locked":true,"survived":true},
    {"week":2,"team":"ARI","locked":true,"survived":true},
    {"week":3,"team":"ARI","locked":false,"survived":null}
  ]
}

Awesome—here’s an “Appendix: v1.5 Feature Add-Ons” you can paste after the prior spec. It’s tight, implementable, and won’t bloat the app.

⸻

Appendix — v1.5 Feature Add-Ons

A) Data prerequisites (light extensions)

Odds table (for Chaos/Underdogs/Future Gauge)

create table odds (
  game_id text references games(game_id) primary key,
  provider text not null default 'consensus',
  -- American odds or decimal; pick one (here: moneyline as implied win prob)
  home_ml int,           -- e.g., -250, +180
  away_ml int,
  home_wp numeric,       -- implied win prob [0,1] after vig-adjust
  away_wp numeric,
  last_updated timestamptz not null default now()
);

Compute implied probs (example, no-vig adjustment optional):

def implied_prob(ml):         # American odds → raw prob
    return (abs(ml)/(abs(ml)+100)) if ml>0 else (100/(abs(ml)+100))

def no_vig(p1, p2):           # simple renorm to sum to 1
    s = p1 + p2
    return p1/s, p2/s

Fill odds during the Scores Updater run or a small hourly “Odds Updater” job (cheap, 1 endpoint).

⸻

B) Future Power Gauge

Definition: for each remaining player, count how many top-K favorites (by win probability) in each future week they still have available (haven’t used the team yet & team has a game that week). Return as an aggregate score.
	•	Config: K=5 favorites per week; future weeks = current_week .. final_week.
	•	Output: per player: available_top5_total, by_week_breakdown.

Pseudocode:

def future_power_gauge(season:int, current_week:int, k:int=5):
    # 1) Get remaining players (no survived=false yet)
    remaining = get_remaining_player_ids(season)

    # 2) Preload:
    #    - games + odds for weeks >= current_week
    sched = load_games_with_odds(season, week_from=current_week)
    #    dict: week -> list[(team_abbr, win_prob)]
    week_top = {}
    for wk, games in group_by_week(sched):
        # flatten to team perspective
        team_probs = []
        for g in games:
            team_probs += [(g.home_team, g.odds.home_wp),
                           (g.away_team, g.odds.away_wp)]
        week_top[wk] = sorted(team_probs, key=lambda t: t[1], reverse=True)[:k]

    # 3) Build used-teams set per player
    used = {pid: set(get_player_used_teams(pid, season)) for pid in remaining}

    # 4) Score
    results = []
    for pid in remaining:
        total = 0
        breakdown = {}
        for wk, top_list in week_top.items():
            avail = [t for (t,_) in top_list if t not in used[pid]]
            breakdown[wk] = len(avail)
            total += len(avail)
        results.append({"player_id": pid, "total": total, "by_week": breakdown})

    return sorted(results, key=lambda r: r["total"], reverse=True)

API: GET /api/future_power?season=2025&week=3&k=5
UI: Table (sortable) or horizontal bars; include a mini per-week sparkline of counts.

⸻

C) Upset Tracker (small card)

Definition: For the current (or last completed) week, find the biggest surprise given odds (or, fallback: biggest negative spread for popular pick). Display:
	•	Game, pregame favorite vs underdog, closing win prob, final score.
	•	Entrants eliminated by that upset.

SQL sketch (finalized games only):

with wk as (
  select g.*, o.home_wp, o.away_wp
  from games g
  join odds o using (game_id)
  where g.season = :season and g.week = :week and g.status = 'final'
),
picked as (
  select pr.pick_id, p.player_id, p.team_abbr, pr.game_id
  from picks p
  join pick_results pr on pr.pick_id = p.pick_id
  where p.season = :season and p.week = :week
),
elim_by_game as (
  select w.game_id,
         sum(case when w.winner_abbr <> picked.team_abbr then 1 else 0 end) as eliminated
  from wk w left join picked on picked.game_id = w.game_id
  group by w.game_id
)
select w.*, e.eliminated,
       -- surprise score: 1 - winner's pregame win prob
       case when w.winner_abbr = w.home_team then (1 - w.home_wp) else (1 - w.away_wp) end as surprise
from wk w join elim_by_game e using (game_id)
order by surprise desc, eliminated desc
limit 1;

UI: A compact card:
	•	Title: “Biggest Upset — Week 3”
	•	Body: Jets (24) def. Bills (20) | Winner pregame WP: 23% | Eliminated: 43
	•	Small footnote: data source for odds.

⸻

D) Graveyard Board

Definition: Show eliminated players and the exact week/team that killed them.

SQL (season-to-date):

select pl.display_name,
       p.week,
       p.team_abbr as doom_team
from players pl
join picks p on p.player_id = pl.player_id
join pick_results pr on pr.pick_id = p.pick_id
where p.season = :season and pr.survived = false
order by p.week asc, pl.display_name asc;

UI:
	•	Simple list or grid of “tombstones”: Name — Week 5 (DAL).
	•	Optional team logo next to doom team.
	•	Keep it collapsible to avoid clutter.

⸻

E) Team of Doom (small card)

Definition: Rank teams by total eliminations caused across the season (ties broken by most recent carnage).

SQL:

select p.team_abbr as team,
       count(*) as eliminations,
       max(p.week) as last_strike_week
from picks p
join pick_results pr on pr.pick_id = p.pick_id
where p.season = :season and pr.survived = false
group by p.team_abbr
order by eliminations desc, last_strike_week desc
limit 5;

UI: Small list card:

Team of Doom
1) NYG — 57
2) BUF — 43
3) DAL — 41
...


⸻

F) Chaos Meter (small dial)

Definition: Compare actual eliminations this week to expected eliminations from odds.
	•	Expected eliminations for a week:
\text{ExpectedElims} = \sum_{\text{picks}} (1 - \text{WP}(team))
where WP(team) is the team’s win probability from odds.home_wp/away_wp for that game.
	•	Chaos score (0–100):
\text{Chaos} = \min\Big(100,\; 50 + 50 \cdot \frac{\text{Actual} - \text{Expected}}{\max(1,\;\text{Expected})}\Big)
	•	50 = “as expected”
	•	50 = more chaos (more eliminated than expected)
	•	<50 = calmer than expected
(Clamp to [0,100].)

Pseudocode:

def chaos_meter(season:int, week:int):
    picks = load_picks_with_odds(season, week)  # each: team_abbr, survived (bool or null), win_prob
    expected = sum(1 - p.win_prob for p in picks)
    actual = sum(1 for p in picks if p.survived is False)  # only final games count
    chaos = max(0, min(100, 50 + 50 * ((actual - expected) / max(1.0, expected))))
    return {"expected": round(expected,1), "actual": actual, "chaos": round(chaos)}

API: GET /api/chaos?season=2025&week=3
UI: Small gauge/dial with three labels: Calm (0–40), Normal (~50), Chaos (60–100). Add a tooltip with Actual vs Expected.

⸻

G) Small performance & UX notes
	•	Caching: Cache each card’s JSON for 30–60s. Odds refresh hourly is fine.
	•	Empty states: If some games aren’t final yet, show partial numbers and “(live)” badges.
	•	Resilience: If odds missing for a game, skip that game in Chaos/Underdog calcs and annotate “partial”.
	•	Accessibility: Provide text fallbacks (SR-only labels) for dials/heat color blocks.

⸻

H) Example responses (ready for UI)

/api/future_power

[
  {"player":"Brent Rossin","total":11,"by_week":{"3":4,"4":3,"5":4}},
  {"player":"Alea Holmes","total":10,"by_week":{"3":3,"4":3,"5":4}}
]

/api/upset_tracker

{
  "week": 3,
  "game": {"winner":"NYJ","loser":"BUF","final":"24-20","winner_wp":0.23},
  "eliminated": 43,
  "note":"Winner had 23% pregame win probability"
}

/api/graveyard

[
  {"name":"Blade","week":2,"team":"BAL"},
  {"name":"Alec Hoag","week":2,"team":"BAL"}
]

/api/team_of_doom

[
  {"team":"NYG","eliminations":57,"last_strike_week":2},
  {"team":"BUF","eliminations":43,"last_strike_week":3}
]

/api/chaos

{"week":3,"expected":28.7,"actual":43,"chaos":84}


⸻

I) Minimal UI placement
	•	Place three small cards in a row (responsive to stack on mobile):
	•	Upset Tracker | Team of Doom | Chaos Meter
	•	Future Power Gauge as a sortable table beneath the donut (collapsible).
	•	Graveyard as a collapsible section under meme stats.

⸻

Implementation order (fastest path)
	1.	Team of Doom (pure DB)
	2.	Graveyard (pure DB)
	3.	Upset Tracker (needs odds per game)
	4.	Chaos Meter (uses odds + outcomes)
	5.	Future Power Gauge (uses odds + availability across future weeks)

If you want, I can also add a tiny Odds Updater module stub (one file, ESPN + a free odds provider) to drop into /jobs/.