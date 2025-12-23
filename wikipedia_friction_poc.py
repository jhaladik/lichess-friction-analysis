#!/usr/bin/env python3
"""
Wikipedia Friction Analysis - Proof of Concept

Tests the hypothesis: edit reverts correlate with friction patterns
(fast edits on unfamiliar topics → higher revert rate)
"""

import requests
import time
from datetime import datetime, timedelta
from collections import defaultdict
import json

WIKI_API = "https://en.wikipedia.org/w/api.php"


def get_article_revisions(title: str, limit: int = 500) -> list:
    """Fetch revision history for an article."""
    params = {
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvprop": "ids|timestamp|user|userid|size|comment|tags",
        "rvlimit": min(limit, 50),  # API limit per request
        "format": "json",
    }

    headers = {
        "User-Agent": "FrictionAnalysis/1.0 (research project)"
    }

    revisions = []
    continue_token = None

    while len(revisions) < limit:
        if continue_token:
            params["rvcontinue"] = continue_token

        response = requests.get(WIKI_API, params=params, headers=headers)
        if response.status_code != 200:
            print(f"API error: {response.status_code}")
            break

        try:
            data = response.json()
        except Exception as e:
            print(f"JSON error: {e}")
            print(f"Response: {response.text[:200]}")
            break

        pages = data.get("query", {}).get("pages", {})
        for page_id, page_data in pages.items():
            revs = page_data.get("revisions", [])
            revisions.extend(revs)

        if "continue" in data:
            continue_token = data["continue"].get("rvcontinue")
        else:
            break

        time.sleep(0.1)  # Be nice to API

    return revisions[:limit]


def get_user_edit_count(username: str) -> int:
    """Get total edit count for a user."""
    params = {
        "action": "query",
        "list": "users",
        "ususers": username,
        "usprop": "editcount",
        "format": "json",
    }

    try:
        response = requests.get(WIKI_API, params=params)
        data = response.json()
        users = data.get("query", {}).get("users", [])
        if users and "editcount" in users[0]:
            return users[0]["editcount"]
    except:
        pass
    return 0


def is_revert(revision: dict) -> bool:
    """Check if revision is a revert."""
    tags = revision.get("tags", [])
    comment = revision.get("comment", "").lower()

    revert_tags = ["mw-rollback", "mw-undo", "mw-manual-revert"]
    if any(tag in tags for tag in revert_tags):
        return True

    revert_words = ["revert", "undo", "rv ", "rvv"]
    if any(word in comment for word in revert_words):
        return True

    return False


def was_reverted(revision: dict, next_revision: dict) -> bool:
    """Check if this revision was reverted by the next one."""
    if next_revision is None:
        return False
    return is_revert(next_revision)


def analyze_article(title: str, limit: int = 300):
    """Analyze friction patterns in article edit history."""
    print(f"\n{'='*60}")
    print(f"Analyzing: {title}")
    print('='*60)

    # Fetch revisions
    print("Fetching revisions...")
    revisions = get_article_revisions(title, limit)
    print(f"Got {len(revisions)} revisions")

    if len(revisions) < 10:
        print("Not enough revisions")
        return

    # Reverse to chronological order
    revisions = list(reversed(revisions))

    # Track editor stats
    editor_edits = defaultdict(list)  # editor -> list of edit info
    editor_total_experience = {}  # editor -> total wiki edit count

    # Process revisions
    edits_data = []

    for i, rev in enumerate(revisions):
        user = rev.get("user", "Anonymous")
        timestamp = datetime.fromisoformat(rev["timestamp"].replace("Z", "+00:00"))
        size = rev.get("size", 0)

        # Get next revision to check if this one was reverted
        next_rev = revisions[i + 1] if i + 1 < len(revisions) else None
        reverted = was_reverted(rev, next_rev)

        # Calculate time since last edit by this user on this article
        prev_edits = editor_edits[user]
        if prev_edits:
            last_edit_time = prev_edits[-1]["timestamp"]
            time_since_last = (timestamp - last_edit_time).total_seconds()
        else:
            time_since_last = None

        # Count edits by this user on this article so far
        article_experience = len(prev_edits)

        edit_info = {
            "user": user,
            "timestamp": timestamp,
            "size": size,
            "reverted": reverted,
            "is_revert": is_revert(rev),
            "time_since_last": time_since_last,
            "article_experience": article_experience,
        }

        edits_data.append(edit_info)
        editor_edits[user].append(edit_info)

    # Get global experience for top editors
    print("Fetching editor experience...")
    top_editors = sorted(editor_edits.keys(), key=lambda x: len(editor_edits[x]), reverse=True)[:20]
    for editor in top_editors:
        if not editor.startswith("Anonymous"):
            editor_total_experience[editor] = get_user_edit_count(editor)
            time.sleep(0.1)

    # Analyze patterns
    print("\n" + "-"*40)
    print("FRICTION ANALYSIS")
    print("-"*40)

    # Filter out reverts themselves (we want to analyze edits that might GET reverted)
    content_edits = [e for e in edits_data if not e["is_revert"]]
    print(f"\nContent edits (excluding reverts): {len(content_edits)}")
    print(f"Reverted edits: {sum(1 for e in content_edits if e['reverted'])}")
    print(f"Overall revert rate: {100*sum(1 for e in content_edits if e['reverted'])/max(1,len(content_edits)):.1f}%")

    # 1. Revert rate by article experience
    print("\n## Revert Rate by Article Experience")
    exp_buckets = {"0 (first edit)": [], "1-5": [], "6-20": [], "20+": []}
    for e in content_edits:
        exp = e["article_experience"]
        if exp == 0:
            exp_buckets["0 (first edit)"].append(e)
        elif exp <= 5:
            exp_buckets["1-5"].append(e)
        elif exp <= 20:
            exp_buckets["6-20"].append(e)
        else:
            exp_buckets["20+"].append(e)

    for bucket, edits in exp_buckets.items():
        if edits:
            revert_rate = sum(1 for e in edits if e["reverted"]) / len(edits)
            print(f"  {bucket}: {100*revert_rate:.1f}% reverted (n={len(edits)})")

    # 2. Revert rate by time since last edit (friction proxy)
    print("\n## Revert Rate by Time Since Last Edit (returning editors only)")
    returning_edits = [e for e in content_edits if e["time_since_last"] is not None]

    if returning_edits:
        time_buckets = {"<1 min": [], "1-10 min": [], "10-60 min": [], "1-24 hr": [], ">24 hr": []}
        for e in returning_edits:
            t = e["time_since_last"]
            if t < 60:
                time_buckets["<1 min"].append(e)
            elif t < 600:
                time_buckets["1-10 min"].append(e)
            elif t < 3600:
                time_buckets["10-60 min"].append(e)
            elif t < 86400:
                time_buckets["1-24 hr"].append(e)
            else:
                time_buckets[">24 hr"].append(e)

        for bucket, edits in time_buckets.items():
            if len(edits) >= 3:
                revert_rate = sum(1 for e in edits if e["reverted"]) / len(edits)
                print(f"  {bucket}: {100*revert_rate:.1f}% reverted (n={len(edits)})")

    # 3. Top editors analysis
    print("\n## Top Editors (firmware vs mind pattern)")
    for editor in top_editors[:10]:
        edits = [e for e in content_edits if e["user"] == editor]
        if len(edits) >= 3:
            revert_rate = sum(1 for e in edits if e["reverted"]) / len(edits)
            global_exp = editor_total_experience.get(editor, "?")
            print(f"  {editor[:20]:20s}: {len(edits):3d} edits, {100*revert_rate:.0f}% reverted, global={global_exp}")

    print("\n" + "="*60)
    return edits_data


if __name__ == "__main__":
    # Test with a few different article types

    # Controversial article (high friction expected)
    analyze_article("Climate change", limit=300)

    # Technical article
    analyze_article("Quantum entanglement", limit=300)

    # Popular but less controversial
    analyze_article("Python (programming language)", limit=300)
