#!/usr/bin/env python3
"""
L1 / L2 / L3 Error Framework

Theory:
  L1: Positive pattern recognition - "this IS template"
  L2: Negative pattern recognition - "this is NOT dangerous"
  L3: Conscious analytical reasoning - slow calculation

All three run in parallel:
  - L1 matches patterns (what IS this position?)
  - L2 scans for danger (is there a threat?)
  - L3 calculates when needed (what happens if...?)

Decision = L1 match + L2 clearance (+ optional L3 verification)

Error Classification:
  L1 error: Fast + Safe position → wrong pattern matched
  L2 error: Fast + Danger position → danger not detected
  L3 error: Slow move → calculation failed

Key insight: L2 failure is FAST action when danger exists.
If player paused, L2 at least partially fired.
"""

import requests
import json
import time
import numpy as np
from typing import Dict, List, Tuple
from collections import defaultdict


def fetch_analyzed_games(username: str, max_games: int = 50) -> List[Dict]:
    """Fetch games with engine analysis from Lichess."""
    url = f"https://lichess.org/api/games/user/{username}"
    params = {
        'max': max_games,
        'perfType': 'blitz',
        'clocks': 'true',
        'evals': 'true',
        'pgnInJson': 'true',
        'analysed': 'true'
    }
    headers = {'Accept': 'application/x-ndjson'}

    response = requests.get(url, params=params, headers=headers, timeout=60)
    games = []
    for line in response.text.strip().split('\n'):
        if line:
            game = json.loads(line)
            if 'analysis' in game and game['analysis']:
                games.append(game)
    return games


def classify_error(eval_before: int, think_time: float,
                   is_blunder: bool) -> str:
    """
    Classify an error as L1, L2, or L3.

    Args:
        eval_before: Evaluation before the move (from player's perspective)
        think_time: Time spent on the move in seconds
        is_blunder: Whether this move was a blunder (eval drop > 150cp)

    Returns:
        'L1', 'L2', 'L3', or 'OK'
    """
    if not is_blunder:
        return 'OK'

    # Position state
    is_safe = eval_before > -100  # Not in danger
    is_danger = eval_before <= -100  # Opponent has advantage/threat

    # Time thresholds (for blitz)
    is_automatic = think_time < 5  # Fast/automatic decision
    is_deliberate = think_time >= 5  # Engaged reasoning

    if is_automatic and is_safe:
        return 'L1'  # Pattern mismatch
    elif is_automatic and is_danger:
        return 'L2'  # Danger blindness
    elif is_deliberate:
        return 'L3'  # Calculation failure
    else:
        return 'UNKNOWN'


def analyze_player_errors(games: List[Dict], username: str) -> Dict[str, int]:
    """Analyze all blunders and classify them."""
    errors = {'L1': 0, 'L2': 0, 'L3': 0, 'OK': 0}

    for game in games:
        analysis = game.get('analysis', [])
        clocks = game.get('clocks', [])
        is_white = game['players']['white'].get('user', {}).get('name', '').lower() == username.lower()

        for i in range(1, len(analysis)):
            move_is_white = (i % 2 == 1)
            if move_is_white != is_white:
                continue

            if 'eval' not in analysis[i-1] or 'eval' not in analysis[i]:
                continue

            eval_before = analysis[i-1]['eval']
            eval_after = analysis[i]['eval']

            # Adjust for player perspective
            if not is_white:
                eval_before = -eval_before
                eval_after = -eval_after

            eval_drop = eval_before - eval_after
            is_blunder = eval_drop > 150

            # Get think time
            if i < len(clocks) and i > 0:
                think_time = (clocks[i-1] - clocks[i]) / 100.0
            else:
                continue

            error_type = classify_error(eval_before, think_time, is_blunder)
            errors[error_type] += 1

    return errors


def compare_skill_levels(elite_players: List[str],
                         intermediate_players: List[str],
                         games_per_player: int = 30) -> Dict:
    """Compare L1/L2/L3 distribution across skill levels."""

    results = {
        'elite': {'L1': 0, 'L2': 0, 'L3': 0},
        'intermediate': {'L1': 0, 'L2': 0, 'L3': 0}
    }

    print("Fetching elite players...")
    for username in elite_players:
        print(f"  {username}...", end=" ", flush=True)
        games = fetch_analyzed_games(username, games_per_player)
        errors = analyze_player_errors(games, username)
        for e in ['L1', 'L2', 'L3']:
            results['elite'][e] += errors[e]
        print(f"L1={errors['L1']}, L2={errors['L2']}, L3={errors['L3']}")
        time.sleep(1)

    print("\nFetching intermediate players...")
    for username in intermediate_players:
        print(f"  {username}...", end=" ", flush=True)
        games = fetch_analyzed_games(username, games_per_player)
        errors = analyze_player_errors(games, username)
        for e in ['L1', 'L2', 'L3']:
            results['intermediate'][e] += errors[e]
        print(f"L1={errors['L1']}, L2={errors['L2']}, L3={errors['L3']}")
        time.sleep(1)

    return results


def print_theory():
    """Print the theoretical framework."""
    print("""
╔══════════════════════════════════════════════════════════════════════╗
║                    L1 / L2 / L3 ERROR FRAMEWORK                       ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  L1: Positive Pattern Recognition                                     ║
║      "This IS a fork" / "This IS a development move"                  ║
║      Fast, automatic, matches to known patterns                       ║
║                                                                       ║
║  L2: Negative Pattern Recognition                                     ║
║      "This is NOT a back-rank threat" / "This is NOT a pin"          ║
║      Fast, automatic, scans for absence of danger signals             ║
║                                                                       ║
║  L3: Conscious Analytical Reasoning                                   ║
║      "If I play this, then they play that, then..."                   ║
║      Slow, deliberate, explicit calculation                           ║
║                                                                       ║
╠══════════════════════════════════════════════════════════════════════╣
║                          ERROR TYPES                                  ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  L1 Error (Pattern Mismatch):                                         ║
║      - Position was SAFE                                              ║
║      - Move was FAST (< 5 seconds)                                    ║
║      - Player matched wrong pattern                                   ║
║      - "I thought I saw a tactic but it wasn't there"                ║
║                                                                       ║
║  L2 Error (Danger Blindness):                                         ║
║      - Position had DANGER (opponent threatening)                     ║
║      - Move was FAST (< 5 seconds)                                    ║
║      - Danger detector didn't fire                                    ║
║      - "I didn't sense anything wrong" - moved without checking       ║
║      - THE KEY FAILURE: no hesitation when there should be            ║
║                                                                       ║
║  L3 Error (Calculation Failure):                                      ║
║      - Move was SLOW (> 5 seconds)                                    ║
║      - Player engaged conscious analysis                              ║
║      - Still got it wrong                                             ║
║      - "I calculated but missed something"                            ║
║                                                                       ║
╠══════════════════════════════════════════════════════════════════════╣
║                        THE APPLE COLLECTOR                            ║
╠══════════════════════════════════════════════════════════════════════╣
║                                                                       ║
║  The expert apple picker:                                             ║
║    L1: "This looks like a good apple" (positive match)                ║
║    L2: "No rot, no bruises, no wrong color" (negative clear)          ║
║                                                                       ║
║  L2 failure = reaching without hesitation for a bad apple             ║
║  The "wrongness" signal didn't fire                                   ║
║                                                                       ║
║  If the hand hovers → L2 partially fired but couldn't resolve         ║
║  If grab is instant → L2 completely failed to detect                  ║
║                                                                       ║
╚══════════════════════════════════════════════════════════════════════╝
""")


def main():
    print_theory()

    # Example usage
    elite = ['penguingim1', 'Fins', 'lovlas']
    intermediate = ['thibault', 'agadmator', 'Zugzwang']

    print("\n" + "=" * 70)
    print("EMPIRICAL TEST")
    print("=" * 70)

    results = compare_skill_levels(elite, intermediate, games_per_player=30)

    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    for level in ['elite', 'intermediate']:
        total = sum(results[level].values()) or 1
        print(f"\n{level.upper()}:")
        for e in ['L1', 'L2', 'L3']:
            pct = results[level][e] / total * 100
            print(f"  {e}: {results[level][e]} ({pct:.1f}%)")


if __name__ == '__main__':
    main()
