#!/usr/bin/env python3
"""
Chaos Meter - Measures how unpredictable and chaotic each week was
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from typing import Dict, Any
import math

def calculate_chaos_score(db, current_season: int, week: int) -> Dict[str, Any]:
    """
    Calculate chaos score for a given week based on:
    - Number of eliminations
    - Upset victories (favorites losing)
    - Close games (decided by < 7 points)
    - Road wins
    - Overtime games
    """
    from api.models import Pick, PickResult, Game, Player

    try:
        # Get all games for the week
        games_query = db.query(Game).filter(
            Game.season == current_season,
            Game.week == week,
            Game.status == "final"  # Only completed games
        )
        games = games_query.all()

        if not games:
            return {"chaos_score": 0, "factors": {}, "total_games": 0}

        # Get eliminations for the week
        eliminations_query = db.query(Pick).join(
            PickResult, Pick.pick_id == PickResult.pick_id
        ).filter(
            Pick.season == current_season,
            Pick.week == week,
            PickResult.survived == False
        )
        eliminations = eliminations_query.count()

        # Calculate chaos factors
        factors = {
            "eliminations": 0,
            "close_games": 0,
            "blowouts": 0,
            "road_wins": 0,
            "upsets": 0,  # We'll estimate based on score margins
            "total_points": 0
        }

        total_score_diff = 0
        close_game_count = 0
        blowout_count = 0
        road_win_count = 0

        for game in games:
            if game.home_score is None or game.away_score is None:
                continue

            score_diff = abs(game.home_score - game.away_score)
            total_score_diff += score_diff

            # Close games (decided by 7 or fewer points)
            if score_diff <= 7:
                close_game_count += 1

            # Blowouts (decided by 21+ points)
            if score_diff >= 21:
                blowout_count += 1

            # Road wins (away team wins)
            if game.winner_abbr == game.away_team:
                road_win_count += 1

        factors["eliminations"] = eliminations
        factors["close_games"] = close_game_count
        factors["blowouts"] = blowout_count
        factors["road_wins"] = road_win_count
        factors["total_points"] = sum(g.home_score + g.away_score for g in games if g.home_score and g.away_score)

        # Calculate chaos score (0-100)
        chaos_score = 0

        # Eliminations factor (0-40 points) - more eliminations = more chaos
        elimination_factor = min(40, eliminations * 5)
        chaos_score += elimination_factor

        # Close games factor (0-25 points) - more close games = more chaos
        close_game_factor = min(25, (close_game_count / len(games)) * 25) if games else 0
        chaos_score += close_game_factor

        # Road wins factor (0-20 points) - more road wins = more chaos
        road_win_factor = min(20, (road_win_count / len(games)) * 20) if games else 0
        chaos_score += road_win_factor

        # Average margin factor (0-15 points) - closer average margins = more chaos
        avg_margin = total_score_diff / len(games) if games else 0
        margin_factor = max(0, 15 - (avg_margin / 2))  # Inverse relationship
        chaos_score += margin_factor

        return {
            "chaos_score": round(chaos_score, 1),
            "factors": factors,
            "total_games": len(games),
            "avg_margin": round(avg_margin, 1) if games else 0,
            "breakdown": {
                "eliminations": round(elimination_factor, 1),
                "close_games": round(close_game_factor, 1),
                "road_wins": round(road_win_factor, 1),
                "margins": round(margin_factor, 1)
            }
        }

    except Exception as e:
        st.error(f"Error calculating chaos score: {e}")
        return {"chaos_score": 0, "factors": {}, "total_games": 0}

def get_chaos_level_description(chaos_score: float) -> tuple:
    """Get chaos level description and emoji"""
    if chaos_score >= 80:
        return "🌪️ ABSOLUTE MAYHEM", "#FF4444"
    elif chaos_score >= 65:
        return "🔥 PURE CHAOS", "#FF6B35"
    elif chaos_score >= 50:
        return "⚡ HIGH DRAMA", "#FFB347"
    elif chaos_score >= 35:
        return "🎲 MODERATE CHAOS", "#87CEEB"
    elif chaos_score >= 20:
        return "😴 MILD EXCITEMENT", "#98FB98"
    else:
        return "💤 BORING WEEK", "#D3D3D3"

def render_chaos_meter_widget(db, current_season: int):
    """
    Render the Chaos Meter widget
    """
    st.subheader("🌪️ Chaos Meter")
    st.caption("Measuring the pure, unadulterated chaos of each week")

    # Get all weeks with completed games
    from api.models import Game

    weeks_query = db.query(Game.week).filter(
        Game.season == current_season,
        Game.status == "final"
    ).distinct().order_by(Game.week)

    completed_weeks = [week.week for week in weeks_query.all()]

    if not completed_weeks:
        st.info("🌪️ **No chaos to measure yet**\n\nThe Chaos Meter will spring to life once games are completed. Prepare for mayhem!")
        return

    # Create tabs for current week and historical
    tab1, tab2 = st.tabs(["📊 This Week", "📈 Historical Chaos"])

    with tab1:
        # Current/latest week chaos
        current_week = max(completed_weeks)
        chaos_data = calculate_chaos_score(db, current_season, current_week)

        col1, col2 = st.columns([2, 1])

        with col1:
            # Chaos meter gauge
            chaos_score = chaos_data["chaos_score"]
            level_desc, color = get_chaos_level_description(chaos_score)

            fig = go.Figure(go.Indicator(
                mode="gauge+number+delta",
                value=chaos_score,
                domain={'x': [0, 1], 'y': [0, 1]},
                title={'text': f"Week {current_week} Chaos Level"},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': color},
                    'steps': [
                        {'range': [0, 20], 'color': "#D3D3D3"},
                        {'range': [20, 35], 'color': "#98FB98"},
                        {'range': [35, 50], 'color': "#87CEEB"},
                        {'range': [50, 65], 'color': "#FFB347"},
                        {'range': [65, 80], 'color': "#FF6B35"},
                        {'range': [80, 100], 'color': "#FF4444"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 90
                    }
                }
            ))

            fig.update_layout(height=300)
            st.plotly_chart(fig, use_container_width=True)

            st.markdown(f"### {level_desc}")

        with col2:
            # Chaos breakdown
            st.markdown("### 🔍 Chaos Factors")

            factors = chaos_data["factors"]
            breakdown = chaos_data.get("breakdown", {})

            st.metric("💀 Eliminations", factors.get("eliminations", 0))
            st.caption(f"Chaos Points: {breakdown.get('eliminations', 0)}")

            st.metric("⚡ Close Games", factors.get("close_games", 0))
            st.caption(f"Chaos Points: {breakdown.get('close_games', 0)}")

            st.metric("🛣️ Road Wins", factors.get("road_wins", 0))
            st.caption(f"Chaos Points: {breakdown.get('road_wins', 0)}")

            st.metric("📊 Avg Margin", f"{chaos_data.get('avg_margin', 0)} pts")
            st.caption(f"Chaos Points: {breakdown.get('margins', 0)}")

    with tab2:
        # Historical chaos chart
        st.subheader("📈 Season Chaos Tracker")

        # Calculate chaos for all completed weeks
        chaos_history = []
        for week in completed_weeks:
            week_chaos = calculate_chaos_score(db, current_season, week)
            chaos_history.append({
                "week": week,
                "chaos_score": week_chaos["chaos_score"],
                "eliminations": week_chaos["factors"].get("eliminations", 0)
            })

        if chaos_history:
            df = pd.DataFrame(chaos_history)

            # Line chart of chaos over time
            fig = go.Figure()

            fig.add_trace(go.Scatter(
                x=df["week"],
                y=df["chaos_score"],
                mode='lines+markers+text',
                text=[get_chaos_level_description(score)[0].split()[1] for score in df["chaos_score"]],
                textposition="top center",
                line=dict(color='#FF6B35', width=3),
                marker=dict(size=10),
                name="Chaos Score"
            ))

            fig.update_layout(
                title="Chaos Score by Week",
                xaxis_title="Week",
                yaxis_title="Chaos Score",
                height=400,
                yaxis=dict(range=[0, 100])
            )

            st.plotly_chart(fig, use_container_width=True)

            # Chaos leaderboard
            st.subheader("🏆 Most Chaotic Weeks")

            top_chaos = df.nlargest(5, "chaos_score")
            for i, (_, week_data) in enumerate(top_chaos.iterrows(), 1):
                week = week_data["week"]
                score = week_data["chaos_score"]
                desc, color = get_chaos_level_description(score)

                st.markdown(f"""
                **{i}. Week {week}** - {score}/100

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