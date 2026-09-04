#!/usr/bin/env python3
"""
Survivors Board - Shows remaining players still in the pool
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from typing import List, Dict, Any
import os
from app.mobile_plotly_config import render_mobile_chart

def get_survivors_data(db, current_season: int, current_week: int = None) -> List[Dict[str, Any]]:
    """
    Get data for surviving players (players not yet eliminated)
    """
    from api.models import Pick, PickResult, Game, Player
    from sqlalchemy import or_, func

    try:
        # Get all players who have been eliminated
        eliminated_player_ids = db.query(Pick.player_id).join(
            PickResult, Pick.pick_id == PickResult.pick_id
        ).filter(
            Pick.season == current_season,
            PickResult.survived == False
        ).distinct().subquery()

        # Get all players who are NOT in the eliminated list
        survivors_query = db.query(
            Player.player_id,
            Player.display_name
        ).filter(
            ~Player.player_id.in_(eliminated_player_ids)
        ).order_by(Player.display_name)

        survivors = survivors_query.all()

        survivors_data = []
        for survivor in survivors:
            player_id = survivor.player_id
            player_name = survivor.display_name

            # Get their pick history
            picks = db.query(
                Pick.week,
                Pick.team_abbr,
                PickResult.survived,
                PickResult.game_id
            ).join(
                PickResult, Pick.pick_id == PickResult.pick_id
            ).filter(
                Pick.player_id == player_id,
                Pick.season == current_season
            ).order_by(Pick.week).all()

            # Calculate stats
            total_picks = len(picks)
            wins = sum(1 for p in picks if p.survived == True)
            pending = sum(1 for p in picks if p.survived is None)
            teams_used = [p.team_abbr for p in picks if p.team_abbr]

            # Get most recent pick
            latest_pick = picks[-1] if picks else None
            latest_week = latest_pick.week if latest_pick else 0
            latest_team = latest_pick.team_abbr if latest_pick else "N/A"
            latest_status = "✅ Won" if latest_pick and latest_pick.survived == True else ("⏳ Pending" if latest_pick and latest_pick.survived is None else "N/A")

            # Check if this week's game has started (for "left to play" metric)
            game_started = False
            if current_week and latest_pick and latest_pick.week == current_week and latest_pick.game_id:
                game = db.query(Game).filter(Game.game_id == latest_pick.game_id).first()
                if game and game.status in ['live', 'final']:
                    game_started = True

            survivors_data.append({
                "player": player_name,
                "total_picks": total_picks,
                "wins": wins,
                "pending": pending,
                "teams_used": teams_used,
                "latest_week": latest_week,
                "latest_team": latest_team,
                "latest_status": latest_status,
                "game_started": game_started,
                "current_week_pick": latest_pick.week == current_week if latest_pick else False
            })

        return survivors_data

    except Exception as e:
        st.error(f"Error fetching survivors data: {e}")
        return []

def render_survivors_widget(db, current_season: int):
    """
    Render the Survivors Board widget
    """
    from api.models import Game

    st.subheader("✨ Survivors Board")
    st.caption("Players still in the hunt for glory")

    # Find the current/latest week with games
    latest_week_result = db.query(Game.week).filter(
        Game.season == current_season
    ).order_by(Game.week.desc()).first()
    current_week = latest_week_result.week if latest_week_result else 1

    # Get survivors data with current week info
    survivors_data = get_survivors_data(db, current_season, current_week)

    if not survivors_data:
        st.info("🎉 **No survivors remain!**\n\nAll players have been eliminated. The pool is complete!")
        return

    # Create DataFrame for display
    df = pd.DataFrame(survivors_data)

    # Calculate "left to play" - survivors whose current week game hasn't started yet
    left_to_play = sum(1 for row in survivors_data
                       if row['current_week_pick'] and not row['game_started'])

    # Summary stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("🏆 Survivors Remaining", len(df))

    with col2:
        st.metric("⏳ Left to Play", left_to_play)

    with col3:
        # Show current week
        st.metric("📅 Current Week", f"Week {current_week}")

    st.divider()

    # Survivors table
    st.subheader("📋 Active Players")

    if df.empty:
        st.info("No active players")
        return

    # Display survivors table
    display_data = []
    for _, row in df.iterrows():
        # Add trophy emoji for survivors
        player_display = f"🏆 {row['player']}"

        # Format teams used
        teams_display = ", ".join(row['teams_used'][:3])  # Show first 3 teams
        if len(row['teams_used']) > 3:
            teams_display += f" +{len(row['teams_used']) - 3} more"

        display_data.append({
            "Player": player_display,
            "Picks": row['total_picks'],
            "Wins": row['wins'],
            "Pending": row['pending'],
            "Latest Pick": f"Week {row['latest_week']}: {row['latest_team']}" if row['latest_week'] > 0 else "No picks yet",
            "Status": row['latest_status']
        })

    display_df = pd.DataFrame(display_data)
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Show most commonly used teams among survivors
    st.divider()
    render_survivor_team_usage(df)

def render_survivor_team_usage(df):
    """
    Show which teams survivors are using most
    """
    st.subheader("🏈 Most Popular Teams (Among Survivors)")

    # Flatten all teams used by survivors
    all_teams = []
    for teams in df["teams_used"]:
        all_teams.extend(teams)

    if not all_teams:
        st.info("No team data available")
        return

    # Count team usage
    team_counts = pd.Series(all_teams).value_counts().reset_index()
    team_counts.columns = ["Team", "Picks"]

    # Create bar chart
    fig = px.bar(
        team_counts.head(10),
        x="Team",
        y="Picks",
        title="Top 10 Teams Used by Survivors",
        labels={"Picks": "Times Picked", "Team": "Team"},
        color="Picks",
        color_continuous_scale="Greens"
    )

    fig.update_layout(
        height=300,
        showlegend=False,
        xaxis_title="Team",
        yaxis_title="Times Picked"
    )

    # Use mobile optimization
    render_mobile_chart(fig, 'heatmap')

def render_survivor_timeline(db, current_season: int):
    """
    Render survivor count timeline
    """
    st.subheader("📈 Survival Rate Over Time")

    from api.models import Pick, PickResult, Player

    # Get survivor count per week
    survivors_data = get_survivors_data(db, current_season)

    if not survivors_data:
        st.info("No survivor data to display")
        return

    # Calculate survivors remaining after each week
    # This is a simplified version - in a real scenario, you'd query eliminations by week
    df = pd.DataFrame(survivors_data)

    total_players = len(df) + len(get_eliminated_count(db, current_season))

    # For now, show current snapshot
    st.info(f"📊 Currently {len(df)} out of {total_players} players remain ({len(df)/total_players*100:.1f}%)")

def get_eliminated_count(db, current_season: int) -> int:
    """Get count of eliminated players"""
    from api.models import Pick, PickResult

    eliminated_count = db.query(Pick.player_id).join(
        PickResult, Pick.pick_id == PickResult.pick_id
    ).filter(
        Pick.season == current_season,
        PickResult.survived == False
    ).distinct().count()

    return eliminated_count
