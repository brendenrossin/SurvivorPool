#!/usr/bin/env python3
"""
GOLD STANDARD Google Sheets Ingestion Logic

This module contains the canonical logic for parsing and ingesting survivor picks.
Both service account and OAuth ingestion methods use this same logic.

DO NOT DUPLICATE THIS LOGIC - update this file if changes are needed.
"""

import hashlib
import json
import os
from datetime import datetime, timezone
from sqlalchemy import text
from api.database import SessionLocal
from api.models import Player, Pick, PickResult, JobMeta
from api.job_locks import advisory_lock, LOCK_INGESTION_AND_SCORING

# The job_meta row monitor_oauth_health.py reads to decide if ingestion is alive.
INGEST_JOB_NAME = "ingest_sheet"


def parse_picks_data(raw_data):
    """Parse raw Google Sheets data into player picks

    Converts raw sheet rows into: {player_name: {week: team}}

    Args:
        raw_data: List of lists from Google Sheets (first row is header)

    Returns:
        dict: {player_name: {week_num: team_abbr}}
    """
    print("🧮 Parsing Google Sheets data...")

    if not raw_data or len(raw_data) < 2:
        print("⚠️ No data to parse")
        return {}

    players_data = {}

    # First row is header
    header = raw_data[0]
    rows = raw_data[1:]

    # Find week columns
    week_columns = []
    for i, col_name in enumerate(header):
        if col_name and col_name.startswith('Week ') and col_name.replace('Week ', '').isdigit():
            week_num = int(col_name.replace('Week ', ''))
            week_columns.append((i, week_num))

    print(f"   Found {len(week_columns)} week columns")

    # Parse each row
    for row_idx, row in enumerate(rows):
        try:
            # Get player name (first column)
            if not row or len(row) == 0:
                continue

            name = row[0].strip() if row[0] else ''
            if not name:
                continue

            # Initialize player if not seen
            if name not in players_data:
                players_data[name] = {}

            # Parse weekly picks
            for col_idx, week_num in week_columns:
                if col_idx < len(row):
                    team = row[col_idx].strip().upper() if row[col_idx] else ''
                    if team and team != '':
                        players_data[name][week_num] = team

        except Exception as e:
            print(f"⚠️ Error parsing row {row_idx + 2}: {e}")
            continue

    print(f"✅ Parsed {len(players_data)} players from Google Sheets")
    return players_data


def clear_season_data(db, season):
    """Remove one season's picks so they can be re-ingested from the sheet.

    Players are a season-independent identity table: the season lives on
    ``picks``, so a player is only deleted once they have no picks left in ANY
    season. This preserves prior seasons as history while still cleaning up
    players who dropped out of the pool entirely.

    Deleting picks cascades to ``pick_results`` via the foreign key.

    Args:
        db: SQLAlchemy session
        season: The season to clear (e.g. 2026)
    """
    print(f"🧹 Clearing season {season} picks...")

    db.execute(text("DELETE FROM picks WHERE season = :season"), {"season": season})

    # Drop players who no longer appear in any season. Deleting players still
    # referenced by prior-season picks would violate the picks.player_id FK.
    db.execute(text("""
        DELETE FROM players
        WHERE player_id NOT IN (SELECT DISTINCT player_id FROM picks)
    """))


def record_job_run(db, job_name, status, message):
    """Record a job's outcome in ``job_meta``.

    ``monitor_oauth_health.py`` reads this to decide whether ingestion is
    healthy, so a run that does not write here is invisible to monitoring no
    matter how well it went.

    ``last_success_at`` is only advanced on success - a later failure must not
    erase when ingestion last actually worked, since that gap is the signal.

    Args:
        db: SQLAlchemy session
        job_name: row key, e.g. ``INGEST_JOB_NAME``
        status: "success", "error" or "skipped"
        message: human-readable detail shown by the monitor
    """
    row = db.query(JobMeta).filter(JobMeta.job_name == job_name).first()
    if not row:
        row = JobMeta(job_name=job_name)
        db.add(row)

    now = datetime.now(timezone.utc)
    row.last_run_at = now
    row.status = status
    row.message = message
    if status == "success":
        row.last_success_at = now

    db.commit()


def _report(db, status, message):
    """Record an outcome without ever changing it.

    Monitoring is not worth losing an ingestion over, so a failure to write
    job_meta is logged and swallowed.
    """
    try:
        record_job_run(db, INGEST_JOB_NAME, status, message)
    except Exception as e:
        print(f"⚠️ Could not record job_meta ({status}): {e}")


FINGERPRINT_JOB_PREFIX = "ingest_sheet_fingerprint"


def fingerprint_job_name(season) -> str:
    """The job_meta key holding one season's last-ingested fingerprint.

    Keyed per season so rolling to a new one cannot inherit the old season's
    fingerprint and skip its first ingestion.
    """
    return f"{FINGERPRINT_JOB_PREFIX}:{season}"


def picks_fingerprint(players_data) -> str:
    """A stable hash of the parsed picks.

    Deliberately over the PARSED picks rather than the raw sheet rows. A
    reordered column, a formatting change or a new column parse_picks_data does
    not recognise would all change the raw bytes while changing nothing anyone
    cares about, and each would trigger a full clear-and-reingest. Hashing what
    was actually understood means only a real pick change costs anything.

    Sorted keys, because the API returns rows in no guaranteed order and order
    must not read as a change. Week keys are stringified so a JSON round trip
    cannot alter the hash.
    """
    canonical = {
        str(player): {str(week): team for week, team in sorted(weeks.items())}
        for player, weeks in players_data.items()
    }
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def read_fingerprint(db, season):
    """The fingerprint of the last ingestion for `season`, or None."""
    row = db.query(JobMeta).filter(
        JobMeta.job_name == fingerprint_job_name(season)).first()
    return row.message if row else None


def store_fingerprint(db, season, fingerprint) -> None:
    """Record what was just ingested, overwriting any previous value."""
    name = fingerprint_job_name(season)
    row = db.query(JobMeta).filter(JobMeta.job_name == name).first()
    if not row:
        row = JobMeta(job_name=name)
        db.add(row)

    now = datetime.now(timezone.utc)
    row.last_run_at = now
    row.last_success_at = now
    row.status = "success"
    row.message = fingerprint
    db.commit()


def ingest_is_unchanged(db, season, fingerprint) -> bool:
    """Whether re-ingesting `season` would be a no-op.

    Requires BOTH a matching fingerprint and picks actually present. A database
    that lost its picks while keeping the job_meta row would otherwise skip the
    very re-ingest that repairs it, permanently and silently.
    """
    if read_fingerprint(db, season) != fingerprint:
        return False
    return db.query(Pick).filter(Pick.season == season).first() is not None


def ingest_players_and_picks(players_data, source_label="google_sheets",
                             force=False):
    """Insert/update players and picks in database

    This is the GOLD STANDARD ingestion logic used by all methods.

    Skips the whole thing when the sheet has not changed since the last run,
    which is what makes an hourly schedule safe rather than merely cheap: the
    ingestion clears the season before rebuilding it, so every run is a window
    in which a partial read leaves the season thin. Fingerprinting keeps that
    window rare instead of hourly.

    Args:
        players_data: dict of {player_name: {week: team}}
        source_label: string to mark the source of picks
        force: ingest even if the fingerprint says nothing changed

    Returns:
        bool: True if successful (including a skip), False otherwise
    """
    db = SessionLocal()

    try:
        print("👥 Ingesting players and picks...")

        # Acquire advisory lock to prevent concurrent execution with score updates
        with advisory_lock(db, LOCK_INGESTION_AND_SCORING):
            season = int(os.getenv('NFL_SEASON', 2025))
            fingerprint = picks_fingerprint(players_data)

            # Checked inside the lock: a concurrent run that finished between
            # the fetch and here has already done this work, and outside the
            # lock both runs would read "changed" and both would rebuild.
            if not force and ingest_is_unchanged(db, season, fingerprint):
                print(f"⏭️  Sheet unchanged since last ingestion "
                      f"(fingerprint {fingerprint[:12]}), nothing to do")
                _report(db, "skipped",
                        f"sheet unchanged (fingerprint {fingerprint[:12]})")
                return True

            # Clear this season's picks so they can be re-ingested from the sheet.
            # Prior seasons are left untouched - see clear_season_data().
            clear_season_data(db, season)
            db.commit()
            print("✅ Existing data cleared")

            players_created = 0
            picks_created = 0
            picks_updated = 0

            for player_name, weekly_picks in players_data.items():
                # Get or create player
                player = db.query(Player).filter(Player.display_name == player_name).first()

                if not player:
                    player = Player(display_name=player_name)
                    db.add(player)
                    db.flush()  # Get ID
                    players_created += 1
                    print(f"   ➕ Created player: {player_name}")

                # Process weekly picks
                for week, team in weekly_picks.items():
                    # Check if pick already exists
                    existing_pick = db.query(Pick).filter(
                        Pick.player_id == player.player_id,
                        Pick.season == season,
                        Pick.week == week
                    ).first()

                    if existing_pick:
                        # Update if team changed
                        if existing_pick.team_abbr != team:
                            print(f"   🔄 Updating {player_name} Week {week}: {existing_pick.team_abbr} → {team}")
                            existing_pick.team_abbr = team
                            picks_updated += 1
                    else:
                        # Create new pick
                        new_pick = Pick(
                            player_id=player.player_id,
                            season=season,
                            week=week,
                            team_abbr=team,
                            source=source_label
                        )
                        db.add(new_pick)
                        picks_created += 1

            # Load-bearing. SessionLocal is autoflush=False, so the picks added
            # above are still pending in the identity map; process_all_eliminations
            # starts by querying picks for the season and would find none, quietly
            # recomputing eliminations against an empty pick set on every run.
            db.flush()

            # Re-calculate ALL elimination results using shared helper
            # This ensures consistency with app startup and cron jobs
            print("🔄 Re-calculating elimination results from current game data...")
            try:
                # Use SHARED HELPER to ensure consistency
                from jobs.update_scores import ScoreUpdater

                updater = ScoreUpdater()

                # Process ALL elimination logic (picks, stuck games, missing picks)
                elimination_results = updater.process_all_eliminations(db)

                print(f"   ✅ Elimination processing complete:")
                print(f"      - Pick results: {elimination_results['picks_updated']}")
                print(f"      - Stuck games fixed: {elimination_results['stuck_games_fixed']}")
                print(f"      - Missing pick eliminations: {elimination_results['missing_pick_eliminations']}")
            except Exception as e:
                print(f"   ⚠️ Failed to process eliminations: {e}")
                import traceback
                traceback.print_exc()

            db.commit()

            print(f"✅ Ingestion complete!")
            print(f"   Players created: {players_created}")
            print(f"   Picks created: {picks_created}")
            print(f"   Picks updated: {picks_updated}")

            # Report the sheet's totals, not just the deltas: a run that changes
            # nothing still says how many picks it saw, so a drop to zero shows up.
            total_players = len(players_data)
            total_picks = sum(len(weeks) for weeks in players_data.values())
            _report(db, "success", (
                f"Ingested {total_players} player{'' if total_players == 1 else 's'}, "
                f"{total_picks} pick{'' if total_picks == 1 else 's'} for season {season} "
                f"({players_created} new players, {picks_created} new picks, "
                f"{picks_updated} updated)"
            ))

            # Last, and only on the success path: a fingerprint written before
            # the ingestion finished would mark a half-done run as current and
            # skip the retry that would complete it.
            store_fingerprint(db, season, fingerprint)

        return True

    except RuntimeError as e:
        # Advisory lock timeout - log but don't fail
        if "advisory lock" in str(e):
            print(f"⏭️  Skipped ingestion (lock busy): {str(e)}")
            _report(db, "skipped", f"Lock busy, will retry next run: {e}")
            return False
        else:
            _report(db, "error", str(e))
            raise  # Re-raise other RuntimeErrors

    except Exception as e:
        print(f"❌ Database ingestion failed: {e}")
        db.rollback()
        import traceback
        traceback.print_exc()
        # After the rollback, so the failure record survives it.
        _report(db, "error", str(e))
        return False

    finally:
        db.close()


def populate_historical_eliminations():
    """Populate historical elimination data after successful ingestion"""
    print("\n🔄 Populating historical elimination data...")
    try:
        from manual_historical import mark_eliminations
        mark_eliminations()
        print("✅ Historical eliminations populated")
    except Exception as e:
        print(f"⚠️ Historical elimination population failed: {e}")
