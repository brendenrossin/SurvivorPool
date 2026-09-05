# Live Scores Cards + Picks Grid Consolidation — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the live-scores widget as a two-column card grid, and fold the "Week N Picks Breakdown" table into the picks grid by giving a busted current-week pick its own visual state.

**Architecture:** Every new rule lands as a **pure function** with its own tests; the Streamlit functions stay view code, and every database read goes through a `@st.cache_data(ttl=60)` wrapper in `dashboard_data.py`. Colour decisions are **computed from a passed `background`**, never from a hardcoded surface, so a light/dark reversal is an argument change rather than a rewrite.

**Tech Stack:** Python 3.11.14, Streamlit 1.50.0, Plotly, SQLAlchemy, pytest.

**Spec:** `docs/design/scores-and-grid-spec.md` (read it first; it carries the reasoning). Its companion `docs/design/picks-grid-spec.md` is **locked** — do not reopen the grid's design.

## Global Constraints

- **Never render picks for a week that has not kicked off.** `aggregate_picks()` in `app/picks_grid.py` is the single enforcement point for the grid and has tests. The scoreboard gets its own rule (Task 6) and its own leak test.
- **Every database read is cached** with `@st.cache_data(ttl=60)` in `app/dashboard_data.py`, and every session closes in a `finally` with the project's `try/except: pass` idiom.
- **`app/dashboard_data.py` is append-only.** Add functions at the end; do not restructure existing ones. Session C shares this file.
- **Do not touch** `app/graveyard.py`, `app/team_of_doom.py`, `app/survivors.py`, `app/chaos_meter.py`, the meme-stats regions, or the CSS block in `app/main.py`. Session C owns them.
- **A tie counts as a LOSS for both teams.** Survivor scoring rule; preserve exactly.
- **No colour literals in `app/live_scores.py`.** Cards are built from `st.container(border=True)` and `st.badge(color=...)`, which are theme-aware.
- **No surface literals in `app/picks_grid.py` colour logic.** Everything derives from the passed `background`.
- Run tests with `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`. **60 pass on base.**
- The local `DATABASE_URL` in `.env` will not resolve; use `DATABASE_PUBLIC_URL`, which points at **production — read-only, never a write or a job.**

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `app/dashboard_data.py` | cached DB reads → plain dicts | append `decide_week_results`, `get_week_team_status`, `get_week_game_statuses`, `get_week_scoreboard` |
| `app/picks_grid.py` | grid geometry + colour rules, all pure | add the eliminated-cell colour rules; make three light-only assumptions surface-derived; add `team_status` to `build_picks_grid` |
| `app/live_scores.py` | scoreboard: week choice, card view models, card rendering | rewritten |
| `app/main.py` | wiring only | delete the breakdown-table block; add the legend; rewire the scoreboard |
| `tests/test_picks_grid.py` | grid rules | append `TestEliminatedCell`, `TestSurfaceDerivedInk` |
| `tests/test_dashboard_data.py` | pure data rules | append `TestDecideWeekResults` |
| `tests/test_live_scores.py` | **new** — scoreboard week + card view models | created |

---

### Task 1: Week results as a pure, testable rule

The tie rule currently lives inline in a Streamlit render function where no test can reach it. Deleting it would pass the whole suite.

**Files:**
- Modify: `app/dashboard_data.py` (append at end)
- Test: `tests/test_dashboard_data.py` (append)

**Interfaces:**
- Consumes: nothing
- Produces: `decide_week_results(games: Iterable[Tuple[str, str, str, Optional[int], Optional[int]]]) -> Dict[str, str]` where each row is `(status, home_team, away_team, home_score, away_score)` and values are `'won' | 'lost' | 'pending'`; `get_week_team_status(season: int, week: int) -> Dict[str, str]`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dashboard_data.py — append
from app.dashboard_data import count_completed_weeks, decide_week_results


class TestDecideWeekResults:
    """The survivor tie rule, finally reachable by a test.

    This lived inline in render_weekly_picks_chart, so deleting it passed the
    entire suite. A tie eliminates BOTH teams' pickers.
    """

    def test_decided_game_splits_winner_and_loser(self):
        # 2025 week 14: NO 24, TB 20 - the game that ended the pool
        assert decide_week_results([("final", "TB", "NO", 20, 24)]) == {
            "TB": "lost", "NO": "won",
        }

    def test_home_win(self):
        assert decide_week_results([("final", "DET", "DAL", 44, 30)]) == {
            "DET": "won", "DAL": "lost",
        }

    def test_a_tie_eliminates_both_teams(self):
        """The rule the whole function exists for."""
        assert decide_week_results([("final", "NYG", "WAS", 17, 17)]) == {
            "NYG": "lost", "WAS": "lost",
        }

    def test_unplayed_games_are_pending(self):
        assert decide_week_results([("pre", "SEA", "NE", None, None)]) == {
            "SEA": "pending", "NE": "pending",
        }
        assert decide_week_results([("scheduled", "SEA", "NE", None, None)]) == {
            "SEA": "pending", "NE": "pending",
        }

    def test_a_live_game_is_pending_not_decided(self):
        """A team leading at half has not survived anything yet."""
        assert decide_week_results([("in", "KC", "HOU", 10, 20)]) == {
            "KC": "pending", "HOU": "pending",
        }

    def test_final_without_scores_is_not_decided(self):
        """Ingestion can mark a game final before the scores land."""
        assert decide_week_results([("final", "KC", "HOU", None, None)]) == {
            "KC": "pending", "HOU": "pending",
        }

    def test_no_games(self):
        assert decide_week_results([]) == {}

    def test_every_team_in_a_full_week_gets_a_verdict(self):
        """2025 week 14: 14 games, 28 teams, all final."""
        games = [("final", f"H{i}", f"A{i}", 20 + i, 10) for i in range(14)]
        assert len(decide_week_results(games)) == 28
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_dashboard_data.py -q`
Expected: FAIL — `ImportError: cannot import name 'decide_week_results'`

- [ ] **Step 3: Implement**

Append to `app/dashboard_data.py`. Add `Iterable` and `Tuple` to the existing `typing` import line.

```python
def decide_week_results(
    games: Iterable[Tuple[str, str, str, Optional[int], Optional[int]]],
) -> Dict[str, str]:
    """{team: 'won' | 'lost' | 'pending'} for one week's games.

    Rows are (status, home_team, away_team, home_score, away_score).

    A TIE IS A LOSS FOR BOTH TEAMS. Survivor pools pay out on a win, so a tie
    eliminates everyone who picked either side. Anything that is not a final
    game with both scores present is 'pending' - including a live game, where
    a team leading at half has survived nothing yet, and a game marked final
    before ingestion has filled the score in.
    """
    status: Dict[str, str] = {}
    for game_status, home, away, home_score, away_score in games:
        decided = (
            game_status == "final"
            and home_score is not None
            and away_score is not None
        )
        if not decided:
            status.setdefault(home, "pending")
            status.setdefault(away, "pending")
        elif home_score == away_score:
            status[home] = status[away] = "lost"
        elif home_score > away_score:
            status[home], status[away] = "won", "lost"
        else:
            status[away], status[home] = "won", "lost"
    return status


@st.cache_data(ttl=60)
def get_week_team_status(season: int, week: int) -> Dict[str, str]:
    """Cached {team: 'won' | 'lost' | 'pending'} for one week.

    Replaces an uncached whole-ORM-row Game query that ran inline in the
    render path on every script rerun - which the grid's two controls now
    trigger on every toggle.
    """
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        rows = db.query(
            Game.status, Game.home_team, Game.away_team,
            Game.home_score, Game.away_score,
        ).filter(Game.season == season, Game.week == week).all()
        return decide_week_results(rows)
    finally:
        try:
            db.close()
        except Exception:
            pass
```

- [ ] **Step 4: Run to verify it passes**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: 68 passed

- [ ] **Step 5: Commit**

```bash
git add app/dashboard_data.py tests/test_dashboard_data.py
git commit -m "🎯 Make the survivor tie rule a tested function"
```

---

### Task 2: The eliminated cell's colour rules

The heart of the ticket. `mute_color()` means "an earlier week"; this must never be mistakable for it.

**Files:**
- Modify: `app/picks_grid.py`
- Test: `tests/test_picks_grid.py` (append)

**Interfaces:**
- Consumes: existing `relative_luminance`, `mute_color`, `label_ink`, `_channels`
- Produces: `contrast_ratio(a: str, b: str) -> float`; `ensure_contrast(color: str, against: str, minimum: float = 3.0) -> str`; `eliminated_fill(hex_color: str, background: str) -> str`; `eliminated_edge(fill: str, danger: str) -> str`; module constant `DANGER = "#B91C1C"`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_picks_grid.py — append; extend the existing import block with
# DANGER, contrast_ratio, ensure_contrast, eliminated_fill, eliminated_edge,
# relative_luminance

LIGHT_SURFACE = "#F8FAFC"
DARK_SURFACE = "#0B1220"
# Every distinct hex in db/seed_team_map.json, spanning LV black to PIT gold.
TEAM_COLORS = ["#D50A0A", "#311D00", "#002244", "#FB4F14", "#000000", "#FFB612",
               "#203731", "#00338D", "#0B162A", "#003594", "#D3BC8D", "#69BE28"]


class TestEliminatedCell:
    """The busted current-week fill must never be readable as history.

    The grid already mutes toward the surface to mean "an earlier week". If
    elimination muted the same way the grid would lose its primary encoding,
    so elimination drains SATURATION while history drains LIGHTNESS.
    """

    def test_the_fill_is_achromatic(self):
        """Hue is the channel elimination gives up."""
        for team in TEAM_COLORS:
            fill = eliminated_fill(team, LIGHT_SURFACE)
            r, g, b = int(fill[1:3], 16), int(fill[3:5], 16), int(fill[5:7], 16)
            assert r == g == b, f"{team} -> {fill} kept a hue"

    def test_it_holds_the_lightness_its_history_cells_take(self):
        """Holding lightness constant is what proves the axes are different."""
        for team in TEAM_COLORS:
            history = mute_color(team, LIGHT_SURFACE)
            fill = eliminated_fill(team, LIGHT_SURFACE)
            assert abs(relative_luminance(fill) - relative_luminance(history)) < 0.02

    def test_it_never_equals_the_muted_history_colour(self):
        """The collision this whole design exists to prevent."""
        for surface in (LIGHT_SURFACE, DARK_SURFACE):
            for team in TEAM_COLORS:
                assert eliminated_fill(team, surface) != mute_color(team, surface)

    def test_it_never_equals_the_current_week_colour(self):
        for surface in (LIGHT_SURFACE, DARK_SURFACE):
            for team in TEAM_COLORS:
                assert eliminated_fill(team, surface).lower() != team.lower()

    def test_it_follows_the_surface(self):
        """A light/dark reversal must be an argument change, not a rewrite."""
        for team in TEAM_COLORS:
            assert eliminated_fill(team, LIGHT_SURFACE) != eliminated_fill(team, DARK_SURFACE)

    def test_a_grey_team_still_moves(self):
        """LV is already black; its history cell and its busted cell still differ."""
        assert eliminated_fill("#000000", LIGHT_SURFACE) != mute_color("#000000", LIGHT_SURFACE)


class TestEliminatedEdge:
    """The red border is the primary signal, so its contrast is computed."""

    def test_the_edge_clears_three_to_one_on_every_team_and_surface(self):
        for surface in (LIGHT_SURFACE, DARK_SURFACE):
            for team in TEAM_COLORS:
                fill = eliminated_fill(team, surface)
                assert contrast_ratio(eliminated_edge(fill, DANGER), fill) >= 3.0

    def test_the_token_passes_through_untouched_when_it_already_clears(self):
        """ensure_contrast is a no-op when the token already works."""
        assert ensure_contrast("#B91C1C", "#FFFFFF") == "#B91C1C"

    def test_contrast_ratio_is_symmetric_and_bounded(self):
        assert contrast_ratio("#000000", "#FFFFFF") == contrast_ratio("#FFFFFF", "#000000")
        assert round(contrast_ratio("#000000", "#FFFFFF"), 1) == 21.0
        assert contrast_ratio("#777777", "#777777") == 1.0
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_picks_grid.py -q`
Expected: FAIL — `ImportError: cannot import name 'eliminated_fill'`

- [ ] **Step 3: Implement**

Add to `app/picks_grid.py`, below `mute_color`:

```python
# Semantic danger hue. Consumed as a HUE ANCHOR, not as a literal border colour:
# the border sits on a fill this module chooses, so its lightness is adjusted
# per-fill by ensure_contrast(). Swap for app.theme.DANGER when it lands.
DANGER = "#B91C1C"

WCAG_GRAPHIC_MIN = 3.0   # WCAG 2.1 non-text contrast floor


def contrast_ratio(a: str, b: str) -> float:
    """WCAG contrast ratio between two hex colours."""
    la, lb = relative_luminance(a), relative_luminance(b)
    lighter, darker = max(la, lb), min(la, lb)
    return (lighter + 0.05) / (darker + 0.05)


def ensure_contrast(
    color: str, against: str, minimum: float = WCAG_GRAPHIC_MIN
) -> str:
    """Move `color` toward white or black until it clears `minimum`.

    The danger token is chosen against the app surface, but this border sits on
    a desaturated fill instead - a different contrast question with a different
    answer. Rather than keeping a second token in step by hand, the lightness is
    computed, the same rule label_ink() already follows. A no-op whenever the
    token already clears.
    """
    if contrast_ratio(color, against) >= minimum:
        return color

    # Move away from the fill: darken a colour on a light fill, lighten it on a
    # dark one. 20 steps of 5% reaches pure black or white, so this terminates.
    toward = "#000000" if relative_luminance(against) > relative_luminance(color) else "#ffffff"
    for step in range(1, 21):
        candidate = mute_color(color, toward, 1 - step * 0.05)
        if contrast_ratio(candidate, against) >= minimum:
            return candidate
    return toward


def _grey_at(luminance: float) -> str:
    """The achromatic colour with this WCAG relative luminance."""
    if luminance <= 0.0031308:
        channel = 12.92 * luminance
    else:
        channel = 1.055 * (luminance ** (1 / 2.4)) - 0.055
    value = max(0, min(255, round(channel * 255)))
    return "#{0:02x}{0:02x}{0:02x}".format(value)


def eliminated_fill(hex_color: str, background: str) -> str:
    """Fill for a current-week pick whose game is lost.

    It takes exactly the lightness this team's *history* cells take, with the
    hue removed. That is the whole design in one line: history mutes on
    lightness and keeps hue, elimination mutes on saturation and keeps
    lightness. Holding lightness constant is what proves the two are different
    axes rather than two points on one, which is what would have collapsed the
    grid's primary encoding.

    The surface enters only through mute_color(), which is already
    parameterised, so a light/dark reversal costs an argument and nothing else.
    """
    return _grey_at(relative_luminance(mute_color(hex_color, background)))


def eliminated_edge(fill: str, danger: str = DANGER) -> str:
    """Border for a busted cell: the danger hue, made legible on `fill`."""
    return ensure_contrast(danger, fill)
```

- [ ] **Step 4: Run to verify it passes**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: 80 passed

- [ ] **Step 5: Commit**

```bash
git add app/picks_grid.py tests/test_picks_grid.py
git commit -m "🎨 Mute elimination on saturation, not on lightness"
```

---

### Task 3: Fix `label_ink`, and make three light-only assumptions surface-derived

`label_ink` thresholds luminance at `0.45`. **The real crossover where dark ink overtakes white is `0.1791`** — `(0.0525 ** 0.5) - 0.05`, from setting the white-ink and black-ink contrast ratios equal. Everything between those two numbers gets white ink where black would be more legible, and **five teams are under the 4.5:1 floor for small text on the current light build**:

| Team | Fill | Now | Best |
|---|---|---|---|
| CIN / DEN | `#FB4F14` | 3.37:1 | **5.84:1** |
| MIA | `#008E97` | 3.95:1 | **4.98:1** |
| CAR | `#0085CA` | 4.03:1 | **4.88:1** |
| LAC | `#0080C6` | 4.28:1 | **4.60:1** |

Verified against `db/seed_team_map.json`. This is surface-independent and lands wherever the app's surface ends up. The module docstring already says contrast is "computed, never assumed" — the threshold *was* the assumption.

The other three are latent today because `main.py` passes a light surface; they invert the moment it does not. All four are entangled with Task 2's fill, so they go in one pass.

**Files:**
- Modify: `app/picks_grid.py`
- Test: `tests/test_picks_grid.py` (append)

**Interfaces:**
- Consumes: `contrast_ratio`, `label_ink`, `mute_color`, `relative_luminance` from Task 2
- Produces: `cell_edge(fill: str, background: str) -> str`; `history_ink(fill: str) -> str`; a corrected `label_ink(hex_color: str) -> str` (same signature, better answer)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_picks_grid.py — append; add cell_edge, history_ink to the imports

class TestLabelInkPicksTheBetterInk:
    """label_ink thresholded luminance at 0.45. The real crossover is 0.1791,
    so every fill between them got white ink where black reads better - five
    teams under the 4.5:1 small-text floor on the shipping light build."""

    def test_the_five_failing_teams_now_clear_the_small_text_floor(self):
        for team in ("#FB4F14", "#008E97", "#0085CA", "#0080C6"):
            assert contrast_ratio(label_ink(team), team) >= 4.5

    def test_it_always_picks_the_higher_contrast_ink(self):
        for team in TEAM_COLORS + ["#FB4F14", "#008E97", "#0085CA", "#0080C6"]:
            chosen = contrast_ratio(label_ink(team), team)
            best = max(contrast_ratio(ink, team) for ink in ("#0b0b0b", "#ffffff"))
            assert chosen == best, f"{team} took the worse ink"

    def test_the_extremes_are_unchanged(self):
        """LV black and PIT gold were already right; don't regress them."""
        assert label_ink("#000000") == "#ffffff"
        assert label_ink("#FFB612") == "#0b0b0b"


class TestSurfaceDerivedInk:
    """Three colours were hardcoded for a light surface. They invert on a dark
    one - a dark fill is the one that dissolves there, not a light one."""

    def test_a_cell_that_would_dissolve_gets_a_hairline(self):
        """A near-white fill on a near-white surface needs an edge."""
        assert cell_edge("#FEFEFE", LIGHT_SURFACE) != "#FEFEFE"

    def test_the_same_rule_catches_a_dark_fill_on_a_dark_surface(self):
        """The case the old > 0.6 threshold could not see."""
        assert cell_edge("#0B162A", DARK_SURFACE) != "#0B162A"

    def test_a_cell_with_its_own_contrast_keeps_its_own_edge(self):
        assert cell_edge("#D50A0A", LIGHT_SURFACE) == "#D50A0A"

    def test_history_ink_is_legible_on_its_own_fill(self):
        for surface in (LIGHT_SURFACE, DARK_SURFACE):
            for team in TEAM_COLORS:
                fill = mute_color(team, surface)
                assert contrast_ratio(history_ink(fill), fill) >= 3.0

    def test_history_ink_recedes_rather_than_shouting(self):
        """Deliberately softer than full contrast - history should recede."""
        fill = mute_color("#D50A0A", LIGHT_SURFACE)
        assert contrast_ratio(history_ink(fill), fill) < contrast_ratio(label_ink(fill), fill)
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_picks_grid.py -q`
Expected: FAIL — `ImportError: cannot import name 'cell_edge'`

- [ ] **Step 3: Implement**

First, replace `label_ink` in `app/picks_grid.py` — same signature, no caller changes:

```python
INKS = ("#0b0b0b", "#ffffff")


def label_ink(hex_color: str) -> str:
    """Text colour that stays legible on `hex_color`.

    Picks whichever ink actually yields more contrast, rather than thresholding
    luminance. The old threshold was 0.45; the real crossover where dark ink
    overtakes white is 0.1791 - solve 1.05/(L+0.05) = (L+0.05)/0.05 - so every
    fill in between took white ink where black reads better. That put five
    teams under the 4.5:1 small-text floor: CIN and DEN #FB4F14 at 3.37:1,
    MIA #008E97 at 3.95:1, CAR #0085CA at 4.03:1, LAC #0080C6 at 4.28:1.

    This module's docstring says contrast is computed, never assumed. The
    threshold was the assumption.
    """
    return max(INKS, key=lambda ink: contrast_ratio(ink, hex_color))
```

Then add to `app/picks_grid.py`; delete `HISTORY_INK`-style literals at their use sites in Task 4.

```python
DISSOLVE_RATIO = 1.35    # below this a fill and the surface read as one block
HISTORY_INK_MIX = 0.72   # how much of full-contrast ink history keeps


def cell_edge(fill: str, background: str) -> str:
    """Hairline that stops a cell dissolving into the surface.

    The old rule drew a dark hairline when the fill's luminance cleared 0.6 -
    correct only because the app was light-only. A light fill on a light
    surface and a dark fill on a dark one are the same problem, so the test is
    against the surface rather than against a fixed threshold, and the hairline
    takes the side the surface is not on.
    """
    if contrast_ratio(fill, background) >= DISSOLVE_RATIO:
        return fill
    return "rgba(0,0,0,.18)" if relative_luminance(background) > 0.45 else "rgba(255,255,255,.28)"


def history_ink(fill: str) -> str:
    """Label ink for an earlier week's cell.

    Deliberately softer than label_ink(): history should recede, and computing
    full contrast here would darken it and cost the recede effect. It was
    hardcoded "#52514e", which is a dark ink - correct on the light surface it
    was written for and invisible on a dark one.
    """
    return mute_color(label_ink(fill), fill, HISTORY_INK_MIX)
```

- [ ] **Step 4: Run to verify it passes**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: 88 passed

- [ ] **Step 5: Commit**

```bash
git add app/picks_grid.py tests/test_picks_grid.py
git commit -m "🔤 Compute label ink by contrast, not by a miscalibrated threshold"
```

---

### Task 4: Wire the eliminated state into the figure

**Files:**
- Modify: `app/picks_grid.py` — `build_picks_grid`
- Test: `tests/test_picks_grid.py` (append)

**Interfaces:**
- Consumes: `eliminated_fill`, `eliminated_edge`, `cell_edge`, `history_ink`
- Produces: `build_picks_grid(..., team_status: Optional[Dict[str, str]] = None, danger: str = DANGER) -> go.Figure` — the two new arguments are keyword-only additions with defaults, so every existing caller and test is unaffected.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_picks_grid.py — append

WK14_COUNTS = {(13, "TB"): 4, (14, "TB"): 16, (14, "CLE"): 2, (14, "SEA"): 1}
WK14_TOTALS = {13: 4, 14: 19}
WK14_COLORS = {"TB": "#D50A0A", "CLE": "#311D00", "SEA": "#002244"}
WK14_STATUS = {"TB": "lost", "CLE": "lost", "SEA": "won"}


def _grid(**kwargs):
    params = dict(
        weeks=[13, 14], rows=["TB", "CLE", "SEA"], counts=WK14_COUNTS,
        week_totals=WK14_TOTALS, team_colors=WK14_COLORS, current_week=14,
        background=LIGHT_SURFACE,
    )
    params.update(kwargs)
    return build_picks_grid(**params)


class TestEliminatedInFigure:
    """2025 week 14: 16 entrants on Tampa Bay, TB lost, the pool ended at one."""

    def test_omitting_team_status_changes_nothing(self):
        """Every existing caller and test must render exactly as before."""
        assert _grid().layout.shapes == _grid(team_status=None).layout.shapes

    def test_a_lost_current_week_cell_takes_the_eliminated_fill(self):
        fills = [s["fillcolor"] for s in _grid(team_status=WK14_STATUS).layout.shapes]
        assert eliminated_fill("#D50A0A", LIGHT_SURFACE) in fills

    def test_a_won_current_week_cell_keeps_true_team_colour(self):
        """Won and not-yet-kicked-off are deliberately identical."""
        fills = [s["fillcolor"] for s in _grid(team_status=WK14_STATUS).layout.shapes]
        assert "#002244" in fills

    def test_an_eliminated_teams_earlier_weeks_are_untouched(self):
        """History's job is volume, not outcome."""
        fills = [s["fillcolor"] for s in _grid(team_status=WK14_STATUS).layout.shapes]
        assert mute_color("#D50A0A", LIGHT_SURFACE) in fills

    def test_a_lost_cell_takes_the_danger_border(self):
        shapes = _grid(team_status=WK14_STATUS).layout.shapes
        fill = eliminated_fill("#D50A0A", LIGHT_SURFACE)
        lost = [s for s in shapes if s["fillcolor"] == fill]
        assert lost and lost[0]["line"]["width"] == 2
        assert lost[0]["line"]["color"] == eliminated_edge(fill)

    def test_a_pending_team_is_not_treated_as_lost(self):
        status = {"TB": "pending", "CLE": "pending", "SEA": "pending"}
        fills = [s["fillcolor"] for s in _grid(team_status=status).layout.shapes]
        assert eliminated_fill("#D50A0A", LIGHT_SURFACE) not in fills

    def test_a_status_for_a_team_not_in_the_grid_is_ignored(self):
        _grid(team_status={"KC": "lost"})  # must not raise

    def test_the_tooltip_names_the_elimination(self):
        trace = _grid(team_status=WK14_STATUS).data[0]
        assert any("Eliminated" in text for text in trace.hovertext)
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_picks_grid.py -k Eliminated -q`
Expected: FAIL — `TypeError: build_picks_grid() got an unexpected keyword argument 'team_status'`

- [ ] **Step 3: Implement**

In `build_picks_grid`, add the two parameters to the signature and their docstring lines:

```python
    team_status: Optional[Dict[str, str]] = None,
    danger: str = DANGER,
```

```
        team_status: {team: 'won'|'lost'|'pending'} for `current_week`. A team
            marked 'lost' takes the eliminated treatment in the current week
            only. None renders exactly as before.
        danger: semantic danger hue for the eliminated border.
```

Add `team_status = team_status or {}` beside the existing `team_names = team_names or {}`.

Replace the body of the cell loop's styling with:

```python
            is_now = week == current_week
            is_out = is_now and team_status.get(team) == "lost"
            total = week_totals.get(week, 0)
            share = (100 * n / total) if total else 0

            if is_out:
                fill = eliminated_fill(base, background)
                edge, edge_width = eliminated_edge(fill, danger), 2
                ink = label_ink(fill)
            elif is_now:
                fill = base
                edge, edge_width = cell_edge(fill, background), 1
                ink = label_ink(fill)
            else:
                fill = mute_color(base, background)
                edge, edge_width = cell_edge(fill, background), 1
                ink = history_ink(fill)

            shapes.append(dict(
                type="rect", xref="x", yref="y",
                x0=col_idx - CELL_W / 2, x1=col_idx + CELL_W / 2,
                y0=row_idx - CELL_H / 2, y1=row_idx + CELL_H / 2,
                fillcolor=fill,
                line=dict(width=edge_width, color=edge),
                layer="below",
            ))

            annotations.append(dict(
                x=col_idx, y=row_idx,
                text=_share_label(share) if as_percent else str(n),
                showarrow=False,
                font=dict(
                    size=12 if is_now else 11,
                    color=ink,
                    family="Inter, system-ui",
                ),
            ))
```

Extend the hover text so the new state is named, not only drawn:

```python
            if is_out:
                state = f"<br><b>Eliminated</b> — {n} out"
            elif is_now:
                state = " (current)"
            else:
                state = ""
            hover.append(
                f"<b>{team_names.get(team, team)}</b><br>"
                f"Week {week}{state}<br>"
                f"{n} of {total} picks — {share:.1f}%"
            )
```

Finally, derive the hover label from the surface instead of hardcoding white:

```python
        hoverlabel=dict(
            bgcolor=background, bordercolor=cell_edge(background, background),
            font=dict(color=label_ink(background), size=12, family="Inter, system-ui"),
            align="left",
        ),
```

- [ ] **Step 4: Run to verify it passes**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: 96 passed

- [ ] **Step 5: Commit**

```bash
git add app/picks_grid.py tests/test_picks_grid.py
git commit -m "💀 Draw a busted current-week pick as eliminated"
```

---

### Task 5: Delete the breakdown table; add the legend

**Files:**
- Modify: `app/main.py` — `render_weekly_picks_chart` only (currently ~line 395 to ~line 550)

**Interfaces:**
- Consumes: `get_week_team_status` (Task 1), `build_picks_grid(team_status=...)` (Task 4)
- Produces: nothing

- [ ] **Step 1: Add the import and pass the status through**

Add `get_week_team_status` to the existing `from app.dashboard_data import (...)` block.

In `render_weekly_picks_chart`, after `rows = select_grid_rows(...)`:

```python
    # Cached: the grid's two controls rerun the whole script on every toggle.
    team_status = get_week_team_status(SEASON, current_week)
```

and pass `team_status=team_status` into `build_picks_grid(...)`.

- [ ] **Step 2: Replace everything after the `st.plotly_chart` call**

Delete the entire `# Add current week picks table` block — from the `try:` through its closing `st.warning(f"⚠️ Couldn't build the picks breakdown: {e}")` — and put the legend in its place:

```python
    # The legend replaces the "Week N Picks Breakdown" table. The table showed
    # team and count, which the grid already shows in the same order; its only
    # unique content was a ✅/💀/🕐 glyph per team, now carried by the cell
    # itself. The grid gained an encoding, so it has to name the three it has.
    eliminated = sorted(
        team for team in rows
        if team_status.get(team) == "lost" and (current_week, team) in counts
    )
    swatches = " &nbsp;·&nbsp; ".join([
        f'<span style="background:{get_team_color_map().get(rows[0], "#666")};'
        'display:inline-block;width:11px;height:11px;border-radius:2px;'
        'vertical-align:-1px;"></span> this week',
        '<span style="background:'
        f'{mute_color(get_team_color_map().get(rows[0], "#666"), APP_SURFACE)};'
        'display:inline-block;width:11px;height:11px;border-radius:2px;'
        'vertical-align:-1px;"></span> earlier weeks',
        '<span style="background:'
        f'{eliminated_fill(get_team_color_map().get(rows[0], "#666"), APP_SURFACE)};'
        f'border:2px solid {eliminated_edge(eliminated_fill(get_team_color_map().get(rows[0], "#666"), APP_SURFACE))};'
        'display:inline-block;width:11px;height:11px;border-radius:2px;'
        'vertical-align:-1px;"></span> eliminated this week',
    ])
    st.caption(swatches, unsafe_allow_html=True)

    if eliminated:
        out = sum(counts[(current_week, team)] for team in eliminated)
        st.caption(
            f"Week {current_week}: {out} "
            f"{'entry' if out == 1 else 'entries'} out on "
            + ", ".join(eliminated)
        )
```

Add `eliminated_edge`, `eliminated_fill`, `mute_color` to the existing `from app.picks_grid import (...)` block.

- [ ] **Step 3: Verify the module imports and nothing else moved**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -c "import app.main"`
Expected: no output.

Run: `git diff --stat app/main.py`
Expected: only `app/main.py`, and the deletion must be larger than the insertion.

- [ ] **Step 4: Run the suite**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: 96 passed

- [ ] **Step 5: Commit**

```bash
git add app/main.py
git commit -m "🧹 Fold the picks breakdown table into the grid"
```

---

### Task 6: The scoreboard's own week

Deliberately **not** unified with `resolve_current_week`. The grid must keep pointing at the last week that kicked off; the scoreboard rolls forward once a week is over.

**Files:**
- Create: `tests/test_live_scores.py`
- Modify: `app/live_scores.py`, `app/dashboard_data.py` (append)

**Interfaces:**
- Consumes: `count_completed_weeks` (existing), `resolve_current_week` (existing)
- Produces: `resolve_scoreboard_week(current_week: int, week_statuses: Dict[int, List[str]]) -> int` in `app/live_scores.py`; `get_week_game_statuses(season: int) -> Dict[int, List[str]]` in `app/dashboard_data.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_live_scores.py — new file
"""The scoreboard's week, and the card view models.

The scoreboard's notion of "current" is deliberately NOT the grid's. The grid
leads with the last week that kicked off; the scoreboard rolls forward to the
next week once the current one is finished, so a Tuesday shows what is coming
rather than what is settled. They are not unified on purpose.
"""

from app.live_scores import resolve_scoreboard_week


class TestResolveScoreboardWeek:

    def test_an_unfinished_week_does_not_roll(self):
        """Sunday afternoon: the week is live, stay on it."""
        assert resolve_scoreboard_week(5, {5: ["final", "in", "pre"]}) == 5

    def test_a_finished_week_rolls_forward(self):
        """Tuesday: Monday night is over, show week 6."""
        assert resolve_scoreboard_week(5, {5: ["final"] * 14, 6: ["pre"] * 16}) == 6

    def test_it_does_not_roll_past_the_schedule(self):
        """2025 ends at week 16 in the games table; never point past it."""
        assert resolve_scoreboard_week(16, {16: ["final"] * 16}) == 16

    def test_a_week_with_no_games_does_not_roll(self):
        assert resolve_scoreboard_week(5, {5: []}) == 5

    def test_it_rolls_only_one_week(self):
        """Backfilling several finished weeks must not skip the season."""
        statuses = {w: ["final"] * 16 for w in range(1, 15)}
        statuses[15] = ["pre"] * 16
        assert resolve_scoreboard_week(14, statuses) == 15

    def test_no_games_at_all(self):
        assert resolve_scoreboard_week(1, {}) == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_live_scores.py -q`
Expected: FAIL — `ImportError: cannot import name 'resolve_scoreboard_week'`

- [ ] **Step 3: Implement**

In `app/live_scores.py`:

```python
def resolve_scoreboard_week(
    current_week: int, week_statuses: Dict[int, List[str]]
) -> int:
    """The week the scoreboard should show.

    Deliberately NOT the grid's `resolve_current_week`. The grid leads with the
    last week that kicked off, because that is the last week whose picks may be
    published. The scoreboard rolls forward once a week is finished, so Tuesday
    shows the upcoming slate rather than a settled one.

    The roll is driven by whether the games actually finished, not by the day of
    the week - the old rule added one every Tuesday after 4am UTC regardless of
    whether anything had been played.
    """
    statuses = week_statuses.get(current_week)
    if not statuses or not all(status == "final" for status in statuses):
        return current_week
    return current_week + 1 if (current_week + 1) in week_statuses else current_week
```

Append to `app/dashboard_data.py`:

```python
@st.cache_data(ttl=60)
def get_week_game_statuses(season: int) -> Dict[int, List[str]]:
    """{week: [game status, ...]} for a whole season."""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        rows = db.query(Game.week, Game.status).filter(Game.season == season).all()
        by_week: Dict[int, List[str]] = {}
        for week, status in rows:
            by_week.setdefault(week, []).append(status)
        return by_week
    finally:
        try:
            db.close()
        except Exception:
            pass
```

- [ ] **Step 4: Run to verify it passes**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: 102 passed

- [ ] **Step 5: Commit**

```bash
git add app/live_scores.py app/dashboard_data.py tests/test_live_scores.py
git commit -m "📅 Give the scoreboard its own week, rolled by results not by weekday"
```

---

### Task 7: Card view models

Pure functions, so the leak rule is testable rather than trusted.

**Files:**
- Modify: `app/live_scores.py`, `app/dashboard_data.py` (append)
- Test: `tests/test_live_scores.py` (append)

**Interfaces:**
- Consumes: `format_pregame_line` (existing, `app/odds_helpers.py`)
- Produces: `build_scoreboard(games, pick_counts, results, reveal_picks) -> List[Dict]` in `app/live_scores.py`, where `games` is a list of dicts with keys `game_id, status, home_team, away_team, home_score, away_score, winner_abbr, kickoff, favorite_team, point_spread`; `get_week_scoreboard(season: int, week: int) -> Dict` in `app/dashboard_data.py`

Each returned card is
`{game_id, status, kickoff, line, away: {team, score, picks, outcome}, home: {...}, has_picks, eliminated, survived}`
where `outcome` is `'won' | 'lost' | None` and `picks` is `0` whenever `reveal_picks` is false.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_live_scores.py — append
from app.live_scores import build_scoreboard, resolve_scoreboard_week

WK14 = [
    dict(game_id="g1", status="final", home_team="TB", away_team="NO",
         home_score=20, away_score=24, winner_abbr="NO",
         kickoff=None, favorite_team=None, point_spread=None),
    dict(game_id="g2", status="final", home_team="ATL", away_team="SEA",
         home_score=9, away_score=37, winner_abbr="SEA",
         kickoff=None, favorite_team=None, point_spread=None),
    dict(game_id="g3", status="pre", home_team="KC", away_team="DEN",
         home_score=None, away_score=None, winner_abbr=None,
         kickoff=None, favorite_team="Kansas City Chiefs", point_spread=3.0),
]
COUNTS = {"TB": 16, "SEA": 1}


class TestBuildScoreboard:
    """2025 week 14 - 16 entrants on Tampa Bay, one on Seattle."""

    def test_only_games_with_a_picked_team_are_shown(self):
        cards = build_scoreboard(WK14, COUNTS, {}, reveal_picks=True)
        assert [c["game_id"] for c in cards] == ["g1", "g2"]

    def test_pick_counts_land_on_the_right_side(self):
        card = build_scoreboard(WK14, COUNTS, {}, reveal_picks=True)[0]
        assert card["home"]["team"] == "TB" and card["home"]["picks"] == 16
        assert card["away"]["team"] == "NO" and card["away"]["picks"] == 0

    def test_a_final_game_carries_the_outcome(self):
        card = build_scoreboard(WK14, COUNTS, {}, reveal_picks=True)[0]
        assert card["home"]["outcome"] == "lost"
        assert card["away"]["outcome"] == "won"

    def test_an_unplayed_week_reveals_no_pick_data_at_all(self):
        """THE LEAK TEST. A week that has not kicked off shows the full slate
        with no counts and no filtering - the filter is itself a disclosure of
        who picked what, days before kickoff."""
        cards = build_scoreboard(WK14, COUNTS, {}, reveal_picks=False)
        assert len(cards) == 3, "an unplayed week shows every game"
        assert all(c["away"]["picks"] == 0 and c["home"]["picks"] == 0 for c in cards)
        assert not any(c["has_picks"] for c in cards)

    def test_live_games_sort_before_everything(self):
        games = [dict(WK14[0]), dict(WK14[1])]
        games[1]["status"] = "in"
        cards = build_scoreboard(games, COUNTS, {}, reveal_picks=True)
        assert cards[0]["game_id"] == "g2"

    def test_the_line_is_shown_when_the_database_has_one(self):
        cards = build_scoreboard(WK14, {"KC": 1}, {}, reveal_picks=True)
        assert cards[0]["line"] == "KC -3.0"

    def test_no_line_when_the_database_has_none(self):
        """2025 carries spreads on only 31 of 240 games."""
        assert build_scoreboard(WK14, COUNTS, {}, reveal_picks=True)[0]["line"] is None

    def test_the_elimination_split_rides_on_the_card(self):
        results = {"g1": {"survived": 0, "eliminated": 16}}
        card = build_scoreboard(WK14, COUNTS, results, reveal_picks=True)[0]
        assert card["eliminated"] == 16 and card["survived"] == 0

    def test_no_picks_at_all_shows_the_full_slate(self):
        cards = build_scoreboard(WK14, {}, {}, reveal_picks=True)
        assert len(cards) == 3
```

- [ ] **Step 2: Run to verify it fails**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/test_live_scores.py -q`
Expected: FAIL — `ImportError: cannot import name 'build_scoreboard'`

- [ ] **Step 3: Implement**

Replace `get_live_scores_data`, `create_game_display` and `get_survivor_counts` in `app/live_scores.py` with:

```python
STATUS_ORDER = {"in": 0, "pre": 1, "final": 2}


def _side(team: str, score, winner, status: str, picks: int) -> Dict[str, Any]:
    if status == "final" and winner:
        outcome = "won" if winner == team else "lost"
    else:
        outcome = None
    return {"team": team, "score": score, "picks": picks, "outcome": outcome}


def build_scoreboard(
    games: List[Dict[str, Any]],
    pick_counts: Dict[str, int],
    results: Dict[str, Dict[str, int]],
    reveal_picks: bool,
) -> List[Dict[str, Any]]:
    """Card view models for one week.

    `reveal_picks` is false for a week that has not kicked off. It suppresses
    the counts AND the filtering, because filtering the slate to picked teams
    is itself a disclosure of the field's picks - by omission rather than by a
    number, but the same leak. So an unplayed week shows every game with no
    pick data at all, and snaps to picked-teams-only with counts at kickoff.
    """
    cards = []
    for game in games:
        home, away = game["home_team"], game["away_team"]
        home_picks = pick_counts.get(home, 0) if reveal_picks else 0
        away_picks = pick_counts.get(away, 0) if reveal_picks else 0

        if reveal_picks and pick_counts and not (home_picks or away_picks):
            continue

        split = results.get(game["game_id"], {}) if reveal_picks else {}
        cards.append({
            "game_id": game["game_id"],
            "status": game["status"],
            "kickoff": game["kickoff"],
            "line": format_pregame_line(
                home, away, game["favorite_team"], game["point_spread"]
            ) if game["favorite_team"] and game["point_spread"] else None,
            "away": _side(away, game["away_score"], game["winner_abbr"],
                          game["status"], away_picks),
            "home": _side(home, game["home_score"], game["winner_abbr"],
                          game["status"], home_picks),
            "has_picks": bool(home_picks or away_picks),
            "eliminated": split.get("eliminated", 0),
            "survived": split.get("survived", 0),
        })

    cards.sort(key=lambda c: (
        STATUS_ORDER.get(c["status"], 3),
        not c["has_picks"],
        c["kickoff"] or datetime.min,
    ))
    return cards
```

Append to `app/dashboard_data.py`:

```python
@st.cache_data(ttl=60)
def get_week_scoreboard(season: int, week: int) -> Dict:
    """Games, pick counts and survival splits for one week, as plain dicts."""
    SessionFactory = get_db_session()
    db = SessionFactory()
    try:
        games = [{
            "game_id": g.game_id, "status": g.status,
            "home_team": g.home_team, "away_team": g.away_team,
            "home_score": g.home_score, "away_score": g.away_score,
            "winner_abbr": g.winner_abbr, "kickoff": g.kickoff,
            "favorite_team": g.favorite_team, "point_spread": g.point_spread,
        } for g in db.query(Game).filter(
            Game.season == season, Game.week == week
        ).order_by(Game.kickoff).all()]

        counts = dict(db.query(Pick.team_abbr, func.count()).filter(
            Pick.season == season, Pick.week == week,
            Pick.team_abbr.isnot(None),
        ).group_by(Pick.team_abbr).all())

        results: Dict[str, Dict[str, int]] = {}
        rows = db.query(PickResult.game_id, PickResult.survived, func.count()).join(
            Pick, Pick.pick_id == PickResult.pick_id
        ).filter(Pick.season == season, Pick.week == week).group_by(
            PickResult.game_id, PickResult.survived
        ).all()
        for game_id, survived, count in rows:
            split = results.setdefault(game_id, {"survived": 0, "eliminated": 0})
            if survived is True:
                split["survived"] += count
            elif survived is False:
                split["eliminated"] += count

        return {"games": games, "pick_counts": counts, "results": results}
    finally:
        try:
            db.close()
        except Exception:
            pass
```

- [ ] **Step 4: Run to verify it passes**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: 111 passed

- [ ] **Step 5: Commit**

```bash
git add app/live_scores.py app/dashboard_data.py tests/test_live_scores.py
git commit -m "🃏 Model the scoreboard as cards, with the leak rule under test"
```

---

### Task 8: Render the cards

**Files:**
- Modify: `app/live_scores.py` — `render_live_scores_widget`, delete `render_compact_live_scores`
- Modify: `app/main.py` — the live-scores block only (currently ~lines 210–235)

**Interfaces:**
- Consumes: `build_scoreboard`, `resolve_scoreboard_week`, `get_week_scoreboard`, `get_week_game_statuses`, `get_started_game_weeks`, `resolve_current_week`
- Produces: `render_live_scores_widget(season: int, week: int, reveal_picks: bool) -> None` — **note the changed signature: it no longer takes a `db`**, because every read is now cached.

- [ ] **Step 1: Replace the renderer**

Cards are built only from `st.container(border=True)` and `st.badge(...)`. **No colour literals and no raw HTML** — those are theme-aware, so Session C's surface change needs no rebase here.

```python
def _status_chip(card) -> None:
    if card["status"] == "in":
        st.badge("LIVE", icon="🔴", color="red")
    elif card["status"] == "final":
        st.badge("FINAL", color="gray")
    elif card["kickoff"]:
        pacific = pytz.timezone("America/Los_Angeles")
        local = card["kickoff"].replace(tzinfo=timezone.utc).astimezone(pacific)
        st.badge(local.strftime("%a %-I:%M %p"), icon="🕐", color="gray")
    else:
        st.badge("TBD", color="gray")


def _team_row(side, status: str) -> None:
    name, score = st.columns([3, 1], vertical_alignment="center")
    with name:
        emphasis = "**" if side["outcome"] == "won" else ""
        label = f"{emphasis}{side['team']}{emphasis}"
        if side["picks"]:
            entries = "entry" if side["picks"] == 1 else "entries"
            label += f" &nbsp; `{side['picks']} {entries}`"
        st.markdown(label)
    with score:
        if status == "pre" or side["score"] is None:
            st.markdown("&nbsp;")
        else:
            weight = "**" if side["outcome"] == "won" else ""
            st.markdown(f"{weight}{side['score']}{weight}")


def _render_card(card) -> None:
    with st.container(border=True):
        head, line = st.columns([2, 1], vertical_alignment="center")
        with head:
            _status_chip(card)
        with line:
            if card["line"]:
                st.caption(card["line"])
        _team_row(card["away"], card["status"])
        _team_row(card["home"], card["status"])

        if card["eliminated"] or card["survived"]:
            st.divider()
            if card["eliminated"]:
                st.badge(f"{card['eliminated']} eliminated", icon="💀", color="red")
            if card["survived"]:
                st.badge(f"{card['survived']} survive", icon="✅", color="green")


def render_live_scores_widget(season: int, week: int, reveal_picks: bool) -> None:
    """The week's scoreboard, as a two-column grid of cards.

    `reveal_picks` is false before the week kicks off; see build_scoreboard.
    """
    data = get_week_scoreboard(season, week)
    cards = build_scoreboard(
        data["games"], data["pick_counts"], data["results"], reveal_picks
    )

    st.markdown(f"### 🏈 Week {week}")

    # Each empty state says WHY it is empty, per the roadmap item.
    if not data["games"]:
        st.info(
            f"**No week {week} schedule yet.** Games appear once the ESPN "
            "ingestion job has run for this week."
        )
        return
    if not cards:
        st.info(
            f"**No picks for week {week} yet.** The sheet is imported at "
            "07:00 PT daily and again at 09:30 PT on Sundays; cards appear "
            "for the teams people take."
        )
        return

    if not reveal_picks:
        st.caption(
            "Week hasn't kicked off — showing the full slate. Pick counts "
            "appear at kickoff."
        )
    elif not any(card["has_picks"] for card in cards):
        st.caption("No picks in yet — showing every game this week.")

    for row in range(0, len(cards), 2):
        left, right = st.columns(2, gap="small")
        with left:
            _render_card(cards[row])
        if row + 1 < len(cards):
            with right:
                _render_card(cards[row + 1])
```

Delete `render_compact_live_scores` — it is unused apart from an import, and it is the last caller of the old text format.

Trim the module imports to what remains: `streamlit as st`, `pytz`, `datetime`/`timezone`, `typing`, `format_pregame_line`, and `get_week_scoreboard` from `app.dashboard_data`.

- [ ] **Step 2: Rewire `main.py`**

Replace the whole `# Live Scores Widget` `try` block with:

```python
    # Live Scores - cards for the week the scoreboard should be showing.
    # Deliberately NOT the grid's week: the grid leads with the last week that
    # kicked off, the scoreboard rolls forward once that week is finished.
    try:
        week_statuses = get_week_game_statuses(SEASON)
        played_week = resolve_current_week(
            sorted(w["week"] for w in get_summary_data(SEASON)["weeks"]) or [1],
            get_started_game_weeks(SEASON),
        )
        scoreboard_week = resolve_scoreboard_week(played_week, week_statuses)
        render_live_scores_widget(
            SEASON, scoreboard_week, reveal_picks=scoreboard_week <= played_week
        )
    except Exception as e:
        logging.exception("Live scores failed to render")
        st.info(f"🏈 Live scores are unavailable right now: {e}")
```

Update the import: `from app.live_scores import render_live_scores_widget, resolve_scoreboard_week`, and add `get_week_game_statuses` to the `dashboard_data` import block.

- [ ] **Step 3: Verify imports and the suite**

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -c "import app.main"`
Expected: no output.

Run: `NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python -m pytest tests/ -q`
Expected: 111 passed

- [ ] **Step 4: Commit**

```bash
git add app/live_scores.py app/main.py
git commit -m "🏈 Rebuild live scores as a card grid"
```

---

### Task 9: Verify against both seasons, headless

**Files:**
- Create: `scripts/testing/verify_scores_and_grid.py`

- [ ] **Step 1: Write the harness**

```python
#!/usr/bin/env python3
"""Run the dashboard headless against a season and report what rendered.

Usage:
    export DATABASE_URL="$(grep -E '^DATABASE_PUBLIC_URL=' .env | cut -d= -f2-)"
    NFL_SEASON=2025 PYTHONPATH=. .venv/bin/python scripts/testing/verify_scores_and_grid.py

Read-only. DATABASE_PUBLIC_URL points at PRODUCTION - never run a write here.
"""
import os
import sys

from streamlit.testing.v1 import AppTest


def main() -> int:
    season = os.getenv("NFL_SEASON", "2026")
    app = AppTest.from_file("app/main.py", default_timeout=90).run()

    print(f"season {season}: {len(app.exception)} exceptions, "
          f"{len(app.error)} errors, {len(app.warning)} warnings")
    for exc in app.exception:
        print("  EXCEPTION:", exc.value)
    for err in app.error:
        print("  ERROR:", err.value)

    # Both grid controls, since each is a full script rerun.
    app.toggle(key="picks_grid_expanded").set_value(True).run()
    app.radio(key="picks_grid_format").set_value("% of week").run()
    print(f"after both controls: {len(app.exception)} exceptions")
    for exc in app.exception:
        print("  EXCEPTION:", exc.value)

    return 1 if app.exception else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run against both seasons**

```bash
export DATABASE_URL="$(grep -E '^DATABASE_PUBLIC_URL=' .env | cut -d= -f2-)"
NFL_SEASON=2025 PYTHONPATH=. .venv/bin/python scripts/testing/verify_scores_and_grid.py
NFL_SEASON=2026 PYTHONPATH=. .venv/bin/python scripts/testing/verify_scores_and_grid.py
```

Expected, both: `0 exceptions`, exit 0.

- [ ] **Step 3: Confirm the two behaviours that matter, by hand**

```bash
NFL_SEASON=2025 PYTHONPATH=. .venv/bin/python -c "
from app.dashboard_data import get_week_team_status, get_week_scoreboard, get_week_game_statuses
from app.live_scores import build_scoreboard, resolve_scoreboard_week
s = get_week_team_status(2025, 14)
print('wk14 TB:', s['TB'], '| SEA:', s['SEA'])           # lost | won
d = get_week_scoreboard(2025, 14)
print('picked-team cards:', len(build_scoreboard(d['games'], d['pick_counts'], d['results'], True)))
cards = build_scoreboard(d['games'], d['pick_counts'], d['results'], False)
print('unplayed-week cards:', len(cards),
      '| counts leaked:', sum(c['away']['picks'] + c['home']['picks'] for c in cards))
print('rolls 14 ->', resolve_scoreboard_week(14, get_week_game_statuses(2025)))
"
```

Expected: `lost | won`; 4 picked-team cards; 14 unplayed-week cards with **0 counts leaked**; rolls `14 -> 15`.

- [ ] **Step 4: Commit**

```bash
git add scripts/testing/verify_scores_and_grid.py
git commit -m "✅ Add a headless verifier for both seasons"
```

---

## Definition of done

- [ ] Full suite green (111 expected, from 60 on base)
- [ ] Headless verifier clean on 2025 and 2026
- [ ] `/tri-review` run, no Critical/High findings outstanding
- [ ] Rebased on `staging`, PR opened into `staging`
- [ ] Worktree removed: `git worktree remove ../SurvivorPool-scores && git worktree prune`
