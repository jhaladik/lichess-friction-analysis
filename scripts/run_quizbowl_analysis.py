#!/usr/bin/env python3
"""
Run Quiz Bowl L2 Analysis

Usage:
    python run_quizbowl_analysis.py
    python run_quizbowl_analysis.py --download  # Download fresh data
    python run_quizbowl_analysis.py --player PLAYER_ID
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from quizbowl_l2_metrics import (
    download_quizbowl_data, load_quizbowl_data,
    calculate_player_l2_metrics, classify_player,
    run_expert_identification, analyze_by_category,
    print_summary, L2_DOMAIN_COMPARISON
)


def main():
    parser = argparse.ArgumentParser(description='Quiz Bowl L2 Analysis')
    parser.add_argument('--data', default='../data/qanta/acf_regionals_2018_buzzes.json',
                        help='Path to Quiz Bowl JSON file')
    parser.add_argument('--download', action='store_true',
                        help='Download fresh data from GitHub')
    parser.add_argument('--player', help='Analyze specific player ID')
    parser.add_argument('--top', type=int, default=10,
                        help='Show top N players by early accuracy')
    parser.add_argument('--compare', action='store_true',
                        help='Show cross-domain L2 comparison')

    args = parser.parse_args()

    if args.compare:
        print(L2_DOMAIN_COMPARISON)
        return

    # Download if requested or file doesn't exist
    data_path = args.data
    if args.download or not os.path.exists(data_path):
        os.makedirs(os.path.dirname(data_path) or '.', exist_ok=True)
        data_path = download_quizbowl_data(os.path.dirname(data_path) or '.')

    # Load data
    print(f"Loading Quiz Bowl data from {data_path}...")
    try:
        df = load_quizbowl_data(data_path)
    except FileNotFoundError:
        print(f"Data file not found. Run with --download to fetch data.")
        sys.exit(1)

    print(f"Loaded {len(df):,} buzzes from {df['player_id'].nunique():,} players")

    if args.player:
        # Analyze specific player
        player_df = df[df['player_id'] == args.player]
        if len(player_df) == 0:
            print(f"Player {args.player} not found")
            sys.exit(1)

        metrics = calculate_player_l2_metrics(player_df)
        if not metrics:
            print(f"Insufficient data for player {args.player}")
            sys.exit(1)

        classification = classify_player(metrics)

        print(f"\n{'='*60}")
        print(f"PLAYER {args.player} L2 ANALYSIS")
        print(f"{'='*60}")

        print(f"""
  Early Accuracy (<50%): {metrics['early_accuracy']:.1%} (n={metrics['n_early']})
  Late Accuracy (>90%):  {metrics['late_accuracy']:.1%} if metrics['late_accuracy'] else 'N/A'
  L2 Trigger:            {metrics['l2_trigger']:.2f}x if metrics['l2_trigger'] else 'N/A'

  Overall Accuracy: {metrics['overall_accuracy']:.1%}
  Mean Buzz Position: {metrics['mean_buzz_position']:.1f}%
  Total Buzzes: {metrics['n_buzzes']}

  Accuracy by Quartile:
""")
        for q, acc in metrics['quartile_accuracy'].items():
            print(f"    {q}: {acc:.1%}")

        print(f"""
  Classification: {classification['category']}
  {classification['description']}
""")

    else:
        # Run full analysis
        print("\nRunning expert identification analysis...")
        validation = run_expert_identification(df)

        print_summary(df, validation)

        # Show top players by early accuracy
        print(f"\n{'='*60}")
        print(f"TOP {args.top} PLAYERS BY EARLY ACCURACY")
        print(f"{'='*60}")

        player_metrics = []
        for player_id, player_df in df.groupby('player_id'):
            metrics = calculate_player_l2_metrics(player_df)
            if metrics and metrics['early_accuracy'] is not None and metrics['n_early'] >= 5:
                metrics['player_id'] = player_id
                player_metrics.append(metrics)

        top_players = sorted(player_metrics,
                            key=lambda x: x['early_accuracy'],
                            reverse=True)[:args.top]

        print(f"\n{'Player':<15} {'Early Acc':>10} {'Overall':>10} {'N Early':>8} {'Avg Pos':>8}")
        print("-" * 55)

        for m in top_players:
            print(f"{str(m['player_id'])[:15]:<15} {m['early_accuracy']:>10.1%} {m['overall_accuracy']:>10.1%} {m['n_early']:>8} {m['mean_buzz_position']:>8.1f}")


if __name__ == '__main__':
    main()
