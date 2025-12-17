"""
PGN Parser Module - Streaming parser with clock extraction.

Handles Lichess PGN format with clock annotations: {[%clk 0:05:23]}
"""

import re
import io
import logging
from dataclasses import dataclass, field
from typing import Iterator, Optional, List, TextIO
from pathlib import Path

import chess
import chess.pgn

try:
    import zstandard as zstd
    HAS_ZSTD = True
except ImportError:
    HAS_ZSTD = False

logger = logging.getLogger(__name__)


@dataclass
class TimeControl:
    """Parsed time control (base + increment)."""
    base_seconds: int
    increment_seconds: int

    @classmethod
    def from_string(cls, tc_string: str) -> Optional['TimeControl']:
        """Parse time control string like '600+5' or '300'."""
        if not tc_string or tc_string == '-':
            return None

        match = re.match(r'(\d+)\+?(\d+)?', tc_string)
        if not match:
            return None

        base = int(match.group(1))
        increment = int(match.group(2)) if match.group(2) else 0
        return cls(base_seconds=base, increment_seconds=increment)

    @property
    def total_base(self) -> int:
        """Total base time in seconds."""
        return self.base_seconds

    def is_classical_or_rapid(self, min_base: int = 600) -> bool:
        """Check if time control is at least rapid (10+0)."""
        return self.base_seconds >= min_base


@dataclass
class MoveRecord:
    """Record for a single move with timing data."""
    ply: int  # half-move number (1 = first white move)
    san: str  # Standard Algebraic Notation
    uci: str  # UCI notation
    fen_before: str  # position before move
    fen_after: str  # position after move
    clock_after: Optional[float] = None  # seconds remaining after move
    clock_before: Optional[float] = None  # seconds remaining before move (derived)
    think_time: Optional[float] = None  # time spent on move
    is_white: bool = True


@dataclass
class GameRecord:
    """Complete game record with all moves and metadata."""
    game_id: str
    white_rating: Optional[int] = None
    black_rating: Optional[int] = None
    time_control: Optional[TimeControl] = None
    result: str = "*"
    eco: str = ""
    date: str = ""
    moves: List[MoveRecord] = field(default_factory=list)
    white_title: str = ""
    black_title: str = ""
    termination: str = ""

    @property
    def num_moves(self) -> int:
        """Number of half-moves (plies)."""
        return len(self.moves)

    @property
    def num_full_moves(self) -> int:
        """Number of full moves."""
        return (len(self.moves) + 1) // 2

    def has_valid_clocks(self) -> bool:
        """Check if game has clock data for most moves."""
        if not self.moves:
            return False
        clock_count = sum(1 for m in self.moves if m.clock_after is not None)
        return clock_count >= len(self.moves) * 0.9  # 90% threshold


class PGNParser:
    """Streaming PGN parser with clock extraction."""

    # Regex for clock annotation: {[%clk H:MM:SS]} or {[%clk M:SS.s]}
    CLOCK_PATTERN = re.compile(r'\[%clk\s+(\d+):(\d+):(\d+(?:\.\d+)?)\]')

    def __init__(self, config: dict):
        self.config = config
        self.filters = config.get('filters', {})
        self.min_rating = self.filters.get('min_rating', 1000)
        self.max_rating = self.filters.get('max_rating', 2500)
        self.min_time_control = self.filters.get('min_time_control', 600)
        self.require_clocks = self.filters.get('require_clocks', True)
        self.min_moves = self.filters.get('min_moves', 20)

        self.games_parsed = 0
        self.games_accepted = 0
        self.games_rejected = 0

    def parse_file(self, filepath: str | Path) -> Iterator[GameRecord]:
        """Parse PGN file (optionally zstd compressed) and yield GameRecords."""
        filepath = Path(filepath)

        if filepath.suffix == '.zst':
            if not HAS_ZSTD:
                raise ImportError("zstandard library required for .zst files")
            yield from self._parse_zstd(filepath)
        else:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                yield from self._parse_stream(f)

    def _parse_zstd(self, filepath: Path) -> Iterator[GameRecord]:
        """Parse zstd-compressed PGN file."""
        dctx = zstd.ZstdDecompressor()
        with open(filepath, 'rb') as fh:
            with dctx.stream_reader(fh) as reader:
                text_stream = io.TextIOWrapper(reader, encoding='utf-8', errors='replace')
                yield from self._parse_stream(text_stream)

    def _parse_stream(self, stream: TextIO) -> Iterator[GameRecord]:
        """Parse PGN stream and yield filtered GameRecords."""
        while True:
            try:
                game = chess.pgn.read_game(stream)
                if game is None:
                    break

                self.games_parsed += 1

                record = self._process_game(game)
                if record and self._passes_filters(record):
                    self.games_accepted += 1
                    yield record
                else:
                    self.games_rejected += 1

            except Exception as e:
                logger.warning(f"Error parsing game: {e}")
                self.games_rejected += 1
                continue

    def _process_game(self, game: chess.pgn.Game) -> Optional[GameRecord]:
        """Convert chess.pgn.Game to GameRecord with clock extraction."""
        headers = game.headers

        # Extract game ID from Site header (Lichess format)
        site = headers.get('Site', '')
        game_id = site.split('/')[-1] if 'lichess.org' in site else headers.get('Event', 'unknown')

        # Parse ratings
        try:
            white_rating = int(headers.get('WhiteElo', 0)) or None
            black_rating = int(headers.get('BlackElo', 0)) or None
        except (ValueError, TypeError):
            white_rating = black_rating = None

        # Parse time control
        time_control = TimeControl.from_string(headers.get('TimeControl', ''))

        record = GameRecord(
            game_id=game_id,
            white_rating=white_rating,
            black_rating=black_rating,
            time_control=time_control,
            result=headers.get('Result', '*'),
            eco=headers.get('ECO', ''),
            date=headers.get('UTCDate', headers.get('Date', '')),
            termination=headers.get('Termination', ''),
        )

        # Process moves
        board = game.board()
        node = game
        ply = 0

        prev_clock_white = time_control.base_seconds if time_control else None
        prev_clock_black = time_control.base_seconds if time_control else None

        while node.variations:
            next_node = node.variation(0)
            move = next_node.move
            ply += 1
            is_white = (ply % 2 == 1)

            # Get FEN before move
            fen_before = board.fen()

            # Extract clock from comment
            clock_after = self._extract_clock(next_node.comment)

            # Calculate think time
            think_time = None
            clock_before = None

            if clock_after is not None:
                if is_white:
                    clock_before = prev_clock_white
                    if clock_before is not None:
                        # Account for increment
                        increment = time_control.increment_seconds if time_control else 0
                        think_time = clock_before - clock_after + increment
                        if think_time < 0:
                            think_time = 0  # Can happen with increment
                    prev_clock_white = clock_after
                else:
                    clock_before = prev_clock_black
                    if clock_before is not None:
                        increment = time_control.increment_seconds if time_control else 0
                        think_time = clock_before - clock_after + increment
                        if think_time < 0:
                            think_time = 0
                    prev_clock_black = clock_after

            # Create move record
            move_record = MoveRecord(
                ply=ply,
                san=board.san(move),
                uci=move.uci(),
                fen_before=fen_before,
                fen_after=None,  # Will set after making move
                clock_after=clock_after,
                clock_before=clock_before,
                think_time=think_time,
                is_white=is_white,
            )

            # Make move on board
            board.push(move)
            move_record.fen_after = board.fen()

            record.moves.append(move_record)
            node = next_node

        return record

    def _extract_clock(self, comment: str) -> Optional[float]:
        """Extract clock time in seconds from comment string."""
        if not comment:
            return None

        match = self.CLOCK_PATTERN.search(comment)
        if not match:
            return None

        hours = int(match.group(1))
        minutes = int(match.group(2))
        seconds = float(match.group(3))

        return hours * 3600 + minutes * 60 + seconds

    def _passes_filters(self, record: GameRecord) -> bool:
        """Check if game passes all configured filters."""
        # Time control filter
        if record.time_control is None:
            return False
        if not record.time_control.is_classical_or_rapid(self.min_time_control):
            return False

        # Rating filter
        if record.white_rating is None or record.black_rating is None:
            return False
        if not (self.min_rating <= record.white_rating <= self.max_rating):
            return False
        if not (self.min_rating <= record.black_rating <= self.max_rating):
            return False

        # Clock data filter
        if self.require_clocks and not record.has_valid_clocks():
            return False

        # Minimum moves filter
        if record.num_full_moves < self.min_moves:
            return False

        # Result filter (no abandons)
        if record.result not in ('1-0', '0-1', '1/2-1/2'):
            return False

        # Termination filter (exclude abandoned games)
        if 'abandon' in record.termination.lower():
            return False

        return True

    def get_stats(self) -> dict:
        """Return parsing statistics."""
        return {
            'games_parsed': self.games_parsed,
            'games_accepted': self.games_accepted,
            'games_rejected': self.games_rejected,
            'acceptance_rate': self.games_accepted / max(1, self.games_parsed),
        }
