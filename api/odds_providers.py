"""
Odds providers for fetching betting lines from various APIs
"""

import os
import requests
from typing import Dict, List, Optional
from datetime import datetime
from api.rate_limiter import get_rate_limiter
import logging

class OddsProvider:
    """Base class for odds providers"""

    def get_nfl_odds(self, season: int, week: int) -> Dict[str, Dict]:
        """
        Get NFL odds for a given week
        Returns: Dict mapping game_id to odds data
        """
        raise NotImplementedError

class TheOddsAPIProvider(OddsProvider):
    """The Odds API provider for NFL betting odds"""

    def __init__(self):
        self.api_key = os.getenv("THE_ODDS_API_KEY")
        self.base_url = "https://api.the-odds-api.com/v4"

        if not self.api_key:
            logging.warning("THE_ODDS_API_KEY not found in environment variables")

    def get_nfl_odds(self, season: int, week: int) -> Dict[str, Dict]:
        """
        Fetch NFL odds from The Odds API
        Returns dict mapping ESPN game_id to odds data
        """
        if not self.api_key:
            print("⚠️ No Odds API key - skipping odds fetch")
            return {}

        rate_limiter = get_rate_limiter()
        cache_key = f"the_odds_api_nfl_{season}_week_{week}"

        def fetch_odds_data():
            try:
                # Get NFL odds for current/upcoming games
                url = f"{self.base_url}/sports/americanfootball_nfl/odds"
                params = {
                    "api_key": self.api_key,
                    "regions": "us",  # US sportsbooks
                    "markets": "spreads",  # Point spreads
                    "oddsFormat": "american",
                    "dateFormat": "iso"
                }

                print(f"🎰 Fetching NFL odds from The Odds API...")
                response = requests.get(url, params=params, timeout=30)
                response.raise_for_status()

                odds_data = response.json()
                parsed_odds = self._parse_odds_response(odds_data)

                print(f"✅ Odds API: Fetched odds for {len(parsed_odds)} games")
                return parsed_odds

            except Exception as e:
                print(f"❌ Odds API Error: {e}")
                return {}

        # Use rate limiter with caching
        return rate_limiter.get_cached_or_fetch(cache_key, fetch_odds_data)  # Uses rate limiter's default cache

    def _parse_odds_response(self, odds_data: List[Dict]) -> Dict[str, Dict]:
        """
        Parse The Odds API response into our format
        Map by game teams since we don't have ESPN game IDs
        """
        parsed_odds = {}

        for game in odds_data:
            try:
                home_team = self._normalize_team_name(game["home_team"])
                away_team = self._normalize_team_name(game["away_team"])

                # Create a key we can match with ESPN data
                game_key = f"{away_team}_at_{home_team}"

                # Get spread from first available sportsbook
                spread_data = self._extract_spread_data(game.get("bookmakers", []), game)

                if spread_data:
                    parsed_odds[game_key] = {
                        "home_team": home_team,
                        "away_team": away_team,
                        "point_spread": spread_data["spread"],
                        "favorite_team": spread_data["favorite"],
                        "commence_time": game.get("commence_time"),
                        "sportsbook": spread_data["sportsbook"]
                    }

            except Exception as e:
                print(f"Error parsing odds for game: {e}")
                continue

        return parsed_odds

    def _extract_spread_data(self, bookmakers: List[Dict], game: Dict) -> Optional[Dict]:
        """Extract point spread data from bookmakers"""

        # Preferred sportsbooks in order
        preferred_books = ["draftkings", "fanduel", "betmgm", "caesars"]

        # Try preferred sportsbooks first
        for book_name in preferred_books:
            for bookmaker in bookmakers:
                if book_name in bookmaker.get("key", "").lower():
                    spread_info = self._parse_bookmaker_spreads(bookmaker, game)
                    if spread_info:
                        spread_info["sportsbook"] = bookmaker.get("title", book_name)
                        return spread_info

        # Fallback to any available sportsbook
        for bookmaker in bookmakers:
            spread_info = self._parse_bookmaker_spreads(bookmaker, game)
            if spread_info:
                spread_info["sportsbook"] = bookmaker.get("title", "Unknown")
                return spread_info

        return None

    def _parse_bookmaker_spreads(self, bookmaker: Dict, game: Dict) -> Optional[Dict]:
        """Parse spread data from a single bookmaker"""

        markets = bookmaker.get("markets", [])
        for market in markets:
            if market.get("key") == "spreads":
                outcomes = market.get("outcomes", [])

                if len(outcomes) == 2:
                    home_outcome = None
                    away_outcome = None

                    for outcome in outcomes:
                        if outcome.get("name") == game.get("home_team"):
                            home_outcome = outcome
                        else:
                            away_outcome = outcome

                    if home_outcome and away_outcome:
                        home_spread = float(home_outcome.get("point", 0))

                        # In betting: negative spread = favorite, positive = underdog
                        # If home team has negative spread (e.g., -8.5), home team is favored
                        # If home team has positive spread (e.g., +8.5), away team is favored
                        if home_spread > 0:
                            # Home team has positive spread = away team favored
                            return {
                                "spread": home_spread,
                                "favorite": game.get("away_team")  # Away team name (not normalized)
                            }
                        else:
                            # Home team has negative spread = home team favored
                            return {
                                "spread": abs(home_spread),
                                "favorite": game.get("home_team")  # Home team name (not normalized)
                            }

        return None

    def _normalize_team_name(self, team_name: str) -> str:
        """Normalize team names to match our system"""
        # The Odds API uses full team names, we need to map to abbreviations
        mapping = {
            "Arizona Cardinals": "ARI",
            "Atlanta Falcons": "ATL",
            "Baltimore Ravens": "BAL",
            "Buffalo Bills": "BUF",
            "Carolina Panthers": "CAR",
            "Chicago Bears": "CHI",
            "Cincinnati Bengals": "CIN",
            "Cleveland Browns": "CLE",
            "Dallas Cowboys": "DAL",
            "Denver Broncos": "DEN",
            "Detroit Lions": "DET",
            "Green Bay Packers": "GB",
            "Houston Texans": "HOU",
            "Indianapolis Colts": "IND",
            "Jacksonville Jaguars": "JAX",
            "Kansas City Chiefs": "KC",
            "Las Vegas Raiders": "LV",
            "Los Angeles Chargers": "LAC",
            "Los Angeles Rams": "LAR",
            "Miami Dolphins": "MIA",
            "Minnesota Vikings": "MIN",
            "New England Patriots": "NE",
            "New Orleans Saints": "NO",
            "New York Giants": "NYG",
            "New York Jets": "NYJ",
            "Philadelphia Eagles": "PHI",
            "Pittsburgh Steelers": "PIT",
            "San Francisco 49ers": "SF",
            "Seattle Seahawks": "SEA",
            "Tampa Bay Buccaneers": "TB",
            "Tennessee Titans": "TEN",
            "Washington Commanders": "WAS"
        }

        # If full name provided, try to map it
        if team_name in mapping:
            return mapping[team_name]

        # Otherwise assume it's already an abbreviation and return as-is
        return team_name.upper()

def get_odds_provider(provider_name: str = "the_odds_api") -> OddsProvider:
    """Factory function to get odds provider instance"""
    if provider_name.lower() == "the_odds_api":
        return TheOddsAPIProvider()
    else:
        raise ValueError(f"Unknown odds provider: {provider_name}")