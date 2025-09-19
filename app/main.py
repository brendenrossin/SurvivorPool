"""
Survivor Pool Dashboard - Streamlit App
"""

import streamlit as st
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

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Configuration
SEASON = int(os.getenv("NFL_SEASON", 2025))
team_data = load_team_data()

def main():
    st.set_page_config(
        page_title=f"Survivor {SEASON} - Live Dashboard",
        page_icon="🏈",
        layout="wide",
        initial_sidebar_state="collapsed"  # Better for mobile
    )

    # Header
    st.title(f"Survivor {SEASON} — Live Dashboard")

    # Live Scores Widget (top of page)
    try:
        from api.database import SessionLocal
        from api.models import Game

        # Get current week from database (NO API CALLS!)
        db = SessionLocal()

        # Find the latest week with games in database
        latest_week_result = db.query(Game.week).filter(
            Game.season == SEASON
        ).order_by(Game.week.desc()).first()

        current_week = latest_week_result.week if latest_week_result else 1

        # Render live scores from database only
        render_live_scores_widget(db, SEASON, current_week)
        db.close()

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

    # Create tabs for v1.5 features
    tab1, tab2, tab3 = st.tabs(["Team of Doom", "Graveyard", "Chaos Meter"])

    with tab1:
        try:
            db = SessionLocal()
            render_team_of_doom_widget(db, SEASON)
            db.close()
        except Exception as e:
            st.info("💀 Team of Doom will appear once eliminations start happening!")

    with tab2:
        try:
            db = SessionLocal()
            render_graveyard_widget(db, SEASON)
            db.close()
        except Exception as e:
            st.info("⚰️ Graveyard will fill up as players get eliminated!")

    with tab3:
        try:
            db = SessionLocal()
            render_chaos_meter_widget(db, SEASON)
            db.close()
        except Exception as e:
            st.info("🌪️ Chaos Meter will activate once games are completed!")

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

    # Create donut chart
    fig = go.Figure(data=[go.Pie(
        labels=['Remaining', 'Eliminated'],
        values=[remaining, eliminated],
        hole=0.6,
        marker_colors=['#28a745', '#dc3545'],
        textinfo='label'  # Only show labels, not percentages
    )])

    fig.update_layout(
        annotations=[dict(text=f"{percentage:.1f}%<br>{remaining}/{total}",
                         x=0.5, y=0.5, font_size=16, showarrow=False)],  # Smaller font for mobile
        showlegend=True,
        height=250,  # Reduced height for mobile
        font=dict(size=10),  # Smaller overall font
        margin=dict(t=0, b=0, l=0, r=0)
    )

    st.plotly_chart(fig, use_container_width=True)

def render_weekly_picks_chart(summary):
    """Render stacked bar chart for weekly picks"""

    if not summary["weeks"]:
        st.info("📊 **No weekly picks data yet**\n\nPicks will appear once:\n1. Google Sheets data is imported (hourly cron)\n2. NFL scores are fetched (Sunday/Monday/Thursday cron)\n3. Picks are linked to games and processed")
        return

    # Load team data for colors
    team_data = load_team_data()

    # Prepare data for stacked bar chart
    chart_data = []
    for week_data in summary["weeks"]:
        week = week_data["week"]
        for team_item in week_data["teams"]:
            team = team_item["team"]
            count = team_item["count"]

            # Get team color
            team_color = team_data["teams"].get(team, {}).get("color", "#666666")

            chart_data.append({
                "Week": f"Week {week}",
                "Team": team,
                "Count": count,
                "Color": team_color
            })

    if not chart_data:
        st.info("No picks data to display")
        return

    df = pd.DataFrame(chart_data)

    # Sort data to ensure largest stack components are on bottom
    # Group by Week and sort by Count within each week (largest first = bottom of stack)
    df_sorted = df.sort_values(['Week', 'Count'], ascending=[True, False])

    # Create stacked bar chart
    fig = px.bar(
        df_sorted,
        x="Week",
        y="Count",
        color="Team",
        color_discrete_map={team: color for team, color in
                           zip(df_sorted["Team"], df_sorted["Color"])},
        title="📊 Team Picks by Week",
        category_orders={"Team": df_sorted.sort_values('Count', ascending=False)['Team'].unique()}
    )

    # Add text annotations for teams with >10 picks
    for trace in fig.data:
        team_name = trace.name
        team_data = df_sorted[df_sorted["Team"] == team_name]

        x_positions = []
        y_positions = []
        texts = []

        for _, row in team_data.iterrows():
            if row["Count"] >= 10:  # Only annotate if 10+ picks
                x_positions.append(row["Week"])
                y_positions.append(row["Count"] / 2)  # Middle of the bar
                texts.append(team_name)

        if x_positions:  # Only add annotations if there are any
            fig.add_scatter(
                x=x_positions,
                y=y_positions,
                text=texts,
                mode="text",
                textfont=dict(size=10, color="white"),
                showlegend=False,
                hoverinfo="skip"
            )

    fig.update_layout(
        height=400,  # Reduced for mobile
        xaxis_title="Week",
        yaxis_title="Picks",
        font=dict(size=12),  # Better font size for mobile
        showlegend=False,  # Remove legend for mobile
        margin=dict(l=40, r=40, t=60, b=40),  # Reduced bottom margin since no legend
        # Mobile-friendly responsive settings
        autosize=True
    )

    st.plotly_chart(fig, use_container_width=True)

def render_player_search():
    """Render player search section"""
    st.subheader("Find a Player")

    # Search input
    search_query = st.text_input("Enter player name:", placeholder="e.g., Bishop Sankey")

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
        st.write("**Big Balls (Road Wins)**")
        big_balls = meme_stats["big_balls_picks"]

        if big_balls:
            for i, pick in enumerate(big_balls[:3], 1):
                st.write(f"{i}. **{pick['team']} @ {pick['opponent']}** ✅ - Week {pick['week']}")
                st.write(f"   ({pick['big_balls_count']} pairs of huge nuts)")
        else:
            st.info("💪 **No road wins yet!**\n\nBig balls picks will show players who picked away teams that won. Road wins = ultimate confidence!")

def render_footer(last_updates):
    """Render footer with update information"""
    st.divider()

    col1, col2 = st.columns(2)

    with col1:
        st.caption("**Data Sources:**")
        if "ingest_sheet" in last_updates and last_updates["ingest_sheet"]:
            sheet_time = last_updates["ingest_sheet"].strftime("%m/%d %H:%M")
            st.caption(f"📊 Picks: {sheet_time}")

        if "update_scores" in last_updates and last_updates["update_scores"]:
            scores_time = last_updates["update_scores"].strftime("%m/%d %H:%M")
            st.caption(f"🏈 Scores: {scores_time}")

    with col2:
        st.caption("*Survivor Pool Dashboard - Real-time NFL elimination tracking*")

if __name__ == "__main__":
    main()