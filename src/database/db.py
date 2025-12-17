"""
Database Module - SQLite storage for friction analysis data.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional, List, Iterator, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class Database:
    """SQLite database for storing games, moves, evaluations, and friction analysis."""

    SCHEMA = """
    -- Games table
    CREATE TABLE IF NOT EXISTS games (
        game_id TEXT PRIMARY KEY,
        white_rating INTEGER,
        black_rating INTEGER,
        time_control TEXT,
        increment INTEGER DEFAULT 0,
        result TEXT,
        eco TEXT,
        num_moves INTEGER,
        date TEXT,
        termination TEXT
    );

    -- Moves table
    CREATE TABLE IF NOT EXISTS moves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id TEXT NOT NULL,
        ply INTEGER NOT NULL,
        san TEXT NOT NULL,
        uci TEXT NOT NULL,
        fen_before TEXT NOT NULL,
        fen_after TEXT NOT NULL,
        clock_before REAL,
        clock_after REAL,
        think_time REAL,
        is_white BOOLEAN,
        FOREIGN KEY (game_id) REFERENCES games(game_id),
        UNIQUE(game_id, ply)
    );

    -- Evaluations cache (by FEN to avoid recomputing)
    CREATE TABLE IF NOT EXISTS evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fen TEXT UNIQUE NOT NULL,
        eval_cp INTEGER,
        best_move TEXT,
        top_moves_json TEXT,
        depth INTEGER,
        multipv INTEGER
    );

    -- Friction analysis results
    CREATE TABLE IF NOT EXISTS friction_analysis (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        game_id TEXT NOT NULL,
        ply INTEGER NOT NULL,
        player_rating INTEGER,

        -- Time metrics
        think_time REAL,
        think_time_normalized REAL,
        time_remaining REAL,
        time_pressure BOOLEAN,

        -- Evaluation metrics
        eval_before INTEGER,
        eval_after INTEGER,
        eval_drop REAL,
        was_best_move BOOLEAN,
        move_rank INTEGER,

        -- Classification
        is_blunder BOOLEAN,
        is_mistake BOOLEAN,
        is_inaccuracy BOOLEAN,

        -- Optionality metrics
        num_alternatives INTEGER,
        eval_spread REAL,
        has_alternatives BOOLEAN,

        -- Friction metrics
        expected_friction BOOLEAN,
        actual_friction BOOLEAN,
        friction_gap BOOLEAN,
        friction_level TEXT,

        -- Position metrics
        game_phase REAL,
        num_legal_moves INTEGER,
        complexity_score REAL,

        FOREIGN KEY (game_id) REFERENCES games(game_id),
        UNIQUE(game_id, ply)
    );

    -- Indexes for common queries
    CREATE INDEX IF NOT EXISTS idx_moves_game ON moves(game_id);
    CREATE INDEX IF NOT EXISTS idx_friction_game ON friction_analysis(game_id);
    CREATE INDEX IF NOT EXISTS idx_friction_blunder ON friction_analysis(is_blunder);
    CREATE INDEX IF NOT EXISTS idx_friction_gap ON friction_analysis(friction_gap);
    CREATE INDEX IF NOT EXISTS idx_friction_time_pressure ON friction_analysis(time_pressure);
    CREATE INDEX IF NOT EXISTS idx_eval_fen ON evaluations(fen);
    """

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.executescript(self.SCHEMA)
            conn.commit()

    @contextmanager
    def _get_connection(self):
        """Get database connection with context manager."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def insert_game(self, game_record) -> bool:
        """Insert a game record. Returns True if inserted, False if duplicate."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()

                # Insert game
                cursor.execute("""
                    INSERT OR IGNORE INTO games
                    (game_id, white_rating, black_rating, time_control, increment,
                     result, eco, num_moves, date, termination)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    game_record.game_id,
                    game_record.white_rating,
                    game_record.black_rating,
                    f"{game_record.time_control.base_seconds}+{game_record.time_control.increment_seconds}"
                        if game_record.time_control else None,
                    game_record.time_control.increment_seconds if game_record.time_control else 0,
                    game_record.result,
                    game_record.eco,
                    game_record.num_moves,
                    game_record.date,
                    game_record.termination,
                ))

                if cursor.rowcount == 0:
                    return False  # Duplicate

                # Insert moves
                for move in game_record.moves:
                    cursor.execute("""
                        INSERT OR IGNORE INTO moves
                        (game_id, ply, san, uci, fen_before, fen_after,
                         clock_before, clock_after, think_time, is_white)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        game_record.game_id,
                        move.ply,
                        move.san,
                        move.uci,
                        move.fen_before,
                        move.fen_after,
                        move.clock_before,
                        move.clock_after,
                        move.think_time,
                        move.is_white,
                    ))

                conn.commit()
                return True

        except Exception as e:
            logger.error(f"Error inserting game {game_record.game_id}: {e}")
            return False

    def get_evaluation(self, fen: str) -> Optional[Dict]:
        """Get cached evaluation for a FEN position."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM evaluations WHERE fen = ?",
                (fen,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def insert_evaluation(self, fen: str, eval_cp: int, best_move: str,
                          top_moves: List[Dict], depth: int, multipv: int):
        """Cache an evaluation result."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO evaluations
                    (fen, eval_cp, best_move, top_moves_json, depth, multipv)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    fen,
                    eval_cp,
                    best_move,
                    json.dumps(top_moves),
                    depth,
                    multipv,
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error inserting evaluation: {e}")

    def insert_friction_record(self, record: Dict):
        """Insert a friction analysis record."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO friction_analysis
                    (game_id, ply, player_rating, think_time, think_time_normalized,
                     time_remaining, time_pressure, eval_before, eval_after, eval_drop,
                     was_best_move, move_rank, is_blunder, is_mistake, is_inaccuracy,
                     num_alternatives, eval_spread, has_alternatives, expected_friction,
                     actual_friction, friction_gap, friction_level, game_phase,
                     num_legal_moves, complexity_score)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    record['game_id'],
                    record['ply'],
                    record['player_rating'],
                    record['think_time'],
                    record['think_time_normalized'],
                    record['time_remaining'],
                    record['time_pressure'],
                    record['eval_before'],
                    record['eval_after'],
                    record['eval_drop'],
                    record['was_best_move'],
                    record['move_rank'],
                    record['is_blunder'],
                    record['is_mistake'],
                    record['is_inaccuracy'],
                    record['num_alternatives'],
                    record['eval_spread'],
                    record['has_alternatives'],
                    record['expected_friction'],
                    record['actual_friction'],
                    record['friction_gap'],
                    record['friction_level'],
                    record['game_phase'],
                    record['num_legal_moves'],
                    record['complexity_score'],
                ))
                conn.commit()
        except Exception as e:
            logger.error(f"Error inserting friction record: {e}")

    def get_moves_for_analysis(self, game_id: str) -> List[Dict]:
        """Get all moves for a game that need analysis."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM moves WHERE game_id = ? ORDER BY ply
            """, (game_id,))
            return [dict(row) for row in cursor.fetchall()]

    def get_game_info(self, game_id: str) -> Optional[Dict]:
        """Get game metadata including ratings."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM games WHERE game_id = ?
            """, (game_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_analyzed_plies(self, game_id: str) -> set:
        """Get set of plies that already have friction analysis."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT ply FROM friction_analysis WHERE game_id = ?
            """, (game_id,))
            return {row[0] for row in cursor.fetchall()}

    def get_games_needing_analysis(self, limit: int = 1000) -> List[str]:
        """Get game IDs that need analysis (none or partial)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # Get games with fewer friction records than expected moves (after skip)
            cursor.execute("""
                SELECT g.game_id, g.num_moves, COUNT(fa.id) as analyzed_count
                FROM games g
                LEFT JOIN friction_analysis fa ON g.game_id = fa.game_id
                GROUP BY g.game_id
                HAVING analyzed_count < (g.num_moves - 16)  -- skip first 8 moves per side
                ORDER BY analyzed_count ASC
                LIMIT ?
            """, (limit,))
            return [row[0] for row in cursor.fetchall()]

    def get_games_without_analysis(self, limit: int = 1000) -> List[str]:
        """Get game IDs that haven't been analyzed yet (legacy, use get_games_needing_analysis)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT g.game_id FROM games g
                LEFT JOIN friction_analysis fa ON g.game_id = fa.game_id
                WHERE fa.game_id IS NULL
                LIMIT ?
            """, (limit,))
            return [row[0] for row in cursor.fetchall()]

    def get_friction_data(self, filters: Optional[Dict] = None) -> Iterator[Dict]:
        """Get friction analysis data with optional filters."""
        query = "SELECT * FROM friction_analysis"
        params = []

        if filters:
            conditions = []
            if 'time_pressure' in filters:
                conditions.append("time_pressure = ?")
                params.append(filters['time_pressure'])
            if 'is_blunder' in filters:
                conditions.append("is_blunder = ?")
                params.append(filters['is_blunder'])
            if 'min_rating' in filters:
                conditions.append("player_rating >= ?")
                params.append(filters['min_rating'])
            if 'max_rating' in filters:
                conditions.append("player_rating <= ?")
                params.append(filters['max_rating'])

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            for row in cursor:
                yield dict(row)

    def get_stats(self) -> Dict:
        """Get database statistics."""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) FROM games")
            num_games = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM moves")
            num_moves = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM evaluations")
            num_evals = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM friction_analysis")
            num_friction = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM friction_analysis WHERE is_blunder = 1")
            num_blunders = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM friction_analysis WHERE friction_gap = 1")
            num_friction_gaps = cursor.fetchone()[0]

            return {
                'games': num_games,
                'moves': num_moves,
                'evaluations_cached': num_evals,
                'friction_records': num_friction,
                'blunders': num_blunders,
                'friction_gaps': num_friction_gaps,
            }

    def export_to_csv(self, output_path: str | Path, table: str = 'friction_analysis'):
        """Export table to CSV."""
        import csv

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(f"SELECT * FROM {table}")

            with open(output_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([desc[0] for desc in cursor.description])
                writer.writerows(cursor.fetchall())
