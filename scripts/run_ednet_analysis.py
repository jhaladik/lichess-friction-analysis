#!/usr/bin/env python3
"""
Run EdNet L2 Analysis

Usage:
    python run_ednet_analysis.py
    python run_ednet_analysis.py --data path/to/ednet.csv
    python run_ednet_analysis.py --user USER_ID
"""

import argparse
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ednet_l2_metrics import (
    load_ednet_data, calculate_user_l2_metrics, classify_user,
    run_expert_identification, analyze_by_part, print_summary, TOEIC_PARTS
)


def main():
    parser = argparse.ArgumentParser(description='EdNet L2 Analysis')
    parser.add_argument('--data', default='../data/ednet/ednet_clean.csv',
                        help='Path to EdNet CSV file')
    parser.add_argument('--user', type=int, help='Analyze specific user ID')
    parser.add_argument('--top', type=int, default=10,
                        help='Show top N users by L2')

    args = parser.parse_args()

    # Load data
    print(f"Loading EdNet data from {args.data}...")
    df = load_ednet_data(args.data)
    print(f"Loaded {len(df):,} responses from {df['user_id'].nunique():,} users")

    if args.user:
        # Analyze specific user
        user_df = df[df['user_id'] == args.user]
        if len(user_df) == 0:
            print(f"User {args.user} not found")
            sys.exit(1)

        metrics = calculate_user_l2_metrics(user_df)
        if not metrics:
            print(f"Insufficient data for user {args.user}")
            sys.exit(1)

        classification = classify_user(metrics)

        print(f"\n{'='*60}")
        print(f"USER {args.user} L2 ANALYSIS")
        print(f"{'='*60}")

        print(f"""
  L2 Trigger (P7/P2): {metrics['l2_trigger']:.2f}x

  Part 2 (firmware):
    Median time: {metrics['p2_median']:.1f}s
    Accuracy: {metrics['p2_accuracy']:.1%}

  Part 7 (ceiling):
    Median time: {metrics['p7_median']:.1f}s
    Accuracy: {metrics['p7_accuracy']:.1%}

  Classification: {classification['category']}
  {classification['description']}

  Total responses: {metrics['n_responses']:,}
""")

    else:
        # Run full analysis
        print("\nRunning expert identification analysis...")
        validation = run_expert_identification(df)

        print_summary(df, validation)

        # Show top users by L2
        print(f"\n{'='*60}")
        print(f"TOP {args.top} USERS BY L2 TRIGGER")
        print(f"{'='*60}")

        user_metrics = []
        for user_id, user_df in df.groupby('user_id'):
            metrics = calculate_user_l2_metrics(user_df)
            if metrics:
                metrics['user_id'] = user_id
                user_metrics.append(metrics)

        top_users = sorted(user_metrics, key=lambda x: x['l2_trigger'], reverse=True)[:args.top]

        print(f"\n{'User ID':<12} {'L2':>6} {'P2 Med':>8} {'P7 Med':>8} {'P7 Acc':>8}")
        print("-" * 50)

        for m in top_users:
            print(f"{m['user_id']:<12} {m['l2_trigger']:>6.2f} {m['p2_median']:>8.1f} {m['p7_median']:>8.1f} {m['p7_accuracy']:>8.1%}")


if __name__ == '__main__':
    main()
