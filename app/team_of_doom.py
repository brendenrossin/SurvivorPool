#!/usr/bin/env python3
"""
Team of Doom - Shows which teams eliminated the most players
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Dict, Any
import os

def get_team_of_doom_data(db, current_season: int) -> Dict[str, Any]:
    """
    Get data for Team of Doom analysis - teams that eliminated the most players
    """
    from api.models import Pick, PickResult, Game, Player

    try:
        # Get all picks that resulted in elimination (survived = False)
        # Use team/week matching since game_id may not be set correctly
        eliminated_picks_query = db.query(
            Pick.team_abbr,
            Pick.week,
            Player.display_name,
            Game.home_team,
            Game.away_team,
            Game.winner_abbr,
            Game.home_score,
            Game.away_score
        ).join(
            PickResult, Pick.pick_id == PickResult.pick_id
        ).join(
            Game, (Game.home_team == Pick.team_abbr) | (Game.away_team == Pick.team_abbr)
        ).join(
            Player, Pick.player_id == Player.player_id
        ).filter(
            Pick.season == current_season,
            Game.season == current_season,
            Game.week == Pick.week,
            PickResult.survived == False,  # Only eliminated picks
            Game.home_score.isnot(None),
            Game.away_score.isnot(None)  # Only games with scores
        )

        eliminated_picks = eliminated_picks_query.all()

        if not eliminated_picks:
            return {
                "doom_teams": [],
                "total_eliminations": 0,
                "worst_week": None,
                "elimination_details": []
            }

        # Count eliminations by team
        doom_count = {}
        elimination_details = []

        for pick in eliminated_picks:
            team = pick.team_abbr
            week = pick.week
            player = pick.display_name

            # Determine opponent and score details
            if pick.home_team == team:
                opponent = pick.away_team
                team_score = pick.home_score
                opponent_score = pick.away_score
                home_away = "vs"
            else:
                opponent = pick.home_team
                team_score = pick.away_score
                opponent_score = pick.home_score
                home_away = "@"

            if team not in doom_count:
                doom_count[team] = {
                    "count": 0,
                    "victims": [],
                    "weeks": set(),
                    "games": []
                }

            doom_count[team]["count"] += 1
            doom_count[team]["victims"].append(player)
            doom_count[team]["weeks"].add(week)
            doom_count[team]["games"].append({
                "week": week,
                "opponent": opponent,
                "home_away": home_away,
                "team_score": team_score,
                "opponent_score": opponent_score,
                "player": player
            })

            elimination_details.append({
                "team": team,
                "week": week,
                "player": player,
                "opponent": opponent,
                "home_away": home_away,
                "score": f"{team_score}-{opponent_score}" if team_score is not None else "N/A"
            })

        # Sort teams by elimination count
        doom_teams = []
        for team, data in doom_count.items():
            doom_teams.append({
                "team": team,
                "eliminations": data["count"],
                "victims": data["victims"],
                "weeks_active": list(data["weeks"]),
                "games": data["games"],
                "average_per_week": data["count"] / len(data["weeks"]) if data["weeks"] else 0
            })

        doom_teams.sort(key=lambda x: x["eliminations"], reverse=True)

        # Find worst week (most eliminations in a single week)
        week_eliminations = {}
        for detail in elimination_details:
            week = detail["week"]
            if week not in week_eliminations:
                week_eliminations[week] = 0
            week_eliminations[week] += 1

        worst_week = max(week_eliminations.items(), key=lambda x: x[1]) if week_eliminations else None

        return {
            "doom_teams": doom_teams,
            "total_eliminations": len(eliminated_picks),
            "worst_week": worst_week,
            "elimination_details": elimination_details
        }

    except Exception as e:
        st.error(f"Error fetching Team of Doom data: {e}")
        return {
            "doom_teams": [],
            "total_eliminations": 0,
            "worst_week": None,
            "elimination_details": []
        }

def render_team_of_doom_widget(db, current_season: int):
    """
    Render the Team of Doom widget
    """
    st.subheader("💀 Team of Doom")
    st.caption("Teams that have eliminated the most players")

    # Get Team of Doom data
    doom_data = get_team_of_doom_data(db, current_season)

    if not doom_data["doom_teams"]:
        st.info("No eliminations yet this season!")
        return

    # Create columns for layout
    col1, col2 = st.columns([2, 1])

    with col1:
        # Bar chart of eliminations by team
        doom_teams = doom_data["doom_teams"][:10]  # Top 10

        df = pd.DataFrame(doom_teams)

        fig = px.bar(
            df,
            x="eliminations",
            y="team",
            orientation="h",
            title="Eliminations by Team",
            labels={"eliminations": "Players Eliminated", "team": "Team"},
            color="eliminations",
            color_continuous_scale="Reds"
        )

        fig.update_layout(
            height=400,
            yaxis={'categoryorder': 'total ascending'},
            showlegend=False
        )

        st.plotly_chart(fig, use_container_width=True)

    with col2:
        # Top doom teams summary
        st.markdown("### 💀 Doom Leaderboard")

        for i, team_data in enumerate(doom_teams[:5], 1):
            team = team_data["team"]
            count = team_data["eliminations"]

            # Try to load team logo
            logo_path = f"app/static/logos/{team}.png"

            if os.path.exists(logo_path):
                col_logo, col_info = st.columns([1, 3])
                with col_logo:
                    st.image(logo_path, width=40)
                with col_info:
                    st.markdown(f"**{i}. {team}**")
                    st.caption(f"{count} eliminations")
            else:
                st.markdown(f"**{i}. {team}** - {count} eliminations")

        # Worst week info
        if doom_data["worst_week"]:
            week_num, week_count = doom_data["worst_week"]
            st.markdown("### 💥 Worst Week")
            st.markdown(f"**Week {week_num}**")
            st.caption(f"{week_count} eliminations")

def render_doom_details(db, current_season: int):
    """
    Render detailed elimination breakdown
    """
    st.subheader("📊 Elimination Details")

    doom_data = get_team_of_doom_data(db, current_season)

    if not doom_data["elimination_details"]:
        st.info("No eliminations to show yet")
        return

    # Create DataFrame for detailed view
    details_df = pd.DataFrame(doom_data["elimination_details"])

    # Add week filter
    all_weeks = sorted(details_df["week"].unique())
    selected_week = st.selectbox(
        "Filter by week:",
        ["All Weeks"] + [f"Week {w}" for w in all_weeks]
    )

    if selected_week != "All Weeks":
        week_num = int(selected_week.split(" ")[1])
        details_df = details_df[details_df["week"] == week_num]

    # Display elimination table
    display_df = details_df.rename(columns={
        "week": "Week",
        "team": "Team",
        "player": "Player",
        "opponent": "vs/at",
        "home_away": "H/A",
        "score": "Final Score"
    })

    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # Summary stats
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total Eliminations", len(doom_data["elimination_details"]))

    with col2:
        if doom_data["doom_teams"]:
            worst_team = doom_data["doom_teams"][0]
            st.metric("Worst Team", f"{worst_team['team']} ({worst_team['eliminations']})")

    with col3:
        if doom_data["worst_week"]:
            week_num, week_count = doom_data["worst_week"]
            st.metric("Worst Week", f"Week {week_num} ({week_count})")