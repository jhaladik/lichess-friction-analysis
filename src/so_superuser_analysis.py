"""
Stack Overflow Super User Analysis

Track firmware development over the career of expert users.
"""

import sys
import pandas as pd
import numpy as np
from scipy import stats
from datetime import datetime
from collections import defaultdict
import logging

from stackoverflow_api import StackOverflowAPI

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def find_super_users(api: StackOverflowAPI, tag: str = "python") -> list:
    """Find top answerers for a tag."""
    logger.info(f"Finding top users for tag: {tag}")
    result = api.get_top_users(tag, pagesize=10)

    users = []
    for item in result.get("items", []):
        user = item.get("user", {})
        users.append({
            "user_id": user.get("user_id"),
            "display_name": user.get("display_name"),
            "reputation": user.get("reputation"),
            "answer_count": item.get("post_count"),
            "score": item.get("score"),
        })

    return users


def fetch_user_career(api: StackOverflowAPI, user_id: int, max_answers: int = 500) -> list:
    """
    Fetch a user's answer history chronologically.

    Returns list of answers with metadata.
    """
    answers = []
    page = 1

    while len(answers) < max_answers:
        logger.info(f"Fetching answers page {page} for user {user_id}")
        result = api.get_user_answers(user_id, page=page, pagesize=100)

        items = result.get("items", [])
        if not items:
            break

        for item in items:
            answer = {
                "answer_id": item.get("answer_id"),
                "question_id": item.get("question_id"),
                "creation_date": datetime.fromtimestamp(item.get("creation_date", 0)),
                "score": item.get("score", 0),
                "is_accepted": item.get("is_accepted", False),
                "tags": item.get("tags", []),
            }
            answers.append(answer)

        if not result.get("has_more", False):
            break

        page += 1

        if api.quota_remaining < 20:
            logger.warning("API quota low, stopping")
            break

    logger.info(f"Fetched {len(answers)} answers for user {user_id}")
    return answers


def fetch_user_tags(api: StackOverflowAPI, user_id: int) -> list:
    """Fetch tags a user has answered in."""
    result = api.get_user_tags(user_id, pagesize=100)

    tags = []
    for item in result.get("items", []):
        tags.append({
            "tag": item.get("name"),
            "count": item.get("count"),
        })

    return tags


def analyze_career_trajectory(answers: list, display_name: str) -> dict:
    """
    Analyze a user's career trajectory.

    Track how their firmware develops over time.
    """
    if not answers:
        return {}

    df = pd.DataFrame(answers)
    df = df.sort_values("creation_date")

    # Split career into phases
    n = len(df)
    df["career_phase"] = pd.cut(
        range(n),
        bins=[0, n//4, n//2, 3*n//4, n],
        labels=["Early", "Growing", "Established", "Expert"],
        include_lowest=True
    )

    # Calculate metrics per phase
    phases = {}
    for phase in ["Early", "Growing", "Established", "Expert"]:
        subset = df[df["career_phase"] == phase]
        if len(subset) == 0:
            continue

        # Tag diversity (firmware breadth)
        all_tags = []
        for tags in subset["tags"]:
            if tags:
                all_tags.extend(tags)
        unique_tags = len(set(all_tags))

        phases[phase] = {
            "n_answers": len(subset),
            "acceptance_rate": subset["is_accepted"].mean() * 100,
            "avg_score": subset["score"].mean(),
            "unique_tags": unique_tags,
            "date_range": f"{subset['creation_date'].min().strftime('%Y-%m')} to {subset['creation_date'].max().strftime('%Y-%m')}",
        }

    # Tag specialization over career
    early_tags = defaultdict(int)
    late_tags = defaultdict(int)

    early_df = df[df["career_phase"] == "Early"]
    late_df = df[df["career_phase"] == "Expert"]

    for tags in early_df["tags"]:
        if tags:
            for t in tags:
                early_tags[t] += 1

    for tags in late_df["tags"]:
        if tags:
            for t in tags:
                late_tags[t] += 1

    # Top tags early vs late
    early_top = sorted(early_tags.items(), key=lambda x: -x[1])[:10]
    late_top = sorted(late_tags.items(), key=lambda x: -x[1])[:10]

    return {
        "display_name": display_name,
        "total_answers": len(df),
        "career_span_days": (df["creation_date"].max() - df["creation_date"].min()).days,
        "phases": phases,
        "early_top_tags": early_top,
        "late_top_tags": late_top,
        "overall_acceptance": df["is_accepted"].mean() * 100,
        "overall_avg_score": df["score"].mean(),
    }


def fetch_user_top_tags(api: StackOverflowAPI, user_id: int) -> list:
    """Fetch user's top answer tags with stats."""
    logger.info(f"Fetching top tags for user {user_id}")
    result = api.get_user_top_tags(user_id)

    tags = []
    for item in result.get("items", []):
        tags.append({
            "tag": item.get("tag_name"),
            "answer_count": item.get("answer_count", 0),
            "answer_score": item.get("answer_score", 0),
        })

    return tags


def analyze_tag_firmware_from_api(tags: list, display_name: str) -> dict:
    """
    Analyze firmware development from tag stats.

    Uses the top-answer-tags API data.
    """
    if not tags:
        return {"display_name": display_name, "tags_analyzed": 0, "firmware_tags": 0,
                "partial_tags": 0, "learning_tags": 0, "top_tags": {}}

    tag_firmware = {}

    for tag_data in tags:
        tag = tag_data["tag"]
        n_answers = tag_data["answer_count"]
        total_score = tag_data["answer_score"]

        if n_answers == 0:
            continue

        avg_score = total_score / n_answers

        # Firmware status based on volume and quality
        # High avg score + many answers = firmware installed
        if avg_score > 5 and n_answers > 100:
            status = "FIRMWARE"
        elif avg_score > 2 and n_answers > 20:
            status = "PARTIAL"
        else:
            status = "LEARNING"

        tag_firmware[tag] = {
            "n_answers": n_answers,
            "total_score": total_score,
            "avg_score": round(avg_score, 2),
            "status": status,
        }

    # Sort by answer count
    sorted_tags = sorted(tag_firmware.items(), key=lambda x: -x[1]["n_answers"])

    return {
        "display_name": display_name,
        "tags_analyzed": len(tag_firmware),
        "firmware_tags": sum(1 for t in tag_firmware.values() if t["status"] == "FIRMWARE"),
        "partial_tags": sum(1 for t in tag_firmware.values() if t["status"] == "PARTIAL"),
        "learning_tags": sum(1 for t in tag_firmware.values() if t["status"] == "LEARNING"),
        "top_tags": dict(sorted_tags[:20]),
    }


def print_career_analysis(analysis: dict):
    """Pretty print career analysis."""
    print(f"\n{'='*60}")
    print(f"CAREER TRAJECTORY: {analysis['display_name']}")
    print(f"{'='*60}")

    print(f"\nTotal answers: {analysis['total_answers']}")
    print(f"Career span: {analysis['career_span_days']} days ({analysis['career_span_days']//365} years)")
    print(f"Overall acceptance: {analysis['overall_acceptance']:.1f}%")
    print(f"Overall avg score: {analysis['overall_avg_score']:.2f}")

    print(f"\n{'Career Phase Analysis':^50}")
    print("-" * 60)
    print(f"{'Phase':<12} {'Answers':>8} {'Accept%':>8} {'Score':>8} {'Tags':>6}")
    print("-" * 60)

    for phase, data in analysis["phases"].items():
        print(f"{phase:<12} {data['n_answers']:>8} {data['acceptance_rate']:>7.1f}% {data['avg_score']:>8.2f} {data['unique_tags']:>6}")

    print(f"\nEarly career top tags: {[t[0] for t in analysis['early_top_tags'][:5]]}")
    print(f"Expert phase top tags: {[t[0] for t in analysis['late_top_tags'][:5]]}")


def print_firmware_analysis(analysis: dict):
    """Pretty print firmware analysis."""
    print(f"\n{'='*60}")
    print(f"FIRMWARE MAP: {analysis['display_name']}")
    print(f"{'='*60}")

    print(f"\nTags analyzed: {analysis['tags_analyzed']}")
    print(f"FIRMWARE (mastered): {analysis['firmware_tags']}")
    print(f"PARTIAL (developing): {analysis['partial_tags']}")
    print(f"LEARNING (early): {analysis['learning_tags']}")

    firmware_pct = analysis['firmware_tags'] / analysis['tags_analyzed'] * 100 if analysis['tags_analyzed'] > 0 else 0
    print(f"\nFirmware coverage: {firmware_pct:.0f}%")

    print(f"\n{'Top Tags by Activity':^60}")
    print("-" * 70)
    print(f"{'Tag':<25} {'Answers':>8} {'Score':>10} {'Avg':>8} {'Status':<10}")
    print("-" * 70)

    for tag, data in analysis["top_tags"].items():
        print(f"{tag:<25} {data['n_answers']:>8} {data['total_score']:>10} {data['avg_score']:>8.2f} {data['status']:<10}")


def run_analysis(user_ids: list = None):
    """Run the super user analysis."""
    api = StackOverflowAPI()

    # First, find top users if not specified
    if not user_ids:
        print("Finding top Python answerers...")
        top_users = find_super_users(api, "python")

        print("\nTop Python answerers:")
        for i, u in enumerate(top_users[:5]):
            print(f"  {i+1}. {u['display_name']} (rep: {u['reputation']:,}, answers: {u['answer_count']})")

        # Use top 2
        user_ids = [top_users[0]["user_id"], top_users[1]["user_id"]]
        user_names = {top_users[0]["user_id"]: top_users[0]["display_name"],
                      top_users[1]["user_id"]: top_users[1]["display_name"]}
    else:
        user_names = {}

    print(f"\nAnalyzing users: {user_ids}")
    print(f"API quota remaining: {api.quota_remaining}")

    results = []

    for user_id in user_ids:
        print(f"\n{'#'*60}")
        print(f"Fetching data for user {user_id}")
        print(f"{'#'*60}")

        # Get user info
        user_info = api.get_user_info(user_id)
        items = user_info.get("items", [])
        if items:
            display_name = items[0].get("display_name", f"User {user_id}")
            reputation = items[0].get("reputation", 0)
            print(f"User: {display_name} (rep: {reputation:,})")
        else:
            display_name = user_names.get(user_id, f"User {user_id}")

        # Fetch answers
        answers = fetch_user_career(api, user_id, max_answers=500)

        if not answers:
            print(f"No answers found for user {user_id}")
            continue

        # Analyze career
        career = analyze_career_trajectory(answers, display_name)
        print_career_analysis(career)

        # Analyze firmware using top tags API
        top_tags = fetch_user_top_tags(api, user_id)
        firmware = analyze_tag_firmware_from_api(top_tags, display_name)
        print_firmware_analysis(firmware)

        results.append({
            "user_id": user_id,
            "display_name": display_name,
            "career": career,
            "firmware": firmware,
            "answers": answers,
        })

        print(f"\nAPI quota remaining: {api.quota_remaining}")

    # Compare the two users
    if len(results) == 2:
        print("\n" + "="*70)
        print("COMPARISON: FIRMWARE DEVELOPMENT PATTERNS")
        print("="*70)

        for r in results:
            c = r["career"]
            f = r["firmware"]
            print(f"\n{r['display_name']}:")
            print(f"  Career: {c['career_span_days']//365} years, {c['total_answers']} answers")
            print(f"  Firmware coverage: {f['firmware_tags']}/{f['tags_analyzed']} tags ({f['firmware_tags']/f['tags_analyzed']*100:.0f}%)")

            # Quality trajectory
            phases = c["phases"]
            if "Early" in phases and "Expert" in phases:
                early_acc = phases["Early"]["acceptance_rate"]
                late_acc = phases["Expert"]["acceptance_rate"]
                print(f"  Acceptance: {early_acc:.0f}% → {late_acc:.0f}% ({late_acc-early_acc:+.0f}%)")

    return results


if __name__ == "__main__":
    # Allow passing user IDs as arguments
    if len(sys.argv) > 2:
        user_ids = [int(sys.argv[1]), int(sys.argv[2])]
    else:
        user_ids = None  # Will find top users

    run_analysis(user_ids)
