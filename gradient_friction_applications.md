# Gradient-Friction Theory: Practical Applications Guide

## How to Apply the Framework in Any Domain

---

## Prerequisites

Any domain can be analyzed if you have:

1. **Decisions with timestamps** — When did each decision occur?
2. **Decision outcomes** — Was the decision correct/successful?
3. **Situation features** — What characterized the situation?
4. **Practitioner skill levels** — Novice, intermediate, expert?

---

## Step 1: Map the Firmware Boundary

### Procedure

1. Collect decisions with response times
2. Calculate each practitioner's average response time
3. Normalize: decision_time / personal_average = normalized_time
4. Classify:
   - **Firmware:** normalized_time < 0.7
   - **System 2:** normalized_time > 1.5
   - **Mixed:** 0.7 - 1.5

### Expected Findings

- Higher-skilled practitioners → more situations in Firmware
- Error rate higher in System 2 situations
- Skill progression = Firmware expansion

---

## Step 2: Identify Error Types

### Fast Errors (Firmware Misfire)

**Signature:**
- Response time: below average
- Situation: objectively complex
- Outcome: wrong

**Meaning:** Template fired inappropriately. Practitioner didn't recognize complexity.

**Intervention:** Train recognition of complexity in these specific situations.

### Slow Errors (System 2 Failure)

**Signature:**
- Response time: above average
- Situation: recognized as complex
- Outcome: wrong

**Meaning:** Backup system couldn't solve the problem.

**Intervention:** Install firmware for these situations through pattern training.

---

## Step 3: Find the Trap Patterns

### The Winning Position Trap

Look for situations where:
- Practitioner has clear advantage
- Response is fast
- Error rate is elevated

**Mechanism:** "Winning" signal suppresses caution.

### The Novelty Trap

Look for situations where:
- Large change from previous state
- Response is fast
- Error rate is elevated

**Mechanism:** Situation changed but firmware still fired.

### The Routine Trap

Look for situations where:
- Surface features match common pattern
- Deep features are unusual
- Fast response, high error

**Mechanism:** Template matched on surface, missed depth.

---

## Domain-Specific Applications

### Medicine: Diagnostic Decisions

**Firmware indicators:**
- Time to initial diagnosis
- Number of differentials considered
- Tests ordered

**Mapping procedure:**
1. Track time from presentation to diagnosis
2. Cluster presentations by features
3. Measure response time per cluster
4. Identify high-friction clusters (System 2)

**Expected findings:**
- Common presentations: Firmware (fast, accurate)
- Rare presentations: System 2 (slow, error-prone)
- Trap: Common presentation + atypical feature

**Interventions:**
- Train pattern recognition for common presentations
- Install Level 2: "Looks like X, check for Y"
- Install Level 3: "Red flags that override routine diagnosis"

### Law: Case Assessment

**Firmware indicators:**
- Time to initial strategy
- Time to settlement recommendation
- Confidence in outcome prediction

**Mapping procedure:**
1. Track time from case intake to strategy decision
2. Cluster cases by type, complexity, parties
3. Measure decision time per cluster
4. Identify high-friction case types

**Expected findings:**
- Standard cases: Firmware (templates apply)
- Novel cases: System 2 (deliberation required)
- Trap: Standard-looking case with unusual feature

**Interventions:**
- Train case pattern recognition
- Install Level 2: "This case type requires X analysis"
- Install Level 3: "Flags that require partner review"

### Trading: Investment Decisions

**Firmware indicators:**
- Time to trade decision
- Confidence level
- Position size

**Mapping procedure:**
1. Track time from signal to execution
2. Cluster market conditions
3. Measure decision time per condition
4. Identify high-friction conditions

**Expected findings:**
- Familiar conditions: Firmware (pattern recognized)
- Unusual conditions: System 2 (analysis required)
- Trap: Winning position → increased risk tolerance

**Interventions:**
- Train pattern recognition for market conditions
- Install Level 2: "This condition requires fresh analysis"
- Install Level 3: "Winning + volatility → reduce position"

### Software Engineering: Code Review

**Firmware indicators:**
- Time per file reviewed
- Comments made
- Issues found

**Mapping procedure:**
1. Track review time per code segment
2. Cluster by code type, complexity, author
3. Measure review time per cluster
4. Identify high-friction code types

**Expected findings:**
- Standard patterns: Firmware (fast review)
- Complex logic: System 2 (slow review)
- Trap: Familiar-looking code with subtle bug

**Interventions:**
- Train pattern recognition for bug patterns
- Install Level 2: "This code type needs extra scrutiny"
- Install Level 3: "Flags for security review"

---

## Measuring Improvement

### Individual Level

Track over time:
- Firmware coverage (% of situations automatic)
- Error rate by situation type
- Friction surface area (inverse of coverage)

**Progress =** Increasing coverage, decreasing friction surface.

### Team Level

Compare:
- Coverage distribution across team
- Which situations are Firmware for experts but System 2 for juniors
- Where do even experts struggle (team ceiling)

**Training targets =** Situations where expert-novice gap is largest.

### Organizational Level

Track:
- Average coverage by tenure
- Coverage growth rate (learning curve)
- Ceiling clusters (universal System 2)

**Institutional knowledge =** Shared firmware across organization.

---

## Installation Procedures

### Installing Level 1 Firmware (Pattern → Response)

1. Identify target situation type
2. Create repetition set (100+ examples)
3. Practice with immediate feedback
4. Track response time reduction
5. Verify accuracy maintained

**Success metric:** Response time drops below 0.7x average while accuracy holds.

### Installing Level 2 Firmware (Pattern → "Calculate")

1. Identify situations requiring deliberation
2. Create recognition triggers (specific features)
3. Train: "When you see X, stop and calculate"
4. Track deliberation rate in target situations
5. Verify error rate decreases

**Success metric:** Elevated response time in target situations, reduced errors.

### Installing Level 3 Firmware (Pattern → "Stop")

1. Identify trap patterns (fast errors)
2. Extract common features of traps
3. Train: "When you see X, STOP regardless of confidence"
4. Track override rate
5. Verify trap errors decrease

**Success metric:** Reduced fast errors in trap situations.

---

## Warning Signs

### Firmware Degradation

- Response times increasing in previously-fast situations
- Error rate rising in "routine" cases
- Practitioner reports "not feeling confident"

**Cause:** Possible skill decay, fatigue, or context change.

### Over-Compilation

- Fast responses in situations that should be System 2
- High confidence, high error rate
- Resistance to new information

**Cause:** Bad patterns compiled, need Level 3 override.

### System 2 Overload

- All situations showing high friction
- Slow responses even in routine cases
- Decision fatigue

**Cause:** Insufficient firmware, need pattern training.

---

## Metrics Dashboard

For any domain, track:

| Metric | What It Shows |
|--------|---------------|
| Firmware coverage | % situations automatic |
| Error rate (Firmware) | Quality of compiled patterns |
| Error rate (System 2) | Backup system capability |
| Fast error rate | Firmware misfire frequency |
| Trap pattern rate | Level 3 installation status |
| Coverage growth | Learning rate |
| Ceiling clusters | Organizational limits |

---

## Quick Start Checklist

- [ ] Identify decisions with timestamps
- [ ] Calculate personal average response times
- [ ] Classify decisions as Firmware/System 2
- [ ] Calculate error rates by category
- [ ] Identify fast errors (firmware misfire)
- [ ] Identify trap patterns
- [ ] Design Level 2/3 interventions
- [ ] Track coverage over time

---

*Framework applicable to any domain with timestamped decisions and outcome data.*
