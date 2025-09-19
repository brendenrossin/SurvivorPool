#!/usr/bin/env python3
"""
Graveyard Board - Shows eliminated players and their tragic picks
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any
import os

def get_graveyard_data(db, current_season: int) -> List[Dict[str, Any]]:
    """
    Get data for eliminated players (the graveyard)
    """
    from api.models import Pick, PickResult, Game, Player

    try:
        # Get all eliminated players - those with at least one pick that didn't survive
        eliminated_query = db.query(
            Player.display_name,
            Pick.week,
            Pick.team_abbr,
            Game.home_team,
            Game.away_team,
            Game.winner_abbr,
            Game.home_score,
            Game.away_score,
            Game.kickoff
        ).join(
            Pick, Player.player_id == Pick.player_id
        ).join(
            PickResult, Pick.pick_id == PickResult.pick_id
        ).join(
            Game, PickResult.game_id == Game.game_id
        ).filter(
            Pick.season == current_season,
            PickResult.survived == False  # Only eliminated picks
        ).order_by(Pick.week, Player.display_name)

        eliminated = eliminated_query.all()

        graveyard = []
        for elimination in eliminated:
            player = elimination.display_name
            week = elimination.week
            team = elimination.team_abbr

            # Determine if home or away
            if elimination.home_team == team:
                opponent = elimination.away_team
                location = "vs"
                team_score = elimination.home_score
                opponent_score = elimination.away_score
            else:
                opponent = elimination.home_team
                location = "@"
                team_score = elimination.away_score
                opponent_score = elimination.home_score

            # Calculate margin of defeat
            margin = opponent_score - team_score if team_score is not None else None

            graveyard.append({
                "player": player,
                "week": week,
                "team": team,
                "opponent": opponent,
                "location": location,
                "team_score": team_score,
                "opponent_score": opponent_score,
                "margin": margin,
                "final_score": f"{team_score}-{opponent_score}" if team_score is not None else "N/A",
                "game_summary": f"{team} {location} {opponent}",
                "elimination_date": elimination.kickoff
            })

        return graveyard

    except Exception as e:
        st.error(f"Error fetching graveyard data: {e}")
        return []

def render_graveyard_widget(db, current_season: int):
    """
    Render the Graveyard Board widget
    """
    st.subheader("⚰️ Graveyard Board")
    st.caption("Rest in peace, eliminated players")

    # Get graveyard data
    graveyard_data = get_graveyard_data(db, current_season)

    if not graveyard_data:
        st.info("⚰️ **The graveyard is empty... for now**\n\nEliminated players will appear here once they pick losing teams. May they rest in peace! 🪦")
        return

    # Create DataFrame for display
    df = pd.DataFrame(graveyard_data)

    # Summary stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("💀 Total Eliminated", len(df))

    with col2:
        worst_week = df["week"].mode().iloc[0] if not df.empty else "N/A"
        worst_week_count = df[df["week"] == worst_week].shape[0] if worst_week != "N/A" else 0
        st.metric("🔥 Worst Week", f"Week {worst_week} ({worst_week_count})")

    with col3:
        if not df.empty and df["margin"].notna().any():
            worst_loss = df.loc[df["margin"].idxmax()]
            st.metric("🤡 Worst Loss", f"{worst_loss['margin']} pts")

    st.divider()

    # Graveyard table
    st.subheader("📋 Death Certificate")

    # Add week filter
    all_weeks = sorted(df["week"].unique()) if not df.empty else []
    selected_week = st.selectbox(
        "Filter by elimination week:",
        ["All Weeks"] + [f"Week {w}" for w in all_weeks],
        key="graveyard_week_filter"
    )

    filtered_df = df.copy()
    if selected_week != "All Weeks":
        week_num = int(selected_week.split(" ")[1])
        filtered_df = df[df["week"] == week_num]

    if filtered_df.empty:
        st.info("No eliminations in the selected week")
        return

    # Display graveyard table with emojis
    display_data = []
    for _, row in filtered_df.iterrows():
        # Add skull emoji for eliminated players
        player_display = f"💀 {row['player']}"

        # Add team logo if available
        team_logo = ""
        logo_path = f"app/static/logos/{row['team']}.png"
        if os.path.exists(logo_path):
            team_logo = "🏈"  # Use emoji since we can't embed images in tables

        display_data.append({
            "Player": player_display,
            "Week": row['week'],
            "Team": f"{team_logo} {row['team']}",
            "Game": row['game_summary'],
            "Score": row['final_score'],
            "Margin": f"-{row['margin']}" if row['margin'] is not None else "N/A"
        })

    display_df = pd.DataFrame(display_data)
    st.dataframe(display_df, use_container_width=True, hide_index=True)

def render_graveyard_timeline(db, current_season: int):
    """
    Render elimination timeline
    """
    st.subheader("📅 Elimination Timeline")

    graveyard_data = get_graveyard_data(db, current_season)

    if not graveyard_data:
        st.info("No eliminations to show yet")
        return

    # Group by week for timeline
    df = pd.DataFrame(graveyard_data)
    week_eliminations = df.groupby("week").size().reset_index(name="eliminations")

    # Create timeline chart
    fig = px.bar(
        week_eliminations,
        x="week",
        y="eliminations",
        title="Eliminations by Week",
        labels={"week": "Week", "eliminations": "Players Eliminated"},
        color="eliminations",
        color_continuous_scale="Reds"
    )

    fig.update_layout(
        height=300,
        showlegend=False,
        xaxis_title="Week",
        yaxis_title="Players Eliminated"
    )

    st.plotly_chart(fig, use_container_width=True)

    # Show worst elimination weeks
    if len(week_eliminations) > 0:
        worst_weeks = week_eliminations.nlargest(3, "eliminations")

        st.subheader("🔥 Bloodbath Weeks")
        for _, row in worst_weeks.iterrows():
            week = row["week"]
            count = row["eliminations"]
            victims = df[df["week"] == week]["player"].tolist()

            with st.expander(f"Week {week}: {count} eliminations"):
                st.write("**Casualties:**")
                for victim in victims:
                    victim_data = df[(df["week"] == week) & (df["player"] == victim)].iloc[0]
                    st.write(f"- 💀 **{victim}**: {victim_data['game_summary']} (Lost by {victim_data['margin']})")

def render_memorial_wall(db, current_season: int):
    """
    Render memorial wall with photos/names
    """
    st.subheader("🕯️ Memorial Wall")
    st.caption("In loving memory of their survivor pool hopes and dreams")

    graveyard_data = get_graveyard_data(db, current_season)

    if not graveyard_data:
        st.info("🕯️ No fallen heroes yet")
        return

    # Group players and show their elimination details
    df = pd.DataFrame(graveyard_data)

    # Create memorial cards
    cols = st.columns(3)
    for i, (_, player_data) in enumerate(df.iterrows()):
        col_index = i % 3

        with cols[col_index]:
            st.markdown(f"""
            <div style="border: 2px solid #333; padding: 10px; margin: 5px; text-align: center; background-color: #1a1a1a;">
                <h4>💀 {player_data['player']}</h4>
                <p><strong>Week {player_data['week']}</strong></p>
                <p>{player_data['game_summary']}</p>
                <p>Final Score: {player_data['final_score']}</p>
                <p><em>"They died as they lived... making questionable picks"</em></p>
            </div>
            """, unsafe_allow_html=True)