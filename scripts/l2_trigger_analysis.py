#!/usr/bin/env python3
"""
L2 Trigger Analysis Script

Computes cross-domain transferable L2 trigger metrics:
1. optionality_delta - Decision space change between moves
2. eval_gradient - Position stability disruption
3. criticality_gap - Consequence asymmetry (best vs second-best)
4. opponent_surprise - Environment model violation

Then analyzes: When triggers fire, does friction appear?
               When friction absent despite trigger → blunder?
"""

import sqlite3
import json
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
import statistics


@dataclass
class L2TriggerMetrics:
    """L2 trigger metrics for a single move."""
    ply: int
    game_id: str

    # Core L2 triggers (cross-domain transferable)
    optionality_delta: Optional[float] = None  # Decision space change
    eval_gradient: Optional[float] = None       # Stability disruption
    criticality_gap: Optional[float] = None     # Consequence asymmetry
    opponent_surprise: Optional[bool] = None    # Environment violation

    # Composite
    l2_trigger_score: Optional[float] = None    # Weighted combination
    l2_should_fire: Optional[bool] = None       # Trigger threshold crossed

    # Outcome tracking
    friction_present: Optional[bool] = None     # Did player slow down?
    is_blunder: Optional[bool] = None
    l2_miss: Optional[bool] = None              # Trigger fired but no friction → blunder


class L2TriggerAnalyzer:
    """Analyzes L2 trigger patterns from chess game data."""

    # Thresholds for L2 trigger detection (tunable)
    OPTIONALITY_DELTA_THRESHOLD = 2      # Significant change in alternatives
    EVAL_GRADIENT_THRESHOLD = 50         # 50cp position shift
    CRITICALITY_GAP_THRESHOLD = 100      # 100cp between best and 2nd best
    FRICTION_THRESHOLD = 1.3             # 1.3x normalized think time = friction

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def setup_schema(self):
        """Add L2 trigger columns to database."""
        cursor = self.conn.cursor()

        # Create L2 triggers table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS l2_triggers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                game_id TEXT NOT NULL,
                ply INTEGER NOT NULL,

                -- L2 Trigger Metrics (cross-domain transferable)
                optionality_delta REAL,       -- Decision space change
                eval_gradient REAL,           -- Stability disruption
                criticality_gap REAL,         -- Consequence asymmetry (best vs 2nd)
                opponent_surprise INTEGER,    -- Opponent move not in top-5

                -- Composite L2 Score
                l2_trigger_score REAL,        -- Weighted combination
                l2_should_fire INTEGER,       -- Any trigger crossed threshold

                -- Friction Response
                friction_present INTEGER,     -- Player showed elevated think time
                think_time_normalized REAL,

                -- Outcome
                is_blunder INTEGER,
                eval_drop REAL,

                -- L2 Analysis
                l2_miss INTEGER,              -- Trigger + no friction + blunder
                l2_hit INTEGER,               -- Trigger + friction (correct response)
                l2_false_alarm INTEGER,       -- Friction but no trigger needed

                UNIQUE(game_id, ply)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_l2_game ON l2_triggers(game_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_l2_miss ON l2_triggers(l2_miss)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_l2_trigger ON l2_triggers(l2_should_fire)")

        self.conn.commit()
        print("Schema setup complete.")

    def get_games(self):
        """Get all game IDs."""
        cursor = self.conn.cursor()
        cursor.execute("SELECT DISTINCT game_id FROM friction_analysis ORDER BY game_id")
        return [row['game_id'] for row in cursor.fetchall()]

    def get_game_moves(self, game_id: str):
        """Get all moves for a game with friction analysis data."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                fa.ply,
                fa.player_rating,
                fa.think_time,
                fa.think_time_normalized,
                fa.eval_before,
                fa.eval_after,
                fa.eval_drop,
                fa.num_alternatives,
                fa.eval_spread,
                fa.is_blunder,
                fa.move_rank,
                fa.friction_gap,
                m.san,
                m.is_white,
                m.fen_before
            FROM friction_analysis fa
            JOIN moves m ON fa.game_id = m.game_id AND fa.ply = m.ply
            WHERE fa.game_id = ?
            ORDER BY fa.ply
        """, (game_id,))
        return cursor.fetchall()

    def get_position_eval(self, fen: str):
        """Get engine evaluation for a position."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT eval_cp, best_move, top_moves_json
            FROM evaluations
            WHERE fen = ?
        """, (fen,))
        return cursor.fetchone()

    def parse_top_moves(self, top_moves_json: str) -> list:
        """Parse top moves JSON into list of (move, eval) tuples."""
        if not top_moves_json:
            return []
        try:
            moves = json.loads(top_moves_json)
            return [(m['move'], m['eval']) for m in moves]
        except (json.JSONDecodeError, KeyError):
            return []

    def compute_criticality_gap(self, top_moves: list) -> Optional[float]:
        """Compute gap between best and second-best move."""
        if len(top_moves) < 2:
            return None
        best_eval = top_moves[0][1]
        second_eval = top_moves[1][1]
        return abs(best_eval - second_eval)

    def compute_opponent_surprise(self, opponent_move: str, top_moves: list) -> bool:
        """Check if opponent's move was outside engine top-5."""
        if not top_moves or not opponent_move:
            return False
        top_move_ucis = [m[0] for m in top_moves]
        return opponent_move not in top_move_ucis

    def compute_triggers_for_game(self, game_id: str) -> list:
        """Compute all L2 trigger metrics for a game."""
        moves = self.get_game_moves(game_id)
        if len(moves) < 4:
            return []

        results = []

        # Group moves by player (white: odd ply, black: even ply)
        # We need previous move by same player for optionality_delta
        prev_by_player = {True: None, False: None}  # is_white -> prev move
        prev_move_san = None  # Previous opponent move for surprise detection
        prev_fen = None

        for i, move in enumerate(moves):
            ply = move['ply']
            is_white = bool(move['is_white'])

            metrics = L2TriggerMetrics(ply=ply, game_id=game_id)

            # 1. Optionality Delta - compare to previous move by same player
            prev_same_player = prev_by_player[is_white]
            if prev_same_player is not None:
                prev_alternatives = prev_same_player['num_alternatives'] or 0
                curr_alternatives = move['num_alternatives'] or 0
                metrics.optionality_delta = curr_alternatives - prev_alternatives

            # 2. Eval Gradient - how much did position change from before?
            # This is eval_before[current] vs eval_after[previous]
            if i > 0:
                prev_eval_after = moves[i-1]['eval_after']
                curr_eval_before = move['eval_before']
                if prev_eval_after is not None and curr_eval_before is not None:
                    metrics.eval_gradient = abs(curr_eval_before - prev_eval_after)

            # 3. Criticality Gap - from position evaluation (best vs 2nd best)
            fen = move['fen_before']
            position_eval = self.get_position_eval(fen)
            if position_eval and position_eval['top_moves_json']:
                top_moves = self.parse_top_moves(position_eval['top_moves_json'])
                metrics.criticality_gap = self.compute_criticality_gap(top_moves)

                # 4. Opponent Surprise - was previous move outside engine top-5?
                # We need to look at opponent's position (prev_fen) and see if their move was in top-5
                if prev_fen and prev_move_san:
                    prev_position_eval = self.get_position_eval(prev_fen)
                    if prev_position_eval and prev_position_eval['top_moves_json']:
                        prev_top_moves = self.parse_top_moves(prev_position_eval['top_moves_json'])
                        # Convert SAN to UCI for comparison (simplified - check if move appears)
                        prev_top_ucis = [m[0] for m in prev_top_moves]
                        # This is imperfect but we check if the move led to unexpected position
                        metrics.opponent_surprise = prev_move_san not in str(prev_top_ucis)

            # Compute composite L2 trigger score
            trigger_signals = []

            if metrics.optionality_delta is not None:
                # Normalize: big changes (±3+) are significant
                opt_signal = abs(metrics.optionality_delta) / 3.0
                trigger_signals.append(min(opt_signal, 1.0))

            if metrics.eval_gradient is not None:
                # Normalize: 100cp change is max signal
                grad_signal = metrics.eval_gradient / 100.0
                trigger_signals.append(min(grad_signal, 1.0))

            if metrics.criticality_gap is not None:
                # Normalize: 200cp gap is max signal
                crit_signal = metrics.criticality_gap / 200.0
                trigger_signals.append(min(crit_signal, 1.0))

            if metrics.opponent_surprise:
                trigger_signals.append(1.0)

            if trigger_signals:
                metrics.l2_trigger_score = sum(trigger_signals) / len(trigger_signals)

            # Did L2 trigger fire? (any threshold crossed)
            metrics.l2_should_fire = (
                (metrics.optionality_delta is not None and
                 abs(metrics.optionality_delta) >= self.OPTIONALITY_DELTA_THRESHOLD) or
                (metrics.eval_gradient is not None and
                 metrics.eval_gradient >= self.EVAL_GRADIENT_THRESHOLD) or
                (metrics.criticality_gap is not None and
                 metrics.criticality_gap >= self.CRITICALITY_GAP_THRESHOLD) or
                bool(metrics.opponent_surprise)
            )

            # Friction response
            think_norm = move['think_time_normalized']
            metrics.friction_present = (think_norm is not None and
                                        think_norm >= self.FRICTION_THRESHOLD)

            # Outcome
            metrics.is_blunder = bool(move['is_blunder'])

            # L2 classification
            if metrics.l2_should_fire:
                if metrics.friction_present:
                    metrics.l2_hit = True  # Correct: trigger → friction
                elif metrics.is_blunder:
                    metrics.l2_miss = True  # L2 failure: trigger + no friction + blunder
            elif metrics.friction_present and not metrics.is_blunder:
                metrics.l2_false_alarm = True  # Wasted mental energy

            results.append({
                'game_id': game_id,
                'ply': ply,
                'optionality_delta': metrics.optionality_delta,
                'eval_gradient': metrics.eval_gradient,
                'criticality_gap': metrics.criticality_gap,
                'opponent_surprise': 1 if metrics.opponent_surprise else 0,
                'l2_trigger_score': metrics.l2_trigger_score,
                'l2_should_fire': 1 if metrics.l2_should_fire else 0,
                'friction_present': 1 if metrics.friction_present else 0,
                'think_time_normalized': think_norm,
                'is_blunder': 1 if metrics.is_blunder else 0,
                'eval_drop': move['eval_drop'],
                'l2_miss': 1 if getattr(metrics, 'l2_miss', False) else 0,
                'l2_hit': 1 if getattr(metrics, 'l2_hit', False) else 0,
                'l2_false_alarm': 1 if getattr(metrics, 'l2_false_alarm', False) else 0,
            })

            # Update state for next iteration
            prev_by_player[is_white] = move
            prev_move_san = move['san']
            prev_fen = fen

        return results

    def save_triggers(self, triggers: list):
        """Save computed triggers to database."""
        cursor = self.conn.cursor()

        for t in triggers:
            cursor.execute("""
                INSERT OR REPLACE INTO l2_triggers (
                    game_id, ply, optionality_delta, eval_gradient,
                    criticality_gap, opponent_surprise, l2_trigger_score,
                    l2_should_fire, friction_present, think_time_normalized,
                    is_blunder, eval_drop, l2_miss, l2_hit, l2_false_alarm
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                t['game_id'], t['ply'], t['optionality_delta'], t['eval_gradient'],
                t['criticality_gap'], t['opponent_surprise'], t['l2_trigger_score'],
                t['l2_should_fire'], t['friction_present'], t['think_time_normalized'],
                t['is_blunder'], t['eval_drop'], t['l2_miss'], t['l2_hit'], t['l2_false_alarm']
            ))

        self.conn.commit()

    def compute_all(self):
        """Compute L2 triggers for all games."""
        games = self.get_games()
        print(f"Processing {len(games)} games...")

        total_triggers = 0
        for i, game_id in enumerate(games):
            triggers = self.compute_triggers_for_game(game_id)
            if triggers:
                self.save_triggers(triggers)
                total_triggers += len(triggers)

            if (i + 1) % 50 == 0:
                print(f"  Processed {i+1}/{len(games)} games, {total_triggers} moves")

        print(f"Complete: {total_triggers} moves analyzed across {len(games)} games")
        return total_triggers

    def analyze_results(self):
        """Analyze L2 trigger effectiveness."""
        cursor = self.conn.cursor()

        print("\n" + "="*60)
        print("L2 TRIGGER ANALYSIS RESULTS")
        print("="*60)

        # Overall stats
        cursor.execute("SELECT COUNT(*) FROM l2_triggers")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM l2_triggers WHERE l2_should_fire = 1")
        triggers_fired = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM l2_triggers WHERE friction_present = 1")
        friction_present = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM l2_triggers WHERE is_blunder = 1")
        blunders = cursor.fetchone()[0]

        print(f"\nTotal moves analyzed: {total}")
        print(f"L2 triggers fired: {triggers_fired} ({100*triggers_fired/total:.1f}%)")
        print(f"Friction present: {friction_present} ({100*friction_present/total:.1f}%)")
        print(f"Blunders: {blunders} ({100*blunders/total:.1f}%)")

        # L2 Miss Analysis (key metric)
        print("\n" + "-"*40)
        print("L2 MISS ANALYSIS (Trigger + No Friction + Blunder)")
        print("-"*40)

        cursor.execute("SELECT COUNT(*) FROM l2_triggers WHERE l2_miss = 1")
        l2_misses = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM l2_triggers WHERE l2_hit = 1")
        l2_hits = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM l2_triggers WHERE l2_false_alarm = 1")
        false_alarms = cursor.fetchone()[0]

        print(f"L2 Hits (trigger → friction): {l2_hits}")
        print(f"L2 Misses (trigger + no friction → blunder): {l2_misses}")
        print(f"L2 False Alarms (friction without trigger): {false_alarms}")

        if triggers_fired > 0:
            sensitivity = l2_hits / triggers_fired
            print(f"\nL2 Sensitivity (P(friction|trigger)): {sensitivity:.3f}")

        # Trigger effectiveness by type
        print("\n" + "-"*40)
        print("TRIGGER EFFECTIVENESS BY TYPE")
        print("-"*40)

        for trigger_col, threshold, name in [
            ('optionality_delta', 2, 'Optionality Delta'),
            ('eval_gradient', 50, 'Eval Gradient'),
            ('criticality_gap', 100, 'Criticality Gap'),
            ('opponent_surprise', 0.5, 'Opponent Surprise'),
        ]:
            if trigger_col == 'optionality_delta':
                condition = f"ABS({trigger_col}) >= {threshold}"
            else:
                condition = f"{trigger_col} >= {threshold}"

            cursor.execute(f"""
                SELECT
                    COUNT(*) as total,
                    SUM(friction_present) as friction_count,
                    SUM(is_blunder) as blunder_count,
                    SUM(CASE WHEN friction_present = 0 AND is_blunder = 1 THEN 1 ELSE 0 END) as miss_count
                FROM l2_triggers
                WHERE {trigger_col} IS NOT NULL AND {condition}
            """)
            row = cursor.fetchone()
            if row and row[0] > 0:
                total, friction, blunders, misses = row
                print(f"\n{name} (threshold={threshold}):")
                print(f"  Triggered: {total} times")
                print(f"  Friction response: {friction} ({100*friction/total:.1f}%)")
                print(f"  Blunders when triggered: {blunders} ({100*blunders/total:.1f}%)")
                print(f"  L2 Misses: {misses} ({100*misses/total:.1f}%)")

        # Blunder analysis: with vs without trigger
        print("\n" + "-"*40)
        print("BLUNDER ANALYSIS: TRIGGER vs NO TRIGGER")
        print("-"*40)

        cursor.execute("""
            SELECT
                l2_should_fire,
                COUNT(*) as total,
                SUM(is_blunder) as blunders,
                AVG(eval_drop) as avg_eval_drop
            FROM l2_triggers
            GROUP BY l2_should_fire
        """)
        for row in cursor.fetchall():
            trigger_status = "Trigger fired" if row[0] else "No trigger"
            total, blunders, avg_drop = row[1], row[2], row[3]
            print(f"{trigger_status}: {blunders}/{total} blunders ({100*blunders/total:.1f}%), avg drop: {avg_drop:.1f}cp")

        # Friction response: with vs without trigger
        print("\n" + "-"*40)
        print("FRICTION RESPONSE: TRIGGER vs NO TRIGGER")
        print("-"*40)

        cursor.execute("""
            SELECT
                l2_should_fire,
                AVG(think_time_normalized) as avg_think_norm,
                SUM(friction_present) * 1.0 / COUNT(*) as friction_rate
            FROM l2_triggers
            WHERE think_time_normalized IS NOT NULL
            GROUP BY l2_should_fire
        """)
        for row in cursor.fetchall():
            trigger_status = "Trigger fired" if row[0] else "No trigger"
            print(f"{trigger_status}: avg think={row[1]:.2f}x, friction rate={100*row[2]:.1f}%")

        # L2 trigger score distribution for blunders vs non-blunders
        print("\n" + "-"*40)
        print("L2 TRIGGER SCORE: BLUNDERS vs NON-BLUNDERS")
        print("-"*40)

        cursor.execute("""
            SELECT AVG(l2_trigger_score) FROM l2_triggers
            WHERE is_blunder = 1 AND l2_trigger_score IS NOT NULL
        """)
        blunder_score = cursor.fetchone()[0]

        cursor.execute("""
            SELECT AVG(l2_trigger_score) FROM l2_triggers
            WHERE is_blunder = 0 AND l2_trigger_score IS NOT NULL
        """)
        non_blunder_score = cursor.fetchone()[0]

        print(f"Avg L2 trigger score on blunders: {blunder_score:.3f}")
        print(f"Avg L2 trigger score on non-blunders: {non_blunder_score:.3f}")

        # Critical finding: L2 misses characteristics
        print("\n" + "-"*40)
        print("L2 MISS CHARACTERISTICS")
        print("-"*40)

        cursor.execute("""
            SELECT
                AVG(optionality_delta) as avg_opt_delta,
                AVG(eval_gradient) as avg_eval_grad,
                AVG(criticality_gap) as avg_crit_gap,
                AVG(eval_drop) as avg_eval_drop
            FROM l2_triggers
            WHERE l2_miss = 1
        """)
        row = cursor.fetchone()
        if row[0]:
            print(f"When L2 misses occur:")
            print(f"  Avg optionality delta: {row[0]:.2f}")
            print(f"  Avg eval gradient: {row[1]:.1f}cp")
            print(f"  Avg criticality gap: {row[2]:.1f}cp")
            print(f"  Avg eval drop (blunder size): {row[3]:.1f}cp")

        return {
            'total_moves': total,
            'triggers_fired': triggers_fired,
            'l2_misses': l2_misses,
            'l2_hits': l2_hits,
            'blunders': blunders
        }

    def close(self):
        self.conn.close()


def main():
    db_path = Path(__file__).parent.parent / "output" / "friction.db"

    if not db_path.exists():
        print(f"Database not found: {db_path}")
        return

    print(f"Analyzing L2 triggers in: {db_path}")

    analyzer = L2TriggerAnalyzer(str(db_path))

    # Setup schema
    analyzer.setup_schema()

    # Compute triggers
    analyzer.compute_all()

    # Analyze results
    results = analyzer.analyze_results()

    analyzer.close()

    print("\n" + "="*60)
    print("Analysis complete. Results saved to l2_triggers table.")
    print("="*60)


if __name__ == "__main__":
    main()
