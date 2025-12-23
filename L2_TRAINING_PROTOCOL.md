# L2 Training Protocol

## Overview

**Goal**: Train L2 trigger recognition - the ability to detect when a situation requires slow, deliberate thinking instead of fast pattern-based response.

**Core Problem**: People slow down for confusion (many options), not danger (one critical path). This is inverted. Training must rewire this response.

**Key Insight**: L2 cannot be trained through metacognitive instruction ("slow down when it's dangerous"). It must be trained through pattern exposure - building a library of "danger looks like this."

---

## The L2 Miss Profile (Training Target)

| Characteristic | L2 Miss | L2 Hit | What to Recognize |
|----------------|---------|--------|-------------------|
| Legal moves | 27.9 | 32.7 | **Fewer moves = MORE danger** |
| Options delta | -0.57 | +0.14 | **Shrinking options = danger** |
| Criticality gap | 1319cp | 389cp | **One good move = danger** |
| Think time | 0.55x | 2.46x | **Current: too fast** |
| Game phase | 0.54 | 0.65 | **Endgame = highest risk** |

**L2 Miss Distribution by Phase:**
- Endgame: 38.7% (highest L2 failure)
- Middlegame: 33.6%
- Opening: 27.7%

---

## Training Levels

### Level 1: Danger Recognition (Pattern Exposure)

**Objective**: Build pattern library of "positions that look simple but are critical"

**Exercise Type**: Position Classification
- Show position for 3 seconds
- Player classifies: "Safe to move quickly" or "Need to think"
- Reveal criticality gap
- Feedback: Position with 1 good move requires thinking, not speed

**Position Selection Criteria**:
```sql
-- Subtle critical positions (training sweet spot)
WHERE criticality_gap BETWEEN 100 AND 300
  AND num_legal_moves < 30        -- Looks simple
  AND game_phase < 0.6            -- Middlegame/Endgame
```

**Target**: 70% accuracy at classifying danger vs. safety

---

### Level 2: Trigger Response Training

**Objective**: Build automatic friction response to danger signals

**Exercise Type**: Timed Decision with Friction Requirement
1. Show position
2. Player must WAIT 5 seconds before moving (forced friction)
3. Then find the move
4. Track: Did waiting improve accuracy?

**Progression**:
- Week 1-2: Forced 5-second wait on all positions
- Week 3-4: Forced wait only on flagged "critical" positions
- Week 5-6: Self-identified wait (player decides when to slow down)
- Week 7+: Measure natural friction calibration improvement

**Success Metric**: Friction increases in critical positions, not in easy ones

---

### Level 3: Optionality Delta Sensitivity

**Objective**: Train recognition of "options shrinking"

**Exercise Type**: Sequence Analysis
1. Show 3-move sequence
2. Player identifies: "When did options shrink?"
3. Highlight the moment optionality_delta went negative
4. Train: This is when L2 should fire

**Key Patterns**:
| Trigger | Chess Pattern | Cross-Domain Analog |
|---------|---------------|---------------------|
| Options → 1 | Forcing sequence begins | Deadline approaching |
| Options shrink by 2+ | Critical response required | Requirements narrowed |
| Opponent surprise | Unexpected move | Environment shifted |

---

### Level 4: Criticality Gap Training

**Objective**: Recognize "only move" situations before calculating

**Exercise Type**: Gap Estimation
1. Show position (no engine eval)
2. Player estimates: "How many reasonable moves exist?"
3. Reveal: Actual criticality gap
4. Train calibration between perceived and actual optionality

**Difficulty Tiers**:

| Tier | Criticality Gap | Description | Training Focus |
|------|-----------------|-------------|----------------|
| A | 100-200cp | Subtle critical | Most common L2 miss zone |
| B | 200-500cp | Clear critical | Building recognition |
| C | 500-1000cp | Forcing | Pattern reinforcement |
| D | 1000cp+ | Only move | Edge case awareness |

**Target**: Player's friction increases proportionally to actual criticality

---

### Level 5: Integrated L2 Calibration

**Objective**: Natural, automatic L2 response in live play

**Exercise Type**: Blitz with L2 Feedback
1. Play blitz games (3+0 or 5+0)
2. Post-game analysis highlights L2 misses
3. Show: "Here you moved in 0.8 seconds, but criticality was 400cp"
4. Track L2 miss rate over time

**Success Metrics**:
- L2 miss rate < 15% (from baseline ~25%)
- Calibration score > -0.15 (from baseline ~-0.27)
- Friction ratio: critical/easy > 1.0 (currently ~0.75)

---

## Cross-Domain Transfer Framework

The L2 trigger patterns are transferable:

| Chess Signal | Universal Signal | Training Transfer |
|--------------|------------------|-------------------|
| Criticality gap high | One right answer exists | Identify "no second chance" moments |
| Optionality shrinking | Decision space narrowing | Recognize closing windows |
| Position looks simple | Situation appears routine | "Easy-looking = potential trap" |
| Endgame phase | Late-stage execution | Final steps need more care |
| Opponent surprise | Environment deviation | Others' unexpected behavior = danger |

### Transfer Training Protocol

1. **Label the pattern abstractly**: "Options narrowing + high stakes"
2. **Practice in chess**: Build intuition with concrete positions
3. **Map to target domain**: "When does this happen in [work/education/etc]?"
4. **Practice in target domain**: Apply friction when pattern recognized

---

## Implementation: Chess Training App

### Core Features

```
1. Position Feed
   - Source: L2 miss positions from database
   - Difficulty: Start with obvious (gap > 500), progress to subtle (gap 100-200)

2. Classification Mode
   - "Need to think?" Yes/No
   - Feedback: Show actual criticality

3. Forced Friction Mode
   - Timer prevents move for N seconds
   - N adjusts based on criticality

4. Live Play Integration
   - Track think time per move
   - Flag L2 misses post-game
   - Trend analysis over sessions

5. Calibration Dashboard
   - Current: think_critical / think_easy ratio
   - Target: > 1.0
   - Progress over time
```

### Position Database Query

```sql
-- Training positions: L2 miss cases from players similar to learner rating
SELECT
    m.fen_before as position,
    m.san as blunder_move,
    e.best_move as correct_move,
    l2.criticality_gap,
    l2.optionality_delta,
    fa.game_phase
FROM l2_triggers l2
JOIN moves m ON l2.game_id = m.game_id AND l2.ply = m.ply
JOIN friction_analysis fa ON l2.game_id = fa.game_id AND l2.ply = fa.ply
JOIN evaluations e ON m.fen_before = e.fen
WHERE l2.l2_miss = 1
  AND l2.criticality_gap BETWEEN ? AND ?  -- Difficulty range
  AND fa.player_rating BETWEEN ? AND ?    -- Similar rating
ORDER BY RANDOM()
LIMIT 20;
```

---

## Training Schedule

### 8-Week Protocol

| Week | Focus | Daily Practice | Goal |
|------|-------|----------------|------|
| 1-2 | Danger Recognition | 20 position classifications | 70% accuracy |
| 3-4 | Forced Friction | 10 positions with mandatory wait | Build habit |
| 5 | Optionality Tracking | 15 sequence analyses | Recognize shrinking |
| 6 | Criticality Estimation | 15 gap estimations | Calibrate intuition |
| 7-8 | Integrated Play | 3 blitz games + analysis | < 18% L2 miss rate |

### Maintenance (Ongoing)

- Weekly: 5 position classifications
- Monthly: L2 calibration check (play 10 games, measure)
- Quarterly: Full L2 assessment

---

## Measurement

### Pre-Training Baseline

Measure in 10 rapid games:
1. L2 miss rate (target: establish baseline)
2. Calibration score (think_critical - think_easy)
3. Blunder rate in critical positions

### Post-Training Assessment

Same 10-game measurement:
1. L2 miss rate reduction (target: 30% improvement)
2. Calibration score improvement (target: 50% better)
3. Critical position blunder rate reduction

### Success Criteria

| Metric | Baseline (typical) | Target | Expert Level |
|--------|-------------------|--------|--------------|
| L2 Miss Rate | 25% | < 18% | < 12% |
| Calibration | -0.27 | > -0.18 | > -0.15 |
| Critical Blunder | 40% | < 32% | < 25% |

---

## Key Principles

1. **Pattern exposure, not metacognition**: Don't say "slow down" - show what danger looks like

2. **Inverted intuition training**: "Simple-looking = potential trap" must become automatic

3. **Concrete before abstract**: Master chess L2 first, then transfer to other domains

4. **Feedback loops**: Every training position shows actual vs. perceived criticality

5. **Progressive difficulty**: Start with obvious danger, end with subtle signals

6. **Integration into play**: Training must transfer to natural game situations

---

## Technical Implementation Notes

### Position Extraction Script

```python
def extract_training_positions(db_path, rating_range, difficulty='medium'):
    """Extract L2 training positions from friction database."""

    difficulty_ranges = {
        'easy': (500, 2000),      # Obvious critical
        'medium': (200, 500),     # Clear critical
        'hard': (100, 200),       # Subtle critical
    }

    crit_min, crit_max = difficulty_ranges[difficulty]

    query = """
        SELECT m.fen_before, m.san, e.best_move,
               l2.criticality_gap, l2.optionality_delta
        FROM l2_triggers l2
        JOIN moves m ON l2.game_id = m.game_id AND l2.ply = m.ply
        JOIN evaluations e ON m.fen_before = e.fen
        JOIN friction_analysis fa ON l2.game_id = fa.game_id AND l2.ply = fa.ply
        WHERE l2.l2_miss = 1
          AND l2.criticality_gap BETWEEN ? AND ?
          AND fa.player_rating BETWEEN ? AND ?
        ORDER BY RANDOM()
        LIMIT 50
    """

    return execute_query(db_path, query,
                        (crit_min, crit_max, rating_range[0], rating_range[1]))
```

---

## Appendix: Sample Training Positions

From database analysis, key L2 miss patterns:

### Pattern A: Endgame Simplification Trap
- Position looks like straightforward endgame
- Actually has one winning line, rest draw/lose
- L2 miss rate: 38.7% in endgame phase

### Pattern B: Quiet Move Critical
- No captures or checks available
- One quiet move maintains advantage
- Most "natural" moves lose material

### Pattern C: Transition Moment
- Just exited opening/middlegame
- Position complexity dropped (fewer pieces)
- Precision suddenly required

### Pattern D: Opponent's Last Move Created Threat
- Previous move wasn't obviously aggressive
- Hidden threat requires specific response
- "Everything looks fine" → L2 should fire
