#!/usr/bin/env python3
"""
L1 vs L2 Error Separation: Empirical Test

Collect blunders from analyzed games and classify them:
- L1: Position was fine, move CREATED the problem (pattern mismatch)
- L2: Danger EXISTED, player didn't see it (danger blindness)
"""

import requests
import json
import time
import numpy as np
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


def fetch_analyzed_games(username: str, max_games: int = 50) -> List[Dict]:
    """Fetch games with engine analysis from Lichess."""
    url = f"https://lichess.org/api/games/user/{username}"
    params = {
        'max': max_games,
        'perfType': 'blitz',
        'clocks': 'true',
        'evals': 'true',
        'pgnInJson': 'true',
        'analysed': 'true'  # Only games with analysis
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


def get_eval(analysis: List[Dict], move_idx: int) -> Optional[int]:
    """Get evaluation at a specific move index."""
    if move_idx < len(analysis):
        eval_data = analysis[move_idx]
        if 'eval' in eval_data:
            return eval_data['eval']
        elif 'mate' in eval_data:
            # Convert mate to large eval
            mate = eval_data['mate']
            return 10000 if mate > 0 else -10000
    return None


def classify_blunder(eval_before: int, eval_after: int,
                     is_white: bool, move_idx: int) -> Tuple[str, int]:
    """
    Classify a blunder as L1 or L2.

    Returns (type, eval_drop)
    """
    # Adjust for perspective (positive = good for player)
    if is_white:
        player_eval_before = eval_before
        player_eval_after = eval_after
    else:
        player_eval_before = -eval_before
        player_eval_after = -eval_after

    eval_drop = player_eval_before - player_eval_after

    if eval_drop < 100:
        return ('NOT_BLUNDER', eval_drop)

    # L1: Position was fine (|eval| < 100), move made it bad
    # The player's move CREATED the problem
    position_was_fine = abs(player_eval_before) < 100

    # L2: Position already had issues (|eval| > 100 against player)
    # Danger already existed, player didn't address it
    danger_existed = player_eval_before < -100

    if position_was_fine and eval_drop > 200:
        return ('L1', eval_drop)  # Pattern mismatch - created the problem
    elif danger_existed and eval_drop > 100:
        return ('L2', eval_drop)  # Danger blindness - missed existing threat
    elif eval_drop > 200:
        return ('L1_SOFT', eval_drop)  # Likely L1 but position was slightly bad
    else:
        return ('MINOR', eval_drop)


def analyze_game_blunders(game: Dict, username: str) -> List[Dict]:
    """Analyze all blunders in a game."""
    analysis = game.get('analysis', [])
    clocks = game.get('clocks', [])
    moves = game.get('moves', '').split()

    if len(analysis) < 10:
        return []

    # Determine player color
    is_white = game['players']['white'].get('user', {}).get('name', '').lower() == username.lower()

    blunders = []

    # Analyze each move
    for i in range(1, len(analysis)):
        # Check if this is player's move
        move_is_white = (i % 2 == 1)  # Odd indices are white moves in analysis

        if move_is_white != is_white:
            continue

        eval_before = get_eval(analysis, i - 1)
        eval_after = get_eval(analysis, i)

        if eval_before is None or eval_after is None:
            continue

        blunder_type, eval_drop = classify_blunder(eval_before, eval_after, is_white, i)

        if blunder_type in ['L1', 'L2', 'L1_SOFT']:
            # Get think time if available
            clock_idx = i
            if clock_idx < len(clocks) and clock_idx > 0:
                think_time = (clocks[clock_idx - 1] - clocks[clock_idx]) / 100.0
            else:
                think_time = None

            # Determine game phase
            move_num = (i + 1) // 2
            if move_num <= 10:
                phase = 'opening'
            elif move_num <= 30:
                phase = 'middlegame'
            else:
                phase = 'endgame'

            blunders.append({
                'type': blunder_type,
                'eval_drop': eval_drop,
                'eval_before': eval_before if is_white else -eval_before,
                'eval_after': eval_after if is_white else -eval_after,
                'move_num': move_num,
                'phase': phase,
                'think_time': think_time,
                'move': moves[i] if i < len(moves) else None
            })

    return blunders


def run_analysis(players: List[str], games_per_player: int = 30):
    """Run L1/L2 separation analysis on multiple players."""

    print("=" * 70)
    print("L1 vs L2 ERROR SEPARATION: EMPIRICAL TEST")
    print("=" * 70)

    all_blunders = defaultdict(list)
    player_stats = {}

    for username in players:
        print(f"\nFetching analyzed games for {username}...", end=" ", flush=True)
        games = fetch_analyzed_games(username, games_per_player)
        print(f"found {len(games)} analyzed games")

        player_blunders = []
        for game in games:
            blunders = analyze_game_blunders(game, username)
            player_blunders.extend(blunders)

        for b in player_blunders:
            all_blunders[b['type']].append(b)

        if player_blunders:
            l1_count = sum(1 for b in player_blunders if b['type'] == 'L1')
            l2_count = sum(1 for b in player_blunders if b['type'] == 'L2')
            player_stats[username] = {
                'total': len(player_blunders),
                'L1': l1_count,
                'L2': l2_count,
                'L1_ratio': l1_count / len(player_blunders) if player_blunders else 0
            }

        time.sleep(1)  # Rate limiting

    # Print results
    print("\n" + "=" * 70)
    print("RESULTS")
    print("=" * 70)

    print(f"\nTotal blunders collected:")
    print(f"  L1 (pattern mismatch): {len(all_blunders['L1'])}")
    print(f"  L2 (danger blindness): {len(all_blunders['L2'])}")
    print(f"  L1_SOFT: {len(all_blunders['L1_SOFT'])}")

    # Compare L1 vs L2 characteristics
    print("\n" + "-" * 70)
    print("L1 vs L2 COMPARISON")
    print("-" * 70)

    for btype in ['L1', 'L2']:
        blunders = all_blunders[btype]
        if not blunders:
            continue

        drops = [b['eval_drop'] for b in blunders]
        times = [b['think_time'] for b in blunders if b['think_time'] is not None and b['think_time'] > 0]
        phases = defaultdict(int)
        for b in blunders:
            phases[b['phase']] += 1

        print(f"\n{btype} Errors (n={len(blunders)}):")
        print(f"  Mean eval drop: {np.mean(drops):.0f} cp")
        if times:
            print(f"  Mean think time: {np.mean(times):.1f}s")
            print(f"  Median think time: {np.median(times):.1f}s")
        print(f"  By phase: {dict(phases)}")

    # Per-player analysis
    print("\n" + "-" * 70)
    print("PER-PLAYER L1/L2 RATIO")
    print("-" * 70)

    print(f"\n{'Player':<20} {'Total':>8} {'L1':>6} {'L2':>6} {'L1 Ratio':>10}")
    print("-" * 55)

    for player, stats in sorted(player_stats.items(), key=lambda x: x[1]['L1_ratio'], reverse=True):
        print(f"{player:<20} {stats['total']:>8} {stats['L1']:>6} {stats['L2']:>6} {stats['L1_ratio']:>10.1%}")

    # Statistical test
    print("\n" + "-" * 70)
    print("INTERPRETATION")
    print("-" * 70)

    l1_blunders = all_blunders['L1']
    l2_blunders = all_blunders['L2']

    if l1_blunders and l2_blunders:
        l1_times = [b['think_time'] for b in l1_blunders if b['think_time'] and b['think_time'] > 0]
        l2_times = [b['think_time'] for b in l2_blunders if b['think_time'] and b['think_time'] > 0]

        if l1_times and l2_times:
            print(f"""
TIME SIGNATURE COMPARISON:
  L1 errors (pattern mismatch):
    - Median think time: {np.median(l1_times):.1f}s
    - These are "I thought I saw a tactic" mistakes

  L2 errors (danger blindness):
    - Median think time: {np.median(l2_times):.1f}s
    - These are "I didn't see the threat" mistakes

PREDICTION CHECK:
  If L1 errors are faster than L2 → supports theory
    (L1 = overconfident pattern match, less checking)
    (L2 = danger existed but wasn't scanned for)

  Observed: L1 median = {np.median(l1_times):.1f}s, L2 median = {np.median(l2_times):.1f}s
  {"L1 faster ✓" if np.median(l1_times) < np.median(l2_times) else "L2 faster (unexpected)"}
""")

    return all_blunders, player_stats


def main():
    # Test with known strong players
    players = [
        'penguingim1',  # Andrew Tang
        'Fins',         # John Bartholomew
        'EricRosen',    # Eric Rosen
        'Chess-Network', # Jerry
        'lovlas',       # Norwegian GM
    ]

    blunders, stats = run_analysis(players, games_per_player=30)

    print("\n" + "=" * 70)
    print("CONCLUSION")
    print("=" * 70)
    print("""
This analysis separates blunders into:

L1 (Pattern Mismatch): Position was fine, player's move created problem
  → The positive pattern recognizer matched incorrectly
  → "I thought this was a good tactic" but it wasn't

L2 (Danger Blindness): Threat existed, player didn't see it
  → The negative pattern detector failed to catch danger
  → "Nothing looked wrong" but danger was present

If these cluster differently, it supports the dual-channel theory:
  L1 and L2 are separate systems running in parallel
  Expert decision = L1 match + L2 clearance

Further analysis needed:
1. Do L1-prone vs L2-prone players have different training needs?
2. Do certain position types trigger more L1 vs L2 errors?
3. Can we predict which error type is coming from position features?
""")


if __name__ == '__main__':
    main()
