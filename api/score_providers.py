from abc import ABC, abstractmethod
from typing import List, Dict, Optional
from datetime import datetime, timezone
import requests
from dataclasses import dataclass

@dataclass
class Game:
    game_id: str
    season: int
    week: int
    kickoff: datetime
    home_team: str
    away_team: str
    status: str  # 'pre', 'in', 'final'
    home_score: Optional[int] = None
    away_score: Optional[int] = None
    winner_abbr: Optional[str] = None

class ScoreProvider(ABC):
    @abstractmethod
    def get_schedule_and_scores(self, season: int, week: int) -> List[Game]:
        """Get schedule and scores for a given season and week"""
        pass

    @abstractmethod
    def get_current_week(self, season: int) -> int:
        """Get the current NFL week for the season"""
        pass

class ESPNScoreProvider(ScoreProvider):
    """ESPN public API adapter for NFL scores"""

    def __init__(self):
        self.base_url = "https://site.api.espn.com/apis/site/v2/sports/football/nfl"

    def get_schedule_and_scores(self, season: int, week: int) -> List[Game]:
        """Fetch games from ESPN API"""
        try:
            url = f"{self.base_url}/scoreboard"
            params = {
                "dates": season,
                "seasontype": 2,  # Regular season
                "week": week
            }

            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            data = response.json()

            games = []
            for event in data.get("events", []):
                game = self._parse_espn_game(event, season, week)
                if game:
                    games.append(game)

            return games

        except Exception as e:
            print(f"Error fetching ESPN data: {e}")
            return []

    def _parse_espn_game(self, event: Dict, season: int, week: int) -> Optional[Game]:
        """Parse ESPN game event into Game object"""
        try:
            game_id = event["id"]

            # Parse kickoff time
            kickoff_str = event["date"]
            kickoff = datetime.fromisoformat(kickoff_str.replace('Z', '+00:00'))

            # Get teams
            competitions = event.get("competitions", [])
            if not competitions:
                return None

            competition = competitions[0]
            competitors = competition.get("competitors", [])

            if len(competitors) != 2:
                return None

            # ESPN typically has home team first, away team second
            home_competitor = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
            away_competitor = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

            home_team = self._normalize_team_name(home_competitor["team"]["abbreviation"])
            away_team = self._normalize_team_name(away_competitor["team"]["abbreviation"])

            # Parse status
            status_info = competition.get("status", {})
            status_type = status_info.get("type", {}).get("name", "").lower()

            if "pre" in status_type or "scheduled" in status_type:
                status = "pre"
            elif "in" in status_type or "progress" in status_type:
                status = "in"
            elif "final" in status_type:
                status = "final"
            else:
                status = "pre"

            # Parse scores
            home_score = None
            away_score = None
            winner_abbr = None

            if status in ["in", "final"]:
                home_score = int(home_competitor.get("score", 0))
                away_score = int(away_competitor.get("score", 0))

                if status == "final":
                    if home_score > away_score:
                        winner_abbr = home_team
                    elif away_score > home_score:
                        winner_abbr = away_team
                    # Handle ties (winner_abbr remains None)

            return Game(
                game_id=game_id,
                season=season,
                week=week,
                kickoff=kickoff,
                home_team=home_team,
                away_team=away_team,
                status=status,
                home_score=home_score,
                away_score=away_score,
                winner_abbr=winner_abbr
            )

        except Exception as e:
            print(f"Error parsing ESPN game: {e}")
            return None

    def _normalize_team_name(self, espn_abbr: str) -> str:
        """Normalize ESPN team abbreviations to standard NFL abbreviations"""
        mapping = {
            "WSH": "WAS",  # Washington
            "LV": "LV",    # Las Vegas (should already be correct)
            "LAR": "LAR",  # LA Rams
            "LAC": "LAC",  # LA Chargers
        }
        return mapping.get(espn_abbr, espn_abbr)

    def get_current_week(self, season: int) -> int:
        """Get current NFL week from ESPN API"""
        try:
            url = f"{self.base_url}/scoreboard"
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()

            # ESPN typically includes current week info in the response
            week_info = data.get("week", {})
            current_week = week_info.get("number", 1)

            return int(current_week)

        except Exception as e:
            print(f"Error getting current week from ESPN: {e}")
            # Fallback to week 1 if we can't determine current week
            return 1

def get_score_provider(provider_name: str = "espn") -> ScoreProvider:
    """Factory function to get score provider instance"""
    if provider_name.lower() == "espn":
        return ESPNScoreProvider()
    else:
        raise ValueError(f"Unknown score provider: {provider_name}")