"""Score the unconfirmed tally against the season the sheet already recorded.

The tally is the one part of the recap work that can be hill-climbed: every
2025 week has ground truth in `picks`, so any change to api/pick_parser.py or
api/pick_tally.py gets a measured before/after instead of an argument.

    python scripts/score_pick_parser.py --season 2025

Capture is the count the widget leads with. Mean share error and top-5 answer
the question the widget is actually for - "is everyone piling onto Denver
again?" - and matter more than capture once capture is in the right range.
Share error is noisy in the late weeks, where a 20-pick sheet makes one pick
worth five points; read those rows with that in mind.
"""

import argparse
import collections
import statistics

from sqlalchemy import func

from api.database import SessionLocal
from api.models import Game, Pick
from api.pick_tally import tally_unconfirmed


def score_week(db, season: int, week: int) -> dict | None:
    """One week's comparison, or None if that week has no games."""
    if db.query(func.count(Game.game_id)).filter(
            Game.season == season, Game.week == week).scalar() == 0:
        return None

    chat = tally_unconfirmed(db, season, week)
    sheet = collections.Counter(
        team for (team,) in db.query(Pick.team_abbr)
        .filter(Pick.season == season, Pick.week == week).all() if team)

    chat_n, sheet_n = sum(chat.values()), sum(sheet.values())
    teams = set(chat) | set(sheet)
    share_error = (
        statistics.mean(abs(100 * chat[t] / chat_n - 100 * sheet[t] / sheet_n)
                        for t in teams)
        if chat_n and sheet_n and teams else float("nan"))

    def top(counter):
        return {t for t, _ in sorted(counter.items(),
                                     key=lambda kv: (-kv[1], kv[0]))[:5]}

    return {"week": week, "chat": chat_n, "sheet": sheet_n,
            "capture": 100 * chat_n / sheet_n if sheet_n else float("nan"),
            "share_error": share_error,
            "top5": len(top(chat) & top(sheet)) if chat_n and sheet_n else 0}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, default=2025)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        weeks = [w for (w,) in db.query(Pick.week)
                 .filter(Pick.season == args.season)
                 .distinct().order_by(Pick.week).all()]
        rows = [r for r in (score_week(db, args.season, w) for w in weeks)
                if r is not None]
        if not rows:
            print(f"no gradeable weeks for {args.season}")
            return 1

        print(f"{'WK':>3} {'CHAT':>5} {'SHEET':>6} {'CAPTURE':>8} "
              f"{'SHARE ERR':>10} {'TOP5':>5}")
        for r in rows:
            print(f"{r['week']:>3} {r['chat']:>5} {r['sheet']:>6} "
                  f"{r['capture']:>7.1f}% {r['share_error']:>9.2f}pt "
                  f"{r['top5']:>3}/5")

        chat_n = sum(r["chat"] for r in rows)
        sheet_n = sum(r["sheet"] for r in rows)
        # A week where the chat produced nothing has no distribution to compare,
        # and averaging its nan silently turned the whole season summary into
        # nan. Weeks like 2025's week 14 - 21 entrants left, nobody announcing -
        # are real, so they are excluded from the mean and counted out loud.
        graded = [r for r in rows if r["share_error"] == r["share_error"]]
        skipped = len(rows) - len(graded)
        print(f"\nseason capture   {100 * chat_n / sheet_n:.1f}%  "
              f"({chat_n}/{sheet_n})")
        print(f"mean share error "
              f"{statistics.mean(r['share_error'] for r in graded):.2f}pt"
              + (f"   [{skipped} week(s) with no parsed picks excluded]"
                 if skipped else ""))
        print(f"top-5 agreement  {sum(r['top5'] for r in rows)}/{5 * len(rows)}")
        return 0
    finally:
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
