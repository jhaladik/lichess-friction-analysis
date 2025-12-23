"""
Lichess API Module - Fetch games for specific players.
"""

import requests
import time
import json
from datetime import datetime
from typing import Iterator, Optional, List, Dict
import logging

logger = logging.getLogger(__name__)

LICHESS_API_BASE = "https://lichess.org/api"


class LichessAPI:
    """Interface to Lichess API for fetching player games."""

    def __init__(self, token: Optional[str] = None):
        """
        Initialize API client.

        Args:
            token: Optional Lichess API token for higher rate limits
        """
        self.headers = {
            "Accept": "application/x-ndjson",
        }
        if token:
            self.headers["Authorization"] = f"Bearer {token}"

        self.request_count = 0
        self.last_request_time = 0

    def _rate_limit(self):
        """Respect Lichess rate limits."""
        # Without token: 20 requests/second
        # With token: 30 requests/second
        min_interval = 0.05  # 50ms between requests
        elapsed = time.time() - self.last_request_time
        if elapsed < min_interval:
            time.sleep(min_interval - elapsed)
        self.last_request_time = time.time()
        self.request_count += 1

    def get_player_games(
        self,
        username: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        max_games: int = 1000,
        perf_type: str = "rapid,classical",
        clocks: bool = True,
        rated: bool = True,
    ) -> Iterator[Dict]:
        """
        Fetch games for a player.

        Args:
            username: Lichess username
            since: Start date (timestamp in ms)
            until: End date (timestamp in ms)
            max_games: Maximum number of games to fetch
            perf_type: Game types (rapid, classical, blitz, etc.)
            clocks: Include clock data
            rated: Only rated games

        Yields:
            Game dictionaries with moves and clock data
        """
        self._rate_limit()

        params = {
            "max": max_games,
            "clocks": str(clocks).lower(),
            "rated": str(rated).lower(),
            "perfType": perf_type,
            "opening": "true",
        }

        if since:
            params["since"] = int(since.timestamp() * 1000)
        if until:
            params["until"] = int(until.timestamp() * 1000)

        url = f"{LICHESS_API_BASE}/games/user/{username}"

        logger.info(f"Fetching games for {username}...")

        try:
            response = requests.get(
                url,
                headers=self.headers,
                params=params,
                stream=True,
                timeout=300
            )
            response.raise_for_status()

            game_count = 0
            for line in response.iter_lines():
                if line:
                    try:
                        game = json.loads(line.decode('utf-8'))
                        game_count += 1
                        if game_count % 100 == 0:
                            logger.info(f"  Fetched {game_count} games...")
                        yield game
                    except json.JSONDecodeError as e:
                        logger.warning(f"Failed to parse game: {e}")
                        continue

            logger.info(f"Fetched {game_count} games for {username}")

        except requests.exceptions.RequestException as e:
            logger.error(f"API request failed: {e}")
            raise

    def get_player_info(self, username: str) -> Optional[Dict]:
        """Get player profile information."""
        self._rate_limit()

        url = f"{LICHESS_API_BASE}/user/{username}"

        try:
            response = requests.get(url, headers={"Accept": "application/json"})
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get player info: {e}")
            return None


def parse_lichess_game(game: Dict) -> Optional[Dict]:
    """
    Parse a Lichess game into our format.

    Args:
        game: Raw game dict from Lichess API

    Returns:
        Parsed game dict or None if invalid
    """
    try:
        # Basic info
        game_id = game.get("id")

        # Players
        players = game.get("players", {})
        white = players.get("white", {})
        black = players.get("black", {})

        white_user = white.get("user", {})
        black_user = black.get("user", {})

        # Ratings
        white_rating = white.get("rating")
        black_rating = black.get("rating")

        # Time control
        clock = game.get("clock", {})
        initial = clock.get("initial", 0)
        increment = clock.get("increment", 0)

        # Must have clock data
        if not clock:
            return None

        # Moves and clocks
        moves = game.get("moves", "").split()
        clocks = game.get("clocks", [])

        if not moves or not clocks:
            return None

        # Opening
        opening = game.get("opening", {})
        eco = opening.get("eco", "")

        # Result
        winner = game.get("winner")
        if winner == "white":
            result = "1-0"
        elif winner == "black":
            result = "0-1"
        else:
            result = "1/2-1/2"

        # Date
        created_at = game.get("createdAt", 0)
        date = datetime.fromtimestamp(created_at / 1000).strftime("%Y-%m-%d")

        return {
            "game_id": game_id,
            "white_username": white_user.get("name", ""),
            "black_username": black_user.get("name", ""),
            "white_rating": white_rating,
            "black_rating": black_rating,
            "time_control": f"{initial}+{increment}",
            "initial_time": initial,
            "increment": increment,
            "moves": moves,
            "clocks": clocks,  # In centiseconds
            "eco": eco,
            "result": result,
            "date": date,
            "num_moves": len(moves),
        }

    except Exception as e:
        logger.warning(f"Failed to parse game: {e}")
        return None


def calculate_think_times(clocks: List[int], initial: int, increment: int) -> List[float]:
    """
    Calculate think times from clock data.

    Args:
        clocks: List of clock times in centiseconds after each move
        initial: Initial time in seconds
        increment: Increment in seconds

    Returns:
        List of think times in seconds
    """
    think_times = []

    # Clocks alternate: white after move 1, black after move 1, white after move 2, etc.
    # First clock value is after white's first move

    prev_white = initial * 100  # Convert to centiseconds
    prev_black = initial * 100

    for i, clock in enumerate(clocks):
        if i % 2 == 0:  # White's move
            think_time = (prev_white + increment * 100 - clock) / 100  # Convert to seconds
            prev_white = clock
        else:  # Black's move
            think_time = (prev_black + increment * 100 - clock) / 100
            prev_black = clock

        # Handle edge cases
        think_time = max(0, think_time)
        think_times.append(think_time)

    return think_times


# Target players for firmware analysis
ELITE_PLAYERS = {
    "DrNykterstein": {
        "name": "Magnus Carlsen",
        "birth_year": 1990,
    },
    "nihalsarin": {
        "name": "Nihal Sarin",
        "birth_year": 2004,
    },
    "Fins": {
        "name": "John Bartholomew",
        "birth_year": 1984,
    },
    "penguingim1": {
        "name": "Andrew Tang",
        "birth_year": 1999,
    },
    "Zhigalko_Sergei": {
        "name": "Sergei Zhigalko",
        "birth_year": 1989,
    },
}
