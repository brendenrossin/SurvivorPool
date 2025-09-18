import os
import base64
import json
from typing import List, Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from dotenv import load_dotenv

load_dotenv()

class GoogleSheetsClient:
    def __init__(self):
        self.spreadsheet_id = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID")
        self.picks_range = os.getenv("GOOGLE_SHEETS_PICKS_RANGE", "Picks!A1:Z5000")

        # Decode service account JSON from base64
        service_account_json_b64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_BASE64")
        if not service_account_json_b64:
            raise ValueError("GOOGLE_SERVICE_ACCOUNT_JSON_BASE64 environment variable is required")

        service_account_json = base64.b64decode(service_account_json_b64).decode('utf-8')
        service_account_info = json.loads(service_account_json)

        credentials = service_account.Credentials.from_service_account_info(
            service_account_info,
            scopes=['https://www.googleapis.com/auth/spreadsheets.readonly']
        )

        self.service = build('sheets', 'v4', credentials=credentials)

    def get_picks_data(self) -> List[List[str]]:
        """Fetch picks data from Google Sheets"""
        try:
            sheet = self.service.spreadsheets()
            result = sheet.values().get(
                spreadsheetId=self.spreadsheet_id,
                range=self.picks_range
            ).execute()

            values = result.get('values', [])
            return values
        except Exception as e:
            print(f"Error fetching sheets data: {e}")
            raise

    def parse_picks_data(self, raw_data: List[List[str]]) -> Dict[str, Any]:
        """Parse raw sheet data into structured picks"""
        if not raw_data:
            return {"players": [], "picks": []}

        header = raw_data[0]
        rows = raw_data[1:]

        # Find week columns
        week_cols = []
        for i, col_name in enumerate(header):
            if col_name and col_name.lower().startswith("week"):
                try:
                    week_num = int(col_name.lower().replace("week", "").strip())
                    week_cols.append((i, week_num))
                except ValueError:
                    continue

        players = []
        picks = []

        for row in rows:
            if not row or len(row) == 0:
                continue

            name = row[0].strip() if row[0] else ""
            if not name:
                continue

            players.append(name)

            for col_idx, week in week_cols:
                if col_idx < len(row):
                    team = row[col_idx].strip().upper() if row[col_idx] else None
                    if team:
                        picks.append({
                            "player_name": name,
                            "week": week,
                            "team_abbr": team
                        })

        return {
            "players": list(set(players)),  # Remove duplicates
            "picks": picks
        }