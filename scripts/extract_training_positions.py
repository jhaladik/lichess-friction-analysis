#!/usr/bin/env python3
"""
L2 Training Position Extractor

Extracts positions for L2 trigger training based on the L2 miss patterns
identified in the friction analysis database.
"""

import sqlite3
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import List, Optional
import argparse


@dataclass
class TrainingPosition:
    """A position for L2 training."""
    fen: str
    blunder_move: str
    best_move: str
    criticality_gap: float
    optionality_delta: float
    game_phase: float
    player_rating: int
    difficulty: str
    pattern_type: str


class TrainingPositionExtractor:
    """Extracts L2 training positions from friction database."""

    DIFFICULTY_RANGES = {
        'easy': (500, 10000),      # Obvious critical - "only move"
        'medium': (200, 500),      # Clear critical
        'hard': (100, 200),        # Subtle critical (highest L2 miss zone)
    }

    PATTERN_TYPES = {
        'endgame_trap': "game_phase < 0.4",
        'quiet_critical': "num_legal_moves < 25",
        'options_shrinking': "optionality_delta <= -2",
        'transition': "game_phase BETWEEN 0.4 AND 0.6",
    }

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.conn.row_factory = sqlite3.Row

    def extract_positions(
        self,
        difficulty: str = 'medium',
        rating_min: int = 1000,
        rating_max: int = 2500,
        pattern_type: Optional[str] = None,
        limit: int = 50
    ) -> List[TrainingPosition]:
        """Extract training positions based on criteria."""

        crit_min, crit_max = self.DIFFICULTY_RANGES.get(difficulty, (100, 500))

        pattern_filter = ""
        if pattern_type and pattern_type in self.PATTERN_TYPES:
            pattern_filter = f"AND {self.PATTERN_TYPES[pattern_type]}"

        query = f"""
            SELECT
                m.fen_before as fen,
                m.san as blunder_move,
                e.best_move,
                l2.criticality_gap,
                l2.optionality_delta,
                fa.game_phase,
                fa.player_rating,
                fa.num_legal_moves
            FROM l2_triggers l2
            JOIN moves m ON l2.game_id = m.game_id AND l2.ply = m.ply
            JOIN evaluations e ON m.fen_before = e.fen
            JOIN friction_analysis fa ON l2.game_id = fa.game_id AND l2.ply = fa.ply
            WHERE l2.l2_miss = 1
              AND l2.criticality_gap BETWEEN ? AND ?
              AND fa.player_rating BETWEEN ? AND ?
              AND e.best_move IS NOT NULL
              {pattern_filter}
            ORDER BY RANDOM()
            LIMIT ?
        """

        cursor = self.conn.cursor()
        cursor.execute(query, (crit_min, crit_max, rating_min, rating_max, limit))

        positions = []
        for row in cursor.fetchall():
            # Determine pattern type from characteristics
            detected_pattern = self._detect_pattern(row)

            positions.append(TrainingPosition(
                fen=row['fen'],
                blunder_move=row['blunder_move'],
                best_move=row['best_move'],
                criticality_gap=row['criticality_gap'],
                optionality_delta=row['optionality_delta'] or 0,
                game_phase=row['game_phase'],
                player_rating=row['player_rating'],
                difficulty=difficulty,
                pattern_type=detected_pattern
            ))

        return positions

    def _detect_pattern(self, row) -> str:
        """Detect the pattern type from position characteristics."""
        if row['game_phase'] < 0.4:
            return 'endgame_trap'
        elif row['num_legal_moves'] < 25:
            return 'quiet_critical'
        elif row['optionality_delta'] and row['optionality_delta'] <= -2:
            return 'options_shrinking'
        elif 0.4 <= row['game_phase'] <= 0.6:
            return 'transition'
        else:
            return 'general'

    def extract_classification_set(
        self,
        count_per_category: int = 20
    ) -> dict:
        """
        Extract a balanced set for danger classification training.
        Returns both critical (should trigger L2) and safe (can move fast) positions.
        """

        # Critical positions (L2 should fire)
        critical = self.extract_positions(
            difficulty='hard',
            limit=count_per_category
        )

        # Safe positions (L2 not needed) - low criticality, move quickly is fine
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT
                m.fen_before as fen,
                m.san as move_played,
                e.best_move,
                l2.criticality_gap,
                fa.game_phase,
                fa.player_rating
            FROM l2_triggers l2
            JOIN moves m ON l2.game_id = m.game_id AND l2.ply = m.ply
            JOIN evaluations e ON m.fen_before = e.fen
            JOIN friction_analysis fa ON l2.game_id = fa.game_id AND l2.ply = fa.ply
            WHERE l2.criticality_gap < 50
              AND l2.is_blunder = 0
              AND e.best_move IS NOT NULL
            ORDER BY RANDOM()
            LIMIT ?
        """, (count_per_category,))

        safe = []
        for row in cursor.fetchall():
            safe.append({
                'fen': row['fen'],
                'move_played': row['move_played'],
                'best_move': row['best_move'],
                'criticality_gap': row['criticality_gap'],
                'game_phase': row['game_phase'],
                'category': 'safe'
            })

        return {
            'critical': [asdict(p) for p in critical],
            'safe': safe,
            'instructions': {
                'task': 'Classify each position: Does this require slow thinking?',
                'critical_threshold': 'If criticality_gap >= 100, answer should be YES',
                'safe_threshold': 'If criticality_gap < 50, answer should be NO'
            }
        }

    def extract_progression_set(self) -> dict:
        """
        Extract a progressive training set from easy to hard.
        """
        return {
            'week_1_2': self.extract_positions(difficulty='easy', limit=40),
            'week_3_4': self.extract_positions(difficulty='medium', limit=40),
            'week_5_6': self.extract_positions(difficulty='hard', limit=40),
            'metadata': {
                'easy': 'Obvious critical positions (gap 500+cp)',
                'medium': 'Clear critical positions (gap 200-500cp)',
                'hard': 'Subtle critical positions (gap 100-200cp)'
            }
        }

    def get_statistics(self) -> dict:
        """Get statistics about available training positions."""
        cursor = self.conn.cursor()

        stats = {}

        # Count by difficulty
        for diff, (crit_min, crit_max) in self.DIFFICULTY_RANGES.items():
            cursor.execute("""
                SELECT COUNT(*) FROM l2_triggers
                WHERE l2_miss = 1 AND criticality_gap BETWEEN ? AND ?
            """, (crit_min, crit_max))
            stats[f'{diff}_positions'] = cursor.fetchone()[0]

        # Count by pattern type
        cursor.execute("""
            SELECT
                CASE
                    WHEN fa.game_phase < 0.4 THEN 'endgame_trap'
                    WHEN fa.num_legal_moves < 25 THEN 'quiet_critical'
                    WHEN l2.optionality_delta <= -2 THEN 'options_shrinking'
                    ELSE 'other'
                END as pattern,
                COUNT(*) as count
            FROM l2_triggers l2
            JOIN friction_analysis fa ON l2.game_id = fa.game_id AND l2.ply = fa.ply
            WHERE l2.l2_miss = 1
            GROUP BY 1
        """)
        stats['by_pattern'] = {row[0]: row[1] for row in cursor.fetchall()}

        # Total available
        cursor.execute("SELECT COUNT(*) FROM l2_triggers WHERE l2_miss = 1")
        stats['total_l2_misses'] = cursor.fetchone()[0]

        return stats

    def export_to_json(self, positions: List[TrainingPosition], output_path: str):
        """Export positions to JSON file."""
        data = [asdict(p) for p in positions]
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"Exported {len(positions)} positions to {output_path}")

    def close(self):
        self.conn.close()


def main():
    parser = argparse.ArgumentParser(description='Extract L2 training positions')
    parser.add_argument('--difficulty', choices=['easy', 'medium', 'hard', 'all'],
                       default='medium', help='Difficulty level')
    parser.add_argument('--rating-min', type=int, default=1000)
    parser.add_argument('--rating-max', type=int, default=2500)
    parser.add_argument('--limit', type=int, default=50)
    parser.add_argument('--pattern', choices=['endgame_trap', 'quiet_critical',
                                              'options_shrinking', 'transition'],
                       help='Filter by pattern type')
    parser.add_argument('--output', type=str, help='Output JSON file')
    parser.add_argument('--stats', action='store_true', help='Show statistics only')
    parser.add_argument('--classification-set', action='store_true',
                       help='Generate balanced classification training set')

    args = parser.parse_args()

    db_path = Path(__file__).parent.parent / "output" / "friction.db"
    extractor = TrainingPositionExtractor(str(db_path))

    if args.stats:
        stats = extractor.get_statistics()
        print("\nL2 Training Position Statistics:")
        print("=" * 40)
        print(f"Total L2 miss positions: {stats['total_l2_misses']}")
        print(f"\nBy difficulty:")
        print(f"  Easy (500+cp gap):    {stats['easy_positions']}")
        print(f"  Medium (200-500cp):   {stats['medium_positions']}")
        print(f"  Hard (100-200cp):     {stats['hard_positions']}")
        print(f"\nBy pattern:")
        for pattern, count in stats['by_pattern'].items():
            print(f"  {pattern}: {count}")
        extractor.close()
        return

    if args.classification_set:
        data = extractor.extract_classification_set()
        output = args.output or 'training_classification_set.json'
        with open(output, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        print(f"Exported classification set to {output}")
        print(f"  Critical positions: {len(data['critical'])}")
        print(f"  Safe positions: {len(data['safe'])}")
        extractor.close()
        return

    if args.difficulty == 'all':
        positions = []
        for diff in ['easy', 'medium', 'hard']:
            positions.extend(extractor.extract_positions(
                difficulty=diff,
                rating_min=args.rating_min,
                rating_max=args.rating_max,
                pattern_type=args.pattern,
                limit=args.limit // 3
            ))
    else:
        positions = extractor.extract_positions(
            difficulty=args.difficulty,
            rating_min=args.rating_min,
            rating_max=args.rating_max,
            pattern_type=args.pattern,
            limit=args.limit
        )

    if args.output:
        extractor.export_to_json(positions, args.output)
    else:
        print(f"\nExtracted {len(positions)} training positions:")
        print("=" * 60)
        for i, pos in enumerate(positions[:5], 1):
            print(f"\n{i}. [{pos.difficulty}] {pos.pattern_type}")
            print(f"   FEN: {pos.fen[:50]}...")
            print(f"   Blunder: {pos.blunder_move}, Best: {pos.best_move}")
            print(f"   Criticality: {pos.criticality_gap}cp, Phase: {pos.game_phase:.2f}")

        if len(positions) > 5:
            print(f"\n... and {len(positions) - 5} more positions")

    extractor.close()


if __name__ == "__main__":
    main()
