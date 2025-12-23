# L2 Trigger Analysis Findings

## Cross-Domain Transferable Metrics

Four L2 trigger metrics were computed from chess data:

| Metric | Chess Definition | Transferable Concept |
|--------|------------------|---------------------|
| **Optionality Delta** | Change in moves within 50cp of best | Decision space shrinking/expanding |
| **Eval Gradient** | Position evaluation shift | Stability disruption |
| **Criticality Gap** | Best move eval - second best eval | Consequence asymmetry |
| **Opponent Surprise** | Opponent move outside engine top-5 | Environment model violation |

---

## Key Finding: L2 Calibration is Inverted

**Players think LESS in critical positions, MORE in easy positions.**

| Skill Level | Think Time (Critical) | Think Time (Easy) | Calibration |
|-------------|----------------------|-------------------|-------------|
| < 1400 | 0.84x | 1.12x | **-11.7** |
| 1400-1800 | 0.86x | 1.13x | **-10.0** |
| 1800+ | 0.89x | 1.13x | **-8.1** |

Higher rated players are slightly better calibrated but still inverted.

### Why This Happens

| Position Type | Legal Moves | Alternatives | Behavior |
|---------------|-------------|--------------|----------|
| Critical (gap ≥100cp) | 26.6 | 0.0 | Fast response (one obvious move) |
| Easy (gap <100cp) | 29.3 | 2.3 | Slow response (choosing among options) |

**People slow down for confusion, not danger.** When there's "only one move," they play it quickly - even when missing it is catastrophic.

---

## L2 Miss Signature

When L2 fails (trigger present + no friction + blunder):

| Metric | L2 Miss | L2 Hit | Meaning |
|--------|---------|--------|---------|
| Optionality Delta | **-0.57** | +0.14 | Options were shrinking |
| Criticality Gap | **1319cp** | 389cp | Only one good move |
| Think Time | **0.59x** | 2.46x | Player moved FAST |
| Eval Drop | **2421cp** | 457cp | Catastrophic error |

---

## Skill Differences: L1 Firmware, Not L2 Sensitivity

### L2 Sensitivity is Constant Across Skill Levels

| Skill | L2 Sensitivity | L1/L2 Usage Ratio |
|-------|---------------|-------------------|
| < 1400 | 26.7% | 73%/27% |
| 1400-1800 | 27.3% | 73%/27% |
| 1800+ | 27.1% | 73%/27% |

**L2 trigger detection does NOT improve with skill.**

### What Improves is L1 and L2 Capacity

| Skill | L1 Success Rate | L2 Success Rate | Overall Blunder Rate |
|-------|-----------------|-----------------|---------------------|
| < 1400 | 76.0% | 67.0% | 26.4% |
| 1400-1800 | 80.2% | 71.3% | 22.2% |
| 1800+ | 84.6% | 76.0% | 17.7% |

**L1 advantage is constant (~9%) but both L1 and L2 quality improve with skill.**

---

## Cross-Domain Implications

### The L2 Failure Pattern

1. **Situation shifts** → Options narrow, one critical path exists
2. **L2 should fire** → "This is dangerous, slow down"
3. **L2 fails** → Player sees "obvious" move, continues fast
4. **L1 executes** → Pattern-based response to wrong pattern
5. **Result** → Catastrophic error

### Transferable Insights

| Finding | Chess | Education | Work |
|---------|-------|-----------|------|
| Inverted calibration | Fast on critical moves, slow on choices | Fast on hard questions, slow on options | Fast on critical decisions, slow on meetings |
| L2 triggered by confusion, not danger | Many legal moves → think | Multiple methods → think | Many stakeholders → think |
| L1 capacity differentiates experts | Better pattern library | More problem templates | More experience patterns |
| L2 sensitivity constant | ~27% across ratings | Similar across grades? | Similar across seniority? |

### What L2 Actually Detects

**Current:** Confusion (many options) → triggers thinking
**Should be:** Risk (narrow path, high stakes) → triggers thinking

L2 is wired for **optionality confusion**, not **criticality danger**.

---

## Database Tables

Results stored in `output/friction.db`:

```sql
-- L2 trigger metrics per move
SELECT * FROM l2_triggers;

-- Key columns:
-- optionality_delta, eval_gradient, criticality_gap, opponent_surprise
-- l2_should_fire, friction_present, l2_miss, l2_hit
```

---

## L2 Trainability Analysis

### Calibration Improves with Rating

| Rating | Calibration | L2 Miss Rate |
|--------|-------------|--------------|
| 1000 | -0.285 | 18.4% |
| 1400 | -0.255 | 15.2% |
| 1800 | -0.231 | 11.7% |
| **2200** | **-0.149** | **8.3%** |

**2200+ players have 48% better calibration** than beginners.

### What Experts Do Differently

| Metric | Strong (2000+) | Developing (<2000) | Delta |
|--------|---------------|-------------------|-------|
| Critical position frequency | 22.6% | 23.4% | Same exposure |
| L2 Miss in critical | **20.4%** | 27.8% | -7.4% |
| Blunder in critical | **30.7%** | 39.3% | -8.6% |
| L2 Hit success rate | **79.2%** | 70.4% | +8.8% |
| Think time when L2 fires | 2.58x | 2.44x | +6% more thorough |

### The Trainable Components

1. **L2 Accuracy** - Better at recognizing when to trigger
   - Less friction on easy positions (27.6% vs 29.6%)
   - Similar friction on critical (22.4% vs 19.5%)

2. **L2 Depth** - More thorough processing when triggered
   - Think 2.58x vs 2.44x when L2 engages
   - 6% more investment in difficult positions

3. **L2 Effectiveness** - Better outcomes when L2 fires
   - 79.2% success when L2 hits vs 70.4%
   - Both L1 and L2 modes improve with skill

### What's NOT Different

- **Exposure to danger** - Experts face critical positions equally often
- **L1 advantage** - Both skill levels show ~8-9% L1 > L2 gap
- **Base trigger response** - Similar friction rates overall (~27%)

### Cross-Domain Trainability Hypothesis

L2 training should focus on:

| Component | Chess Training | Transferable Training |
|-----------|---------------|----------------------|
| Recognition | Study critical position patterns | Learn domain danger signals |
| Calibration | Practice identifying "only move" | Practice identifying high-stakes decisions |
| Depth | Deliberate calculation practice | Structured deliberation protocols |
| Effectiveness | Tactical puzzle solving | Decision quality under pressure |

The key insight: **L2 is trainable, but through pattern exposure (expanding when L2 fires correctly) rather than metacognitive instruction (telling someone to slow down).**

---

## Summary: L2 Trigger System

### The L2 Failure Mode (Cross-Domain)

```
Situation changes (options narrow, stakes rise)
    ↓
L2 should fire ("this is dangerous")
    ↓
L2 fails (player sees "obvious" move)
    ↓
L1 executes (fast pattern response)
    ↓
Catastrophic error
```

### The Expert Advantage

Experts don't avoid danger - they:
1. **Recognize** slightly more danger signals
2. **Process** more deeply when triggered
3. **Execute** better in both L1 and L2 modes

### Inverted Calibration (Universal Finding)

All skill levels think **more** when confused (many options) and **less** when at risk (one critical path). This is backwards.

Higher skill = slightly better calibration, but still inverted.

---

## Database Tables

```sql
-- L2 trigger metrics per move
SELECT * FROM l2_triggers;

-- Analysis query: L2 calibration by rating
SELECT
    player_rating / 200 * 200 as rating_band,
    AVG(CASE WHEN criticality_gap >= 100 THEN think_time_normalized END) as think_critical,
    AVG(CASE WHEN criticality_gap < 100 THEN think_time_normalized END) as think_easy
FROM l2_triggers l2
JOIN friction_analysis fa ON l2.game_id = fa.game_id AND l2.ply = fa.ply
GROUP BY 1;
```

---

## Next Steps

1. **Test in other domains** - Does inverted calibration replicate?
2. **Build L2 intervention** - Alert systems for critical moments
3. **Design training protocol** - Pattern-based L2 calibration training
4. **Longitudinal validation** - Track L2 changes with deliberate training
