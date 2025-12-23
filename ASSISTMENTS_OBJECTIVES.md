# ASSISTments Friction Analysis: Objectives

## Why ASSISTments is Better Than Stack Overflow

| Aspect | Chess | ASSISTments | Stack Overflow |
|--------|-------|-------------|----------------|
| Time signal | Clock (think time) | `ms_first_response` | Response time (confounded) |
| Error signal | Engine eval (objective) | `correct` (objective) | Votes (social) |
| Skill tracking | Rating | `skill_id` + `opportunity` | Reputation |
| Friction visible | Long think | Hints + attempts | Not visible |

**ASSISTments has OBJECTIVE signals like chess, not social signals like SO.**

---

## The Parallel to Chess

```
CHESS                          ASSISTMENTS
─────                          ───────────
Position appears        →      Problem appears
Clock starts            →      Timer starts (ms_first_response)
Player thinks           →      Student thinks
Player moves            →      Student answers
Engine evaluates        →      System checks correct/incorrect
Rating updates          →      Skill mastery tracked
```

---

## Core Hypothesis (Same as Chess)

**Friction signals firmware failure, not careful thinking.**

Predictions:
1. Fast + correct = firmware (pattern recognized)
2. Fast + wrong = firmware misfire (wrong pattern applied)
3. Slow + correct = S2 success (calculated despite no pattern)
4. Slow + wrong = S2 failure (calculated but still failed)

**Key test**: Do errors correlate with think time by skill difficulty?

---

## Objectives

### Objective 1: Validate Think Time → Error Correlation

**Question**: Does `ms_first_response` predict `correct` like chess think time predicts blunders?

**Test**:
- Bin problems by difficulty (skill complexity)
- Calculate correlation between response time and error rate
- Expect: Positive correlation in complex skills (longer think → more errors)

**Chess finding to replicate**: r=0.175 in complex positions (Q4)

---

### Objective 2: Map Firmware Development

**Question**: Does `opportunity` (experience) show firmware development?

**Test**:
- Track same student across opportunities on same skill
- Plot: response time vs opportunity number
- Plot: error rate vs opportunity number

**Expected pattern**:
- Early opportunities: slow + high error (no firmware)
- Later opportunities: fast + low error (firmware installed)

**Chess parallel**: Rating progression = firmware breadth

---

### Objective 3: Identify Friction Signals

**Question**: What signals S2 engagement (friction)?

**Candidates**:
- `hint_count > 0` → Asked for help (S2)
- `attempt_count > 1` → Multiple tries (S2)
- `ms_first_response` > threshold → Long think (S2)
- `first_action = 'hint'` → Started with hint (S2)

**Test**:
- Compare error rates: hint users vs non-hint users
- Compare error rates: fast vs slow responders
- Find the friction boundary

---

### Objective 4: Detect Firmware Misfires

**Question**: Can we identify "fast wrong" answers (firmware misfires)?

**Chess parallel**: Fast blunders in complex positions = firmware confidently handled something it shouldn't

**Test**:
- Find: fast response + wrong answer + high skill difficulty
- These are firmware misfires
- Compare to: slow response + wrong answer (S2 failures)

**Expected**: Fast-wrong happens on problems that LOOK like known patterns but aren't

---

### Objective 5: Skill-Specific Firmware

**Question**: Do students develop firmware for specific skills?

**Test**:
- Track response time by skill for each student
- Identify "firmware skills" (fast + accurate)
- Identify "S2 skills" (slow + variable)

**Chess parallel**:
- Expert fast in openings (firmware)
- Expert slow in middlegame (S2)

---

## Data Requirements

### From ASSISTments 2009-2010:

| Field | Use |
|-------|-----|
| `user_id` | Track individual students |
| `skill_id` | Group by skill type |
| `ms_first_response` | Think time (friction signal) |
| `correct` | Error signal |
| `hint_count` | S2 engagement signal |
| `attempt_count` | Friction signal |
| `opportunity` | Experience level |
| `first_action` | Initial approach (attempt vs hint) |

### Sample Size

- Dataset: 346,860 interactions
- Students: 4,217
- Problems: 26,688

**Much larger than our chess sample (29,735 moves)**

---

## Success Criteria

| Test | Success Metric |
|------|----------------|
| Think time → error correlation | r > 0.1 in complex skills, p < 0.001 |
| Firmware development | Response time drops 30%+ with opportunity |
| S2 signal validity | Hint users have 2x+ error rate |
| Firmware misfire detection | Fast-wrong clusters in specific problem types |
| Skill-specific firmware | Measurable per-student skill profiles |

---

## Analysis Plan

### Phase 1: Data Exploration
- [ ] Download ASSISTments 2009-2010 skill builder data
- [ ] Understand field distributions
- [ ] Identify data quality issues

### Phase 2: Core Friction Test
- [ ] Replicate chess Test 1: complexity-blunder-friction triangle
- [ ] Bin by skill difficulty
- [ ] Calculate time-error correlations

### Phase 3: Firmware Development
- [ ] Track students over opportunities
- [ ] Map learning curves (time + accuracy)
- [ ] Identify firmware installation point

### Phase 4: S2 Analysis
- [ ] Validate hint_count as S2 signal
- [ ] Compare fast-wrong vs slow-wrong errors
- [ ] Identify firmware misfire patterns

### Phase 5: Cross-Domain Validation
- [ ] Compare findings to chess results
- [ ] Write validation report
- [ ] Identify universal patterns

---

## Questions to Answer

1. **Does friction predict errors in education like chess?**
2. **Is expertise = firmware coverage (pattern recognition)?**
3. **Do students develop skill-specific firmware?**
4. **Can we identify firmware misfires (fast wrong answers)?**
5. **Is the gradient-friction theory universal?**

---

*Objectives defined December 2024*
*For cross-domain validation of Gradient-Friction Theory*
