# L1 / L2 / L3 Cognitive Framework

## Executive Summary

We identified three parallel cognitive systems that govern expert decision-making:

- **L1**: Positive pattern recognition ("This IS X")
- **L2**: Negative pattern recognition ("This is NOT dangerous")
- **L3**: Conscious analytical reasoning (slow calculation)

**Key Finding**: L2 (danger/uncertainty detection) shows the largest expert-novice difference, particularly for internal states (knowing what you don't know).

---

## The Framework

### L1: Positive Pattern Recognition

- Fast, automatic
- Matches current situation to known templates
- "This IS a fork" / "This IS the answer to a literature question"

**L1 Error**: Wrong pattern matched
- Confident, fast action
- Pattern recognizer fired on wrong template
- "I thought I saw a tactic but it wasn't there"

### L2: Negative Pattern Recognition

- Fast, automatic
- Scans for absence of danger signals
- "This is NOT a back-rank threat" / "I am NOT uncertain"

**L2 Error**: Danger not detected
- Confident, fast action when danger exists
- The "wrongness detector" returned false negative
- "I didn't sense anything wrong" - THE KEY FAILURE

### L3: Conscious Analytical Reasoning

- Slow, deliberate
- Explicit calculation and reasoning
- "If I play this, then they play that..."

**L3 Error**: Calculation failure
- Took time to analyze
- Still got it wrong
- "I calculated but missed something"

---

## Decision Process

```
Decision = L1 match + L2 clearance (+ optional L3 verification)

Normal flow:
  1. L1 fires: "I recognize this pattern"
  2. L2 clears: "No danger signals detected"
  3. Action taken

When L2 detects something:
  1. L1 fires: "I recognize this pattern"
  2. L2 flags: "Something seems wrong"
  3. L3 engaged: Conscious analysis
  4. Deliberate action (or override L1)
```

---

## The Apple Collector Analogy

Expert apple picker:
- **L1**: "This looks like a good apple" (shape, color match)
- **L2**: "No rot, no bruises, no wrong color" (danger clear)

**L2 failure** = reaching without hesitation for a bad apple
- The "wrongness" signal didn't fire
- Hand doesn't hover - goes straight to grab

**Key insight**: L2 is not "hesitation before action"
- L2 is a fast, automatic scan for negative patterns
- If hand hovers → L2 fired, passed to L3
- If grab is instant → L2 completely failed

---

## Empirical Validation

### Chess Results

**Sample**: 250 games from elite (2400+) and intermediate (1400-2000) players

| Error Type | Elite | Intermediate |
|------------|-------|--------------|
| L1 (pattern mismatch) | 57.7% | 45.0% |
| L2 (danger blindness) | 23.1% | 25.0% |
| L3 (calculation error) | 19.2% | 30.0% |

**Classification criteria**:
- L1: Fast (<5s) + Safe position → wrong pattern
- L2: Fast (<5s) + Danger position → threat not detected
- L3: Slow (>5s) → calculation failed

**Findings**:
- L2 rates similar (~24%) across skill levels
- Elite have higher L1/L3 ratio (3.0 vs 1.5)
- Elite trust patterns more, calculate less

### Quiz Bowl Results

**Sample**: 16,854 buzzes from 526 players (ACF Regionals 2018)

| Error Type | Expert (top 25%) | Novice (bottom 25%) |
|------------|------------------|---------------------|
| L1 (pattern mismatch) | 19.8% | 4.7% |
| L2 (uncertainty blindness) | 2.5% | 12.4% |
| L3 (reasoning failure) | 26.1% | 37.6% |

**Classification criteria**:
- L1: Early buzz (<50%) + Wrong + Good category for player
- L2: Early buzz (<50%) + Wrong + Bad category for player
- L3: Late buzz (>80%) + Wrong

**Key Finding**: 5x difference in L2 rate!
- Experts: 2.5% (they know when they don't know)
- Novices: 12.4% (buzz confidently when uncertain)

---

## Cross-Domain Comparison

| Aspect | Chess | Quiz Bowl |
|--------|-------|-----------|
| **L2 Target** | External threat | Internal uncertainty |
| **L2 Question** | "Is there danger on the board?" | "Am I uncertain about this?" |
| **Expert L2 Rate** | ~23% | 2.5% |
| **Novice L2 Rate** | ~25% | 12.4% |
| **Expert/Novice Ratio** | 1.1x | 5.0x |

### Interpretation

**Chess L2** (external threat detection):
- Similar rates across skill levels
- External threats may be more uniformly salient
- Or: chess positions vary in threat visibility

**Quiz Bowl L2** (internal uncertainty detection):
- Massive expert-novice difference
- "Knowing what you don't know" is a key skill
- Metacognition about knowledge state is trainable

**Unified principle**:
- L2 detects "danger" broadly defined
- External danger: opponent's threats, traps
- Internal danger: own uncertainty, lack of knowledge
- Expert advantage is largest for internal L2

---

## Theoretical Implications

### 1. L2 is Not Hesitation

Previous L2 model: "knowing when to slow down"
Refined L2 model: "fast detection of negative patterns"

L2 is automatic and fast, not deliberate:
- If you pause, L2 already fired
- True L2 failure = no pause when there should be

### 2. Two Types of L2

| Type | Target | Domain | Trainability |
|------|--------|--------|--------------|
| External L2 | Threats, traps | Chess, driving | Moderate |
| Internal L2 | Uncertainty, gaps | Quiz Bowl, expertise | High |

### 3. Expert Advantage

Experts don't just have more patterns (L1), they have:
- Reliable danger detection (L2)
- Especially for internal states (knowing what they don't know)
- This may be the more trainable component

### 4. Error Taxonomy for Training

| Error Type | Training Implication |
|------------|---------------------|
| High L1 | Need more/better patterns |
| High L2 | Need threat awareness / metacognition |
| High L3 | Need calculation practice |

---

## Methodological Notes

### Chess Classification

```python
def classify_chess_error(eval_before, think_time, is_blunder):
    is_safe = eval_before > -100  # Not in danger
    is_danger = eval_before <= -100  # Threat exists
    is_automatic = think_time < 5  # Fast move

    if is_automatic and is_safe and is_blunder:
        return 'L1'  # Pattern mismatch
    elif is_automatic and is_danger and is_blunder:
        return 'L2'  # Danger blindness
    elif not is_automatic and is_blunder:
        return 'L3'  # Calculation failure
```

### Quiz Bowl Classification

```python
def classify_qb_error(buzz_pct, category_accuracy, is_wrong):
    is_early = buzz_pct < 0.5
    is_late = buzz_pct > 0.8
    is_good_category = category_accuracy > 0.6

    if is_early and is_good_category and is_wrong:
        return 'L1'  # Pattern mismatch
    elif is_early and not is_good_category and is_wrong:
        return 'L2'  # Uncertainty blindness
    elif is_late and is_wrong:
        return 'L3'  # Reasoning failure
```

---

## Data Sources

- **Chess**: Lichess API, analyzed games with engine evaluations
- **Quiz Bowl**: ACF Regionals 2018, quizbowl/open-data repository

---

## Future Directions

1. **Larger samples** for statistical significance
2. **More skill levels** (beginner → GM continuum)
3. **EdNet/ASSISTments** application of L1/L2/L3 framework
4. **Training interventions** targeting specific error types
5. **Physiological correlates** (eye tracking, mouse movements for L2 detection)

---

*Analysis conducted December 2024*
*Framework validated across Chess (250 games) and Quiz Bowl (16,854 buzzes)*
