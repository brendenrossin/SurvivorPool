"""
Odds and spread helper functions
"""

def get_team_name_to_abbr_mapping():
    """Get mapping from full team names to abbreviations"""
    from app.dashboard_data import load_team_data

    team_data = load_team_data()
    name_to_abbr = {}

    for abbr, info in team_data["teams"].items():
        full_name = info["name"]
        name_to_abbr[full_name] = abbr

    return name_to_abbr

def normalize_team_to_abbr(team_identifier: str) -> str:
    """
    Convert team identifier (full name or abbreviation) to abbreviation

    Args:
        team_identifier: Either a full team name or abbreviation

    Returns:
        Team abbreviation
    """
    # If it's already 2-4 characters, assume it's an abbreviation
    if len(team_identifier) <= 4 and team_identifier.isupper():
        return team_identifier

    # Otherwise try to map from full name to abbreviation
    name_to_abbr = get_team_name_to_abbr_mapping()
    return name_to_abbr.get(team_identifier, team_identifier)

def get_team_spread_display(team_abbr: str, favorite_team: str, point_spread: float) -> str:
    """
    Get the correct spread display for a team

    Args:
        team_abbr: The team we want to show the spread for
        favorite_team: Which team is favored (from database)
        point_spread: The point spread (always positive, represents favorite's spread)

    Returns:
        String like "+7.5" for underdog or "-7.5" for favorite
    """
    if not favorite_team or not point_spread:
        return ""

    if team_abbr == favorite_team:
        return f"-{point_spread}"  # Favorite gets negative spread
    else:
        return f"+{point_spread}"  # Underdog gets positive spread

def get_underdog_spread_text(team_abbr: str, favorite_team: str, point_spread: float) -> str:
    """
    Get descriptive text for underdog wins

    Args:
        team_abbr: The team that won
        favorite_team: Which team was favored (can be full name or abbreviation)
        point_spread: The point spread

    Returns:
        Text like "underdog by 7.5 pts" or empty string if not underdog
    """
    if not favorite_team or not point_spread:
        return ""

    # Normalize favorite_team to abbreviation for comparison
    favorite_abbr = normalize_team_to_abbr(favorite_team)

    if team_abbr != favorite_abbr:  # This team was the underdog
        return f"underdog by {point_spread} pts"
    else:
        return ""

def format_pregame_line(home_team: str, away_team: str, favorite_team: str, point_spread: float) -> str:
    """
    Format pregame betting line display

    Args:
        home_team: Home team abbreviation
        away_team: Away team abbreviation
        favorite_team: Which team is favored (can be full name or abbreviation)
        point_spread: The point spread

    Returns:
        Formatted string like "KC -6.5" or "vs" if no spread data
    """
    if not favorite_team or not point_spread:
        return "vs"

    # Normalize favorite_team to abbreviation for display
    favorite_abbr = normalize_team_to_abbr(favorite_team)
    return f"{favorite_abbr} -{point_spread}"