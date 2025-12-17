"""
Friction Metrics Module - Calculate friction indicators from move data.

Core hypothesis: Blunders correlate with friction absence—situations where
the player should have experienced elevated thinking time but didn't.
"""

from dataclasses import dataclass
from typing import Optional, List, Dict, Any
from enum import Enum
import statistics


class FrictionLevel(Enum):
    """Classification of friction intensity."""
    HIGH = "high"      # think_time_normalized > 1.5
    NORMAL = "normal"  # 0.7 < think_time_normalized < 1.5
    LOW = "low"        # think_time_normalized < 0.7


@dataclass
class FrictionRecord:
    """Complete friction analysis for a single move."""
    # Identifiers
    game_id: str
    ply: int
    player_rating: int

    # Time metrics
    think_time: float
    think_time_normalized: float
    time_remaining: float
    time_pressure: bool

    # Evaluation metrics
    eval_before: int
    eval_after: int
    eval_drop: float
    was_best_move: bool
    move_rank: int

    # Classification
    is_blunder: bool
    is_mistake: bool
    is_inaccuracy: bool

    # Optionality metrics (from engine)
    num_alternatives: int
    eval_spread: float  # diff between best and 5th best move
    has_alternatives: bool

    # Friction metrics
    expected_friction: bool  # position has alternatives
    actual_friction: bool    # player showed friction (high think time)
    friction_gap: bool       # expected but not actual
    friction_level: FrictionLevel

    # Position context
    game_phase: float
    num_legal_moves: int
    complexity_score: float

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for database storage."""
        return {
            'game_id': self.game_id,
            'ply': self.ply,
            'player_rating': self.player_rating,
            'think_time': self.think_time,
            'think_time_normalized': self.think_time_normalized,
            'time_remaining': self.time_remaining,
            'time_pressure': self.time_pressure,
            'eval_before': self.eval_before,
            'eval_after': self.eval_after,
            'eval_drop': self.eval_drop,
            'was_best_move': self.was_best_move,
            'move_rank': self.move_rank,
            'is_blunder': self.is_blunder,
            'is_mistake': self.is_mistake,
            'is_inaccuracy': self.is_inaccuracy,
            'num_alternatives': self.num_alternatives,
            'eval_spread': self.eval_spread,
            'has_alternatives': self.has_alternatives,
            'expected_friction': self.expected_friction,
            'actual_friction': self.actual_friction,
            'friction_gap': self.friction_gap,
            'friction_level': self.friction_level.value,
            'game_phase': self.game_phase,
            'num_legal_moves': self.num_legal_moves,
            'complexity_score': self.complexity_score,
        }


class FrictionAnalyzer:
    """Analyzes moves for friction indicators."""

    def __init__(self, config: dict):
        self.config = config
        thresholds = config.get('thresholds', {})

        # Error thresholds (centipawns)
        self.blunder_cp = thresholds.get('blunder_cp', 100)
        self.mistake_cp = thresholds.get('mistake_cp', 50)
        self.inaccuracy_cp = thresholds.get('inaccuracy_cp', 25)

        # Time thresholds
        self.time_pressure_seconds = thresholds.get('time_pressure_seconds', 30)
        self.high_friction_multiplier = thresholds.get('high_friction_multiplier', 1.5)
        self.low_friction_multiplier = thresholds.get('low_friction_multiplier', 0.7)
        self.premove_threshold = thresholds.get('premove_threshold', 0.5)

        # Optionality threshold
        self.alternative_threshold_cp = thresholds.get('alternative_threshold_cp', 50)

    def calculate_normalized_think_time(
        self,
        think_times: List[float],
        current_think_time: float,
        exclude_premoves: bool = True
    ) -> float:
        """
        Calculate normalized think time relative to player's average in this game.

        Args:
            think_times: All think times for this player in the game
            current_think_time: Think time for the move being analyzed
            exclude_premoves: Whether to exclude very fast moves from baseline

        Returns:
            Normalized think time (1.0 = average, >1 = slower, <1 = faster)
        """
        if not think_times:
            return 1.0

        # Filter valid think times
        valid_times = [t for t in think_times if t is not None and t >= 0]

        if exclude_premoves:
            valid_times = [t for t in valid_times if t > self.premove_threshold]

        if not valid_times:
            return 1.0

        avg_think_time = statistics.mean(valid_times)

        if avg_think_time == 0:
            return 1.0

        return current_think_time / avg_think_time

    def classify_friction_level(self, think_time_normalized: float) -> FrictionLevel:
        """Classify friction level based on normalized think time."""
        if think_time_normalized > self.high_friction_multiplier:
            return FrictionLevel.HIGH
        elif think_time_normalized < self.low_friction_multiplier:
            return FrictionLevel.LOW
        else:
            return FrictionLevel.NORMAL

    def has_alternatives(self, top_moves: List[Dict]) -> tuple[bool, int, float]:
        """
        Determine if position has meaningful alternatives.

        Args:
            top_moves: List of {move: str, eval: int} from engine multi-PV

        Returns:
            (has_alternatives, num_alternatives, eval_spread)
        """
        if not top_moves or len(top_moves) < 2:
            return False, 0, 0.0

        best_eval = top_moves[0].get('eval', 0)
        alternatives = 0

        for move_data in top_moves[1:]:
            move_eval = move_data.get('eval', 0)
            if abs(best_eval - move_eval) <= self.alternative_threshold_cp:
                alternatives += 1

        # Eval spread is difference between best and worst in top moves
        worst_eval = top_moves[-1].get('eval', 0)
        eval_spread = abs(best_eval - worst_eval)

        return alternatives > 0, alternatives, eval_spread

    def analyze_move(
        self,
        game_id: str,
        ply: int,
        player_rating: int,
        think_time: float,
        think_times_in_game: List[float],
        time_remaining: float,
        eval_before: int,
        eval_after: int,
        best_move: str,
        move_played: str,
        top_moves: List[Dict],
        position_features: 'PositionFeatures',
    ) -> FrictionRecord:
        """
        Perform complete friction analysis for a single move.

        Args:
            game_id: Unique game identifier
            ply: Half-move number
            player_rating: Player's rating
            think_time: Time spent on this move
            think_times_in_game: All think times for this player in the game
            time_remaining: Clock time remaining after move
            eval_before: Position evaluation before move (centipawns)
            eval_after: Position evaluation after move (centipawns)
            best_move: Engine's best move (UCI)
            move_played: Move actually played (UCI)
            top_moves: Engine's top moves with evaluations
            position_features: Encoded position features

        Returns:
            Complete FrictionRecord
        """
        # Time analysis
        think_time_normalized = self.calculate_normalized_think_time(
            think_times_in_game, think_time
        )
        time_pressure = time_remaining < self.time_pressure_seconds
        friction_level = self.classify_friction_level(think_time_normalized)

        # Evaluation analysis
        # Note: eval_drop should be from the perspective of the player who moved
        eval_drop = eval_before - eval_after  # Positive = mistake

        # Move quality classification
        is_blunder = eval_drop >= self.blunder_cp
        is_mistake = self.mistake_cp <= eval_drop < self.blunder_cp
        is_inaccuracy = self.inaccuracy_cp <= eval_drop < self.mistake_cp

        # Was it the best move?
        was_best_move = (move_played == best_move)

        # Move rank (1 = best, 2 = second best, etc.)
        move_rank = self._get_move_rank(move_played, top_moves)

        # Optionality analysis
        has_alts, num_alts, eval_spread = self.has_alternatives(top_moves)

        # Friction gap detection
        # Expected friction: position has alternatives (player should think)
        expected_friction = has_alts

        # Actual friction: player showed elevated thinking time
        actual_friction = think_time_normalized > 1.0

        # Friction gap: expected friction but didn't show it
        friction_gap = expected_friction and not actual_friction

        return FrictionRecord(
            game_id=game_id,
            ply=ply,
            player_rating=player_rating,
            think_time=think_time,
            think_time_normalized=think_time_normalized,
            time_remaining=time_remaining,
            time_pressure=time_pressure,
            eval_before=eval_before,
            eval_after=eval_after,
            eval_drop=eval_drop,
            was_best_move=was_best_move,
            move_rank=move_rank,
            is_blunder=is_blunder,
            is_mistake=is_mistake,
            is_inaccuracy=is_inaccuracy,
            num_alternatives=num_alts,
            eval_spread=eval_spread,
            has_alternatives=has_alts,
            expected_friction=expected_friction,
            actual_friction=actual_friction,
            friction_gap=friction_gap,
            friction_level=friction_level,
            game_phase=position_features.game_phase,
            num_legal_moves=position_features.num_legal_moves,
            complexity_score=0.0,  # Will be set by encoder
        )

    def _get_move_rank(self, move: str, top_moves: List[Dict]) -> int:
        """Get the rank of the played move in engine's top moves."""
        for i, move_data in enumerate(top_moves):
            if move_data.get('move') == move:
                return i + 1
        return len(top_moves) + 1  # Not in top moves

    def get_player_think_times(self, moves: List[Dict], is_white: bool) -> List[float]:
        """Extract think times for one player from a list of moves."""
        return [
            m['think_time']
            for m in moves
            if m.get('is_white') == is_white and m.get('think_time') is not None
        ]
