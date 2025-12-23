#!/usr/bin/env python3
"""
Run ASSISTments L2 Analysis

Usage:
    python run_assistments_analysis.py
    python run_assistments_analysis.py --data path/to/assistments.csv
    python run_assistments_analysis.py --user USER_ID
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from assistments_l2_metrics import (
    load_assistments_data, calculate_user_l2_metrics,
    calculate_skill_mastery_l2, classify_user,
    run_expert_identification, print_summary
)


def main():
    parser = argparse.ArgumentParser(description='ASSISTments L2 Analysis')
    parser.add_argument('--data', default='../data/assistments/skill_builder_data.csv',
                        help='Path to ASSISTments CSV file')
    parser.add_argument('--user', type=int, help='Analyze specific user ID')
    parser.add_argument('--top', type=int, default=10,
                        help='Show top N users by bimodal index')

    args = parser.parse_args()

    # Load data
    print(f"Loading ASSISTments data from {args.data}...")
    df = load_assistments_data(args.data)
    print(f"Loaded {len(df):,} responses from {df['user_id'].nunique():,} users")

    if args.user:
        # Analyze specific user
        user_df = df[df['user_id'] == args.user]
        if len(user_df) == 0:
            print(f"User {args.user} not found")
            sys.exit(1)

        metrics = calculate_user_l2_metrics(user_df)
        mastery = calculate_skill_mastery_l2(user_df)

        if not metrics:
            print(f"Insufficient data for user {args.user}")
            sys.exit(1)

        classification = classify_user(metrics)

        print(f"\n{'='*60}")
        print(f"USER {args.user} L2 ANALYSIS")
        print(f"{'='*60}")

        print(f"""
  Bimodal Index (P90/P10): {metrics['bimodal']:.1f}x
  L2 Trigger (wrong/right time): {metrics['l2_trigger']:.2f}x

  Response Time Distribution:
    P10 (fast): {metrics['p10']:.1f}s
    Median:     {metrics['p50']:.1f}s
    P90 (slow): {metrics['p90']:.1f}s

  Accuracy: {metrics['accuracy']:.1%}
  Skills practiced: {metrics['n_skills']}

  Classification: {classification['category']}
  {classification['description']}
""")

        if mastery:
            print(f"""
  Skill Mastery Analysis:
    Learning speedup: {mastery['learning_speedup']:.2f}x
    Skills showing speedup: {mastery['skills_with_speedup']}/{mastery['n_skills_analyzed']}
""")

    else:
        # Run full analysis
        print("\nRunning expert identification analysis...")
        validation = run_expert_identification(df)

        print_summary(df, validation)

        # Show top users by bimodal
        print(f"\n{'='*60}")
        print(f"TOP {args.top} USERS BY BIMODAL INDEX")
        print(f"{'='*60}")

        user_metrics = []
        for user_id, user_df in df.groupby('user_id'):
            metrics = calculate_user_l2_metrics(user_df)
            if metrics:
                metrics['user_id'] = user_id
                user_metrics.append(metrics)

        top_users = sorted(user_metrics, key=lambda x: x['bimodal'], reverse=True)[:args.top]

        print(f"\n{'User ID':<12} {'Bimodal':>8} {'L2':>6} {'Accuracy':>10} {'Skills':>8}")
        print("-" * 50)

        for m in top_users:
            print(f"{m['user_id']:<12} {m['bimodal']:>8.1f} {m['l2_trigger']:>6.2f} {m['accuracy']:>10.1%} {m['n_skills']:>8}")


if __name__ == '__main__':
    main()
