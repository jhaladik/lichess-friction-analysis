# Testing Plan: Friction as Firmware Boundary Detection

## Revised Hypothesis

**Friction signals firmware failure, not blindness.**
- Low friction = firmware handling position = safe
- High friction = mind-mode activated = error-prone

**Think time is a quantifiable firmware boundary detector.**

---

## Test Suite

### TEST 1: Complexity-Blunder-Friction Triangle
**Prediction:** In complex positions (high optionality), blunder rate increases with think time.

```
Measure:
- Partition by complexity quartile (eval_spread or num_alternatives)
- Within each quartile: correlate think_time with blunder rate
- Expected: positive correlation strengthens as complexity increases
```

**Current status:** Preliminary support (r=0.27, p=0.0008 in Q4)
**Needed:** More data, bootstrap confidence intervals

---

### TEST 2: Firmware Boundary by Rating
**Prediction:** Higher-rated players have firmware that covers more position types.

```
Measure:
- Same position complexity → lower think time for higher-rated players
- Same think time → lower blunder rate for higher-rated players
- Firmware boundary (think time spike threshold) shifts with rating
```

**Metric:** Plot mean think_time vs complexity, segmented by rating band (1000-1400, 1400-1800, 1800-2200)

---

### TEST 3: Firmware vs Mind Error Signatures
**Prediction:** Two distinct error types with different signatures.

| Error Type | Think Time | Position | Mechanism |
|------------|-----------|----------|-----------|
| Firmware error | LOW | Simple | Template misfired |
| Mind error | HIGH | Complex | Search failed |

```
Measure:
- Cluster blunders by (think_time, complexity)
- Test for bimodal distribution
- Characterize each cluster
```

---

### TEST 4: Blunder Predictability
**Prediction:** Think time + complexity predicts blunder probability before move is made.

```
Measure:
- Logistic regression: P(blunder) ~ think_time * complexity + controls
- ROC-AUC for prediction
- Compare to baseline (complexity only)
```

**Success:** AUC > 0.65 indicates useful predictive signal

---

### TEST 5: Position-Type Firmware Gaps
**Prediction:** Certain position types consistently trigger mind-mode across players.

```
Measure:
- Cluster positions by features (material, pawn structure, piece activity)
- Find clusters with high mean think_time AND high blunder rate
- These are population-level firmware gaps
```

**Application:** Training recommendations for position types lacking firmware coverage

---

### TEST 6: Within-Player Firmware Mapping
**Prediction:** Individual players have consistent firmware boundaries.

```
Measure:
- For players with 10+ games: correlate think_time patterns across games
- Test if same position types trigger high friction for same player
- ICC (intraclass correlation) for within-player consistency
```

---

### TEST 7: Opening vs Middlegame vs Endgame
**Prediction:** Firmware coverage varies by game phase.

```
Measure:
- Mean think_time by game_phase
- Blunder rate by game_phase
- Interaction: does think_time predict blunders equally across phases?
```

**Expected:** Opening = high firmware coverage, Middlegame = lowest coverage

---

## Data Requirements

| Test | Min Games | Min Moves | Rating Range |
|------|-----------|-----------|--------------|
| 1-4  | 500       | 20,000    | 1000-2500    |
| 5    | 1,000     | 40,000    | 1000-2500    |
| 6    | 200 players × 10 games | - | 1000-2500 |
| 7    | 500       | 20,000    | 1000-2500    |

**Immediate next step:** Run 500 games to enable Tests 1-4.

---

## Quality Controls

1. **Exclude time pressure:** All analysis on moves with >30s remaining
2. **Exclude premoves:** think_time < 0.5s excluded
3. **Exclude forced moves:** Positions with only 1-2 legal moves
4. **Bootstrap confidence intervals:** 1000 resamples for all key statistics
5. **Multiple comparison correction:** Bonferroni for test battery

---

## Success Criteria

| Finding | Threshold | Status |
|---------|-----------|--------|
| Complexity → think_time correlation | r > 0.15, p < 0.01 | ✓ Confirmed |
| Within-complexity: think_time → blunder | r > 0.10, p < 0.01 | ✓ Preliminary |
| Rating effect on firmware boundary | Significant interaction | Pending |
| Blunder prediction AUC | > 0.65 | Pending |
| Bimodal error distribution | Cluster separation | Pending |

---

## Execution Order

1. **Now:** Run 500 more games (overnight)
2. **Tomorrow:** Execute Tests 1-4, document results
3. **If supported:** Run Tests 5-7
4. **Final:** Write findings, update theory document
