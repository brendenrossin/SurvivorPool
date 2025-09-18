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

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.dashboard_data import (
    load_team_data,
    get_summary_data,
    get_player_data,
    get_meme_stats,
    search_players
)

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
        layout="wide"
    )

    # Header
    st.title(f"🏈 Survivor {SEASON} — Live Dashboard")

    # Load data
    try:
        summary = get_summary_data(SEASON)
        meme_stats = get_meme_stats(SEASON)
    except Exception as e:
        st.error(f"Error loading data: {e}")
        st.stop()

    # Main dashboard layout
    col1, col2 = st.columns([1, 2])

    with col1:
        # Donut chart - Remaining players
        render_remaining_players_donut(summary)

        # Player search
        render_player_search()

    with col2:
        # Weekly picks chart
        render_weekly_picks_chart(summary)

    # Meme stats section
    st.divider()
    render_meme_stats(meme_stats)

    # Footer with update times
    render_footer(summary.get("last_updates", {}))

def render_remaining_players_donut(summary):
    """Render donut chart for remaining players"""
    st.subheader("🎯 Players Remaining")

    remaining = summary["entrants_remaining"]
    total = summary["entrants_total"]
    eliminated = total - remaining
    percentage = (remaining / total * 100) if total > 0 else 0

    # Create donut chart
    fig = go.Figure(data=[go.Pie(
        labels=['Remaining', 'Eliminated'],
        values=[remaining, eliminated],
        hole=0.6,
        marker_colors=['#28a745', '#dc3545']
    )])

    fig.update_layout(
        annotations=[dict(text=f"{percentage:.1f}%<br>{remaining}/{total}",
                         x=0.5, y=0.5, font_size=20, showarrow=False)],
        showlegend=True,
        height=300,
        margin=dict(t=0, b=0, l=0, r=0)
    )

    st.plotly_chart(fig, use_container_width=True)

def render_weekly_picks_chart(summary):
    """Render stacked bar chart for weekly picks"""
    st.subheader("📊 Weekly Picks Distribution")

    if not summary["weeks"]:
        st.info("No picks data available yet")
        return

    # Prepare data for stacked bar chart
    chart_data = []
    for week_data in summary["weeks"]:
        week = week_data["week"]
        for team_data in week_data["teams"]:
            team = team_data["team"]
            count = team_data["count"]

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

    # Create stacked bar chart
    fig = px.bar(
        df,
        x="Week",
        y="Count",
        color="Team",
        color_discrete_map={team: color for team, color in
                           zip(df["Team"], df["Color"])},
        title="Team Picks by Week"
    )

    fig.update_layout(
        height=400,
        xaxis_title="Week",
        yaxis_title="Number of Picks",
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )

    st.plotly_chart(fig, use_container_width=True)

def render_player_search():
    """Render player search section"""
    st.subheader("🔍 Find a Player")

    # Search input
    search_query = st.text_input("Enter player name:", placeholder="e.g., Brent Rossin")

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
    st.subheader("🎭 Meme Stats")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**🤡 Dumbest Picks (Season)**")
        dumbest = meme_stats["dumbest_picks"]

        if dumbest:
            for i, pick in enumerate(dumbest[:3], 1):
                st.write(f"{i}. **{pick['player']}** - Week {pick['week']}")
                st.write(f"   {pick['team']} vs {pick['opponent']} (Lost by {pick['margin']})")
        else:
            st.info("No eliminated picks yet")

    with col2:
        st.write("**💪 Big Balls (Road Wins)**")
        big_balls = meme_stats["big_balls_picks"]

        if big_balls:
            for i, pick in enumerate(big_balls[:3], 1):
                st.write(f"{i}. **{pick['player']}** - Week {pick['week']}")
                st.write(f"   {pick['team']} @ {pick['opponent']} ✅")
        else:
            st.info("No road wins yet")

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