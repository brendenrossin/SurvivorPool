"""What counts as a pick declaration in the GroupMe, and what does not.

The parser is deliberately strict. Its failure mode is undercounting, which is
the safe direction for a tally labelled unconfirmed - see
docs/design/groupme-recap-spec.md, "The unconfirmed pick tally". Every
loosening here was measured against the 2025 sheet before it was added.
"""

import pytest

from api.pick_parser import parse_team


@pytest.mark.parametrize("text,expected", [
    ("Broncos", "DEN"),
    ("DEN", "DEN"),
    ("denver", "DEN"),
    ("Denver Broncos", "DEN"),
    ("jags", "JAX"),
    ("niners", "SF"),
    ("brownies", "CLE"),
])
def test_bare_declarations_parse(text, expected):
    assert parse_team(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("Taking the Broncos", "DEN"),
    ("switching to the Jags", "JAX"),
    ("I'm taking Denver", "DEN"),
    ("Locking in Eagles", "PHI"),
])
def test_lead_ins_are_stripped(text, expected):
    assert parse_team(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("Paid - Jags", "JAX"),
    ("Paid, Jaguars", "JAX"),
    ("Paid Chargers", "LAC"),
    ("Paid / jags", "JAX"),
    ("Paid + Jaguars", "JAX"),
    ("Paid. Jags", "JAX"),
    ("paid + chargers", "LAC"),
    ("Paid \nChargers", "LAC"),
])
def test_paid_prefix_is_stripped(text, expected):
    """The pool's dues convention. 29 messages in 2025, and still in use in 2026."""
    assert parse_team(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("Rams 🐏", "LAR"),
    ("Eagles 🦅", "PHI"),
    ("Packers 🧀", "GB"),
    ("Chargers ⚡️", "LAC"),
    ("Buffalo 🦬", "BUF"),
    ("Cowboys ⭐️📣", "DAL"),
])
def test_trailing_emoji_are_stripped(text, expected):
    assert parse_team(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("(KC)", "KC"),
    ("(Hawks)", "SEA"),
])
def test_parenthesised_declarations_parse(text, expected):
    assert parse_team(text) == expected


@pytest.mark.parametrize("text", [
    "Good luck boys",
    "It was fun boys",
    "Fuck yeah boys",
])
def test_banter_containing_a_team_token_is_not_a_pick(text):
    """`boys` maps to DAL. Loosening the match far enough to catch conversational
    declarations turns every one of these into a Dallas pick, which is why the
    conversational cluster is deliberately left uncaptured."""
    assert parse_team(text) is None


@pytest.mark.parametrize("text", [
    # "" is deliberately absent: no mutation of this module can make the empty
    # string return a team, so a case for it could never fail. None covers the
    # null-text guard (122 rows in the live table have no text) and "   "
    # covers the whitespace path past it.
    None,
    "   ",
    "😂",
    "Who even is Kyle Brown?",
    "Fly eagles fly",
])
def test_non_declarations_return_none(text):
    assert parse_team(text) is None


@pytest.mark.parametrize("text", ["los angeles", "new york"])
def test_tokens_naming_two_teams_are_refused(text):
    """"los angeles" is both LAR and LAC. Resolving it by dict insertion order
    is a coin flip dressed up as a parse, so the token is dropped instead."""
    from api.pick_parser import TEAM_TOKENS

    assert text not in TEAM_TOKENS
    assert parse_team(text) is None


def test_unambiguous_city_names_still_parse():
    """Dropping ambiguous cities must not take the unambiguous ones with it."""
    assert parse_team("denver") == "DEN"
    assert parse_team("cincinnati") == "CIN"
