"""
Survivor Pool Dashboard - Streamlit App
"""

import streamlit as st

# Configure Streamlit FIRST, before any other imports that might trigger Streamlit
st.set_page_config(
    page_title="Survivor 2025 - Live Dashboard",
    page_icon="🏈",
    layout="wide",
    initial_sidebar_state="collapsed"  # Better for mobile
)

import plotly.express as px
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
    get_player_data,
    get_meme_stats,
    search_players
)
from app.live_scores import render_live_scores_widget, render_compact_live_scores
from app.team_of_doom import render_team_of_doom_widget
from app.graveyard import render_graveyard_widget
from app.chaos_meter import render_chaos_meter_widget
from app.mobile_plotly_config import render_mobile_chart, get_mobile_color_scheme
from app.odds_helpers import get_underdog_spread_text

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Configuration
SEASON = int(os.getenv("NFL_SEASON", 2025))
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
                    from datetime import timezone, timedelta
                    pst_tz = timezone(timedelta(hours=-8))
                    ts_pst = ts.replace(tzinfo=timezone.utc).astimezone(pst_tz)
                    label = ts_pst.strftime("%m/%d %H:%M")
                    st.markdown(f'<span class="chip gray">🕒 Last updated: {label} PST</span>', unsafe_allow_html=True)
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
                weeks_played = len(summary_preview.get('weeks', []))
                kpi("Weeks Completed", f"{weeks_played:,}", "survival rounds", icon="📅")
    except:
        pass

    # Live Scores Widget
    try:
        from api.database import SessionLocal
        from api.models import Game

        # Get current week from database (NO API CALLS!)
        db = SessionLocal()
        try:
            # Find the latest week with games in database
            latest_week_result = db.query(Game.week).filter(
                Game.season == SEASON
            ).order_by(Game.week.desc()).first()

            current_week = latest_week_result.week if latest_week_result else 1

            # Render live scores widget (handles its own card-like styling with expander)
            render_live_scores_widget(db, SEASON, current_week)
        finally:
            try:
                db.close()
            except:
                pass
    except Exception as e:
        st.info("🏈 Live scores will appear once data is populated")

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
    tab1, tab2, tab3 = st.tabs(["Team of Doom", "Graveyard", "Elimination Tracker"])

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
                render_graveyard_widget(db, SEASON)
            finally:
                try:
                    db.close()
                except:
                    pass
        except Exception as e:
            st.info("⚰️ Graveyard will fill up as players get eliminated!")

    with tab3:
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

def get_team_color_map():
    """Get centralized team color mapping"""
    team_data = load_team_data()
    return {team: data.get("color", "#666666") for team, data in team_data["teams"].items()}

def render_weekly_picks_chart(summary):
    """Render stacked bar chart for weekly picks"""

    if not summary["weeks"]:
        st.info("📊 **No weekly picks data yet**\n\nPicks will appear once:\n1. Google Sheets data is imported (hourly cron)\n2. NFL scores are fetched (Sunday/Monday/Thursday cron)\n3. Picks are linked to games and processed")
        return

    # Get centralized color map
    color_map = get_team_color_map()

    # Prepare data for stacked bar chart
    chart_data = []
    for week_data in summary["weeks"]:
        week = week_data["week"]
        for team_item in week_data["teams"]:
            team = team_item["team"]
            count = team_item["count"]

            chart_data.append({
                "Week": f"Week {week}",
                "Week_Num": week,  # Keep numeric week for proper sorting
                "Team": team,
                "Count": count
            })

    if not chart_data:
        st.info("No picks data to display")
        return

    df = pd.DataFrame(chart_data)

    # Get overall team order by total count (largest first for bottom stacking)
    team_totals = df.groupby('Team')['Count'].sum().sort_values(ascending=False)
    team_order = team_totals.index.tolist()

    # CRITICAL: For proper stacking order, we need to sort by team order WITHIN each week
    # Plotly stacks in the order data appears in DataFrame, not category_orders
    df_for_stacking = []
    for week_num in sorted(df['Week_Num'].unique()):
        week_data = df[df['Week_Num'] == week_num]

        # Sort this week's data by team_order (largest total teams first = bottom of stack)
        for team in team_order:
            team_row = week_data[week_data['Team'] == team]
            if not team_row.empty:
                df_for_stacking.append(team_row.iloc[0])

    df_sorted = pd.DataFrame(df_for_stacking)

    # Create stacked bar chart with proper ordering
    fig = px.bar(
        df_sorted,
        x="Week",
        y="Count",
        color="Team",
        color_discrete_map=color_map,  # Use centralized color map
        title="📊 Team Picks by Week",
        category_orders={
            "Week": [f"Week {i}" for i in sorted(df['Week_Num'].unique())],  # Force numeric week order
            "Team": team_order  # Largest totals first (bottom of stack)
        }
    )

    # Calculate proper annotation positions for stacked bars - mobile optimized
    week_annotations = []
    # Process weeks in proper numeric order
    for week_num in sorted(df['Week_Num'].unique()):
        week_label = f"Week {week_num}"

        # Get data for this week sorted by team order (same as stacking order)
        week_data = df_sorted[df_sorted["Week"] == week_label]

        # Sort by the same team order used in the chart (largest totals first = bottom)
        week_data_ordered = []
        for team in team_order:
            team_row = week_data[week_data["Team"] == team]
            if not team_row.empty:
                week_data_ordered.append(team_row.iloc[0])

        cumulative_y = 0

        # Get top-3 teams by count for this specific week (for mobile optimization)
        week_teams_by_count = sorted(week_data_ordered, key=lambda x: x["Count"], reverse=True)
        top_3_teams = set([team["Team"] for team in week_teams_by_count[:3]])

        for row in week_data_ordered:
            # Only annotate top-3 teams with minimum threshold
            if row["Team"] in top_3_teams and row["Count"] >= 5:
                # Position text at center of this team's bar segment
                y_center = cumulative_y + (row["Count"] / 2)

                week_annotations.append({
                    "x": week_label,
                    "y": y_center,
                    "text": row["Team"]
                })

            cumulative_y += row["Count"]

    # Add mobile-friendly annotations with better contrast
    if week_annotations:
        fig.add_scatter(
            x=[ann["x"] for ann in week_annotations],
            y=[ann["y"] for ann in week_annotations],
            text=[ann["text"] for ann in week_annotations],
            mode="text",
            textfont=dict(size=9, color="white", family="Arial Black"),
            showlegend=False,
            hoverinfo="skip"
        )

    # Use mobile optimization
    render_mobile_chart(fig, 'bar_chart')

    # Add current week picks table
    try:
        from api.database import SessionLocal
        from api.models import Game, Pick

        # Get current week from database
        # Use the latest week with picks (not games), so we show Week 5 picks
        # even if Week 5 games haven't started yet
        db = SessionLocal()
        try:
            # Check latest week with picks
            latest_pick_week = db.query(Pick.week).filter(
                Pick.season == SEASON
            ).order_by(Pick.week.desc()).first()

            # Also check latest week with games
            latest_game_week = db.query(Game.week).filter(
                Game.season == SEASON
            ).order_by(Game.week.desc()).first()

            # Use whichever is higher (picks or games)
            pick_week = latest_pick_week.week if latest_pick_week else 1
            game_week = latest_game_week.week if latest_game_week else 1
            current_week = max(pick_week, game_week)
        finally:
            try:
                db.close()
            except:
                pass

        # Find current week's data in summary
        current_week_data = None
        for week_data in summary["weeks"]:
            if week_data["week"] == current_week:
                current_week_data = week_data
                break

        st.subheader(f"📋 Week {current_week} Picks Breakdown")

        if current_week_data and current_week_data["teams"]:
            # Get team game status for styling
            try:
                from api.models import Game, Pick, PickResult
                from sqlalchemy import text
                losing_teams = set()  # Teams that lost, tied, or caused eliminations (💀)
                winning_teams = set()  # Teams that won their games (✅)
                pending_teams = set()  # Teams with games not started yet (🕐)

                # Find all teams with games in current week
                week_games = db.query(Game).filter(
                    Game.week == current_week,
                    Game.season == SEASON
                ).all()

                for game in week_games:
                    if game.status == 'final' and game.home_score is not None and game.away_score is not None:
                        # CRITICAL: Handle ties - both teams are considered "losing" for survivor purposes
                        if game.home_score == game.away_score:
                            # TIE GAME - both teams cause eliminations!
                            losing_teams.add(game.home_team)
                            losing_teams.add(game.away_team)
                        elif game.home_score > game.away_score:
                            # Home team won
                            winning_teams.add(game.home_team)
                            losing_teams.add(game.away_team)
                        else:
                            # Away team won
                            winning_teams.add(game.away_team)
                            losing_teams.add(game.home_team)
                    elif game.status in ['pre', 'scheduled']:
                        # Games not started yet
                        pending_teams.add(game.home_team)
                        pending_teams.add(game.away_team)

                # NOTE: We only use game results, not database eliminations
                # This ensures emojis reflect current game status, not stale elimination data

            except Exception as e:
                losing_teams = set()
                winning_teams = set()
                pending_teams = set()

            # Create DataFrame for the table with emoji indicators
            table_data = []
            for team_item in current_week_data["teams"]:
                team = team_item["team"]

                # Determine emoji based on game status
                if team in losing_teams:
                    team_display = f"💀 {team}"  # Lost, tied, or eliminated
                elif team in winning_teams:
                    team_display = f"✅ {team}"  # Won their game
                elif team in pending_teams:
                    team_display = f"🕐 {team}"  # Game not started
                else:
                    team_display = team  # Default (no game data)

                table_data.append({
                    "Team Picked": team_display,
                    "Number of Survivors": team_item["count"]
                })

            # Sort by count descending
            table_data = sorted(table_data, key=lambda x: x["Number of Survivors"], reverse=True)

            # Display table (no background styling, just emojis)
            df_table = pd.DataFrame(table_data)
            st.dataframe(df_table, use_container_width=True, hide_index=True)
        else:
            st.info("📝 No picks uploaded to Google Sheet Tracker yet")

    except Exception as e:
        st.info("📝 No picks uploaded to Google Sheet Tracker yet")

def render_player_search():
    """Render player search section"""
    st.subheader("Find a Survivor")

    # Search input
    search_query = st.text_input("Enter survivor name:", placeholder="e.g., Travis Taylor")

    if search_query:
        # Search for matching players
        matching_players = search_players(search_query)

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
        # Convert UTC to PST (UTC-8)
        pst_tz = timezone(timedelta(hours=-8))
        ts_pst = ts.replace(tzinfo=timezone.utc).astimezone(pst_tz)
        label = ts_pst.strftime("%m/%d %H:%M")
        st.caption(f"🕒 Last updated: {label} (PST)")

def render_footer(last_updates):
    """Render footer with update information"""
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        from datetime import timezone, timedelta
        pst_tz = timezone(timedelta(hours=-8))

        st.caption("**Data Sources:**")
        if "ingest_sheet" in last_updates and last_updates["ingest_sheet"]:
            sheet_time_pst = last_updates["ingest_sheet"].replace(tzinfo=timezone.utc).astimezone(pst_tz)
            sheet_time = sheet_time_pst.strftime("%m/%d %H:%M")
            st.caption(f"📊 Picks: {sheet_time} PST")

        if "update_scores" in last_updates and last_updates["update_scores"]:
            scores_time_pst = last_updates["update_scores"].replace(tzinfo=timezone.utc).astimezone(pst_tz)
            scores_time = scores_time_pst.strftime("%m/%d %H:%M")
            st.caption(f"🏈 Scores: {scores_time} PST")

    with col2:
        st.caption("*Survivor Pool Dashboard - Real-time NFL elimination tracking*")

if __name__ == "__main__":
    main()