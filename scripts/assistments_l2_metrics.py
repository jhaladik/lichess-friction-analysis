"""
ASSISTments L2 Firmware Analysis

L2 metric for ASSISTments: Bimodal response time distribution by skill mastery.

Key insight: ASSISTments shows INVERTED L2 pattern for some users.
- Users who are fast on mastered skills and slow on new skills = L2 present
- Users who are uniformly slow = no firmware developed
- Users who are uniformly fast = may be guessing

The L2 signature here is about skill-specific timing adjustment.
"""

import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Any
from sklearn.metrics import roc_auc_score


def load_assistments_data(filepath: str) -> pd.DataFrame:
    """Load and prepare ASSISTments data."""
    df = pd.read_csv(filepath)

    # Key columns
    required = ['user_id', 'skill_id', 'ms_first_response', 'correct']
    for col in required:
        if col not in df.columns:
            raise ValueError(f"Missing required column: {col}")

    # Convert ms to seconds
    df['response_time_sec'] = df['ms_first_response'] / 1000.0

    # Filter valid response times (0.5s to 300s)
    df = df[(df['response_time_sec'] >= 0.5) & (df['response_time_sec'] <= 300)]

    return df


def calculate_user_l2_metrics(user_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Calculate L2 metrics for a single user.

    For ASSISTments, L2 = skill-specific timing adjustment.
    """
    if len(user_df) < 20:
        return None

    # Get response times
    times = user_df['response_time_sec'].values

    # Bimodal index (P90/P10)
    p10 = np.percentile(times, 10)
    p25 = np.percentile(times, 25)
    p50 = np.percentile(times, 50)
    p75 = np.percentile(times, 75)
    p90 = np.percentile(times, 90)

    bimodal = p90 / p10 if p10 > 0 else 0

    # CV (coefficient of variation)
    cv = np.std(times) / np.mean(times) if np.mean(times) > 0 else 0

    # Skill-specific analysis
    skill_times = user_df.groupby('skill_id')['response_time_sec'].median()

    if len(skill_times) >= 3:
        # Compare fastest vs slowest skills
        fastest_skills = skill_times.nsmallest(3).mean()
        slowest_skills = skill_times.nlargest(3).mean()
        skill_range = slowest_skills / fastest_skills if fastest_skills > 0 else 0
    else:
        skill_range = 0

    # Accuracy vs timing relationship
    # For problems they got right vs wrong
    correct_times = user_df[user_df['correct'] == 1]['response_time_sec']
    incorrect_times = user_df[user_df['correct'] == 0]['response_time_sec']

    if len(correct_times) > 5 and len(incorrect_times) > 5:
        # L2 trigger: Do they take longer on problems they get wrong?
        l2_trigger = incorrect_times.median() / correct_times.median()
    else:
        l2_trigger = 1.0

    return {
        'l2_trigger': round(l2_trigger, 2),
        'bimodal': round(bimodal, 2),
        'cv': round(cv, 2),
        'skill_range': round(skill_range, 2),
        'p10': round(p10, 2),
        'p50': round(p50, 2),
        'p90': round(p90, 2),
        'accuracy': round(user_df['correct'].mean(), 3),
        'n_responses': len(user_df),
        'n_skills': user_df['skill_id'].nunique()
    }


def calculate_skill_mastery_l2(user_df: pd.DataFrame) -> Optional[Dict[str, Any]]:
    """
    Calculate L2 based on skill mastery progression.

    Tracks if user speeds up on skills they've practiced more.
    """
    if len(user_df) < 30:
        return None

    # Calculate opportunity count per skill
    user_df = user_df.copy()

    # Group by skill and analyze timing progression
    skill_progression = []

    for skill_id, skill_df in user_df.groupby('skill_id'):
        if len(skill_df) < 3:
            continue

        skill_df = skill_df.sort_values('opportunity' if 'opportunity' in skill_df.columns else 'order_id')
        times = skill_df['response_time_sec'].values

        # Compare first attempts vs later attempts
        early = times[:len(times)//3]
        late = times[-len(times)//3:]

        if len(early) > 0 and len(late) > 0:
            speedup = np.median(early) / np.median(late) if np.median(late) > 0 else 1
            skill_progression.append({
                'skill_id': skill_id,
                'early_time': np.median(early),
                'late_time': np.median(late),
                'speedup': speedup,
                'n_attempts': len(skill_df)
            })

    if len(skill_progression) < 3:
        return None

    # L2 = average speedup across skills (learning signal)
    speedups = [s['speedup'] for s in skill_progression]

    return {
        'learning_speedup': round(np.median(speedups), 2),
        'speedup_consistency': round(np.std(speedups), 2),
        'n_skills_analyzed': len(skill_progression),
        'skills_with_speedup': sum(1 for s in speedups if s > 1.2)
    }


def classify_user(metrics: Dict[str, Any]) -> Dict[str, str]:
    """
    Classify user based on ASSISTments L2 metrics.
    """
    bimodal = metrics['bimodal']
    l2 = metrics['l2_trigger']
    acc = metrics['accuracy']

    if bimodal >= 5.0 and l2 >= 1.2 and acc >= 0.7:
        category = "STRONG_L2"
        description = "High bimodality + longer on hard = strong metacognition"
    elif bimodal >= 3.0 and l2 >= 1.1:
        category = "DEVELOPING_L2"
        description = "Shows timing variation and some L2 pattern"
    elif bimodal < 2.0:
        category = "UNIFORM"
        description = "Low bimodality - same speed for all problems"
    else:
        category = "MIXED"
        description = "Variable pattern, needs more analysis"

    return {
        'category': category,
        'description': description,
        'bimodal': bimodal,
        'l2_trigger': l2
    }


def run_expert_identification(df: pd.DataFrame,
                              accuracy_threshold: float = 0.75) -> Dict[str, Any]:
    """
    Test if bimodal index can identify experts.

    Note: ASSISTments often shows WEAK or INVERTED L2 signal
    because the task structure is different from EdNet/Chess.
    """
    user_metrics = []

    for user_id, user_df in df.groupby('user_id'):
        metrics = calculate_user_l2_metrics(user_df)
        if metrics:
            metrics['user_id'] = user_id
            user_metrics.append(metrics)

    if len(user_metrics) < 100:
        return {'error': 'Insufficient users'}

    # Define experts by accuracy
    bimodal_values = [m['bimodal'] for m in user_metrics]
    l2_values = [m['l2_trigger'] for m in user_metrics]
    accuracies = [m['accuracy'] for m in user_metrics]
    is_expert = [1 if a >= accuracy_threshold else 0 for a in accuracies]

    # Calculate AUC for different predictors
    auc_bimodal = roc_auc_score(is_expert, bimodal_values)
    auc_l2 = roc_auc_score(is_expert, l2_values)

    return {
        'auc_bimodal': round(auc_bimodal, 3),
        'auc_l2': round(auc_l2, 3),
        'n_users': len(user_metrics),
        'n_experts': sum(is_expert),
        'note': 'ASSISTments often shows weak L2 due to task structure'
    }


def print_summary(df: pd.DataFrame, validation: Dict[str, Any]):
    """Print formatted analysis summary."""
    print("=" * 70)
    print("ASSISTments L2 ANALYSIS SUMMARY")
    print("=" * 70)

    print(f"\nData: {len(df):,} responses from {df['user_id'].nunique():,} users")
    print(f"Skills: {df['skill_id'].nunique():,} unique skills")

    print("\n" + "-" * 70)
    print("L2 EXPERT IDENTIFICATION")
    print("-" * 70)

    print(f"""
  AUC (Bimodal Index): {validation['auc_bimodal']}
  AUC (L2 Trigger): {validation['auc_l2']}

  Note: {validation['note']}

  In ASSISTments, the L2 signal is often weaker because:
  - Problems are more uniform in difficulty within skills
  - Scaffolding (hints) changes the timing dynamics
  - Mastery-based progression affects response patterns
""")
