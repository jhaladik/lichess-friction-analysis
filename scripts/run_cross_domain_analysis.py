#!/usr/bin/env python3
"""
Cross-Domain L2 Firmware Analysis

Run L2 analysis across all domains and compare results.

Usage:
    python run_cross_domain_analysis.py
    python run_cross_domain_analysis.py --domains chess ednet
"""

import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def run_chess_analysis():
    """Run Chess L2 analysis."""
    print("\n" + "=" * 70)
    print("CHESS L2 ANALYSIS")
    print("=" * 70)

    try:
        from l2_metrics import calculate_l2_metrics, ELITE_BENCHMARKS
        import json

        data_path = '../data/longitudinal_games.json'
        if not os.path.exists(data_path):
            print("  [SKIP] No longitudinal data found. Run run_l2_analysis.py first.")
            return None

        with open(data_path, 'r') as f:
            data = json.load(f)

        results = []
        for username in data:
            games = data[username].get('games_2024', [])
            if len(games) >= 20:
                metrics = calculate_l2_metrics(games, username)
                if metrics:
                    results.append({
                        'username': username,
                        'l2_trigger': metrics['l2_trigger'],
                        'sandwich': metrics['sandwich'],
                        'bimodal': metrics['bimodal']
                    })

        if results:
            l2_values = [r['l2_trigger'] for r in results]
            sandwich_pct = sum(1 for r in results if r['sandwich']) / len(results) * 100

            print(f"""
  Players analyzed: {len(results)}
  Mean L2 Trigger: {sum(l2_values)/len(l2_values):.2f}x
  With Sandwich: {sandwich_pct:.0f}%

  Elite Benchmarks:
    Carlsen: L2 = {ELITE_BENCHMARKS['carlsen']['l2_trigger']}
    Tang: L2 = {ELITE_BENCHMARKS['tang']['l2_trigger']}
    Bartholomew: L2 = {ELITE_BENCHMARKS['bartholomew']['l2_trigger']}
""")
            return {'domain': 'Chess', 'n': len(results), 'mean_l2': sum(l2_values)/len(l2_values)}

    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


def run_ednet_analysis():
    """Run EdNet L2 analysis."""
    print("\n" + "=" * 70)
    print("EDNET L2 ANALYSIS")
    print("=" * 70)

    try:
        from ednet_l2_metrics import load_ednet_data, run_expert_identification

        data_path = '../data/ednet/ednet_clean.csv'
        if not os.path.exists(data_path):
            print("  [SKIP] No EdNet data found.")
            return None

        df = load_ednet_data(data_path)
        validation = run_expert_identification(df)

        print(f"""
  Responses: {len(df):,}
  Users: {df['user_id'].nunique():,}

  Expert Identification:
    AUC: {validation['auc']}
    Expert L2 (median): {validation['expert_l2_median']}x
    Novice L2 (median): {validation['novice_l2_median']}x

  L2 Pattern: Experts wait {validation['expert_l2_median']:.1f}x longer on Part 7 vs Part 2
""")
        return {'domain': 'EdNet', 'auc': validation['auc'], 'n': validation['n_users']}

    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


def run_assistments_analysis():
    """Run ASSISTments L2 analysis."""
    print("\n" + "=" * 70)
    print("ASSISTMENTS L2 ANALYSIS")
    print("=" * 70)

    try:
        from assistments_l2_metrics import load_assistments_data, run_expert_identification

        data_path = '../data/assistments/skill_builder_data.csv'
        if not os.path.exists(data_path):
            print("  [SKIP] No ASSISTments data found.")
            return None

        df = load_assistments_data(data_path)
        validation = run_expert_identification(df)

        print(f"""
  Responses: {len(df):,}
  Users: {df['user_id'].nunique():,}

  Expert Identification:
    AUC (Bimodal): {validation['auc_bimodal']}
    AUC (L2 Trigger): {validation['auc_l2']}

  Note: {validation['note']}
""")
        return {'domain': 'ASSISTments', 'auc': validation['auc_bimodal'], 'n': validation['n_users']}

    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


def run_quizbowl_analysis():
    """Run Quiz Bowl L2 analysis."""
    print("\n" + "=" * 70)
    print("QUIZ BOWL L2 ANALYSIS")
    print("=" * 70)

    try:
        from quizbowl_l2_metrics import load_quizbowl_data, run_expert_identification, download_quizbowl_data

        data_path = '../data/qanta/acf_regionals_2018_buzzes.json'

        if not os.path.exists(data_path):
            print("  Downloading Quiz Bowl data...")
            os.makedirs(os.path.dirname(data_path), exist_ok=True)
            data_path = download_quizbowl_data(os.path.dirname(data_path))

        df = load_quizbowl_data(data_path)
        validation = run_expert_identification(df)

        if 'error' in validation:
            print(f"  [SKIP] {validation['error']}")
            return None

        print(f"""
  Buzzes: {len(df):,}
  Players: {df['player_id'].nunique():,}

  Expert Identification (INVERTED L2):
    AUC: {validation['auc']}
    Expert early accuracy: {validation['expert_early_acc_median']:.1%}
    Novice early accuracy: {validation['novice_early_acc_median']:.1%}

  L2 Pattern: Experts buzz EARLY with high accuracy (firmware domain)
""")
        return {'domain': 'Quiz Bowl', 'auc': validation['auc'], 'n': validation['n_players']}

    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


def print_comparison(results):
    """Print cross-domain comparison."""
    print("\n" + "=" * 70)
    print("CROSS-DOMAIN L2 COMPARISON")
    print("=" * 70)

    valid_results = [r for r in results if r is not None]

    if not valid_results:
        print("  No valid results to compare.")
        return

    print("""
  ┌─────────────┬───────────┬───────────┬─────────────────────────────────┐
  │ Domain      │ Task Type │ Expert ID │ L2 Signature                    │
  ├─────────────┼───────────┼───────────┼─────────────────────────────────┤""")

    domain_info = {
        'Chess': ('Mixed', 'Middlegame slowdown'),
        'EdNet': ('Ceiling', 'Wait MORE on P7'),
        'ASSISTments': ('Mixed', 'Skill-specific timing'),
        'Quiz Bowl': ('Firmware', 'Buzz EARLY + accurate')
    }

    for r in valid_results:
        domain = r['domain']
        task_type, signature = domain_info.get(domain, ('Unknown', 'Unknown'))
        auc = r.get('auc', r.get('mean_l2', 'N/A'))
        if isinstance(auc, float):
            auc_str = f"AUC={auc:.2f}"
        else:
            auc_str = str(auc)

        print(f"  │ {domain:<11} │ {task_type:<9} │ {auc_str:<9} │ {signature:<31} │")

    print("  └─────────────┴───────────┴───────────┴─────────────────────────────────┘")

    print("""
  THE UNIFIED L2 PRINCIPLE:
  ========================

  L2 = Meta-recognition of your own cognitive state

  In CEILING domains (EdNet P7):
    "I don't have firmware for this" → WAIT for more time/info

  In FIRMWARE domains (Quiz Bowl):
    "I already know this" → ACT FAST with confidence

  In MIXED domains (Chess):
    Opening (firmware) → Fast
    Middlegame (ceiling) → Slow
    Endgame (firmware) → Fast

  The pattern is universal - the direction depends on task automability.
""")


def main():
    parser = argparse.ArgumentParser(description='Cross-Domain L2 Analysis')
    parser.add_argument('--domains', nargs='+',
                        choices=['chess', 'ednet', 'assistments', 'quizbowl', 'all'],
                        default=['all'],
                        help='Domains to analyze')

    args = parser.parse_args()

    print("=" * 70)
    print("GRADIENT-FRICTION THEORY: CROSS-DOMAIN L2 VALIDATION")
    print("=" * 70)

    domains = args.domains
    if 'all' in domains:
        domains = ['chess', 'ednet', 'assistments', 'quizbowl']

    results = []

    if 'chess' in domains:
        results.append(run_chess_analysis())

    if 'ednet' in domains:
        results.append(run_ednet_analysis())

    if 'assistments' in domains:
        results.append(run_assistments_analysis())

    if 'quizbowl' in domains:
        results.append(run_quizbowl_analysis())

    print_comparison(results)


if __name__ == '__main__':
    main()
