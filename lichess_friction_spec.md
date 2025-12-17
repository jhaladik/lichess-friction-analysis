# Lichess Friction Analysis Tool: Technical Specification

## Project Overview

### Purpose
Validate the hypothesis that blunders in chess correlate with friction absence—situations where the player should have experienced demonstrated optionality (elevated thinking time) but didn't.

### Core Hypothesis
In non-time-pressure situations, blunders occur when thinking time is *below* average for that player/position type, not above. The player followed their firmware gradient without seeing options that existed.

### Success Criteria
Statistical significance showing negative correlation between thinking time and blunder probability in non-time-pressure conditions, controlling for position complexity and player rating.

---

## Data Source

### Lichess Open Database
- URL: https://database.lichess.org/
- Format: PGN files with clock annotations
- Size: Billions of games, monthly exports
- License: CC0 (public domain)

### Required Data Fields
```
- Game ID
- Player ratings (both sides)
- Time control (base + increment)
- Move sequence (SAN notation)
- Clock times per move (when available)
- Game result
- Opening classification (ECO code)
- Date/time of game
```

### Data Filtering Criteria
```
- Time control: Classical or Rapid only (≥10+0)
- Clock annotations: Must be present
- Rating: 1000-2500 (exclude extreme outliers)
- Game completion: Must have result (no abandons)
- Minimum moves: ≥20 moves per player
```

---

## Architecture

### Components

```
┌─────────────────────────────────────────────────────────────────┐
│                         PIPELINE                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │   PGN    │───▶│  Parser  │───▶│ Position │───▶│ Stockfish│  │
│  │  Source  │    │          │    │ Encoder  │    │   Eval   │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                        │        │
│                                                        ▼        │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  Output  │◀───│ Analysis │◀───│ Friction │◀───│  Move    │  │
│  │   CSV    │    │  Engine  │    │ Metrics  │    │ Records  │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Module Specifications

#### 1. PGN Parser Module
**Input:** Raw PGN files from Lichess
**Output:** Structured game records

```python
GameRecord:
    game_id: str
    white_rating: int
    black_rating: int
    time_control: TimeControl
    result: str  # "1-0", "0-1", "1/2-1/2"
    eco: str
    moves: List[MoveRecord]

MoveRecord:
    ply: int  # half-move number
    san: str  # move in SAN notation
    uci: str  # move in UCI notation
    clock_after: float  # seconds remaining after move
    clock_before: float  # seconds remaining before move (derived)
    think_time: float  # clock_before - clock_after
```

**Requirements:**
- Handle malformed PGN gracefully (skip, log)
- Extract clock annotations from comments: `{[%clk 0:05:23]}`
- Calculate think_time accounting for increment
- Stream processing (don't load full file to memory)

#### 2. Position Encoder Module
**Input:** Board state (FEN) + game context
**Output:** Feature vector for position

```python
PositionFeatures:
    # Material
    material_balance: int  # centipawns
    total_material: int
    
    # Structure
    pawn_structure_hash: str  # cluster identifier
    open_files: int
    pawn_islands: List[int]  # per side
    
    # King safety
    king_shelter: Tuple[int, int]  # per side
    king_zone_attacks: Tuple[int, int]
    
    # Piece activity
    mobility: Tuple[int, int]  # legal moves per side
    
    # Phase
    game_phase: float  # 0.0 (endgame) to 1.0 (opening)
    
    # Complexity proxy
    num_legal_moves: int
    num_captures: int
    num_checks: int
    
    # Template indicators
    is_book_position: bool
    moves_out_of_book: int
```

**Requirements:**
- Use python-chess for board representation
- Fast feature extraction (will process millions of positions)
- Optional: integrate with opening book for template detection

#### 3. Engine Evaluation Module
**Input:** Position (FEN) + move played
**Output:** Evaluation data

```python
EvalRecord:
    position_fen: str
    move_played: str
    
    # Pre-move eval
    eval_before: float  # centipawns, from side-to-move perspective
    best_move: str
    second_best_move: str
    eval_best: float
    eval_second: float
    
    # Post-move eval
    eval_after: float
    
    # Derived
    eval_drop: float  # eval_before - eval_after (positive = mistake)
    was_best_move: bool
    move_rank: int  # 1 = best, 2 = second best, etc.
    
    # Multi-PV data
    top_moves: List[Tuple[str, float]]  # top 5 moves with evals
    eval_spread: float  # difference between best and 5th best
```

**Requirements:**
- Use Stockfish 16+ via python-chess or direct UCI
- Depth: 20 ply minimum (configurable)
- Multi-PV: 5 lines for optionality measurement
- Cache evaluations (same position = same eval)
- Batch processing for efficiency

#### 4. Friction Metrics Module
**Input:** MoveRecord + EvalRecord + PositionFeatures
**Output:** Friction analysis per move

```python
FrictionRecord:
    # Identifiers
    game_id: str
    ply: int
    player_rating: int
    
    # Time metrics
    think_time: float
    think_time_normalized: float  # vs player's average in this game
    time_pressure: bool  # <30 seconds remaining
    time_ratio: float  # think_time / time_remaining
    
    # Position metrics
    position_features: PositionFeatures
    
    # Evaluation metrics
    eval_drop: float
    was_blunder: bool  # eval_drop > threshold (e.g., 100cp)
    was_mistake: bool  # eval_drop > 50cp
    move_rank: int
    
    # Optionality metrics
    eval_spread: float  # how close are top moves
    has_alternatives: bool  # multiple moves within 50cp of best
    
    # Derived friction indicators
    expected_friction: bool  # has_alternatives = true
    actual_friction: bool  # think_time_normalized > 1.0
    friction_gap: bool  # expected but not actual
```

**Blunder Classification:**
```
BLUNDER: eval_drop > 100 centipawns
MISTAKE: eval_drop > 50 centipawns
INACCURACY: eval_drop > 25 centipawns
```

**Friction Classification:**
```
HIGH_FRICTION: think_time_normalized > 1.5
NORMAL_FRICTION: 0.7 < think_time_normalized < 1.5
LOW_FRICTION: think_time_normalized < 0.7
```

#### 5. Analysis Engine Module
**Input:** Collection of FrictionRecords
**Output:** Statistical analysis

```python
AnalysisResults:
    # Core hypothesis test
    correlation_blunder_thinktime: CorrelationResult
    correlation_by_time_pressure: Dict[bool, CorrelationResult]
    
    # Segmented analysis
    blunder_rate_by_friction_level: Dict[str, float]
    avg_think_time_blunders: float
    avg_think_time_non_blunders: float
    
    # Controls
    blunder_rate_by_rating_band: Dict[str, float]
    blunder_rate_by_game_phase: Dict[str, float]
    blunder_rate_by_position_complexity: Dict[str, float]
    
    # Friction gap analysis
    friction_gap_rate: float  # how often expected friction absent
    blunder_rate_given_friction_gap: float
    blunder_rate_given_friction_present: float
    
    # Statistical tests
    t_test_result: TTestResult
    chi_square_result: ChiSquareResult
    logistic_regression: RegressionResult
```

**Required Statistical Tests:**
1. **T-test:** Compare mean think time for blunders vs non-blunders
2. **Chi-square:** Independence of friction_gap and blunder occurrence
3. **Logistic regression:** Predict blunder from think_time_normalized, controlling for:
   - Rating
   - Game phase
   - Position complexity (num_legal_moves)
   - Time remaining
   - Eval spread (optionality)

---

## Database Schema

### SQLite for intermediate storage

```sql
CREATE TABLE games (
    game_id TEXT PRIMARY KEY,
    white_rating INTEGER,
    black_rating INTEGER,
    time_control TEXT,
    result TEXT,
    eco TEXT,
    num_moves INTEGER,
    date TEXT
);

CREATE TABLE moves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT,
    ply INTEGER,
    san TEXT,
    uci TEXT,
    fen_before TEXT,
    fen_after TEXT,
    clock_before REAL,
    clock_after REAL,
    think_time REAL,
    FOREIGN KEY (game_id) REFERENCES games(game_id)
);

CREATE TABLE evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fen TEXT UNIQUE,
    eval_cp INTEGER,
    best_move TEXT,
    top_moves_json TEXT,  -- JSON array of {move, eval}
    depth INTEGER
);

CREATE TABLE friction_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT,
    ply INTEGER,
    player_rating INTEGER,
    think_time REAL,
    think_time_normalized REAL,
    time_pressure BOOLEAN,
    eval_drop REAL,
    is_blunder BOOLEAN,
    is_mistake BOOLEAN,
    has_alternatives BOOLEAN,
    expected_friction BOOLEAN,
    actual_friction BOOLEAN,
    friction_gap BOOLEAN,
    game_phase REAL,
    num_legal_moves INTEGER,
    FOREIGN KEY (game_id) REFERENCES games(game_id)
);

CREATE INDEX idx_friction_blunder ON friction_analysis(is_blunder);
CREATE INDEX idx_friction_gap ON friction_analysis(friction_gap);
CREATE INDEX idx_friction_time_pressure ON friction_analysis(time_pressure);
```

---

## Configuration

```yaml
# config.yaml

data:
  pgn_source: "lichess_db_standard_rated_2024-01.pgn.zst"
  output_dir: "./output"
  sample_size: 100000  # games to process, null for all

filters:
  min_rating: 1000
  max_rating: 2500
  min_time_control: 600  # seconds base time
  require_clocks: true
  min_moves: 20

engine:
  path: "/usr/bin/stockfish"
  depth: 20
  multipv: 5
  threads: 4
  hash_mb: 2048

thresholds:
  blunder_cp: 100
  mistake_cp: 50
  inaccuracy_cp: 25
  time_pressure_seconds: 30
  high_friction_multiplier: 1.5
  low_friction_multiplier: 0.7
  alternative_threshold_cp: 50  # moves within this of best = alternatives

analysis:
  control_variables:
    - rating_band  # 1000-1200, 1200-1400, etc.
    - game_phase   # opening, middlegame, endgame
    - complexity   # num_legal_moves quartiles
  significance_level: 0.05
```

---

## Output Specifications

### 1. Raw Data Export
```
output/
├── friction_records.csv       # All processed moves
├── blunder_analysis.csv       # Blunders only with context
├── player_profiles.csv        # Per-player friction patterns
└── position_clusters.csv      # Position types with friction stats
```

### 2. Statistical Report
```markdown
# Friction Analysis Report

## Summary Statistics
- Games analyzed: N
- Moves analyzed: N
- Blunders identified: N (X%)
- Friction gaps identified: N (X%)

## Core Hypothesis Test
- Mean think time (blunders): X.XX seconds
- Mean think time (non-blunders): X.XX seconds
- T-statistic: X.XX
- P-value: X.XXXX
- Effect size (Cohen's d): X.XX

## Friction Gap Analysis
- Blunder rate when friction gap present: X.X%
- Blunder rate when friction gap absent: X.X%
- Relative risk: X.XX
- Chi-square: X.XX (p = X.XXXX)

## Logistic Regression
[coefficient table]

## Visualizations
[embedded charts]
```

### 3. Visualizations Required

1. **Scatter plot:** Think time vs eval drop (with density)
2. **Box plot:** Think time distribution for blunders vs non-blunders
3. **Heatmap:** Blunder rate by friction level × position complexity
4. **Line chart:** Blunder rate by think_time_normalized decile
5. **Bar chart:** Friction gap presence by rating band

---

## Implementation Notes

### Performance Considerations
- PGN parsing is I/O bound → use streaming, zstd decompression
- Engine evaluation is CPU bound → batch positions, use cache
- Expect ~1-2 seconds per position at depth 20
- For 100K games × 40 moves = 4M positions → ~2-4 days eval time
- Use multiprocessing for engine evaluation
- Consider cloud compute (GPU not needed, multi-core helps)

### Edge Cases to Handle
1. **Increment vs delay:** Time control "10+5" means 5 sec increment per move
2. **Pre-move:** Some moves have 0 think time (pre-moved) → exclude or flag
3. **First moves:** Opening moves often pre-moved → separate analysis
4. **Disconnections:** Clock jumps → detect and exclude
5. **Berserking:** Player halves their time → filter these games

### Validation Steps
1. Sanity check: average think time should decrease as time runs low
2. Sanity check: blunder rate should increase in time pressure
3. Compare results across rating bands (should be consistent pattern)
4. Bootstrap confidence intervals on core metrics

---

## Development Phases

### Phase 1: Data Pipeline (Week 1)
- [ ] PGN parser with clock extraction
- [ ] Position encoder
- [ ] Database schema and loading
- [ ] Unit tests for each module

### Phase 2: Engine Integration (Week 2)
- [ ] Stockfish UCI wrapper
- [ ] Evaluation caching
- [ ] Batch processing
- [ ] Multi-PV extraction

### Phase 3: Friction Analysis (Week 3)
- [ ] Friction metrics calculation
- [ ] Normalization logic
- [ ] Friction gap detection
- [ ] Integration tests

### Phase 4: Statistical Analysis (Week 4)
- [ ] Core hypothesis tests
- [ ] Segmented analysis
- [ ] Visualization generation
- [ ] Report compilation

### Phase 5: Validation & Refinement (Week 5)
- [ ] Edge case handling
- [ ] Result validation
- [ ] Parameter sensitivity analysis
- [ ] Documentation

---

## Dependencies

```
python >= 3.10
python-chess >= 1.9
stockfish >= 16
pandas >= 2.0
numpy >= 1.24
scipy >= 1.10
statsmodels >= 0.14
matplotlib >= 3.7
seaborn >= 0.12
sqlite3 (stdlib)
zstandard >= 0.21
pyyaml >= 6.0
tqdm >= 4.65
```

---

## Success Metrics

### Primary
**The hypothesis is supported if:**
- Negative correlation between think_time_normalized and blunder probability (p < 0.05)
- Blunder rate is higher when friction_gap = true vs false (p < 0.05)
- Effect persists after controlling for time pressure, rating, complexity

### Secondary
- Identify position types with highest friction gap rates
- Identify rating bands where effect is strongest/weakest
- Quantify "missing friction" as predictor of errors

### Null Result
If think time shows no relationship or positive relationship with blunders in non-time-pressure situations, the hypothesis is not supported for chess. Document and report.

---

## Extensions (Future Work)

1. **Player firmware profiling:** Map individual players' friction patterns to predict their blunder-prone positions
2. **Real-time application:** Flag positions where player should slow down based on friction model
3. **Training tool:** Generate puzzles from positions with high friction gap rates
4. **Cross-domain validation:** Apply same methodology to other domains with decision timestamps
