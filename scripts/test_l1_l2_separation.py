#!/usr/bin/env python3
"""
L1 vs L2 Error Separation Test

Theory:
- L1: Positive pattern recognition ("this IS template")
- L2: Negative pattern recognition ("this is NOT dangerous")

Blunder Classification:
- L1 error: Wrong pattern executed (played move does something, but wrong)
- L2 error: Danger not detected (missed opponent's existing threat)

Test: Can we separate these two error types in chess blunder data?
"""

import json
import numpy as np
from collections import defaultdict
from typing import Dict, List, Tuple, Optional


def classify_blunder_type(position_before: dict, move_played: dict,
                          position_after: dict) -> str:
    """
    Classify a blunder as L1 or L2 error.

    L1 error: The move CREATED the problem
    - Eval was okay before, bad after
    - The move itself was the mistake

    L2 error: The problem EXISTED and was missed
    - Opponent had a winning threat/tactic before the move
    - Player's move failed to address existing danger
    """
    eval_before = position_before.get('eval', 0)
    eval_after = position_after.get('eval', 0)
    best_move = position_before.get('best_move')

    # Was there already a significant advantage for opponent?
    # (indicating existing threat that should trigger L2)
    threat_existed = abs(eval_before) > 100  # >1 pawn disadvantage already

    # Did this move make things significantly worse?
    eval_drop = eval_after - eval_before if move_played.get('color') == 'white' else eval_before - eval_after

    if threat_existed and eval_drop < -100:
        # Danger existed AND wasn't addressed → L2 failure
        return 'L2'
    elif not threat_existed and eval_drop < -200:
        # No prior danger, but move created problem → L1 failure
        return 'L1'
    else:
        return 'UNCLEAR'


def analyze_blunder_patterns():
    """
    Analyze blunder patterns to test L1/L2 separation.

    Without engine analysis, we use proxy measures:
    """
    print("=" * 70)
    print("L1 vs L2 ERROR SEPARATION: THEORETICAL FRAMEWORK")
    print("=" * 70)

    print("""
THEORY
======

L1 (Positive Pattern Recognition):
  - "This IS a fork opportunity"
  - "This IS a development move"
  - Fires on pattern MATCH

L2 (Negative Pattern Recognition):
  - "This is NOT a hanging piece situation"
  - "This is NOT a back-rank threat"
  - Fires on pattern ABSENCE (danger clear)

DECISION = L1 match + L2 clearance

BLUNDER TAXONOMY
================

L1 Error (Active Mistake):
  - Wrong pattern matched
  - "I thought I saw a tactic" but it wasn't there
  - The move DOES something, but wrong thing
  - Signature: Player initiated action that backfired

L2 Error (Passive Blindness):
  - Danger not detected
  - "Nothing looked wrong" but threat existed
  - The move is reasonable in vacuum, but misses threat
  - Signature: Player failed to see opponent's resource

TESTABLE PREDICTIONS
====================

1. L1 and L2 errors cluster differently by:
   - Position type (tactical vs positional)
   - Game phase (opening vs middlegame vs endgame)
   - Time pressure signature
   - Player style

2. L1 errors more common in:
   - Complex tactical positions (many patterns to match)
   - When player is attacking/active
   - Faster time controls (less L3 verification)

3. L2 errors more common in:
   - Quiet positions that hide danger
   - When player is passive/defensive
   - After opponent's subtle move (trap not obvious)

DATA REQUIREMENTS
=================

To properly test this, we need:
1. Chess positions with engine evaluation BEFORE move
2. Engine evaluation AFTER move
3. Best move analysis (what should have been played)
4. Classification of whether threat existed before

PROXY MEASURES (without full engine analysis):
- Move that drops evaluation: L1 if position was equal, L2 if already bad
- Opponent's previous move: subtle (L2 trap) vs obvious (L1 tactical miss)
- Player's move type: active (L1 candidate) vs passive (L2 candidate)
""")

    return True


def design_experiment():
    """Design the experiment to test L1/L2 separation."""

    print("\n" + "=" * 70)
    print("EXPERIMENTAL DESIGN")
    print("=" * 70)

    print("""
EXPERIMENT: L1 vs L2 Error Classification in Expert Blunders

HYPOTHESIS:
  Expert blunders are not uniform - they cluster into two distinct types
  that correspond to L1 (pattern mismatch) and L2 (danger blindness) failures.

METHOD:

Step 1: Collect Blunder Data
  - Use Lichess API to get games with significant eval drops
  - Filter for fast moves (< median time) that lose > 200 centipawns
  - Need: position FEN before, move played, eval before/after

Step 2: Classify Each Blunder

  L1 Classification Criteria:
  - Position was roughly equal before move (|eval| < 100 cp)
  - Move actively does something (capture, check, attack)
  - Move creates the problem (eval drops from good to bad)

  L2 Classification Criteria:
  - Position already had hidden threat (opponent has tactic)
  - Move is passive/neutral (development, prophylaxis)
  - Threat existed before move (eval was already concerning)
  - Player failed to see/address the threat

Step 3: Analyze Clusters
  - Do L1 and L2 errors have different:
    * Time signatures (L1 might be faster - overconfidence)
    * Phase distribution (L2 more in quiet middlegame?)
    * Position complexity (L1 in sharp, L2 in quiet?)
    * Recovery patterns (do players notice differently?)

Step 4: Cross-Validate
  - Same framework in Quiz Bowl:
    * L1: Buzzed with wrong answer (pattern mismatch)
    * L2: Didn't buzz when they knew it (failed danger clear)
  - Same framework in EdNet:
    * L1: Chose wrong answer confidently (matched wrong pattern)
    * L2: Missed trap in question (didn't detect danger)

PREDICTIONS:

1. L1/L2 ratio differs by player strength:
   - Novices: More L1 errors (wrong patterns, less repertoire)
   - Experts: More L2 errors (good patterns, occasional blindness)

2. L1/L2 ratio differs by time pressure:
   - More time: L3 catches both, few blunders
   - Moderate time: L2 errors dominate (L1 corrected, L2 missed)
   - Severe time: L1 errors increase (no time to verify match)

3. L1/L2 errors predict differently:
   - High L1 rate → needs pattern training
   - High L2 rate → needs threat awareness training
""")


def propose_implementation():
    """Propose concrete implementation steps."""

    print("\n" + "=" * 70)
    print("IMPLEMENTATION PLAN")
    print("=" * 70)

    print("""
PHASE 1: Data Collection (requires Lichess + Stockfish)

```python
# Pseudocode for blunder collection
for game in elite_games:
    for move in game.moves:
        eval_before = stockfish.evaluate(position_before)
        eval_after = stockfish.evaluate(position_after)

        eval_drop = calculate_drop(eval_before, eval_after, color)

        if eval_drop < -200:  # Significant blunder
            blunder = {
                'fen_before': position_before.fen(),
                'move': move,
                'eval_before': eval_before,
                'eval_after': eval_after,
                'best_move': stockfish.best_move(position_before),
                'threat_before': detect_threats(position_before),
                'think_time': move.time,
                'game_phase': classify_phase(position_before)
            }
            blunders.append(blunder)
```

PHASE 2: Classification Algorithm

```python
def classify_blunder(blunder):
    threat_existed = blunder['threat_before'] is not None
    move_is_active = is_active_move(blunder['move'])  # capture, check, etc.
    position_was_equal = abs(blunder['eval_before']) < 100

    if position_was_equal and move_is_active:
        # No danger, player initiated action that failed
        return 'L1'  # Pattern mismatch

    elif threat_existed and not addresses_threat(blunder['move'], blunder['threat_before']):
        # Danger existed, player didn't see it
        return 'L2'  # Danger blindness

    else:
        # Mixed or unclear
        return 'MIXED'
```

PHASE 3: Statistical Analysis

- Chi-square test: L1/L2 distribution vs player strength
- Cluster analysis: Do L1 and L2 have different feature profiles?
- Logistic regression: Can we predict L1 vs L2 from position features?

PHASE 4: Cross-Domain Validation

- Quiz Bowl: Classify wrong buzzes as L1 (wrong answer) vs L2 (hesitation error)
- EdNet: Classify wrong answers as L1 (active mistake) vs L2 (trap missed)

REQUIRED RESOURCES:
1. Stockfish engine access for evaluation
2. ~1000 blunders from expert games with full analysis
3. Statistical analysis tools (scipy, sklearn)
""")


def main():
    analyze_blunder_patterns()
    design_experiment()
    propose_implementation()

    print("\n" + "=" * 70)
    print("NEXT STEPS")
    print("=" * 70)
    print("""
To run this experiment:

1. Install Stockfish: sudo apt install stockfish
2. Run blunder collection with engine analysis
3. Classify blunders into L1/L2 categories
4. Analyze whether the separation is meaningful

The key question: Do L1 and L2 errors have different signatures
that would support the dual-channel theory?

If YES: This validates the refined model
If NO: The original L2-as-hesitation model may be correct
""")


if __name__ == '__main__':
    main()
