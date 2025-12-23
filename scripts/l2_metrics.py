"""
L2 Firmware Metrics Calculator

Core functions for calculating L2 talent identification metrics from Lichess games.
"""

import numpy as np
from typing import Dict, List, Optional, Any


def calculate_l2_metrics(games: List[Dict], username: str) -> Optional[Dict[str, Any]]:
    """
    Calculate L2 metrics from a set of Lichess games.

    Args:
        games: List of game dictionaries from Lichess API (with clocks)
        username: Player's username

    Returns:
        Dictionary with L2 metrics or None if insufficient data
    """
    phase_times = {'opening': [], 'middlegame': [], 'endgame': []}
    all_think_times = []

    for game in games:
        if 'clocks' not in game or not game['clocks']:
            continue

        # Determine player color
        is_white = game['players']['white'].get('user', {}).get('name', '').lower() == username.lower()

        clocks = game['clocks']
        clocks_sec = [c / 100.0 for c in clocks]  # Convert centiseconds to seconds

        # Get player's clocks (every other move)
        if is_white:
            player_clocks = clocks_sec[::2]  # 0, 2, 4, ...
        else:
            player_clocks = clocks_sec[1::2]  # 1, 3, 5, ...

        if len(player_clocks) < 10:
            continue

        # Calculate think times (time spent on each move)
        think_times = []
        for i in range(1, len(player_clocks)):
            think = player_clocks[i-1] - player_clocks[i]
            if 0.1 <= think <= 60:  # Valid think time range
                think_times.append(think)

        if len(think_times) < 8:
            continue

        all_think_times.extend(think_times)

        # Classify by game phase (using move index)
        for i, think in enumerate(think_times):
            move_num = i + 1  # Move number (1-indexed)
            if move_num <= 8:
                phase_times['opening'].append(think)
            elif move_num <= 25:
                phase_times['middlegame'].append(think)
            else:
                phase_times['endgame'].append(think)

    if not all_think_times or not phase_times['opening'] or not phase_times['middlegame']:
        return None

    # Calculate metrics
    median = np.median(all_think_times)

    op_median = np.median(phase_times['opening'])
    mg_median = np.median(phase_times['middlegame'])
    eg_median = np.median(phase_times['endgame']) if phase_times['endgame'] else median

    # Normalized ratios (relative to player's overall median)
    op_ratio = op_median / median
    mg_ratio = mg_median / median
    eg_ratio = eg_median / median

    # L2 Trigger: How much slower in middlegame vs opening
    l2_trigger = mg_median / op_median if op_median > 0 else 0

    # Firmware sandwich: Fast opening + slow middlegame + fast endgame
    sandwich = op_ratio < 1.0 and mg_ratio > 1.0

    # Bimodal index: Range between fast and slow moves
    p10 = np.percentile(all_think_times, 10)
    p25 = np.percentile(all_think_times, 25)
    p75 = np.percentile(all_think_times, 75)
    p90 = np.percentile(all_think_times, 90)
    bimodal = p90 / p10 if p10 > 0 else 0

    # Coefficient of variation
    cv = np.std(all_think_times) / np.mean(all_think_times) if np.mean(all_think_times) > 0 else 0

    return {
        'l2_trigger': round(l2_trigger, 2),
        'op_ratio': round(op_ratio, 2),
        'mg_ratio': round(mg_ratio, 2),
        'eg_ratio': round(eg_ratio, 2),
        'sandwich': sandwich,
        'bimodal': round(bimodal, 2),
        'cv': round(cv, 2),
        'median': round(median, 2),
        'p10': round(p10, 2),
        'p25': round(p25, 2),
        'p75': round(p75, 2),
        'p90': round(p90, 2),
        'n_games': len([g for g in games if 'clocks' in g]),
        'n_moves': len(all_think_times)
    }


def get_rating_from_games(games: List[Dict], username: str) -> Optional[int]:
    """
    Extract average rating from a set of games.

    Args:
        games: List of game dictionaries from Lichess API
        username: Player's username

    Returns:
        Average rating or None if not available
    """
    ratings = []
    for game in games:
        if 'clocks' not in game:
            continue
        is_white = game['players']['white'].get('user', {}).get('name', '').lower() == username.lower()
        player = game['players']['white'] if is_white else game['players']['black']
        if 'rating' in player:
            ratings.append(player['rating'])
    return int(np.mean(ratings)) if ratings else None


def classify_player(metrics: Dict[str, Any]) -> Dict[str, str]:
    """
    Classify player based on L2 metrics.

    Args:
        metrics: Dictionary from calculate_l2_metrics()

    Returns:
        Dictionary with classification and interpretation
    """
    l2 = metrics['l2_trigger']
    sandwich = metrics['sandwich']
    bimodal = metrics['bimodal']

    # Classification
    if sandwich and l2 >= 1.3:
        category = "HIGH_POTENTIAL"
        description = "Strong L2 signature - likely to improve"
    elif sandwich and l2 < 1.3:
        category = "MODERATE_POTENTIAL"
        description = "Has sandwich but weak L2 trigger"
    elif not sandwich and l2 > 1.0:
        category = "DEVELOPING"
        description = "L2 present but sandwich not formed - monitor"
    else:
        category = "PLATEAU_RISK"
        description = "No L2 signature - may struggle to improve"

    # Style profile
    if l2 >= 2.0:
        style = "Speed Merchant"
    elif l2 >= 1.5:
        style = "Balanced"
    else:
        style = "Deliberate"

    return {
        'category': category,
        'description': description,
        'style': style,
        'l2_trigger': l2,
        'has_sandwich': sandwich,
        'bimodal_index': bimodal
    }


# Elite benchmarks for comparison
ELITE_BENCHMARKS = {
    'carlsen': {
        'l2_trigger': 1.50,
        'op_ratio': 0.94,
        'mg_ratio': 1.41,
        'eg_ratio': 0.76,
        'bimodal': 13.7,
        'style': 'Complete Player'
    },
    'tang': {
        'l2_trigger': 2.12,
        'op_ratio': 0.67,
        'mg_ratio': 1.42,
        'eg_ratio': 0.83,
        'bimodal': 13.5,
        'style': 'Speed Merchant'
    },
    'bartholomew': {
        'l2_trigger': 1.80,
        'op_ratio': 0.79,
        'mg_ratio': 1.42,
        'eg_ratio': 0.63,
        'bimodal': 12.7,
        'style': 'Deliberate Tactician'
    }
}


def compare_to_elite(metrics: Dict[str, Any]) -> Dict[str, Any]:
    """
    Compare player metrics to elite benchmarks.

    Args:
        metrics: Dictionary from calculate_l2_metrics()

    Returns:
        Dictionary with comparison to each elite player
    """
    comparisons = {}

    for name, benchmark in ELITE_BENCHMARKS.items():
        # Calculate similarity score (lower is more similar)
        l2_diff = abs(metrics['l2_trigger'] - benchmark['l2_trigger'])
        op_diff = abs(metrics['op_ratio'] - benchmark['op_ratio'])
        mg_diff = abs(metrics['mg_ratio'] - benchmark['mg_ratio'])

        similarity = 1.0 / (1.0 + l2_diff + op_diff + mg_diff)

        comparisons[name] = {
            'similarity': round(similarity, 2),
            'l2_diff': round(l2_diff, 2),
            'style': benchmark['style']
        }

    # Find closest match
    closest = max(comparisons.items(), key=lambda x: x[1]['similarity'])

    return {
        'closest_elite': closest[0],
        'similarity_score': closest[1]['similarity'],
        'closest_style': closest[1]['style'],
        'all_comparisons': comparisons
    }
