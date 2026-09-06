"""An ingestion that fetched nothing must not report success.

Both entry points returned True when the sheet could not be read, with the
comment "Don't fail deployment". Boot continuing is right; the exit code lying
about it is not - start.sh already continues on a non-zero exit, so the two are
separable. While they were conflated, start.sh printed
"Real data ingested successfully from Google Sheets" immediately after
"No data retrieved from Google Sheets (check OAuth credentials)", and once the
Railway cron schedules exist the same conflation would report a green run for a
sheet it never reached.
"""

import pytest

from jobs import ingest_personal_sheets, ingest_sheet


class FakeClient:
    """Stands in for the Sheets client; returns whatever it was built with."""

    def __init__(self, payload):
        self._payload = payload

    def get_picks_data(self):
        return self._payload


@pytest.fixture
def no_db(monkeypatch):
    """Fail loudly if a test reaches real ingestion; these never should."""
    def boom(*_a, **_kw):
        raise AssertionError("ingestion ran despite having no data")

    monkeypatch.setattr(ingest_sheet, "ingest_players_and_picks", boom)
    monkeypatch.setattr(ingest_personal_sheets, "ingest_players_and_picks", boom)


# --- service-account path (jobs/ingest_sheet.py), used by the Railway cron ---

def test_service_account_reports_failure_when_the_sheet_cannot_be_read(
        monkeypatch, no_db):
    monkeypatch.setattr(ingest_sheet, "GoogleSheetsClient",
                        lambda *a, **k: FakeClient(None))
    assert ingest_sheet.main([]) is False


def test_service_account_reports_failure_when_nothing_parses(monkeypatch, no_db):
    monkeypatch.setattr(ingest_sheet, "GoogleSheetsClient",
                        lambda *a, **k: FakeClient([["Name", "Week 1"]]))
    monkeypatch.setattr(ingest_sheet, "parse_picks_data", lambda _raw: {})
    assert ingest_sheet.main([]) is False


def test_service_account_reports_success_when_it_ingests(monkeypatch):
    monkeypatch.setattr(ingest_sheet, "GoogleSheetsClient",
                        lambda *a, **k: FakeClient([["Name", "Week 1"]]))
    monkeypatch.setattr(ingest_sheet, "parse_picks_data",
                        lambda _raw: {"Alice": {1: "DEN"}})
    monkeypatch.setattr(ingest_sheet, "ingest_players_and_picks",
                        lambda *a, **k: True)
    monkeypatch.setattr(ingest_sheet, "populate_historical_eliminations",
                        lambda: None)
    assert ingest_sheet.main([]) is True


# --- OAuth path (jobs/ingest_personal_sheets.py), used by start.sh on boot ---

def test_oauth_reports_failure_when_the_token_will_not_refresh(
        monkeypatch, no_db):
    """The observed production-shaped failure: invalid_grant, no data, and a
    tick printed by start.sh anyway."""
    monkeypatch.setattr(ingest_personal_sheets, "RailwayPersonalSheetsClient",
                        lambda *a, **k: FakeClient(None))
    assert ingest_personal_sheets.main() is False


def test_oauth_reports_failure_when_nothing_parses(monkeypatch, no_db):
    monkeypatch.setattr(ingest_personal_sheets, "RailwayPersonalSheetsClient",
                        lambda *a, **k: FakeClient({"values": [["Name"]]}))
    monkeypatch.setattr(ingest_personal_sheets,
                        "convert_oauth_format_to_raw", lambda d: [["Name"]])
    monkeypatch.setattr(ingest_personal_sheets, "parse_picks_data",
                        lambda _raw: {})
    assert ingest_personal_sheets.main() is False


def test_oauth_reports_success_when_it_ingests(monkeypatch):
    monkeypatch.setattr(ingest_personal_sheets, "RailwayPersonalSheetsClient",
                        lambda *a, **k: FakeClient({"values": [["Name"]]}))
    monkeypatch.setattr(ingest_personal_sheets,
                        "convert_oauth_format_to_raw", lambda d: [["Name"]])
    monkeypatch.setattr(ingest_personal_sheets, "parse_picks_data",
                        lambda _raw: {"Alice": {1: "DEN"}})
    monkeypatch.setattr(ingest_personal_sheets, "ingest_players_and_picks",
                        lambda *a, **k: True)
    monkeypatch.setattr(ingest_personal_sheets,
                        "populate_historical_eliminations", lambda: None)
    assert ingest_personal_sheets.main() is True
