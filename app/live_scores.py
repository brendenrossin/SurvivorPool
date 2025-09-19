#!/usr/bin/env python3
"""
Live Scores Widget - Shows current week's games for picked teams only
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
import os

def get_live_scores_data(db, current_season: int, current_week: int) -> List[Dict[str, Any]]:
    """
    Get live scores for teams that players have picked this week
    DATA ONLY FROM DATABASE - NO API CALLS!
    (API calls happen via cron jobs only)
    """
    from api.models import Pick, Game, Player

    try:
        # Get all picks for current week
        picks_query = db.query(Pick, Player.display_name).join(
            Player, Pick.player_id == Player.player_id
        ).filter(
            Pick.season == current_season,
            Pick.week == current_week,
            Pick.team_abbr.is_not(None)
        )

        picks = picks_query.all()

        if not picks:
            return []

        # Get unique teams that were picked
        picked_teams = set(pick.Pick.team_abbr for pick in picks)

        # Get games for current week involving picked teams FROM DATABASE ONLY
        games_query = db.query(Game).filter(
            Game.season == current_season,
            Game.week == current_week
        ).filter(
            (Game.home_team.in_(picked_teams)) | (Game.away_team.in_(picked_teams))
        ).order_by(Game.kickoff)

        games = games_query.all()

        # Build the live scores data
        live_scores = []

        for game in games:
            # Find who picked teams in this game
            home_pickers = [
                pick.Player.display_name for pick in picks
                if pick.Pick.team_abbr == game.home_team
            ]
            away_pickers = [
                pick.Player.display_name for pick in picks
                if pick.Pick.team_abbr == game.away_team
            ]

            # Determine game status display
            if game.status == 'pre':
                status_display = f"🕐 {game.kickoff.strftime('%a %I:%M %p ET')}"
                score_display = "vs"
            elif game.status == 'in':
                status_display = "🔴 LIVE"
                score_display = f"{game.home_score} - {game.away_score}"
            elif game.status == 'final':
                status_display = "✅ FINAL"
                score_display = f"{game.home_score} - {game.away_score}"
                # Add winner indicator
                if game.winner_abbr == game.home_team:
                    status_display += f" ({game.home_team} WINS)"
                elif game.winner_abbr == game.away_team:
                    status_display += f" ({game.away_team} WINS)"
            else:
                status_display = game.status.upper()
                score_display = f"{game.home_score or 0} - {game.away_score or 0}"

            live_scores.append({
                'game_id': game.game_id,
                'away_team': game.away_team,
                'home_team': game.home_team,
                'away_score': game.away_score or 0,
                'home_score': game.home_score or 0,
                'status': game.status,
                'status_display': status_display,
                'score_display': score_display,
                'kickoff': game.kickoff,
                'away_pickers': away_pickers,
                'home_pickers': home_pickers,
                'has_pickers': len(home_pickers) > 0 or len(away_pickers) > 0
            })

        return live_scores

    except Exception as e:
        st.error(f"Error fetching live scores: {e}")
        return []

def render_live_scores_widget(db, current_season: int, current_week: int):
    """
    Render the live scores widget in Streamlit
    """
    from datetime import datetime, timedelta

    # Tuesday reset logic: show next week's games if it's Tuesday after Monday games
    today = datetime.now()
    if today.weekday() == 1:  # Tuesday (0=Monday, 1=Tuesday, etc.)
        # Check if Monday night game is over (typically ends by 11:30 PM ET = 3:30 AM UTC)
        if today.hour >= 4:  # 4 AM UTC = 11 PM PST previous day
            current_week += 1

    st.subheader(f"🏈 Live Scores - Week {current_week}")
    st.caption("Showing games for teams picked by players this week")

    # Get live scores data
    live_scores = get_live_scores_data(db, current_season, current_week)

    if not live_scores:
        st.info("🏈 **No games to show this week**\n\nPossible reasons:\n- No players have picked teams playing this week\n- Game data hasn't been loaded yet (check cron jobs)\n- It's early in the week and games haven't been scheduled")
        return

    # Sort by game status priority (live games first, then by kickoff time)
    def sort_key(game):
        status_priority = {'in': 0, 'pre': 1, 'final': 2}
        return (status_priority.get(game['status'], 3), game['kickoff'])

    live_scores.sort(key=sort_key)

    # Create columns for better layout
    cols = st.columns([1, 3, 1, 1, 3])

    # Header row
    with cols[0]:
        st.caption("**Away**")
    with cols[1]:
        st.caption("**Away Pickers**")
    with cols[2]:
        st.caption("**Score**")
    with cols[3]:
        st.caption("**Home**")
    with cols[4]:
        st.caption("**Home Pickers**")

    # Game rows
    for game in live_scores:
        cols = st.columns([1, 3, 1, 1, 3])

        # Away team logo and name
        with cols[0]:
            logo_path = f"app/static/logos/{game['away_team']}.png"
            if os.path.exists(logo_path):
                st.image(logo_path, width=40)
            st.write(f"**{game['away_team']}**")

        # Away team pickers
        with cols[1]:
            if game['away_pickers']:
                st.write(", ".join(game['away_pickers']))
            else:
                st.write("—")

        # Score/Status
        with cols[2]:
            st.write(f"**{game['score_display']}**")
            st.caption(game['status_display'])

        # Home team logo and name
        with cols[3]:
            logo_path = f"app/static/logos/{game['home_team']}.png"
            if os.path.exists(logo_path):
                st.image(logo_path, width=40)
            st.write(f"**{game['home_team']}**")

        # Home team pickers
        with cols[4]:
            if game['home_pickers']:
                st.write(", ".join(game['home_pickers']))
            else:
                st.write("—")

        # Add separator
        st.divider()

def render_compact_live_scores(db, current_season: int, current_week: int):
    """
    Render a more compact version for the sidebar or top of page
    """
    st.markdown("### 🏈 Live Scores")

    live_scores = get_live_scores_data(db, current_season, current_week)

    if not live_scores:
        st.caption("No games for picked teams")
        return

    # Show only live and final games in compact view
    active_games = [
        game for game in live_scores
        if game['status'] in ['in', 'final']
    ]

    if not active_games:
        next_game = min(live_scores, key=lambda x: x['kickoff'])
        st.caption(f"Next: {next_game['away_team']} @ {next_game['home_team']}")
        st.caption(f"{next_game['kickoff'].strftime('%a %I:%M %p ET')}")
        return

    for game in active_games:
        # Create a compact one-line display
        if game['status'] == 'in':
            icon = "🔴"
        elif game['status'] == 'final':
            icon = "✅"
        else:
            icon = "🕐"

        st.caption(
            f"{icon} {game['away_team']} {game['away_score']} - "
            f"{game['home_score']} {game['home_team']}"
        )