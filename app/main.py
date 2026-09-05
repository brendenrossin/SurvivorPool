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

import plotly.graph_objects as go
import pandas as pd
from datetime import datetime
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
from app.live_scores import render_live_scores_widget, resolve_scoreboard_week
from app.team_of_doom import render_team_of_doom_widget
from app.graveyard import render_graveyard_widget
from app.survivors import render_survivors_widget
from app.chaos_meter import render_chaos_meter_widget
from app.mobile_plotly_config import render_mobile_chart, get_mobile_config, get_mobile_color_scheme
from app.odds_helpers import get_underdog_spread_text

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Configuration
SEASON = int(os.getenv("NFL_SEASON", 2025))
# Kept in step with the .stApp background in the CSS block below.
APP_SURFACE = "#F8FAFC"
COUNT_LABEL, PERCENT_LABEL = "Count", "% of week"
# Floor the current week's fills must clear against APP_SURFACE. WCAG 2.1's
# non-text minimum; see contrast_fill in app/picks_grid.py for why the grid
# needs it at all.
EMPHASIS_MIN_CONTRAST = 3.0
team_data = load_team_data()

def main():

    # Load Inter font and modern CSS styling
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');

    /* Force light modern theme */
    .stApp {
      background-color: #F8FAFC !important;
      color: #0F172A !important;
    }

    html, body, [class*="css"]  {
      font-family: 'Inter', system-ui, -apple-system, Segoe UI, Roboto, Arial, sans-serif !important;
      background-color: #F8FAFC !important;
      color: #0F172A !important;
    }

    /* Aggressive text color overrides to fix Railway visibility issues */
    .stApp > div, .main, .block-container, p, span, div, h1, h2, h3, h4, h5, h6 {
      color: #0F172A !important;
    }

    /* Fix specific Streamlit components */
    .stMarkdown, .stText, .stTitle, .stSubheader, .stHeader, .stCaption {
      color: #0F172A !important;
    }

    /* Fix metric labels and values */
    [data-testid="metric-container"] > div, [data-testid="metric-container"] label, [data-testid="metric-container"] div {
      color: #0F172A !important;
    }

    /* tighter layout + max width */
    .main .block-container { padding-top: 1rem; padding-bottom: 3rem; max-width: 1100px; }

    /* "card" look for sections */
    .card {
      background: #FFFFFF;
      border: 1px solid rgba(148,163,184,.25);
      border-radius: 16px;
      padding: 16px 18px;
      box-shadow: 0 6px 20px rgba(0,0,0,.08);
      margin-bottom: 14px;
    }

    /* section headers */
    h1, h2, h3 { letter-spacing: -0.01em; }
    h1 { font-weight: 800; }
    h2 { font-weight: 700; margin-top: .5rem; }

    /* chips/badges */
    .chip {
      display:inline-flex; align-items:center; gap:.35rem;
      padding: .22rem .6rem; border-radius: 999px;
      font-size: .78rem; font-weight:600; border:1px solid rgba(148,163,184,.35);
      background: linear-gradient(180deg, rgba(255,255,255,.06), rgba(255,255,255,.02));
    }
    .chip.green { color:#10B981; border-color:rgba(16,185,129,.35); }
    .chip.red   { color:#EF4444; border-color:rgba(239,68,68,.35); }
    .chip.gray  { color:#94A3B8; }

    /* live pulse dot */
    .dot { width:8px;height:8px;border-radius:999px; background:#10B981; box-shadow:0 0 0 0 rgba(16,185,129,.7); animation:pulse 1.8s infinite; }
    @keyframes pulse { 0%{box-shadow:0 0 0 0 rgba(16,185,129,.6)} 70%{box-shadow:0 0 0 14px rgba(16,185,129,0)} 100%{box-shadow:0 0 0 0 rgba(16,185,129,0)} }

    /* nicer tabs */
    .stTabs [data-baseweb="tab-list"] { gap: .75rem; }
    .stTabs [data-baseweb="tab"] { background:transparent; padding:.5rem .8rem; border-radius:10px; border:1px solid rgba(148,163,184,.25); }
    .stTabs [aria-selected="true"] { border-color:#2563EB; }

    /* plotly container spacing */
    .js-plotly-plot, .stPlotlyChart { border-radius: 14px; overflow:hidden; }
    </style>
    """, unsafe_allow_html=True)

    # Header
    st.title(f"Survivor {SEASON} — Live Dashboard")

    # Subtle gradient header band
    st.markdown("""
    <div style="
      height: 8px;
      background: linear-gradient(90deg, #2563EB, #10B981 50%, #F59E0B);
      border-radius: 999px;
      opacity:.85; margin:-4px 0 10px 0;">
    </div>
    """, unsafe_allow_html=True)

    # Modern header with subtitle and chips
    with st.container():
        col_left, col_right = st.columns([0.72, 0.28])
        with col_left:
            st.caption("Live elimination tracking • NFL " + str(SEASON))
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
                    st.markdown(f'<span class="chip gray">🕒 Last updated: {label} {tz_abbr}</span>', unsafe_allow_html=True)
            except:
                pass

    # KPI Cards - modern at-a-glance stats
    try:
        summary_preview = get_summary_data(SEASON)
        with st.container():
            st.markdown("### Key Stats")
            k1, k2, k3 = st.columns(3)

            def kpi(title, value, subtitle, icon="🏈"):
                st.markdown(f"""
                <div class="card">
                    <div style="font-size:.85rem; color:#94A3B8;">{icon} {title}</div>
                    <div style="font-size:2rem; font-weight:800; margin:.1rem 0;">{value}</div>
                    <div style="font-size:.85rem; color:#94A3B8;">{subtitle}</div>
                </div>
                """, unsafe_allow_html=True)

            entrants_remaining = summary_preview.get('entrants_remaining', 0)
            entrants_total = summary_preview.get('entrants_total', 0)
            eliminated_count = entrants_total - entrants_remaining

            with k1:
                kpi("Players Remaining", f"{entrants_remaining:,}", f"of {entrants_total:,} total entries")
            with k2:
                kpi("Eliminated Total", f"{eliminated_count:,}", "sent to graveyard", icon="💀")
            with k3:
                # Weeks that have been played out, not weeks that have picks -
                # the sheet is filled in weeks ahead of kickoff.
                weeks_played = get_completed_week_count(SEASON)
                kpi("Weeks Completed", f"{weeks_played:,}", "survival rounds", icon="📅")
    except:
        pass

    # Live Scores - cards for the week the scoreboard should show. Deliberately
    # NOT the grid's week: the grid leads with the last week that kicked off,
    # because that is the last week whose picks may be published; the scoreboard
    # rolls forward once that week has finished.
    try:
        summary_preview = get_summary_data(SEASON)
        week_statuses = get_week_game_statuses(SEASON)
        played_week = resolve_current_week(
            sorted(w["week"] for w in summary_preview["weeks"]) or [1],
            get_started_game_weeks(SEASON),
        )
        scoreboard_week = resolve_scoreboard_week(played_week, week_statuses)
        render_live_scores_widget(
            SEASON, scoreboard_week, reveal_picks=scoreboard_week <= played_week
        )
    except Exception as e:
        logging.exception("Live scores failed to render")
        st.info(f"🏈 Live scores are unavailable right now: {e}")

    st.divider()

    # Load data
    try:
        summary = get_summary_data(SEASON)
        meme_stats = get_meme_stats(SEASON)
        data_loaded = True
    except Exception as e:
        st.warning(f"⚠️ Database not fully populated yet: {e}")
        st.info("🚀 App is starting up! Data will appear once Google Sheets access is configured.")
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
        data_loaded = False

    # Main dashboard layout - Weekly picks chart as main focus
    render_weekly_picks_chart(summary)

    st.divider()

    # Secondary layout - Mobile-optimized: stack on small screens
    col1, col2 = st.columns([1, 1])

    with col1:
        # Donut chart - Remaining players
        render_remaining_players_donut(summary)

    with col2:
        # Player search
        render_player_search()

    # Add some mobile spacing
    st.write("")

    # Meme stats section
    st.divider()
    render_meme_stats(meme_stats)

    # Pool Insights Section
    st.divider()
    st.markdown("### 📊 Pool Insights")

    # Create tabs for Pool Insights features
    tab1, tab2, tab3, tab4 = st.tabs(["Team of Doom", "Survivors", "Graveyard", "Elimination Tracker"])

    with tab1:
        try:
            db = SessionLocal()
            try:
                render_team_of_doom_widget(db, SEASON)
            finally:
                try:
                    db.close()
                except:
                    pass
        except Exception as e:
            st.info("💀 Team of Doom will appear once eliminations start happening!")

    with tab2:
        try:
            db = SessionLocal()
            try:
                render_survivors_widget(db, SEASON)
            finally:
                try:
                    db.close()
                except:
                    pass
        except Exception as e:
            st.info("✨ Survivors will appear once picks are made!")

    with tab3:
        try:
            db = SessionLocal()
            try:
                render_graveyard_widget(db, SEASON)
            finally:
                try:
                    db.close()
                except:
                    pass
        except Exception as e:
            st.info("⚰️ Graveyard will fill up as players get eliminated!")

    with tab4:
        try:
            db = SessionLocal()
            try:
                render_chaos_meter_widget(db, SEASON)
            finally:
                try:
                    db.close()
                except:
                    pass
        except Exception as e:
            st.info("📊 Elimination Tracker will activate once eliminations begin!")

    # Footer with update times
    render_footer(summary.get("last_updates", {}))

def render_remaining_players_donut(summary):
    """Render donut chart for remaining players"""
    st.subheader("Players Remaining")

    remaining = summary["entrants_remaining"]
    total = summary["entrants_total"]

    if total == 0:
        st.info("🏈 **No players loaded yet**\n\nPlayer data will appear once Google Sheets picks are imported via the hourly cron job.")
        return

    eliminated = total - remaining
    percentage = (remaining / total * 100) if total > 0 else 0

    # Create mobile-optimized donut chart with consistent colors
    mobile_colors = get_mobile_color_scheme()
    fig = go.Figure(data=[go.Pie(
        labels=['Remaining', 'Eliminated'],
        values=[remaining, eliminated],
        hole=0.6,
        marker_colors=[mobile_colors['remaining'], mobile_colors['eliminated']],
        textinfo='label',  # Only show labels for better mobile experience
        hovertemplate="<b>%{label}</b><br>Count: %{value}<br>Percentage: %{percent}<extra></extra>"
    )])

    # Add center annotation
    fig.update_layout(
        annotations=[dict(
            text=f"{percentage:.1f}%<br>{remaining}/{total}",
            x=0.5, y=0.5,
            font_size=14,
            showarrow=False,
            font_color="black"
        )]
    )

    # Render with mobile optimization
    render_mobile_chart(fig, 'donut')

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
        st.info("No picks data to display")
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
        background=APP_SURFACE,
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
    st.plotly_chart(fig, use_container_width=True, config=get_mobile_config())

    # This replaces the "Week N Picks Breakdown" table. The table listed team
    # and count, which the grid already shows in the same order; its only
    # unique content was a ✅/💀/🕐 glyph per team, now carried by the cell
    # itself. The grid gained an encoding, so it has to name the three it has.
    swatch = (
        'display:inline-block;width:11px;height:11px;'
        'border-radius:2px;vertical-align:-1px;'
    )
    sample = get_team_color_map().get(rows[0], "#666666")
    lifted = contrast_fill(sample, APP_SURFACE, EMPHASIS_MIN_CONTRAST)
    out_fill = eliminated_fill(sample, APP_SURFACE)
    st.caption(
        f'<span style="background:{lifted};{swatch}"></span> this week'
        ' &nbsp;·&nbsp; '
        f'<span style="background:{mute_color(sample, APP_SURFACE)};{swatch}"></span>'
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
    st.subheader("Find a Survivor")

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
                            "🔒" if row["locked"] and row["survived"] is None
                            else "✅" if row["survived"] is True
                            else "❌" if row["survived"] is False
                            else "⏳" if row["team"] is not None
                            else "—", axis=1)

                        # Add validity indicators
                        picks_df["Valid"] = picks_df["valid"].apply(lambda x: "✅" if x else "⚠️")

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

def render_meme_stats(meme_stats):
    """Render meme statistics section"""
    st.markdown("### 🎯 Notable Picks")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### 🤡 Dumbest Picks (Season)")
        dumbest = meme_stats["dumbest_picks"]

        if dumbest:
            # Create table data
            table_data = []
            for pick in dumbest[:5]:  # Show up to 5
                matchup = f"{pick['team']} vs {pick['opponent']}"
                table_data.append({
                    "Matchup": matchup,
                    "Week": pick['week'],
                    "Lost By": pick['margin'],
                    "Eliminated": pick['eliminated_count']
                })

            # Display as table
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("🤡 **No eliminations yet!**\n\nDumbest picks will appear once players start getting eliminated. The worse the loss, the higher the shame!")

    with col2:
        st.markdown("#### 💪 Big Balls (Risky Wins)")
        big_balls = meme_stats["big_balls_picks"]

        if big_balls:
            # Create table data
            table_data = []
            for pick in big_balls[:5]:  # Show up to 5
                # Create the matchup display
                if pick['road_win']:
                    matchup = f"{pick['team']} @ {pick['opponent']}"
                else:
                    matchup = f"{pick['team']} vs {pick['opponent']}"

                # Add indicators
                indicators = []
                if pick.get('was_underdog', False):
                    indicators.append("🐕")
                if pick['road_win']:
                    indicators.append("🛣️")

                indicator_str = " ".join(indicators) if indicators else ""

                # Create description
                description = ""
                if pick.get('point_spread') and pick.get('was_underdog'):
                    underdog_text = get_underdog_spread_text(
                        pick['team'],
                        pick.get('favorite_team'),
                        pick['point_spread']
                    )
                    if underdog_text:
                        description = underdog_text.capitalize()
                elif pick['road_win']:
                    description = "Road win"

                table_data.append({
                    "Matchup": f"{matchup} {indicator_str}".strip(),
                    "Week": pick['week'],
                    "Type": description,
                    "Players": pick['big_balls_count']
                })

            # Display as table
            df = pd.DataFrame(table_data)
            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.info("💪 **No risky wins yet!**\n\nBig balls picks show road wins and underdog victories. The riskier the pick, the bigger the glory!")

def render_last_updated_chip(last_updates):
    """Render last updated timestamp at top of page"""
    from datetime import timezone, timedelta

    # Prefer scores timestamp if present, else ingest
    ts = last_updates.get("update_scores") or last_updates.get("ingest_sheet")
    if ts:
        # Convert UTC to Pacific time (handles PST/PDT automatically)
        import pytz
        pacific = pytz.timezone('America/Los_Angeles')
        ts_pacific = ts.replace(tzinfo=timezone.utc).astimezone(pacific)
        label = ts_pacific.strftime("%m/%d %I:%M %p")
        tz_abbr = ts_pacific.strftime("%Z")  # PDT or PST
        st.caption(f"🕒 Last updated: {label} {tz_abbr}")

def render_footer(last_updates):
    """Render footer with update information"""
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        from datetime import timezone
        import pytz
        pacific = pytz.timezone('America/Los_Angeles')

        st.caption("**Data Sources:**")
        if "ingest_sheet" in last_updates and last_updates["ingest_sheet"]:
            sheet_time_pacific = last_updates["ingest_sheet"].replace(tzinfo=timezone.utc).astimezone(pacific)
            sheet_time = sheet_time_pacific.strftime("%m/%d %I:%M %p")
            tz_abbr = sheet_time_pacific.strftime("%Z")
            st.caption(f"📊 Picks: {sheet_time} {tz_abbr}")

        if "update_scores" in last_updates and last_updates["update_scores"]:
            scores_time_pacific = last_updates["update_scores"].replace(tzinfo=timezone.utc).astimezone(pacific)
            scores_time = scores_time_pacific.strftime("%m/%d %I:%M %p")
            tz_abbr = scores_time_pacific.strftime("%Z")
            st.caption(f"🏈 Scores: {scores_time} {tz_abbr}")

    with col2:
        st.caption("*Survivor Pool Dashboard - Real-time NFL elimination tracking*")

if __name__ == "__main__":
    main()