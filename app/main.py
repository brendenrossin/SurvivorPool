"""
Survivor Pool Dashboard - Streamlit App
"""

import os

import streamlit as st

# Configure Streamlit FIRST, before any other imports that might trigger Streamlit
st.set_page_config(
    page_title=f"Survivor {os.getenv('NFL_SEASON', 2025)} - Live Dashboard",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="collapsed"  # Better for mobile
)

import pandas as pd
import os
import sys
import logging

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Simple startup
print("🚀 Starting Survivor Pool Dashboard...")
print("✅ Streamlit app starting...")

from app.dashboard_data import (
    load_team_data,
    get_summary_data,
    get_started_game_weeks,
    get_completed_week_count,
    get_week_team_status,
    get_week_game_statuses,
    get_attrition_series,
    get_player_data,
    get_meme_stats,
    search_players
)
from app.picks_grid import (
    MIN_ROWS,
    aggregate_picks,
    build_picks_grid,
    contrast_fill,
    eliminated_edge,
    eliminated_fill,
    mute_color,
    resolve_current_week,
    select_grid_rows,
)
from app.attrition import build_sparkline, describe_worst_stretch
from app.meme_cards import render_meme_stats
from app.theme import GLOBAL_CSS, SURFACE
from app.live_scores import (
    render_live_scores_widget,
    resolve_scoreboard_week,
    should_reveal_picks,
)
from app.team_of_doom import render_team_of_doom_widget
from app.graveyard import render_graveyard_widget
from app.survivors import render_survivors_widget
from app.chaos_meter import render_chaos_meter_widget
from app.mobile_plotly_config import get_mobile_config, lock_zoom

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Configuration
SEASON = int(os.getenv("NFL_SEASON", 2025))
COUNT_LABEL, PERCENT_LABEL = "Count", "% of week"
# Floor the current week's fills must clear against SURFACE. WCAG 2.1's
# non-text minimum; see contrast_fill in app/picks_grid.py for why the grid
# needs it at all.
EMPHASIS_MIN_CONTRAST = 3.0
team_data = load_team_data()

def main():

    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)

    # Header
    st.title(f"Survivor {SEASON}")

    # Modern header with subtitle and chips
    with st.container():
        col_left, col_right = st.columns([0.72, 0.28])
        with col_left:
            st.caption("Live elimination tracking, NFL " + str(SEASON))
        with col_right:
            # Last update chip
            try:
                summary_preview = get_summary_data(SEASON)
                last_updates = summary_preview.get("last_updates", {})
                ts = last_updates.get("update_scores") or last_updates.get("ingest_sheet")
                if ts:
                    import pytz
                    from datetime import timezone
                    pacific = pytz.timezone('America/Los_Angeles')
                    ts_pacific = ts.replace(tzinfo=timezone.utc).astimezone(pacific)
                    label = ts_pacific.strftime("%m/%d %I:%M %p")
                    tz_abbr = ts_pacific.strftime("%Z")  # PDT or PST depending on DST
                    st.markdown(f'<div class="kpi-label">Updated {label} {tz_abbr}</div>', unsafe_allow_html=True)
            except:
                pass

    # KPI row. "Players Remaining" carries the attrition sparkline: the
    # donut it replaces showed a two-part ratio, and 2025 ended at 1 of 252.
    try:
        summary_preview = get_summary_data(SEASON)
        series = get_attrition_series(SEASON)

        st.markdown('<div class="section-title">Key stats</div>',
                    unsafe_allow_html=True)
        k1, k2, k3 = st.columns(3)

        remaining = summary_preview.get("entrants_remaining", 0)
        total = summary_preview.get("entrants_total", 0)

        with k1:
            st.markdown(
                '<div class="kpi-label">Players remaining</div>'
                f'<div class="kpi-value">{remaining:,}</div>',
                unsafe_allow_html=True,
            )
            if series:
                st.plotly_chart(build_sparkline(series),
                                use_container_width=True,
                                config=get_mobile_config())
                worst = describe_worst_stretch(series)
                tail = f" - {worst}" if worst else ""
                st.markdown(
                    f'<div class="kpi-sub">of {total:,} entered{tail}</div>',
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    f'<div class="kpi-sub">of {total:,} entered - the curve '
                    'starts once week 1 is final</div>',
                    unsafe_allow_html=True,
                )

        with k2:
            st.markdown(
                '<div class="kpi-label">Eliminated</div>'
                f'<div class="kpi-value">{total - remaining:,}</div>'
                '<div class="kpi-sub">out of the running</div>',
                unsafe_allow_html=True,
            )

        with k3:
            # Weeks that have been played out, not weeks that have picks - the
            # sheet is filled in weeks ahead of kickoff.
            weeks_played = get_completed_week_count(SEASON)
            st.markdown(
                '<div class="kpi-label">Weeks completed</div>'
                f'<div class="kpi-value">{weeks_played:,}</div>'
                '<div class="kpi-sub">survival rounds</div>',
                unsafe_allow_html=True,
            )
    except Exception as error:
        # Never fail silently: the whole Key Stats row vanishing with no
        # explanation is the exact thing this branch set out to remove.
        logging.exception("KPI row failed to render")
        st.warning(f"Key stats are unavailable right now: {error}")

    # Live Scores - cards for the week the scoreboard should show. Deliberately
    # NOT the grid's week: the grid leads with the last week that kicked off,
    # because that is the last week whose picks may be published; the scoreboard
    # rolls forward once that week has finished.
    try:
        started_weeks = get_started_game_weeks(SEASON)
        week_statuses = get_week_game_statuses(SEASON)
        played_week = resolve_current_week(
            sorted(w["week"] for w in get_summary_data(SEASON)["weeks"]) or [1],
            started_weeks,
        )
        scoreboard_week = resolve_scoreboard_week(played_week, week_statuses)
        render_live_scores_widget(
            SEASON, scoreboard_week,
            # Asked of the scoreboard's own week, never derived by comparing it
            # against the grid's - see should_reveal_picks.
            reveal_picks=should_reveal_picks(scoreboard_week, started_weeks),
        )
    except Exception:
        # The detail goes to the Railway logs. Rendering str(e) here publishes
        # the production database host and user to every pool member the first
        # time Postgres refuses a connection.
        logging.exception("Live scores failed to render")
        st.info("🏈 Live scores are unavailable right now.")

    st.divider()

    # Load data
    try:
        summary = get_summary_data(SEASON)
        meme_stats = get_meme_stats(SEASON)
    except Exception as e:
        st.warning(f"Database not fully populated yet: {e}")
        st.info("Starting up. Data appears once Google Sheets access is configured.")
        # Create empty data structure for demo
        summary = {
            "season": SEASON,
            "weeks": [],
            "entrants_total": 0,
            "entrants_remaining": 0,
            "last_updates": {}
        }
        meme_stats = {
            "dumbest_picks": [],
            "big_balls_picks": []
        }

    # Main dashboard layout - Weekly picks chart as main focus
    render_weekly_picks_chart(summary)

    st.divider()

    # The donut's half-width column is gone, so search gets the full width.
    render_player_search()

    st.divider()
    render_meme_stats(meme_stats)

    st.divider()
    st.markdown('<div class="section-title">Pool insights</div>',
                unsafe_allow_html=True)

    # Each widget reads through a cached function in dashboard_data, so these
    # tab bodies no longer open a session apiece on every script run.
    tabs = st.tabs(["Team of Doom", "Survivors", "Graveyard", "Elimination Tracker"])
    panels = (
        ("Team of Doom", render_team_of_doom_widget),
        ("Survivors", render_survivors_widget),
        ("Graveyard", render_graveyard_widget),
        ("Elimination Tracker", render_chaos_meter_widget),
    )
    for tab, (name, render) in zip(tabs, panels):
        with tab:
            try:
                render(SEASON)
            except Exception as error:
                # One panel failing must not take out the others, and it must
                # say so rather than showing a raw traceback.
                logging.exception("%s failed to render", name)
                st.warning(f"{name} is unavailable right now: {error}")

    # Footer with update times
    render_footer(summary.get("last_updates", {}))

@st.cache_data
def get_team_color_map():
    """Get centralized team color mapping"""
    team_data = load_team_data()
    return {team: data.get("color", "#666666") for team, data in team_data["teams"].items()}

@st.cache_data
def get_team_name_map():
    """Full team names, for tooltips."""
    team_data = load_team_data()
    return {team: data.get("name", team) for team, data in team_data["teams"].items()}

def render_weekly_picks_chart(summary):
    """Render the team x week picks grid, leading with the current week."""

    if not summary["weeks"]:
        st.info("📊 **No weekly picks data yet**\n\nPicks will appear once:\n1. Google Sheets data is imported (hourly cron)\n2. NFL scores are fetched (Sunday/Monday/Thursday cron)\n3. Picks are linked to games and processed")
        return

    pick_weeks = sorted(w["week"] for w in summary["weeks"])

    # The sheet holds picks for unplayed weeks, so the latest week with a pick
    # is not "now" - resolve against the weeks whose games have actually
    # started, and never aggregate past that or we leak next week's picks.
    current_week = resolve_current_week(pick_weeks, get_started_game_weeks(SEASON))
    weeks = list(range(1, current_week + 1))  # spec: columns are 1..current_week

    counts, week_totals, season_totals = aggregate_picks(
        summary["weeks"], current_week
    )
    if not counts:
        # Reachable when the sheet holds only future weeks: aggregate_picks
        # clips at the current week, so picks exist but none are publishable.
        st.info(
            f"**No picks for week {current_week} or earlier.** The sheet is "
            "filled in ahead of kickoff, so picks appear here once their "
            "games start."
        )
        return

    st.markdown("### 📊 Team Picks by Week")

    control_left, control_right = st.columns([2, 3])
    with control_left:
        label_mode = st.radio(
            "Cell labels",
            [COUNT_LABEL, PERCENT_LABEL],
            horizontal=True,
            label_visibility="collapsed",
            key="picks_grid_format",
        )
    with control_right:
        expanded = st.toggle(
            "Show every team picked",
            key="picks_grid_expanded",
            help=f"Drop the {MIN_ROWS}-row floor and list every team picked so far",
        )
    as_percent = label_mode == PERCENT_LABEL

    week_counts = {t: n for (w, t), n in counts.items() if w == current_week}
    rows = select_grid_rows(week_counts, season_totals, expanded=expanded)

    # Cached: the grid's two controls make every toggle a full script rerun.
    team_status = get_week_team_status(SEASON, current_week)

    fig = build_picks_grid(
        weeks=weeks,
        rows=rows,
        counts=counts,
        week_totals=week_totals,
        team_colors=get_team_color_map(),
        current_week=current_week,
        as_percent=as_percent,
        background=SURFACE,
        team_names=get_team_name_map(),
        team_status=team_status,
        # The grid's emphasis is bounded by team-colour-to-surface distance, so
        # a dark team on a dark surface has nowhere for its history to recede
        # to. Bidirectional: this also darkens PIT and NO on a light surface,
        # where they fail against #F8FAFC.
        current_week_min_contrast=EMPHASIS_MIN_CONTRAST,
    )

    # Deliberately not render_mobile_chart: CHART_CONFIGS would overwrite the
    # grid's computed height and its axis config with the bar-chart defaults.
    # It still needs the axes pinned, which that path would have done.
    st.plotly_chart(lock_zoom(fig), use_container_width=True,
                    config=get_mobile_config())

    # This replaces the "Week N Picks Breakdown" table. The table listed team
    # and count, which the grid already shows in the same order; its only
    # unique content was a ✅/💀/🕐 glyph per team, now carried by the cell
    # itself. The grid gained an encoding, so it has to name the three it has.
    swatch = (
        'display:inline-block;width:11px;height:11px;'
        'border-radius:2px;vertical-align:-1px;'
    )
    sample = get_team_color_map().get(rows[0], "#666666")
    lifted = contrast_fill(sample, SURFACE, EMPHASIS_MIN_CONTRAST)
    out_fill = eliminated_fill(sample, SURFACE)
    st.caption(
        f'<span style="background:{lifted};{swatch}"></span> this week'
        ' &nbsp;·&nbsp; '
        f'<span style="background:{mute_color(sample, SURFACE)};{swatch}"></span>'
        ' earlier weeks'
        ' &nbsp;·&nbsp; '
        f'<span style="background:{out_fill};border:2px solid '
        f'{eliminated_edge(out_fill)};{swatch}"></span> eliminated this week',
        unsafe_allow_html=True,
    )

    eliminated = sorted(
        team for team in rows
        if team_status.get(team) == "lost" and (current_week, team) in counts
    )
    if eliminated:
        out = sum(counts[(current_week, team)] for team in eliminated)
        st.caption(
            f"Week {current_week}: {out} {'entry' if out == 1 else 'entries'} "
            f"out on {', '.join(eliminated)}"
        )


def render_player_search():
    """Render player search section"""
    st.markdown('<div class="eyebrow">Find a survivor</div>', unsafe_allow_html=True)

    # Search input
    search_query = st.text_input("Enter survivor name:", placeholder="e.g., Travis Taylor")

    if search_query:
        # Search for matching players
        matching_players = search_players(search_query, SEASON)

        if matching_players:
            selected_player = st.selectbox("Select player:", matching_players)

            if selected_player:
                # Get player data
                player_data = get_player_data(selected_player, SEASON)

                if player_data:
                    st.write(f"**{selected_player}**")

                    # Display picks table
                    picks_df = pd.DataFrame(player_data["picks"])

                    if not picks_df.empty:
                        # Add status column with emojis
                        picks_df["Status"] = picks_df.apply(lambda row:
                            "Locked" if row["locked"] and row["survived"] is None
                            else "Won" if row["survived"] is True
                            else "Out" if row["survived"] is False
                            else "Pending" if row["team"] is not None
                            else "-", axis=1)

                        picks_df["Valid"] = picks_df["valid"].apply(
                            lambda ok: "Yes" if ok else "Check")

                        # Display table
                        display_df = picks_df[["week", "team", "Status", "Valid"]].rename(columns={
                            "week": "Week",
                            "team": "Team",
                            "Status": "Result",
                            "Valid": "Valid"
                        })

                        st.dataframe(display_df, use_container_width=True, hide_index=True)
                    else:
                        st.info("No picks found for this player")
                else:
                    st.error("Player not found")
        else:
            st.info("No players found matching your search")

def render_last_updated_chip(last_updates):
    """Render last updated timestamp at top of page"""
    from datetime import timezone

    # Prefer scores timestamp if present, else ingest
    ts = last_updates.get("update_scores") or last_updates.get("ingest_sheet")
    if ts:
        # Convert UTC to Pacific time (handles PST/PDT automatically)
        import pytz
        pacific = pytz.timezone('America/Los_Angeles')
        ts_pacific = ts.replace(tzinfo=timezone.utc).astimezone(pacific)
        label = ts_pacific.strftime("%m/%d %I:%M %p")
        tz_abbr = ts_pacific.strftime("%Z")  # PDT or PST
        st.caption(f"Last updated {label} {tz_abbr}")

def render_footer(last_updates):
    """Render footer with update information"""
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        from datetime import timezone
        import pytz
        pacific = pytz.timezone('America/Los_Angeles')

        st.caption("**Data sources**")
        if "ingest_sheet" in last_updates and last_updates["ingest_sheet"]:
            sheet_time_pacific = last_updates["ingest_sheet"].replace(tzinfo=timezone.utc).astimezone(pacific)
            sheet_time = sheet_time_pacific.strftime("%m/%d %I:%M %p")
            tz_abbr = sheet_time_pacific.strftime("%Z")
            st.caption(f"Picks {sheet_time} {tz_abbr}")

        if "update_scores" in last_updates and last_updates["update_scores"]:
            scores_time_pacific = last_updates["update_scores"].replace(tzinfo=timezone.utc).astimezone(pacific)
            scores_time = scores_time_pacific.strftime("%m/%d %I:%M %p")
            tz_abbr = scores_time_pacific.strftime("%Z")
            st.caption(f"Scores {scores_time} {tz_abbr}")

    with col2:
        st.caption("Survivor Pool Dashboard")

if __name__ == "__main__":
    main()