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

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Configuration
SEASON = int(os.getenv("NFL_SEASON", 2025))
team_data = load_team_data()

def main():

    # Header
    st.title(f"Survivor {SEASON} — Live Dashboard")

    # Last updated chip at top for transparency
    try:
        summary_preview = get_summary_data(SEASON)
        render_last_updated_chip(summary_preview.get("last_updates", {}))
    except:
        pass  # If data not available, skip the timestamp

    # Live Scores Widget (top of page)
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

            # Render live scores from database only
            render_live_scores_widget(db, SEASON, current_week)
        finally:
            try:
                db.close()
            except:
                pass

        st.divider()
    except Exception as e:
        st.info("🏈 Live scores will appear once data is populated")

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
    st.header("Pool Insights")

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
                "Team": team,
                "Count": count
            })

    if not chart_data:
        st.info("No picks data to display")
        return

    df = pd.DataFrame(chart_data)

    # Sort data to ensure largest stack components are on bottom
    # Group by Week and sort by Count within each week (largest first = bottom of stack)
    df_sorted = df.sort_values(['Week', 'Count'], ascending=[True, False])

    # Create stacked bar chart with consistent color mapping
    fig = px.bar(
        df_sorted,
        x="Week",
        y="Count",
        color="Team",
        color_discrete_map=color_map,  # Use centralized color map
        title="📊 Team Picks by Week",
        category_orders={"Team": df_sorted.sort_values('Count', ascending=False)['Team'].unique()}
    )

    # Calculate proper annotation positions for stacked bars - mobile optimized
    week_annotations = []
    for week in df_sorted["Week"].unique():
        # Get data for this week and sort by count descending (largest first = bottom of stack)
        week_data = df_sorted[df_sorted["Week"] == week].sort_values('Count', ascending=False)
        cumulative_y = 0

        # Get top-3 teams for annotation (mobile optimization)
        top_3_teams = set(week_data.head(3)["Team"].tolist())

        for _, row in week_data.iterrows():
            # Only annotate top-3 teams with minimum threshold
            if row["Team"] in top_3_teams and row["Count"] >= 5:
                # Position text at center of this team's bar segment
                y_center = cumulative_y + (row["Count"] / 2)

                week_annotations.append({
                    "x": row["Week"],
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
    st.subheader("Notable Picks")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Dumbest Picks (Season)**")
        dumbest = meme_stats["dumbest_picks"]

        if dumbest:
            for i, pick in enumerate(dumbest[:3], 1):
                st.write(f"{i}. **{pick['team']} vs {pick['opponent']}** - Week {pick['week']}")
                st.write(f"   Lost by {pick['margin']} ({pick['eliminated_count']} players eliminated)")
        else:
            st.info("🤡 **No eliminations yet!**\n\nDumbest picks will appear once players start getting eliminated. The worse the loss, the higher the shame!")

    with col2:
        st.write("**Big Balls (Risky Wins)**")
        big_balls = meme_stats["big_balls_picks"]

        if big_balls:
            for i, pick in enumerate(big_balls[:3], 1):
                # Create the matchup display
                if pick['road_win']:
                    matchup = f"{pick['team']} @ {pick['opponent']}"
                else:
                    matchup = f"{pick['team']} vs {pick['opponent']}"

                # Add dog emoji for underdog wins
                underdog_emoji = " 🐕" if pick.get('was_underdog', False) else ""

                st.write(f"{i}. **{matchup}** ✅{underdog_emoji} - Week {pick['week']}")

                # Show spread info if available
                spread_info = ""
                if pick.get('point_spread') and pick.get('was_underdog'):
                    spread_info = f" (underdog by {pick['point_spread']} pts)"
                elif pick['road_win']:
                    spread_info = " (road win)"

                st.write(f"   ({pick['big_balls_count']} pairs of huge nuts{spread_info})")
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