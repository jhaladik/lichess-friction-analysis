"""
Lichess API Functions

Functions for fetching player data and games from Lichess.
"""

import requests
import json
import time
from typing import Dict, List, Optional, Any


def fetch_player_info(username: str) -> Optional[Dict[str, Any]]:
    """
    Fetch player profile information from Lichess.

    Args:
        username: Lichess username

    Returns:
        Player info dictionary or None if not found
    """
    url = f"https://lichess.org/api/user/{username}"

    try:
        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            data = response.json()
            return {
                'username': data.get('username'),
                'created': data.get('createdAt'),
                'blitz_games': data.get('count', {}).get('blitz', 0),
                'bullet_games': data.get('count', {}).get('bullet', 0),
                'blitz_rating': data.get('perfs', {}).get('blitz', {}).get('rating'),
                'bullet_rating': data.get('perfs', {}).get('bullet', {}).get('rating')
            }
        return None
    except Exception as e:
        print(f"Error fetching {username}: {e}")
        return None


def fetch_games(username: str, year: int, max_games: int = 50,
                perf_type: str = 'blitz') -> List[Dict]:
    """
    Fetch games from a specific year for a player.

    Args:
        username: Lichess username
        year: Year to fetch games from
        max_games: Maximum number of games to fetch
        perf_type: Game type ('blitz', 'bullet', 'rapid')

    Returns:
        List of game dictionaries with clock data
    """
    url = f"https://lichess.org/api/games/user/{username}"

    # Calculate timestamps for the year
    year_starts = {
        2015: 1420070400000,
        2016: 1451606400000,
        2017: 1483228800000,
        2018: 1514764800000,
        2019: 1546300800000,
        2020: 1577836800000,
        2021: 1609459200000,
        2022: 1640995200000,
        2023: 1672531200000,
        2024: 1704067200000,
    }

    if year not in year_starts:
        # Calculate dynamically
        import datetime
        since = int(datetime.datetime(year, 1, 1).timestamp() * 1000)
        until = int(datetime.datetime(year, 12, 31, 23, 59, 59).timestamp() * 1000)
    else:
        since = year_starts[year]
        until = year_starts.get(year + 1, since + 31536000000) - 1

    params = {
        'since': since,
        'until': until,
        'max': max_games,
        'perfType': perf_type,
        'clocks': 'true',
        'pgnInJson': 'true'
    }

    headers = {'Accept': 'application/x-ndjson'}

    try:
        response = requests.get(url, params=params, headers=headers, timeout=60)
        if response.status_code == 200:
            games = []
            for line in response.text.strip().split('\n'):
                if line:
                    games.append(json.loads(line))
            return games
        else:
            print(f"Error {response.status_code} fetching games for {username}")
            return []
    except Exception as e:
        print(f"Error fetching games for {username}: {e}")
        return []


def fetch_longitudinal_games(username: str, years: List[int],
                             games_per_year: int = 50) -> Dict[int, List[Dict]]:
    """
    Fetch games across multiple years for longitudinal analysis.

    Args:
        username: Lichess username
        years: List of years to fetch
        games_per_year: Games to fetch per year

    Returns:
        Dictionary mapping year to list of games
    """
    result = {}

    for year in years:
        print(f"  Fetching {username} {year}...", end=" ", flush=True)
        games = fetch_games(username, year, games_per_year)
        valid = len([g for g in games if 'clocks' in g])
        print(f"{valid} games with clocks")
        result[year] = games
        time.sleep(0.5)  # Rate limiting

    return result


def search_players_by_pattern(pattern: str, limit: int = 100) -> List[str]:
    """
    Search for players matching a pattern.

    Note: Lichess autocomplete API is limited. This is best-effort.

    Args:
        pattern: Search pattern
        limit: Maximum results

    Returns:
        List of usernames
    """
    url = "https://lichess.org/api/player/autocomplete"
    params = {'term': pattern, 'limit': limit}

    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            return response.json()
        return []
    except Exception as e:
        print(f"Error searching: {e}")
        return []


def batch_fetch_players(usernames: List[str],
                        years: tuple = (2017, 2024)) -> Dict[str, Dict]:
    """
    Fetch longitudinal data for multiple players.

    Args:
        usernames: List of usernames to fetch
        years: Tuple of (start_year, end_year)

    Returns:
        Dictionary mapping username to their game data
    """
    all_data = {}

    for username in usernames:
        print(f"\nFetching {username}...")

        player_data = {
            'info': fetch_player_info(username),
            'games': {}
        }
        time.sleep(0.3)

        for year in years:
            games = fetch_games(username, year)
            valid = len([g for g in games if 'clocks' in g])
            player_data['games'][year] = {
                'games': games,
                'valid_count': valid
            }
            print(f"  {year}: {valid} games with clocks")
            time.sleep(0.5)

        all_data[username] = player_data

    return all_data


# Known players with long histories (for testing)
KNOWN_PLAYERS = [
    'penguingim1',      # Andrew Tang
    'Fins',             # John Bartholomew
    'Chess-Network',    # Jerry
    'EricRosen',        # Eric Rosen
    'thibault',         # Lichess founder
    'Lance5500',        # GM Lance Henderson
    'lovlas',           # Norwegian GM
    'agadmator',        # Antonio Radic
    'alexandra_botez',  # Alexandra Botez
    'opperwezen',       # Dutch IM
]
