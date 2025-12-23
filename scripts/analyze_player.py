#!/usr/bin/env python3
"""
Analyze a single player's L2 signature.

Usage:
    python analyze_player.py penguingim1
    python analyze_player.py EricRosen --games 100
"""

import argparse
import sys

from l2_metrics import calculate_l2_metrics, classify_player, compare_to_elite
from lichess_api import fetch_games, fetch_player_info


def main():
    parser = argparse.ArgumentParser(description='Analyze player L2 signature')
    parser.add_argument('username', help='Lichess username')
    parser.add_argument('--games', type=int, default=50, help='Number of games to analyze')
    parser.add_argument('--year', type=int, default=2024, help='Year to analyze')

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print(f"L2 ANALYSIS: {args.username}")
    print(f"{'='*60}")

    # Fetch player info
    print("\nFetching player info...")
    info = fetch_player_info(args.username)
    if info:
        print(f"  Blitz rating: {info.get('blitz_rating', 'N/A')}")
        print(f"  Blitz games: {info.get('blitz_games', 0):,}")
        print(f"  Bullet games: {info.get('bullet_games', 0):,}")

    # Fetch games
    print(f"\nFetching {args.games} games from {args.year}...")
    games = fetch_games(args.username, args.year, args.games)
    valid = [g for g in games if 'clocks' in g]
    print(f"  Found {len(valid)} games with clock data")

    if len(valid) < 10:
        print("\nError: Insufficient games with clock data")
        sys.exit(1)

    # Calculate metrics
    print("\nCalculating L2 metrics...")
    metrics = calculate_l2_metrics(games, args.username)

    if not metrics:
        print("\nError: Could not calculate metrics")
        sys.exit(1)

    # Display results
    print(f"\n{'='*60}")
    print("L2 METRICS")
    print(f"{'='*60}")

    print(f"""
  L2 Trigger:        {metrics['l2_trigger']:.2f}x
  Firmware Sandwich: {'YES' if metrics['sandwich'] else 'NO'}

  Phase Ratios:
    Opening:         {metrics['op_ratio']:.2f}x median
    Middlegame:      {metrics['mg_ratio']:.2f}x median
    Endgame:         {metrics['eg_ratio']:.2f}x median

  Time Distribution:
    P10 (firmware):  {metrics['p10']:.2f}s
    P25:             {metrics['p25']:.2f}s
    Median:          {metrics['median']:.2f}s
    P75:             {metrics['p75']:.2f}s
    P90 (deep):      {metrics['p90']:.2f}s

  Bimodal Index:     {metrics['bimodal']:.1f}x
  CV:                {metrics['cv']:.2f}
""")

    # Classification
    classification = classify_player(metrics)
    print(f"{'='*60}")
    print("CLASSIFICATION")
    print(f"{'='*60}")
    print(f"""
  Category:    {classification['category']}
  Style:       {classification['style']}
  Description: {classification['description']}
""")

    # Elite comparison
    comparison = compare_to_elite(metrics)
    print(f"{'='*60}")
    print("ELITE COMPARISON")
    print(f"{'='*60}")
    print(f"""
  Closest match: {comparison['closest_elite'].title()}
  Similarity:    {comparison['similarity_score']:.0%}
  Style profile: {comparison['closest_style']}
""")

    print(f"  Comparison to all elites:")
    for name, comp in comparison['all_comparisons'].items():
        print(f"    {name.title()}: {comp['similarity']:.0%} ({comp['style']})")

    print()


if __name__ == '__main__':
    main()
