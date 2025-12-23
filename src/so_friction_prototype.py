"""
Stack Overflow Friction Analysis Prototype

Quick test of core hypothesis using Stack Exchange API.
"""

import sys
import sqlite3
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime, timedelta
import logging

from stackoverflow_api import (
    StackOverflowAPI,
    parse_question,
    parse_answer,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def fetch_sample_data(api: StackOverflowAPI, tag: str, max_questions: int = 200) -> tuple:
    """
    Fetch sample questions and answers for a tag.

    Returns:
        (questions_list, answers_list)
    """
    questions = []
    questions_by_id = {}

    # Fetch recent questions (last 30 days)
    todate = int(datetime.now().timestamp())
    fromdate = int((datetime.now() - timedelta(days=30)).timestamp())

    page = 1
    while len(questions) < max_questions:
        try:
            result = api.get_questions_with_answers(
                tag=tag,
                page=page,
                pagesize=100,
                fromdate=fromdate,
                todate=todate,
            )

            items = result.get("items", [])
            if not items:
                break

            for item in items:
                q = parse_question(item)
                if q and q["answer_count"] > 0:
                    questions.append(q)
                    questions_by_id[q["question_id"]] = q

            if not result.get("has_more", False):
                break

            page += 1

            if api.quota_remaining < 20:
                logger.warning("API quota low, stopping questions")
                break

        except Exception as e:
            logger.error(f"Error fetching questions: {e}")
            break

    logger.info(f"Fetched {len(questions)} questions")

    # Now fetch answers for these questions in batches
    answers = []
    question_ids = list(questions_by_id.keys())

    for i in range(0, len(question_ids), 100):
        batch = question_ids[i:i+100]
        try:
            result = api.get_answers_for_questions(batch)
            for ans_item in result.get("items", []):
                qid = ans_item.get("question_id")
                if qid in questions_by_id:
                    a = parse_answer(ans_item, questions_by_id[qid])
                    if a:
                        answers.append(a)

            if api.quota_remaining < 10:
                logger.warning("API quota low, stopping answers")
                break
        except Exception as e:
            logger.error(f"Error fetching answers: {e}")
            break

    logger.info(f"Fetched {len(answers)} answers")
    return questions, answers


def create_friction_records(answers: list) -> pd.DataFrame:
    """
    Create friction analysis records from answers.
    """
    df = pd.DataFrame(answers)

    if df.empty:
        return df

    # Filter to answers with valid response times
    df = df[df["response_time_seconds"] > 0]
    df = df[df["response_time_seconds"] < 86400 * 7]  # Max 1 week

    # Calculate user-normalized response time
    # (simplified: use overall median as baseline for prototype)
    median_response = df["response_time_seconds"].median()
    df["response_time_normalized"] = df["response_time_seconds"] / median_response

    # Classify friction
    df["friction_level"] = pd.cut(
        df["response_time_normalized"],
        bins=[0, 0.5, 1.5, float("inf")],
        labels=["fast", "normal", "slow"]
    )

    # Error classification (conservative: downvoted = error)
    df["is_error"] = df["score"] < 0

    # Alternative: low quality = score <= 0 and not accepted
    df["is_low_quality"] = (df["score"] <= 0) & (~df["is_accepted"])

    # Friction gap: complex question + fast answer
    df["expected_friction"] = df["question_complexity"] > 0.5
    df["actual_friction"] = df["response_time_normalized"] > 1.0
    df["friction_gap"] = df["expected_friction"] & ~df["actual_friction"]

    return df


def test_speed_error_correlation(df: pd.DataFrame) -> dict:
    """
    Test 1: In complex questions, do faster answers have higher error rates?

    Chess finding: r=0.175 (longer think → more blunders)
    Hypothesis inversion: If same pattern, SLOWER responses should have more errors
    """
    results = {}

    # Divide by complexity quartile
    df["complexity_quartile"] = pd.qcut(
        df["question_complexity"],
        4,
        labels=["Q1_simple", "Q2", "Q3", "Q4_complex"],
        duplicates="drop"
    )

    for quartile in ["Q1_simple", "Q2", "Q3", "Q4_complex"]:
        subset = df[df["complexity_quartile"] == quartile]

        if len(subset) < 20:
            continue

        # Use low_quality as error proxy (more signal than downvotes)
        if subset["is_low_quality"].var() == 0:
            continue

        corr, p_value = stats.pointbiserialr(
            subset["is_low_quality"],
            subset["response_time_normalized"]
        )

        results[quartile] = {
            "correlation": round(corr, 3),
            "p_value": round(p_value, 4),
            "n": len(subset),
            "error_rate": round(subset["is_low_quality"].mean() * 100, 1),
            "mean_response_hours": round(subset["response_time_seconds"].mean() / 3600, 1),
        }

    return results


def test_firmware_by_reputation(df: pd.DataFrame) -> dict:
    """
    Test 2: Higher reputation → more firmware coverage?

    Chess finding: 33% → 53% firmware across rating bands
    """
    rep_bands = [
        (0, 100, "Novice"),
        (100, 1000, "Learner"),
        (1000, 10000, "Intermediate"),
        (10000, 100000, "Expert"),
        (100000, float("inf"), "Elite"),
    ]

    results = {}

    for low, high, label in rep_bands:
        subset = df[(df["owner_reputation"] >= low) & (df["owner_reputation"] < high)]

        if len(subset) < 20:
            continue

        # Firmware = fast + successful (accepted or score >= 1)
        firmware = subset[
            (subset["response_time_normalized"] < 0.7) &
            (subset["is_accepted"] | (subset["score"] >= 1))
        ]

        coverage = len(firmware) / len(subset)

        # Fast answers only
        fast = subset[subset["response_time_normalized"] < 0.7]
        fast_error_rate = fast["is_low_quality"].mean() if len(fast) > 0 else 0

        results[label] = {
            "n": len(subset),
            "firmware_coverage": round(coverage * 100, 1),
            "fast_error_rate": round(fast_error_rate * 100, 1),
            "avg_response_hours": round(subset["response_time_seconds"].mean() / 3600, 1),
            "acceptance_rate": round(subset["is_accepted"].mean() * 100, 1),
        }

    return results


def test_friction_gap_trap(df: pd.DataFrame) -> dict:
    """
    Test 3: Friction gap (complex + fast) → higher error rate?

    Chess finding: Fast blunders in complex positions = firmware misfire
    """
    # Complex questions
    complex_q = df[df["question_complexity"] > 0.5]

    if len(complex_q) < 20:
        return {"error": "Not enough complex questions"}

    # Fast vs slow on complex questions
    fast_complex = complex_q[complex_q["response_time_normalized"] < 0.7]
    slow_complex = complex_q[complex_q["response_time_normalized"] > 1.5]

    results = {
        "fast_on_complex": {
            "n": len(fast_complex),
            "error_rate": round(fast_complex["is_low_quality"].mean() * 100, 1) if len(fast_complex) > 0 else 0,
            "downvote_rate": round(fast_complex["is_error"].mean() * 100, 1) if len(fast_complex) > 0 else 0,
        },
        "slow_on_complex": {
            "n": len(slow_complex),
            "error_rate": round(slow_complex["is_low_quality"].mean() * 100, 1) if len(slow_complex) > 0 else 0,
            "downvote_rate": round(slow_complex["is_error"].mean() * 100, 1) if len(slow_complex) > 0 else 0,
        },
    }

    # Simple questions for comparison
    simple_q = df[df["question_complexity"] < 0.3]
    fast_simple = simple_q[simple_q["response_time_normalized"] < 0.7]

    results["fast_on_simple"] = {
        "n": len(fast_simple),
        "error_rate": round(fast_simple["is_low_quality"].mean() * 100, 1) if len(fast_simple) > 0 else 0,
    }

    return results


def test_reputation_gap_trap(df: pd.DataFrame) -> dict:
    """
    Test 4: Expert answering newbie → relaxation trap?

    Chess finding: Winning position → 37.4% blunder rate (vs 27.4% baseline)
    """
    # Calculate reputation gap
    df = df.copy()
    df["rep_gap"] = df["owner_reputation"] / (df["question_owner_reputation"] + 1)

    # High gap (expert >> asker)
    high_gap = df[df["rep_gap"] > 10]
    low_gap = df[df["rep_gap"] <= 2]

    results = {}

    for label, subset in [("high_gap", high_gap), ("low_gap", low_gap)]:
        if len(subset) < 20:
            continue

        # Complex questions only
        complex_subset = subset[subset["question_complexity"] > 0.5]

        # Fast answers
        fast = complex_subset[complex_subset["response_time_normalized"] < 0.7]

        results[label] = {
            "n_complex": len(complex_subset),
            "n_fast_complex": len(fast),
            "fast_error_rate": round(fast["is_low_quality"].mean() * 100, 1) if len(fast) > 0 else 0,
            "all_error_rate": round(complex_subset["is_low_quality"].mean() * 100, 1) if len(complex_subset) > 0 else 0,
        }

    return results


def run_prototype(tags: list = None):
    """
    Run the prototype analysis.
    """
    if tags is None:
        tags = ["python"]  # Start with just Python

    api = StackOverflowAPI()

    all_answers = []

    for tag in tags:
        logger.info(f"\n{'='*50}")
        logger.info(f"Fetching data for tag: {tag}")
        logger.info(f"{'='*50}")

        questions, answers = fetch_sample_data(api, tag, max_questions=300)
        all_answers.extend(answers)

        logger.info(f"API quota remaining: {api.quota_remaining}")

    if not all_answers:
        logger.error("No data fetched!")
        return

    logger.info(f"\nTotal answers: {len(all_answers)}")

    # Create friction records
    df = create_friction_records(all_answers)
    logger.info(f"Valid friction records: {len(df)}")

    # Summary stats
    print("\n" + "="*60)
    print("STACK OVERFLOW FRICTION PROTOTYPE RESULTS")
    print("="*60)

    print(f"\nSample size: {len(df)} answers")
    print(f"Tags: {tags}")
    print(f"Date range: last 30 days")

    print(f"\nBasic stats:")
    print(f"  Median response time: {df['response_time_seconds'].median() / 3600:.1f} hours")
    print(f"  Mean complexity: {df['question_complexity'].mean():.2f}")
    print(f"  Overall acceptance rate: {df['is_accepted'].mean() * 100:.1f}%")
    print(f"  Downvote rate: {df['is_error'].mean() * 100:.1f}%")
    print(f"  Low quality rate: {df['is_low_quality'].mean() * 100:.1f}%")

    # Run tests
    print("\n" + "-"*60)
    print("TEST 1: Speed-Error Correlation by Complexity")
    print("-"*60)
    print("(Chess finding: r=0.175 in Q4 - longer think → more errors)")
    print()

    test1 = test_speed_error_correlation(df)
    for q, data in test1.items():
        print(f"  {q}:")
        print(f"    r = {data['correlation']}, p = {data['p_value']}, n = {data['n']}")
        print(f"    error_rate = {data['error_rate']}%, avg_response = {data['mean_response_hours']}h")

    print("\n" + "-"*60)
    print("TEST 2: Firmware Coverage by Reputation")
    print("-"*60)
    print("(Chess finding: 33% → 53% firmware across rating bands)")
    print()

    test2 = test_firmware_by_reputation(df)
    for level, data in test2.items():
        print(f"  {level}: coverage={data['firmware_coverage']}%, fast_error={data['fast_error_rate']}%, n={data['n']}")

    print("\n" + "-"*60)
    print("TEST 3: Friction Gap Trap")
    print("-"*60)
    print("(Chess finding: Fast on complex = firmware misfire)")
    print()

    test3 = test_friction_gap_trap(df)
    for condition, data in test3.items():
        print(f"  {condition}: error={data.get('error_rate', 'N/A')}%, n={data.get('n', 'N/A')}")

    print("\n" + "-"*60)
    print("TEST 4: Reputation Gap Trap")
    print("-"*60)
    print("(Chess finding: Winning → relaxation → 37% blunder rate)")
    print()

    test4 = test_reputation_gap_trap(df)
    for gap, data in test4.items():
        print(f"  {gap}: fast_error={data.get('fast_error_rate', 'N/A')}%, n_fast={data.get('n_fast_complex', 'N/A')}")

    print("\n" + "="*60)
    print("PROTOTYPE INTERPRETATION")
    print("="*60)

    # Save data for further analysis
    df.to_pickle("/tmp/so_friction_prototype.pkl")
    print(f"\nData saved to /tmp/so_friction_prototype.pkl")

    return df, {
        "test1": test1,
        "test2": test2,
        "test3": test3,
        "test4": test4,
    }


if __name__ == "__main__":
    tags = sys.argv[1:] if len(sys.argv) > 1 else ["python"]
    run_prototype(tags)
