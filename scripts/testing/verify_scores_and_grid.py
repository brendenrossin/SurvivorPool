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
    app = AppTest.from_file("app/main.py", default_timeout=120).run()

    print(f"season {season}: {len(app.exception)} exceptions, "
          f"{len(app.error)} errors, {len(app.warning)} warnings")
    for exc in app.exception:
        print("  EXCEPTION:", exc.value)
    for err in app.error:
        print("  ERROR:", err.value)

    # A widget that raises inside its own `except` renders st.info and never
    # reaches app.exception. That is how a NameError which killed all four
    # Pool Insights tabs passed this script with 0 exceptions: the failure
    # was wearing an empty state's clothes.
    broken = [i.value for i in app.info if "unavailable right now" in i.value]
    for message in broken:
        print("  BROKEN WIDGET:", message)

    # Both grid controls, since each is a full script rerun.
    app.toggle(key="picks_grid_expanded").set_value(True).run()
    app.radio(key="picks_grid_format").set_value("% of week").run()
    print(f"  after both controls: {len(app.exception)} exceptions")
    for exc in app.exception:
        print("  EXCEPTION:", exc.value)

    return 1 if (app.exception or broken) else 0


if __name__ == "__main__":
    sys.exit(main())
