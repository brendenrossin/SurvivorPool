#!/usr/bin/env python3
"""
One-time fix script to process missing pick results and auto-eliminations.
This simulates what update_scores.py SHOULD have done.
"""

import os
import sys
from dotenv import load_dotenv

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from api.database import SessionLocal
from api.models import Pick, PickResult, Game, Player
from sqlalchemy import and_
from datetime import datetime, timezone

load_dotenv()

def fix_missing_pick_results():
    """Process any picks that are missing their results for completed games"""
    db = SessionLocal()
    season = int(os.getenv("NFL_SEASON", 2025))
    fixed_count = 0

    try:
        print("🔍 Finding picks with completed games but no results...")

        # Get all picks with team_abbr that don't have results
        picks_needing_results = db.query(Pick).outerjoin(
            PickResult, Pick.pick_id == PickResult.pick_id
        ).filter(
            and_(
                Pick.season == season,
                Pick.team_abbr.isnot(None),
                PickResult.pick_id == None  # No result exists
            )
        ).all()

        print(f"Found {len(picks_needing_results)} picks without results")

        for pick in picks_needing_results:
            # Find the game for this pick
            game = db.query(Game).filter(
                and_(
                    Game.season == pick.season,
                    Game.week == pick.week,
                    ((Game.home_team == pick.team_abbr) | (Game.away_team == pick.team_abbr))
                )
            ).first()

            if not game:
                print(f"  ⚠️  No game found for pick_id {pick.pick_id} (Week {pick.week}, {pick.team_abbr})")
                continue

            if game.status != "final":
                print(f"  ⏳ Game not final yet for pick_id {pick.pick_id} (Week {pick.week}, {pick.team_abbr})")
                continue

            # Create the pick result
            now = datetime.now(timezone.utc)
            game_kickoff = game.kickoff.replace(tzinfo=timezone.utc) if game.kickoff.tzinfo is None else game.kickoff

            # Determine survival
            if game.winner_abbr is not None:
                survived = (pick.team_abbr == game.winner_abbr)
            else:
                # Tie game - nobody survives
                survived = False

            pick_result = PickResult(
                pick_id=pick.pick_id,
                game_id=game.game_id,
                is_valid=True,
                is_locked=True,
                survived=survived
            )
            db.add(pick_result)

            player = db.query(Player).filter(Player.player_id == pick.player_id).first()
            result_emoji = "✅" if survived else "❌"
            print(f"  {result_emoji} Created result for {player.display_name}: Week {pick.week} {pick.team_abbr} (survived={survived})")
            fixed_count += 1

        db.commit()
        print(f"\n✅ Fixed {fixed_count} missing pick results")
        return fixed_count

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()

def eliminate_missing_picks():
    """Auto-eliminate players who failed to submit picks for completed weeks"""
    db = SessionLocal()
    season = int(os.getenv("NFL_SEASON", 2025))
    current_week = 5  # Hardcode for now, could query ESPN
    eliminated_count = 0

    try:
        print("\n🔍 Checking for missing picks...")

        # Get alive players
        eliminated_player_ids = db.query(Pick.player_id).join(PickResult).filter(
            and_(Pick.season == season, PickResult.survived == False)
        ).distinct().all()
        eliminated_player_ids = {p[0] for p in eliminated_player_ids}

        all_active_players = db.query(Pick.player_id).filter(
            Pick.season == season
        ).distinct().all()
        all_active_players = {p[0] for p in all_active_players}

        alive_player_ids = all_active_players - eliminated_player_ids

        print(f"Found {len(alive_player_ids)} players still alive")

        # Check each completed week
        for week in range(1, current_week):
            week_games = db.query(Game).filter(
                and_(Game.season == season, Game.week == week)
            ).all()

            if not week_games:
                continue

            all_games_final = all(g.status == "final" for g in week_games)
            if not all_games_final:
                continue

            # Get players with picks for this week
            players_with_picks = db.query(Pick.player_id).filter(
                and_(
                    Pick.season == season,
                    Pick.week == week,
                    Pick.player_id.in_(alive_player_ids)
                )
            ).distinct().all()
            players_with_picks = {p[0] for p in players_with_picks}

            missing_pick_players = alive_player_ids - players_with_picks

            for player_id in missing_pick_players:
                # Check if already handled
                existing = db.query(Pick).filter(
                    and_(
                        Pick.player_id == player_id,
                        Pick.season == season,
                        Pick.week == week,
                        Pick.team_abbr == None
                    )
                ).first()

                if existing:
                    continue

                # Check if they had been participating
                last_pick = db.query(Pick).filter(
                    and_(
                        Pick.player_id == player_id,
                        Pick.season == season,
                        Pick.week < week
                    )
                ).order_by(Pick.week.desc()).first()

                if last_pick:
                    player = db.query(Player).filter(Player.player_id == player_id).first()
                    print(f"  ⚠️  Week {week}: Auto-eliminating {player.display_name} (last pick: Week {last_pick.week})")

                    # Create no-pick entry
                    no_pick = Pick(
                        player_id=player_id,
                        season=season,
                        week=week,
                        team_abbr=None,
                        source="auto_elimination"
                    )
                    db.add(no_pick)
                    db.flush()

                    # Create failed result
                    pick_result = PickResult(
                        pick_id=no_pick.pick_id,
                        game_id=None,
                        is_valid=False,
                        is_locked=True,
                        survived=False
                    )
                    db.add(pick_result)

                    eliminated_count += 1
                    alive_player_ids.discard(player_id)

        db.commit()
        print(f"\n✅ Auto-eliminated {eliminated_count} players for missing picks")
        return eliminated_count

    except Exception as e:
        db.rollback()
        print(f"❌ Error: {e}")
        raise
    finally:
        db.close()

if __name__ == "__main__":
    print("=" * 60)
    print("FIX MISSING PICK RESULTS AND AUTO-ELIMINATIONS")
    print("=" * 60)
    print()

    fixed = fix_missing_pick_results()
    eliminated = eliminate_missing_picks()

    print()
    print("=" * 60)
    print(f"SUMMARY: Fixed {fixed} pick results, eliminated {eliminated} players")
    print("=" * 60)
