#!/usr/bin/env python3
"""
Chaos Meter - Measures how unpredictable and chaotic each week was
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, Any
import math
from app.mobile_plotly_config import render_mobile_chart, get_mobile_color_scheme

def calculate_elimination_percentage(db, current_season: int, week: int) -> Dict[str, Any]:
    """
    Calculate elimination percentage for a given week:
    Percentage = eliminations in this week / players that made it to this week
    """
    from api.models import Pick, PickResult, Player

    try:
        # Get total players who originally started
        total_original_players = db.query(Player).count()

        # Get players eliminated in previous weeks (before this week)
        eliminated_before_week = db.query(Pick.player_id).join(
            PickResult, Pick.pick_id == PickResult.pick_id
        ).filter(
            Pick.season == current_season,
            Pick.week < week,
            PickResult.survived == False
        ).distinct().count()

        # Get players eliminated in this specific week
        eliminated_this_week = db.query(Pick.player_id).join(
            PickResult, Pick.pick_id == PickResult.pick_id
        ).filter(
            Pick.season == current_season,
            Pick.week == week,
            PickResult.survived == False
        ).distinct().count()

        # Players that made it to this week (started minus eliminated before)
        players_entering_week = total_original_players - eliminated_before_week

        # Calculate elimination percentage for this week
        week_elimination_percentage = (eliminated_this_week / players_entering_week * 100) if players_entering_week > 0 else 0

        # Calculate cumulative elimination percentage (total eliminated / original total)
        total_eliminated = eliminated_before_week + eliminated_this_week
        cumulative_elimination_percentage = (total_eliminated / total_original_players * 100) if total_original_players > 0 else 0

        return {
            "week_elimination_percentage": round(week_elimination_percentage, 1),
            "cumulative_elimination_percentage": round(cumulative_elimination_percentage, 1),
            "eliminated_this_week": eliminated_this_week,
            "players_entering_week": players_entering_week,
            "total_eliminated": total_eliminated,
            "total_original_players": total_original_players,
            "survivors_remaining": total_original_players - total_eliminated
        }

    except Exception as e:
        st.error(f"Error calculating elimination percentage: {e}")
        return {
            "week_elimination_percentage": 0,
            "cumulative_elimination_percentage": 0,
            "eliminated_this_week": 0,
            "players_entering_week": 0,
            "total_eliminated": 0,
            "total_original_players": 0,
            "survivors_remaining": 0
        }

def get_elimination_level_description(elimination_percentage: float) -> tuple:
    """Get elimination level description and emoji based on weekly elimination percentage"""
    if elimination_percentage >= 25:
        return "🩸 BLOODBATH", "#FF4444"
    elif elimination_percentage >= 15:
        return "💀 MASSACRE", "#FF6B35"
    elif elimination_percentage >= 10:
        return "⚡ BRUTAL WEEK", "#FFB347"
    elif elimination_percentage >= 5:
        return "🎯 STEADY CUTS", "#87CEEB"
    elif elimination_percentage >= 1:
        return "😌 LIGHT CASUALTIES", "#98FB98"
    else:
        return "😴 SAFE WEEK", "#D3D3D3"

def render_chaos_meter_widget(db, current_season: int):
    """
    Render the Elimination Tracker widget (formerly Chaos Meter)
    """
    st.subheader("📊 Elimination Tracker")
    st.caption("Tracking survivor elimination rates week by week")

    # Get all weeks with picks (show current week even if no eliminations yet)
    from api.models import Game, Pick, PickResult

    weeks_query = db.query(Pick.week).filter(
        Pick.season == current_season
    ).distinct().order_by(Pick.week)

    available_weeks = [week.week for week in weeks_query.all()]

    if not available_weeks:
        st.info("📊 **No elimination data yet**\n\nThe Elimination Tracker will activate once picks are processed and eliminations begin!")
        return

    # Create tabs for current week and historical
    tab1, tab2 = st.tabs(["📊 Latest Week", "📈 Season Tracker"])

    with tab1:
        # Latest week elimination data
        current_week = max(available_weeks)
        elimination_data = calculate_elimination_percentage(db, current_season, current_week)

        col1, col2 = st.columns([2, 1])

        with col1:
            # Elimination percentage gauge
            week_percentage = elimination_data["week_elimination_percentage"]
            level_desc, color = get_elimination_level_description(week_percentage)

            fig = go.Figure(go.Indicator(
                mode="gauge+number",
                value=week_percentage,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': f"Week {current_week} Elimination Rate"},
                gauge={
                    'axis': {'range': [None, 30]},  # Max 30% for scale
                    'bar': {'color': color},
                    'steps': [
                        {'range': [0, 1], 'color': "#D3D3D3"},
                        {'range': [1, 5], 'color': "#98FB98"},
                        {'range': [5, 10], 'color': "#87CEEB"},
                        {'range': [10, 15], 'color': "#FFB347"},
                        {'range': [15, 25], 'color': "#FF6B35"},
                        {'range': [25, 30], 'color': "#FF4444"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 25
                    }
                },
                number={'suffix': "%"}
            ))

            # Use mobile optimization for gauge
            render_mobile_chart(fig, 'gauge')

            st.markdown(f"### {level_desc}")

        with col2:
            # Elimination breakdown
            st.markdown("### 📈 Week Stats")

            st.metric("💀 Eliminated This Week", elimination_data["eliminated_this_week"])

            st.metric("👥 Entered This Week", elimination_data["players_entering_week"])

            st.metric("🏆 Still Alive", elimination_data["survivors_remaining"])

            st.metric("📊 Cumulative Eliminated", f"{elimination_data['cumulative_elimination_percentage']:.1f}%")

    with tab2:
        # Historical elimination chart
        st.subheader("📈 Season Elimination Tracker")

        # Calculate elimination percentages for all weeks
        elimination_history = []
        for week in available_weeks:
            week_data = calculate_elimination_percentage(db, current_season, week)
            elimination_history.append({
                "week": week,
                "cumulative_percentage": week_data["cumulative_elimination_percentage"],
                "week_percentage": week_data["week_elimination_percentage"],
                "survivors_remaining": week_data["survivors_remaining"]
            })

        if elimination_history:
            df = pd.DataFrame(elimination_history)

            # Line chart of cumulative eliminations over time
            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=df["week"],
                y=df["cumulative_percentage"],
                mode='lines+markers',
                line=dict(color='#FF6B35', width=3),
                marker=dict(size=10),
                name="Cumulative Eliminations %",
                hovertemplate="Week %{x}<br>Eliminated: %{y:.1f}%<extra></extra>"
            ))

            # Set y-axis range before mobile optimization
            fig.update_yaxes(range=[0, max(df["cumulative_percentage"]) + 5])

            # Use mobile optimization for line chart
            render_mobile_chart(fig, 'line_chart')

            # Worst elimination weeks
            st.subheader("💀 Worst Elimination Weeks")

            worst_weeks = df.nlargest(5, "week_percentage")
            for i, (_, week_data) in enumerate(worst_weeks.iterrows(), 1):
                week = week_data["week"]
                percentage = week_data["week_percentage"]
                desc, color = get_elimination_level_description(percentage)

                st.markdown(f"""
                **{i}. Week {week}** - {percentage:.1f}% eliminated

                {desc}
                """)

def render_chaos_explanation():
    """Explain how chaos score is calculated"""
    st.subheader("🤔 How Chaos is Measured")

    st.markdown("""
    The **Chaos Meter** calculates a score from 0-100 based on:

    ### 📊 Chaos Factors (Max Points)
    - **💀 Eliminations (40 pts)**: More survivor eliminations = more chaos
    - **⚡ Close Games (25 pts)**: Games decided by ≤7 points create tension
    - **🛣️ Road Wins (20 pts)**: Away teams winning is unexpected
    - **📊 Game Margins (15 pts)**: Closer average margins = more unpredictable

    ### 🌪️ Chaos Levels
    - **💤 0-20**: Boring Week (chalk holds, no surprises)
    - **😴 20-35**: Mild Excitement (a few upsets)
    - **🎲 35-50**: Moderate Chaos (decent drama)
    - **⚡ 50-65**: High Drama (lots of close games)
    - **🔥 65-80**: Pure Chaos (eliminations everywhere)
    - **🌪️ 80-100**: ABSOLUTE MAYHEM (survivor pool massacre)
    """)

def render_weekly_chaos_summary(db, current_season: int, week: int):
    """Render a compact chaos summary for a specific week"""
    chaos_data = calculate_chaos_score(db, current_season, week)
    chaos_score = chaos_data["chaos_score"]
    level_desc, color = get_chaos_level_description(chaos_score)

    st.markdown(f"""
    ### Week {week} Chaos: {chaos_score}/100
    **{level_desc}**

    - 💀 {chaos_data['factors'].get('eliminations', 0)} eliminations
    - ⚡ {chaos_data['factors'].get('close_games', 0)} close games
    - 🛣️ {chaos_data['factors'].get('road_wins', 0)} road wins
    """)

    return chaos_score