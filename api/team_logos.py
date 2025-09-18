#!/usr/bin/env python3
"""
NFL Team Logo Fetcher - Downloads team logos from ESPN
"""

import os
import requests
from typing import Dict, Optional

# ESPN team logo URL pattern - they have consistent URLs for team logos
ESPN_LOGO_URL = "https://a.espncdn.com/i/teamlogos/nfl/500/{team}.png"

# Team mapping for any special cases
TEAM_LOGO_MAPPING = {
    "LV": "lv",   # Las Vegas Raiders
    "LAR": "lar", # Los Angeles Rams
    "LAC": "lac", # Los Angeles Chargers
}

def get_team_logo_url(team_abbr: str) -> str:
    """Get the ESPN logo URL for a team"""
    team_code = TEAM_LOGO_MAPPING.get(team_abbr, team_abbr.lower())
    return ESPN_LOGO_URL.format(team=team_code)

def download_team_logo(team_abbr: str, logos_dir: str = "app/static/logos") -> Optional[str]:
    """
    Download a team logo from ESPN
    Returns the local file path if successful, None if failed
    """
    # Create logos directory
    os.makedirs(logos_dir, exist_ok=True)

    logo_url = get_team_logo_url(team_abbr)
    logo_path = os.path.join(logos_dir, f"{team_abbr}.png")

    # Skip if already exists
    if os.path.exists(logo_path):
        return logo_path

    try:
        print(f"   Downloading {team_abbr} logo...")
        response = requests.get(logo_url, timeout=10)
        response.raise_for_status()

        with open(logo_path, 'wb') as f:
            f.write(response.content)

        print(f"   ✅ {team_abbr} logo saved")
        return logo_path

    except Exception as e:
        print(f"   ❌ Failed to download {team_abbr}: {e}")
        return None

def download_all_nfl_logos(logos_dir: str = "app/static/logos") -> Dict[str, str]:
    """
    Download all NFL team logos
    Returns a dict mapping team_abbr -> local_file_path
    """
    print("🏈 Downloading NFL Team Logos...")

    # All 32 NFL teams
    nfl_teams = [
        "ARI", "ATL", "BAL", "BUF", "CAR", "CHI", "CIN", "CLE",
        "DAL", "DEN", "DET", "GB", "HOU", "IND", "JAX", "KC",
        "LAC", "LAR", "LV", "MIA", "MIN", "NE", "NO", "NYG",
        "NYJ", "PHI", "PIT", "SEA", "SF", "TB", "TEN", "WAS"
    ]

    logos = {}
    successful = 0

    for team in nfl_teams:
        logo_path = download_team_logo(team, logos_dir)
        if logo_path:
            logos[team] = logo_path
            successful += 1

    print(f"✅ Downloaded {successful}/{len(nfl_teams)} team logos")
    print(f"📁 Logos saved to: {logos_dir}/")

    return logos

def get_team_logo_path(team_abbr: str, logos_dir: str = "app/static/logos") -> Optional[str]:
    """Get the local path to a team logo, download if needed"""
    logo_path = os.path.join(logos_dir, f"{team_abbr}.png")

    if os.path.exists(logo_path):
        return logo_path

    # Try to download it
    return download_team_logo(team_abbr, logos_dir)

if __name__ == "__main__":
    # Test the logo fetcher
    logos = download_all_nfl_logos()

    print(f"\n📊 Logo Download Summary:")
    for team, path in sorted(logos.items()):
        print(f"   {team}: {path}")