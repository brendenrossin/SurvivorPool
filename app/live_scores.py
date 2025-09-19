#!/usr/bin/env python3
"""
Live Scores Widget - Shows current week's games
- When picks exist: shows games for picked teams only
- When no picks exist: shows ALL games to make dashboard engaging
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List, Dict, Any
import os

def create_game_display(game, home_pickers: List[str], away_pickers: List[str]) -> Dict[str, Any]:
    """Create display data for a single game"""
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

    return {
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
    }

def get_live_scores_data(db, current_season: int, current_week: int) -> List[Dict[str, Any]]:
    """
    Get live scores for teams that players have picked this week
    If no picks exist, show ALL games to make dashboard more engaging
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
            # No picks yet - show ALL games for this week to make dashboard engaging
            games_query = db.query(Game).filter(
                Game.season == current_season,
                Game.week == current_week
            ).order_by(Game.kickoff)

            games = games_query.all()

            # Build live scores with no pickers (show all games)
            live_scores = []
            for game in games:
                live_scores.append(create_game_display(game, [], []))

            return live_scores

        # Get unique teams that were picked
        picked_teams = set(pick[0].team_abbr for pick in picks)

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
                pick[1] for pick in picks  # pick[1] is Player.display_name
                if pick[0].team_abbr == game.home_team  # pick[0] is Pick
            ]
            away_pickers = [
                pick[1] for pick in picks  # pick[1] is Player.display_name
                if pick[0].team_abbr == game.away_team  # pick[0] is Pick
            ]

            live_scores.append(create_game_display(game, home_pickers, away_pickers))

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

    # Create compact live scores widget
    with st.expander(f"Week {current_week} Live Scores", expanded=False):

        # Get live scores data
        live_scores = get_live_scores_data(db, current_season, current_week)

        if not live_scores:
            st.info("**No games this week** - Game data will appear once loaded")
            return

        # Check if we're showing all games or just picked games
        has_any_pickers = any(game['has_pickers'] for game in live_scores)
        if has_any_pickers:
            st.caption("Showing games for teams picked by players this week")
        else:
            st.caption("No picks yet - showing all games this week")

        # Sort by game status priority (live games first, then by kickoff time)
        def sort_key(game):
            status_priority = {'in': 0, 'pre': 1, 'final': 2}
            return (status_priority.get(game['status'], 3), game['kickoff'])

        live_scores.sort(key=sort_key)

        # Show games in a compact table format
        for i in range(0, len(live_scores), 2):
            cols = st.columns(2)

            for j, col in enumerate(cols):
                if i + j < len(live_scores):
                    game = live_scores[i + j]

                    with col:
                        # Compact game display
                        if game['status'] == 'in':
                            status_emoji = "🔴"
                        elif game['status'] == 'final':
                            status_emoji = "✅"
                        else:
                            status_emoji = "🕐"

                        # Show team logos with score
                        from api.team_logos import get_team_logo_url

                        away_logo = get_team_logo_url(game['away_team'])
                        home_logo = get_team_logo_url(game['home_team'])

                        # Create a mobile-optimized display
                        col1, col2, col3 = st.columns([1, 1, 1])

                        with col1:
                            st.image(away_logo, width=30)
                            st.caption(game['away_team'])

                        with col2:
                            st.write(f"{status_emoji}")
                            if game['status'] != 'pre':
                                st.write(f"**{game['score_display']}**")
                            else:
                                st.write("vs")

                        with col3:
                            st.image(home_logo, width=30)
                            st.caption(game['home_team'])

                        # Show pickers if any
                        all_pickers = game['away_pickers'] + game['home_pickers']
                        if all_pickers:
                            st.caption(f"Picked by: {', '.join(all_pickers)}")
                        elif game['status'] == 'pre':
                            kickoff_time = game['kickoff'].strftime('%a %I:%M %p') if game['kickoff'] else 'TBD'
                            st.caption(f"Kickoff: {kickoff_time}")

                        st.write("")  # Add some spacing

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