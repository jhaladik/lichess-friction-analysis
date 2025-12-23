"""
EdNet L2 Firmware Analysis

L2 metric for EdNet: Part 7 (reading comprehension) / Part 2 (basic) response time ratio.
- Part 2: Grammar/vocabulary - can be "firmware" (pattern recognition)
- Part 7: Reading comprehension - "ceiling" task (can't be automated)

Expert signature: HIGH P7/P2 ratio (knows to slow down on ceiling tasks)
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from sklearn.metrics import roc_auc_score


def load_ednet_data(filepath: str) -> pd.DataFrame:
    """Load and prepare EdNet data."""
    df = pd.read_csv(filepath)

    # Ensure we have required columns
    required = ['user_id', 'part', 'elapsed_time_sec', 'correct']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Filter valid response times (0.5s to 300s)
    df = df[(df['elapsed_time_sec'] >= 0.5) & (df['elapsed_time_sec'] <= 300)]

    return df


def calculate_user_l2_metrics(user_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Calculate L2 metrics for a single user.

    Returns None if insufficient data.
    """
    # Need data from both Part 2 and Part 7
    part2 = user_df[user_df['part'] == 2]['elapsed_time_sec']
    part7 = user_df[user_df['part'] == 7]['elapsed_time_sec']

    if len(part2) < 5 or len(part7) < 5:
        return None

    # Median response times by part
    p2_median = part2.median()
    p7_median = part7.median()

    # L2 Trigger: How much slower on ceiling (P7) vs firmware (P2)
    l2_trigger = p7_median / p2_median if p2_median > 0 else 0

    # Accuracy by part
    p2_acc = user_df[user_df['part'] == 2]['correct'].mean()
    p7_acc = user_df[user_df['part'] == 7]['correct'].mean()

    # Overall metrics
    overall_median = user_df['elapsed_time_sec'].median()
    overall_acc = user_df['correct'].mean()

    # Part ratios (normalized to user's overall median)
    part_medians = user_df.groupby('part')['elapsed_time_sec'].median()
    part_ratios = part_medians / overall_median

    return {
        'l2_trigger': round(l2_trigger, 2),
        'p2_median': round(p2_median, 2),
        'p7_median': round(p7_median, 2),
        'p2_accuracy': round(p2_acc, 3),
        'p7_accuracy': round(p7_acc, 3),
        'overall_accuracy': round(overall_acc, 3),
        'overall_median': round(overall_median, 2),
        'part_ratios': {int(k): round(v, 2) for k, v in part_ratios.items()},
        'n_responses': len(user_df),
        'n_p2': len(part2),
        'n_p7': len(part7)
    }


def classify_user(metrics: Dict[str, Any]) -> Dict[str, str]:
    """
    Classify user based on L2 metrics.

    Expert signature: High P7/P2 ratio (knows to slow down on reading)
    """
    l2 = metrics['l2_trigger']
    p7_acc = metrics['p7_accuracy']

    if l2 >= 1.5 and p7_acc >= 0.7:
        category = "EXPERT"
        description = "High L2 + high P7 accuracy - strategic slowdown works"
    elif l2 >= 1.3:
        category = "DEVELOPING"
        description = "Shows L2 pattern but may need more practice"
    elif l2 >= 1.0:
        category = "INTERMEDIATE"
        description = "Slight slowdown on P7 - developing awareness"
    else:
        category = "NOVICE"
        description = "Faster on P7 than P2 - may be rushing through reading"

    return {
        'category': category,
        'description': description,
        'l2_trigger': l2,
        'p7_accuracy': p7_acc
    }


def run_expert_identification(df: pd.DataFrame,
                              accuracy_threshold: float = 0.75) -> Dict[str, Any]:
    """
    Test if L2 trigger can identify experts (defined by accuracy).

    Returns AUC and other validation metrics.
    """
    # Calculate metrics for each user
    user_metrics = []

    for user_id, user_df in df.groupby('user_id'):
        metrics = calculate_user_l2_metrics(user_df)
        if metrics:
            metrics['user_id'] = user_id
            user_metrics.append(metrics)

    if len(user_metrics) < 100:
        return {'error': 'Insufficient users'}

    # Define experts by overall accuracy
    l2_values = [m['l2_trigger'] for m in user_metrics]
    accuracies = [m['overall_accuracy'] for m in user_metrics]
    is_expert = [1 if a >= accuracy_threshold else 0 for a in accuracies]

    # Calculate AUC
    auc = roc_auc_score(is_expert, l2_values)

    # Compare groups
    expert_l2 = [m['l2_trigger'] for m in user_metrics if m['overall_accuracy'] >= accuracy_threshold]
    novice_l2 = [m['l2_trigger'] for m in user_metrics if m['overall_accuracy'] < accuracy_threshold]

    return {
        'auc': round(auc, 3),
        'n_users': len(user_metrics),
        'n_experts': sum(is_expert),
        'expert_l2_mean': round(np.mean(expert_l2), 2),
        'novice_l2_mean': round(np.mean(novice_l2), 2),
        'expert_l2_median': round(np.median(expert_l2), 2),
        'novice_l2_median': round(np.median(novice_l2), 2)
    }


def analyze_by_part(df: pd.DataFrame) -> pd.DataFrame:
    """
    Analyze response time patterns by TOEIC part.

    TOEIC Parts:
    1: Photos (listening)
    2: Question-Response (listening)
    3: Conversations (listening)
    4: Talks (listening)
    5: Incomplete Sentences (grammar/vocab - FIRMWARE)
    6: Text Completion (grammar in context)
    7: Reading Comprehension (CEILING)
    """
    part_stats = df.groupby('part').agg({
        'elapsed_time_sec': ['median', 'mean', 'std', 'count'],
        'correct': 'mean'
    }).round(2)

    part_stats.columns = ['median_time', 'mean_time', 'std_time', 'count', 'accuracy']

    return part_stats


# Part descriptions for TOEIC
TOEIC_PARTS = {
    1: "Photos (listening)",
    2: "Question-Response (firmware)",
    3: "Conversations (listening)",
    4: "Talks (listening)",
    5: "Incomplete Sentences (firmware)",
    6: "Text Completion (mixed)",
    7: "Reading Comprehension (ceiling)"
}


def print_summary(df: pd.DataFrame, validation: Dict[str, Any]):
    """Print formatted analysis summary."""
    print("=" * 70)
    print("EdNet L2 ANALYSIS SUMMARY")
    print("=" * 70)

    print(f"\nData: {len(df):,} responses from {df['user_id'].nunique():,} users")

    print("\n" + "-" * 70)
    print("RESPONSE TIME BY TOEIC PART")
    print("-" * 70)

    part_stats = analyze_by_part(df)
    for part in sorted(part_stats.index):
        row = part_stats.loc[part]
        desc = TOEIC_PARTS.get(part, "Unknown")
        print(f"  Part {part} ({desc}):")
        print(f"    Median: {row['median_time']:.1f}s, Accuracy: {row['accuracy']:.1%}")

    print("\n" + "-" * 70)
    print("L2 EXPERT IDENTIFICATION")
    print("-" * 70)

    print(f"""
  AUC: {validation['auc']} (ability to identify experts from L2 alone)

  Expert L2 (median): {validation['expert_l2_median']}
  Novice L2 (median): {validation['novice_l2_median']}

  Key Finding: Experts wait {validation['expert_l2_median']}x longer on Part 7 vs Part 2
               Novices wait {validation['novice_l2_median']}x longer
""")
