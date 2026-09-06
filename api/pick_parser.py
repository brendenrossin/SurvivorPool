"""Decide whether a GroupMe message declares a pick, and for which team.

This is the whole of the text logic behind the unconfirmed tally. It is pure -
no database, no Streamlit - so the question "is this a pick?" can be tested
directly against the strings the pool actually posts.

The parser is deliberately strict: a message must reduce to a bare team token
after known decoration is stripped. Loosening it far enough to catch
conversational declarations ("Lions pls", "LAC for me") also catches banter,
because `boys` is a Dallas token and the group says "good luck boys" a lot. The
failure mode is undercounting, which is the safe direction for a number the UI
labels unconfirmed. See docs/design/groupme-recap-spec.md.

Every rule here was measured against the 2025 sheet before being added; see
scripts/score_pick_parser.py for the harness that does the measuring.
"""

import json
import re
from pathlib import Path

_SEED = Path(__file__).resolve().parent.parent / "db" / "seed_team_map.json"


def _build_tokens() -> dict[str, str]:
    """Map every unambiguous way of naming a team to its abbreviation.

    Tokens that name two teams are dropped rather than resolved. "los angeles"
    is both LAR and LAC and "new york" is both NYG and NYJ; leaving them in let
    dict insertion order decide which team a message meant, which is a coin
    flip dressed up as a parse.
    """
    with open(_SEED) as fh:
        teams = json.load(fh)["teams"]

    claims: dict[str, set[str]] = {}

    def claim(token: str, abbr: str) -> None:
        claims.setdefault(token, set()).add(abbr)

    for abbr, data in teams.items():
        full = data["name"].lower()
        words = full.split()
        claim(abbr.lower(), abbr)
        claim(full, abbr)
        claim(words[-1], abbr)                 # "cardinals"
        claim(" ".join(words[:-1]), abbr)      # "arizona", "los angeles"

    # Slang the pool actually uses. Extend against ground truth, not intuition.
    for token, abbr in {
        "jags": "JAX", "niners": "SF", "9ers": "SF", "bolts": "LAC",
        "fins": "MIA", "phins": "MIA", "brownies": "CLE", "pats": "NE",
        "bucs": "TB", "cards": "ARI", "boys": "DAL", "hawks": "SEA",
        "skins": "WAS", "commies": "WAS", "gmen": "NYG", "g-men": "NYG",
        "philly": "PHI", "iggles": "PHI", "pack": "GB", "stillers": "PIT",
        "vikes": "MIN", "cinci bengals": "CIN", "kc chiefs": "KC",
        "ne patriots": "NE",
    }.items():
        claim(token, abbr)

    return {token: next(iter(abbrs))
            for token, abbrs in claims.items()
            if len(abbrs) == 1 and token}


TEAM_TOKENS = _build_tokens()

# Dues and pick get posted in one breath: "Paid - Jags", "paid + chargers".
# 29 messages in 2025 and still in use in 2026, all of them otherwise unparsed.
PAID_PREFIX = re.compile(r"^paid\b[\s.,\-+/|:;–—]*", re.I)

LEAD_IN = re.compile(
    r"^(switching to|switch to|switched to|going with|going|taking|"
    r"i'?m taking|im taking|give me|i'?ll take|ill take|hanging to|"
    r"sticking with|staying|locking in|gonna take|riding|rolling with|the)\s+",
    re.I,
)

# Trailing decoration: emoji, variation selectors, ZWJ, skin-tone modifiers and
# ordinary punctuation. Matched only at the ends, never inside, so a team name
# wrapped in a sentence still fails to parse.
_EDGE = (
    r"\s.,!?*'\"“”‘’…:;\-+/|~"
    r"\U0001F000-\U0001FAFF"      # pictographs, symbols, supplemental
    r"\U0001F1E6-\U0001F1FF"      # regional indicators (flags)
    r"☀-➿"              # misc symbols and dingbats
    r"⬀-⯿←-⇿"
    r"︎️‍�"   # variation selectors, ZWJ, replacement char
    r"\U0001F3FB-\U0001F3FF"      # skin tone modifiers
)
STRIP_EDGES = re.compile(f"^[{_EDGE}]+|[{_EDGE}]+$")


def parse_team(text: str | None) -> str | None:
    """The team a message declares, or None if it is not a pick declaration.

    Strips, in order: surrounding whitespace and decoration, a wrapping pair of
    parentheses, a "Paid" prefix, and any stacked lead-ins. What survives must
    be exactly a team token; anything else is not a declaration.
    """
    if not text:
        return None

    token = " ".join(text.split()).lower()

    # Bounded: each pass must shorten the string or the loop stops. Lead-ins do
    # stack in real messages ("I'm taking the Jags"), and "the" is itself one.
    for _ in range(6):
        before = token
        token = STRIP_EDGES.sub("", token)
        if token.startswith("(") and token.endswith(")"):
            token = token[1:-1]
        token = PAID_PREFIX.sub("", token)
        token = LEAD_IN.sub("", token)
        if token == before:
            break

    return TEAM_TOKENS.get(token)
