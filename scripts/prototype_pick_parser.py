"""PROTOTYPE - the measured starting point for GRPM-6's unconfirmed pick tally.

Not production code. It exists so the next session does not re-derive what was
already measured against ground truth.

Measured on week 1 of the 2025 season, comparing against the 252 picks the
Google Sheet eventually recorded:

    unique senders with a parsed pick : 187
    picks recorded in the sheet       : 252
    capture rate                      : 74.2%
    mean absolute share error         : 0.98 pts
    top-5 teams, chat vs sheet        : 5 of 5

The failure mode is UNDERCOUNTING, which is the safe direction - see
docs/design/groupme-recap-spec.md, "The unconfirmed pick tally".

Known gaps, in rough order of value:
  - roster posts ("Blake: Broncos Andrew: Philly ...") parse as nothing, and
    must NOT collapse to one pick per sender
  - team names wrapped in a sentence ("I'm taking the brownies") are missed
  - lead-in variants: "switching to THE Jags", "switch to", "hanging to"

Every 2025 week has ground truth, so each gap can be hill-climbed with a
measured before/after rather than argued about.

Usage:  python scripts/prototype_pick_parser.py --season 2025 --week 1
"""

import argparse
import collections
import json
import re
from datetime import datetime, timezone

from api.database import SessionLocal
from api.models import ChatMessage

with open("db/seed_team_map.json") as fh:
    _TEAMS = json.load(fh)["teams"]

TEAM_TOKENS: dict[str, str] = {}
for _abbr, _d in _TEAMS.items():
    _full = _d["name"].lower()
    TEAM_TOKENS[_abbr.lower()] = _abbr
    TEAM_TOKENS[_full] = _abbr
    TEAM_TOKENS[_full.split()[-1]] = _abbr                 # "cardinals"
    TEAM_TOKENS[" ".join(_full.split()[:-1])] = _abbr      # "arizona"

# Slang the pool actually uses. Extend this against ground truth, not intuition.
TEAM_TOKENS.update({
    "jags": "JAX", "niners": "SF", "9ers": "SF", "bolts": "LAC",
    "fins": "MIA", "phins": "MIA", "brownies": "CLE", "pats": "NE",
    "bucs": "TB", "cards": "ARI", "boys": "DAL", "hawks": "SEA",
    "skins": "WAS", "commies": "WAS", "gmen": "NYG", "g-men": "NYG",
    "philly": "PHI", "iggles": "PHI", "pack": "GB", "stillers": "PIT",
    "vikes": "MIN",
})

LEAD_IN = re.compile(
    r"^(switching to|switch to|switched to|going with|going|taking|"
    r"i'?m taking|im taking|give me|i'?ll take|ill take|hanging to|"
    r"sticking with|staying|locking in|gonna take|riding|rolling with|the)\s+",
    re.I,
)


def parse_team(text: str | None) -> str | None:
    """The team a message declares, or None if it is not a pick declaration.

    Deliberately strict: a message must reduce to a bare team token. Loosening
    this trades precision for coverage, and precision is what makes an
    unconfirmed tally trustworthy.
    """
    if not text:
        return None
    token = " ".join(text.split()).lower().strip(" .!?,🔒🙏😤🫡")
    for _ in range(4):
        stripped = LEAD_IN.sub("", token).strip(" .!?,")
        if stripped == token:
            break
        token = stripped
    return TEAM_TOKENS.get(token)


def tally(db, before: datetime) -> collections.Counter:
    """Picks per team from chat, deduped by sender with last declaration winning.

    Sender uniqueness is required - without it a switch counts twice. Mapping a
    sender to a sheet entrant is NOT required; the manager does that himself.
    """
    rows = (db.query(ChatMessage)
              .filter(ChatMessage.is_system.is_(False))
              .filter(ChatMessage.created_at < before)
              .order_by(ChatMessage.created_at)
              .all())

    per_sender: dict[str, str] = {}
    for row in rows:
        if row.sender_type == "bot":
            continue
        team = parse_team(row.text)
        if team:
            per_sender[row.sender_id] = team      # last declaration wins
    return collections.Counter(per_sender.values())


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    args = ap.parse_args()

    db = SessionLocal()
    try:
        from sqlalchemy import func
        from api.models import Game, Pick

        last_kick = (db.query(func.max(Game.kickoff))
                       .filter(Game.season == args.season, Game.week == args.week)
                       .scalar())
        if last_kick is None:
            print(f"no games for {args.season} week {args.week}")
            return 1

        chat = tally(db, before=last_kick)
        sheet = collections.Counter(
            t for (t,) in db.query(Pick.team_abbr)
                            .filter(Pick.season == args.season, Pick.week == args.week)
                            .all() if t)

        print(f"chat  : {sum(chat.values())} picks")
        print(f"sheet : {sum(sheet.values())} picks")
        if sheet:
            print(f"capture: {100 * sum(chat.values()) / sum(sheet.values()):.1f}%\n")
        print(f"{'TEAM':<5} {'CHAT':>5} {'SHEET':>6}")
        for team in sorted(set(chat) | set(sheet), key=lambda t: -sheet[t]):
            print(f"{team:<5} {chat[team]:>5} {sheet[team]:>6}")
        return 0
    finally:
        try:
            db.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
