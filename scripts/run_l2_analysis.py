#!/usr/bin/env python3
"""
L2 Talent Identification Analysis

Main script for running longitudinal L2 analysis on Lichess players.

Usage:
    python run_l2_analysis.py                    # Analyze default players
    python run_l2_analysis.py player1 player2    # Analyze specific players
    python run_l2_analysis.py --load data.json   # Load from saved data
"""

import json
import argparse
import numpy as np
from typing import Dict, List, Any

from l2_metrics import calculate_l2_metrics, get_rating_from_games, classify_player
from lichess_api import fetch_games, KNOWN_PLAYERS


def analyze_player_longitudinal(username: str, games_2017: List[Dict],
                                 games_2024: List[Dict]) -> Dict[str, Any]:
    """
    Analyze a player's L2 evolution from 2017 to 2024.
    """
    metrics_2017 = calculate_l2_metrics(games_2017, username)
    metrics_2024 = calculate_l2_metrics(games_2024, username)

    if not metrics_2017 or not metrics_2024:
        return None

    rating_2017 = get_rating_from_games(games_2017, username)
    rating_2024 = get_rating_from_games(games_2024, username)

    if not rating_2017 or not rating_2024:
        return None

    return {
        'username': username,
        'l2_2017': metrics_2017['l2_trigger'],
        'l2_2024': metrics_2024['l2_trigger'],
        'l2_change': metrics_2024['l2_trigger'] - metrics_2017['l2_trigger'],
        'sandwich_2017': metrics_2017['sandwich'],
        'sandwich_2024': metrics_2024['sandwich'],
        'rating_2017': rating_2017,
        'rating_2024': rating_2024,
        'rating_change': rating_2024 - rating_2017,
        'classification_2017': classify_player(metrics_2017),
        'classification_2024': classify_player(metrics_2024),
        'metrics_2017': metrics_2017,
        'metrics_2024': metrics_2024
    }


def run_validation(results: List[Dict]) -> Dict[str, Any]:
    """
    Run statistical validation on results.
    """
    # Filter valid results
    valid = [r for r in results if r is not None]

    if len(valid) < 3:
        return {'error': 'Insufficient data'}

    # Correlation analysis
    l2_2017 = [r['l2_2017'] for r in valid]
    rating_2024 = [r['rating_2024'] for r in valid]
    rating_change = [r['rating_change'] for r in valid]

    corr_l2_rating = np.corrcoef(l2_2017, rating_2024)[0, 1]
    corr_l2_change = np.corrcoef(l2_2017, rating_change)[0, 1]

    # Two-class model
    high_l2_sandwich = [r for r in valid if r['l2_2017'] >= 1.3 and r['sandwich_2017']]
    low_l2_or_no_sandwich = [r for r in valid if r['l2_2017'] < 1.3 or not r['sandwich_2017']]

    high_l2_improved = sum(1 for r in high_l2_sandwich if r['rating_change'] > 50)
    high_l2_mean = np.mean([r['rating_change'] for r in high_l2_sandwich]) if high_l2_sandwich else 0

    # Effect size
    if high_l2_sandwich and low_l2_or_no_sandwich:
        high_changes = [r['rating_change'] for r in high_l2_sandwich]
        low_changes = [r['rating_change'] for r in low_l2_or_no_sandwich]
        pooled_std = np.sqrt((np.var(high_changes) + np.var(low_changes)) / 2)
        cohens_d = (np.mean(high_changes) - np.mean(low_changes)) / pooled_std if pooled_std > 0 else 0
    else:
        cohens_d = 0

    return {
        'n': len(valid),
        'correlation_l2_rating': round(corr_l2_rating, 3),
        'correlation_l2_change': round(corr_l2_change, 3),
        'high_l2_sandwich_n': len(high_l2_sandwich),
        'high_l2_improved_pct': round(100 * high_l2_improved / len(high_l2_sandwich), 1) if high_l2_sandwich else 0,
        'high_l2_mean_change': round(high_l2_mean, 0),
        'cohens_d': round(cohens_d, 2)
    }


def print_results(results: List[Dict], validation: Dict):
    """
    Print formatted results.
    """
    print("=" * 80)
    print("L2 LONGITUDINAL ANALYSIS: 2017 → 2024")
    print("=" * 80)

    print(f"\n{'Username':<20} {'L2 2017':>8} {'L2 2024':>8} {'Sand':>6} {'Rating':>12} {'Change':>8}")
    print("-" * 70)

    valid = [r for r in results if r is not None]
    for r in sorted(valid, key=lambda x: x['rating_change'], reverse=True):
        sand = "YES" if r['sandwich_2017'] else "NO"
        rating_str = f"{r['rating_2017']}→{r['rating_2024']}"
        print(f"{r['username']:<20} {r['l2_2017']:>8.2f} {r['l2_2024']:>8.2f} {sand:>6} {rating_str:>12} {r['rating_change']:>+8}")

    print("\n" + "=" * 80)
    print("VALIDATION STATISTICS")
    print("=" * 80)

    print(f"""
Sample size: n={validation['n']}

CORRELATIONS:
  L2 (2017) → Rating (2024):  r = {validation['correlation_l2_rating']}
  L2 (2017) → Rating Change:  r = {validation['correlation_l2_change']}

TWO-CLASS MODEL:
  High L2 + Sandwich (n={validation['high_l2_sandwich_n']}):
    Improved: {validation['high_l2_improved_pct']}%
    Mean change: {validation['high_l2_mean_change']:+.0f}

EFFECT SIZE:
  Cohen's d = {validation['cohens_d']}
""")


def main():
    parser = argparse.ArgumentParser(description='L2 Talent Identification Analysis')
    parser.add_argument('players', nargs='*', help='Players to analyze')
    parser.add_argument('--load', help='Load from saved JSON file')
    parser.add_argument('--save', help='Save results to JSON file')

    args = parser.parse_args()

    if args.load:
        # Load from file
        with open(args.load, 'r') as f:
            all_data = json.load(f)
        players = list(all_data.keys())
    else:
        # Fetch from Lichess
        players = args.players if args.players else KNOWN_PLAYERS[:5]

        print(f"Fetching games for {len(players)} players...")
        all_data = {}

        for username in players:
            print(f"\n{username}:")

            games_2017 = fetch_games(username, 2017)
            print(f"  2017: {len([g for g in games_2017 if 'clocks' in g])} games")

            games_2024 = fetch_games(username, 2024)
            print(f"  2024: {len([g for g in games_2024 if 'clocks' in g])} games")

            all_data[username] = {
                'games_2017': games_2017,
                'games_2024': games_2024
            }

            import time
            time.sleep(1)

        if args.save:
            with open(args.save, 'w') as f:
                json.dump(all_data, f)
            print(f"\nData saved to {args.save}")

    # Analyze
    print("\nAnalyzing...")
    results = []

    for username in all_data:
        data = all_data[username]
        result = analyze_player_longitudinal(
            username,
            data.get('games_2017', data.get(2017, {}).get('games', [])),
            data.get('games_2024', data.get(2024, {}).get('games', []))
        )
        results.append(result)

    # Validate
    validation = run_validation(results)

    # Print
    print_results(results, validation)


if __name__ == '__main__':
    main()
