"""
Stockfish Evaluation Module - Chess engine integration for position analysis.

Uses python-chess UCI interface to get multi-PV evaluations.
Optimized to avoid redundant evaluations.
"""

import logging
from dataclasses import dataclass
from typing import List, Dict, Optional, Tuple
from pathlib import Path

import chess
import chess.engine

logger = logging.getLogger(__name__)


@dataclass
class EvalRecord:
    """Evaluation data for a position."""
    fen: str
    eval_cp: int  # centipawns, from side-to-move perspective
    best_move: str
    top_moves: List[Dict]  # [{move: str, eval: int}, ...]
    depth: int
    multipv: int

    def get_move_eval(self, move: str) -> Optional[int]:
        """Get evaluation for a specific move if in top moves."""
        for m in self.top_moves:
            if m['move'] == move:
                return m['eval']
        return None

    def get_move_rank(self, move: str) -> int:
        """Get rank of a move (1 = best, 2 = second best, etc.)."""
        for i, m in enumerate(self.top_moves):
            if m['move'] == move:
                return i + 1
        return len(self.top_moves) + 1  # Not in top moves

    def calculate_eval_drop(self, move: str) -> float:
        """
        Calculate eval drop for a move using multi-PV data.

        Returns the difference between best eval and played move eval.
        Positive = mistake, negative = found better than engine expected.
        """
        if not self.top_moves:
            return 0.0

        best_eval = self.top_moves[0]['eval']
        move_eval = self.get_move_eval(move)

        if move_eval is not None:
            # Move is in top moves, use its eval directly
            return best_eval - move_eval
        else:
            # Move not in top moves - it's likely worse than the worst top move
            # Estimate: use worst top move eval as upper bound
            worst_top_eval = self.top_moves[-1]['eval']
            # Conservative estimate: at least as bad as worst top move
            return best_eval - worst_top_eval + 50  # Add penalty for being outside top moves


class StockfishEvaluator:
    """Stockfish engine wrapper for position evaluation."""

    def __init__(self, config: dict):
        self.config = config
        engine_config = config.get('engine', {})

        self.engine_path = engine_config.get('path', '/usr/games/stockfish')
        self.depth = engine_config.get('depth', 14)  # Reduced from 20
        self.multipv = engine_config.get('multipv', 5)
        self.threads = engine_config.get('threads', 4)
        self.hash_mb = engine_config.get('hash_mb', 1024)  # Reduced from 2048

        self.engine: Optional[chess.engine.SimpleEngine] = None
        self._eval_cache: Dict[str, EvalRecord] = {}

    def start(self):
        """Start the engine process."""
        if self.engine is not None:
            return

        try:
            self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
            self.engine.configure({
                'Threads': self.threads,
                'Hash': self.hash_mb,
            })
            logger.info(f"Started Stockfish at {self.engine_path} (depth={self.depth}, multipv={self.multipv})")
        except Exception as e:
            logger.error(f"Failed to start engine: {e}")
            raise

    def stop(self):
        """Stop the engine process."""
        if self.engine is not None:
            self.engine.quit()
            self.engine = None
            logger.info("Stopped Stockfish engine")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
        return False

    def evaluate(self, fen: str, use_cache: bool = True) -> EvalRecord:
        """
        Evaluate a position and return multi-PV analysis.

        Args:
            fen: Position in FEN notation
            use_cache: Whether to use cached evaluations

        Returns:
            EvalRecord with evaluation data
        """
        # Normalize FEN for cache (remove move counters for better hit rate)
        cache_key = self._normalize_fen(fen)

        # Check cache
        if use_cache and cache_key in self._eval_cache:
            return self._eval_cache[cache_key]

        if self.engine is None:
            self.start()

        board = chess.Board(fen)

        # Get multi-PV analysis
        result = self.engine.analyse(
            board,
            chess.engine.Limit(depth=self.depth),
            multipv=self.multipv,
        )

        # Parse results
        top_moves = []
        best_move = None
        best_eval = 0

        for i, info in enumerate(result):
            if 'pv' not in info or not info['pv']:
                continue

            move = info['pv'][0]
            move_uci = move.uci()

            # Extract evaluation
            score = info.get('score')
            if score is None:
                continue

            # Convert to centipawns (from side-to-move perspective)
            pov_score = score.relative
            if pov_score.is_mate():
                # Convert mate to large centipawn value
                mate_in = pov_score.mate()
                eval_cp = 30000 - abs(mate_in) * 100 if mate_in > 0 else -30000 + abs(mate_in) * 100
            else:
                eval_cp = pov_score.score()

            top_moves.append({
                'move': move_uci,
                'eval': eval_cp,
                'depth': info.get('depth', self.depth),
            })

            if i == 0:
                best_move = move_uci
                best_eval = eval_cp

        record = EvalRecord(
            fen=fen,
            eval_cp=best_eval,
            best_move=best_move or '',
            top_moves=top_moves,
            depth=self.depth,
            multipv=self.multipv,
        )

        # Cache result
        if use_cache:
            self._eval_cache[cache_key] = record

        return record

    def _normalize_fen(self, fen: str) -> str:
        """
        Normalize FEN for caching.
        Keep position, side to move, castling, en passant.
        Remove halfmove and fullmove counters (they don't affect eval).
        """
        parts = fen.split()
        if len(parts) >= 4:
            return ' '.join(parts[:4])
        return fen

    def analyze_move(self, fen_before: str, move_uci: str) -> Dict:
        """
        Analyze a single move efficiently using only pre-move evaluation.

        Args:
            fen_before: Position before move
            move_uci: Move in UCI notation

        Returns:
            Dict with eval_before, eval_drop, move_rank, best_move, top_moves, was_best
        """
        eval_record = self.evaluate(fen_before)

        return {
            'eval_before': eval_record.eval_cp,
            'eval_drop': eval_record.calculate_eval_drop(move_uci),
            'move_rank': eval_record.get_move_rank(move_uci),
            'best_move': eval_record.best_move,
            'top_moves': eval_record.top_moves,
            'was_best': move_uci == eval_record.best_move,
            'num_alternatives': sum(
                1 for m in eval_record.top_moves[1:]
                if abs(eval_record.top_moves[0]['eval'] - m['eval']) <= 50
            ),
            'eval_spread': (
                eval_record.top_moves[0]['eval'] - eval_record.top_moves[-1]['eval']
                if eval_record.top_moves else 0
            ),
        }

    def get_cache_stats(self) -> Dict:
        """Get cache statistics."""
        return {
            'cached_positions': len(self._eval_cache),
        }

    def clear_cache(self):
        """Clear the evaluation cache."""
        self._eval_cache.clear()
