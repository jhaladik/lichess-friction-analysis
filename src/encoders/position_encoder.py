"""
Position Encoder Module - Extract features from chess positions.

Provides position complexity metrics and game phase detection.
"""

from dataclasses import dataclass
from typing import Tuple, List, Optional

import chess


@dataclass
class PositionFeatures:
    """Feature vector for a chess position."""
    # Material
    material_balance: int  # centipawns (positive = white advantage)
    total_material: int  # total material on board (excluding kings)

    # Mobility
    mobility_white: int  # legal moves for white
    mobility_black: int  # legal moves for black

    # Complexity proxies
    num_legal_moves: int  # current side to move
    num_captures: int  # available captures
    num_checks: int  # available checking moves
    num_pieces: int  # total pieces on board

    # Game phase (0.0 = endgame, 1.0 = opening)
    game_phase: float

    # Position type indicators
    is_check: bool
    has_castling_rights: bool
    moves_since_pawn_or_capture: int  # for 50-move rule proximity

    # Tactical indicators
    has_hanging_pieces: bool
    pawn_structure_tension: int  # pawns that can capture each other


class PositionEncoder:
    """Encodes chess positions into feature vectors."""

    # Piece values in centipawns for material calculation
    PIECE_VALUES = {
        chess.PAWN: 100,
        chess.KNIGHT: 320,
        chess.BISHOP: 330,
        chess.ROOK: 500,
        chess.QUEEN: 900,
        chess.KING: 0,
    }

    # Phase weights for game phase calculation
    PHASE_WEIGHTS = {
        chess.KNIGHT: 1,
        chess.BISHOP: 1,
        chess.ROOK: 2,
        chess.QUEEN: 4,
    }
    MAX_PHASE = 24  # 2*(2*1 + 2*1 + 2*2 + 1*4) = 24

    def __init__(self):
        pass

    def encode(self, board: chess.Board) -> PositionFeatures:
        """Extract features from a chess position."""
        # Material calculation
        material_white = self._calculate_material(board, chess.WHITE)
        material_black = self._calculate_material(board, chess.BLACK)
        material_balance = material_white - material_black
        total_material = material_white + material_black

        # Mobility (legal moves from each side's perspective)
        mobility_current = board.legal_moves.count()

        # Get mobility for opponent
        board_copy = board.copy()
        board_copy.turn = not board.turn
        # This is a simplification - doesn't account for check status change
        mobility_opponent = len(list(board_copy.pseudo_legal_moves))

        if board.turn == chess.WHITE:
            mobility_white = mobility_current
            mobility_black = mobility_opponent
        else:
            mobility_white = mobility_opponent
            mobility_black = mobility_current

        # Complexity metrics
        legal_moves = list(board.legal_moves)
        num_captures = sum(1 for m in legal_moves if board.is_capture(m))
        num_checks = sum(1 for m in legal_moves if self._gives_check(board, m))

        # Piece count
        num_pieces = len(board.piece_map())

        # Game phase
        game_phase = self._calculate_game_phase(board)

        # Position indicators
        is_check = board.is_check()
        has_castling_rights = bool(board.castling_rights)
        moves_since_pawn_or_capture = board.halfmove_clock

        # Tactical indicators
        has_hanging = self._has_hanging_pieces(board)
        pawn_tension = self._calculate_pawn_tension(board)

        return PositionFeatures(
            material_balance=material_balance,
            total_material=total_material,
            mobility_white=mobility_white,
            mobility_black=mobility_black,
            num_legal_moves=mobility_current,
            num_captures=num_captures,
            num_checks=num_checks,
            num_pieces=num_pieces,
            game_phase=game_phase,
            is_check=is_check,
            has_castling_rights=has_castling_rights,
            moves_since_pawn_or_capture=moves_since_pawn_or_capture,
            has_hanging_pieces=has_hanging,
            pawn_structure_tension=pawn_tension,
        )

    def encode_from_fen(self, fen: str) -> PositionFeatures:
        """Extract features from FEN string."""
        board = chess.Board(fen)
        return self.encode(board)

    def _calculate_material(self, board: chess.Board, color: chess.Color) -> int:
        """Calculate total material for one side in centipawns."""
        total = 0
        for piece_type in self.PIECE_VALUES:
            count = len(board.pieces(piece_type, color))
            total += count * self.PIECE_VALUES[piece_type]
        return total

    def _calculate_game_phase(self, board: chess.Board) -> float:
        """
        Calculate game phase from 0.0 (endgame) to 1.0 (opening).
        Based on remaining minor/major pieces.
        """
        phase = 0
        for piece_type, weight in self.PHASE_WEIGHTS.items():
            white_count = len(board.pieces(piece_type, chess.WHITE))
            black_count = len(board.pieces(piece_type, chess.BLACK))
            phase += (white_count + black_count) * weight

        return phase / self.MAX_PHASE

    def _gives_check(self, board: chess.Board, move: chess.Move) -> bool:
        """Check if a move gives check."""
        board.push(move)
        is_check = board.is_check()
        board.pop()
        return is_check

    def _has_hanging_pieces(self, board: chess.Board) -> bool:
        """
        Quick check for hanging pieces (pieces attacked but not defended).
        Simplified heuristic.
        """
        for square, piece in board.piece_map().items():
            if piece.piece_type == chess.KING:
                continue

            attackers = board.attackers(not piece.color, square)
            if attackers:
                defenders = board.attackers(piece.color, square)
                if not defenders:
                    return True

                # Check if least valuable attacker < piece value
                min_attacker_value = min(
                    self.PIECE_VALUES.get(board.piece_at(sq).piece_type, 0)
                    for sq in attackers
                )
                piece_value = self.PIECE_VALUES.get(piece.piece_type, 0)
                if min_attacker_value < piece_value:
                    return True

        return False

    def _calculate_pawn_tension(self, board: chess.Board) -> int:
        """
        Count pawn pairs that can capture each other.
        High tension = more tactical complexity.
        """
        tension = 0
        white_pawns = board.pieces(chess.PAWN, chess.WHITE)
        black_pawns = board.pieces(chess.PAWN, chess.BLACK)

        for wp in white_pawns:
            wp_file = chess.square_file(wp)
            wp_rank = chess.square_rank(wp)

            # Check for black pawns that white can capture
            for target_rank in [wp_rank + 1]:  # Pawns capture diagonally forward
                if target_rank > 7:
                    continue
                for target_file in [wp_file - 1, wp_file + 1]:
                    if 0 <= target_file <= 7:
                        target_square = chess.square(target_file, target_rank)
                        if target_square in black_pawns:
                            tension += 1

        return tension

    def get_complexity_score(self, features: PositionFeatures) -> float:
        """
        Calculate overall complexity score (0-1).
        Higher = more complex position.
        """
        # Normalize components
        mobility_norm = min(features.num_legal_moves / 40, 1.0)
        captures_norm = min(features.num_captures / 10, 1.0)
        checks_norm = min(features.num_checks / 3, 1.0)
        tension_norm = min(features.pawn_structure_tension / 4, 1.0)

        # Weighted combination
        complexity = (
            0.4 * mobility_norm +
            0.3 * captures_norm +
            0.2 * checks_norm +
            0.1 * tension_norm
        )

        # Adjust for game phase (middlegame is most complex)
        phase_multiplier = 1.0 - abs(features.game_phase - 0.6) * 0.5

        return complexity * phase_multiplier
