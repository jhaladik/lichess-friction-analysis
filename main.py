#!/usr/bin/env python3
"""
Lichess Friction Analysis - Main Pipeline

Validates the hypothesis that blunders correlate with friction absence:
situations where the player should have experienced elevated thinking time
but didn't.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

import yaml
import pandas as pd
from tqdm import tqdm

from src.parsers import PGNParser, GameRecord
from src.encoders import PositionEncoder
from src.engine import StockfishEvaluator
from src.friction import FrictionAnalyzer
from src.analysis import StatisticalAnalyzer
from src.database import Database

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> dict:
    """Load configuration from YAML file."""
    with open(config_path, 'r') as f:
        return yaml.safe_load(f)


def run_phase1_parse(config: dict, pgn_path: str, limit: Optional[int] = None):
    """
    Phase 1: Parse PGN and store games in database.

    This can run without Stockfish - just extracts games and clock data.
    """
    logger.info("=== Phase 1: PGN Parsing ===")

    db_path = config['data']['database_path']
    db = Database(db_path)

    parser = PGNParser(config)
    pgn_path = Path(pgn_path)

    if not pgn_path.exists():
        logger.error(f"PGN file not found: {pgn_path}")
        return

    logger.info(f"Parsing {pgn_path}...")

    games_stored = 0
    sample_size = limit or config['data'].get('sample_size')

    try:
        for game in tqdm(parser.parse_file(pgn_path), desc="Parsing games"):
            if db.insert_game(game):
                games_stored += 1

            if sample_size and games_stored >= sample_size:
                logger.info(f"Reached sample size limit: {sample_size}")
                break

    except KeyboardInterrupt:
        logger.info("Interrupted by user")

    stats = parser.get_stats()
    logger.info(f"Parsing complete:")
    logger.info(f"  - Games parsed: {stats['games_parsed']}")
    logger.info(f"  - Games accepted: {stats['games_accepted']}")
    logger.info(f"  - Games stored: {games_stored}")
    logger.info(f"  - Acceptance rate: {stats['acceptance_rate']:.2%}")


def run_phase2_evaluate(config: dict, limit: Optional[int] = None):
    """
    Phase 2: Evaluate positions with Stockfish.

    This is the slow part - requires engine evaluation.
    """
    logger.info("=== Phase 2: Engine Evaluation ===")

    db_path = config['data']['database_path']
    db = Database(db_path)

    # Get games that need evaluation
    game_ids = db.get_games_without_analysis(limit or 10000)
    logger.info(f"Found {len(game_ids)} games to analyze")

    if not game_ids:
        logger.info("No games to analyze")
        return

    encoder = PositionEncoder()
    friction_analyzer = FrictionAnalyzer(config)

    with StockfishEvaluator(config) as evaluator:
        for game_id in tqdm(game_ids, desc="Analyzing games"):
            try:
                analyze_game(
                    db, evaluator, encoder, friction_analyzer,
                    game_id, config
                )
            except Exception as e:
                logger.warning(f"Error analyzing game {game_id}: {e}")
                continue

    logger.info("Evaluation complete")
    logger.info(f"Database stats: {db.get_stats()}")


def analyze_game(
    db: Database,
    evaluator: StockfishEvaluator,
    encoder: PositionEncoder,
    friction_analyzer: FrictionAnalyzer,
    game_id: str,
    config: dict
):
    """Analyze a single game and store friction records."""
    moves = db.get_moves_for_analysis(game_id)
    if not moves:
        return

    # Config
    skip_opening = config.get('engine', {}).get('skip_opening_moves', 8)

    # Separate think times by player
    white_times = friction_analyzer.get_player_think_times(moves, is_white=True)
    black_times = friction_analyzer.get_player_think_times(moves, is_white=False)

    for move in moves:
        ply = move['ply']

        # Skip opening moves (book moves, not interesting for friction analysis)
        if ply <= skip_opening * 2:  # ply is half-moves
            continue

        fen_before = move['fen_before']
        move_uci = move['uci']
        is_white = move['is_white']
        think_time = move['think_time']

        if think_time is None:
            continue

        # Use efficient single-evaluation analysis
        analysis = evaluator.analyze_move(fen_before, move_uci)

        # Cache evaluation in DB for future use
        db.insert_evaluation(
            fen_before,
            analysis['eval_before'],
            analysis['best_move'],
            analysis['top_moves'],
            evaluator.depth,
            evaluator.multipv
        )

        # Encode position features
        position_features = encoder.encode_from_fen(fen_before)

        # Get player rating (TODO: get from game record)
        player_rating = 1500

        # Get player's think times for this game
        player_times = white_times if is_white else black_times

        # Calculate friction metrics
        friction_record = friction_analyzer.analyze_move(
            game_id=game_id,
            ply=ply,
            player_rating=player_rating,
            think_time=think_time,
            think_times_in_game=player_times,
            time_remaining=move['clock_after'] or 0,
            eval_before=analysis['eval_before'],
            eval_after=analysis['eval_before'] - analysis['eval_drop'],  # Derived
            best_move=analysis['best_move'],
            move_played=move_uci,
            top_moves=analysis['top_moves'],
            position_features=position_features,
        )

        # Store friction record
        db.insert_friction_record(friction_record.to_dict())


def run_phase3_analyze(config: dict, output_dir: Optional[str] = None):
    """
    Phase 3: Statistical analysis.

    Generates report and visualizations.
    """
    logger.info("=== Phase 3: Statistical Analysis ===")

    db_path = config['data']['database_path']
    db = Database(db_path)
    output_dir = Path(output_dir or config['data']['output_dir'])
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load friction data
    logger.info("Loading friction data...")
    data = list(db.get_friction_data())

    if not data:
        logger.error("No friction data found. Run phase 2 first.")
        return

    df = pd.DataFrame(data)
    logger.info(f"Loaded {len(df)} friction records")

    # Run statistical analysis
    analyzer = StatisticalAnalyzer(config)
    results = analyzer.analyze(df)

    # Generate report
    report = analyzer.generate_report(results)
    report_path = output_dir / "friction_report.md"
    with open(report_path, 'w') as f:
        f.write(report)
    logger.info(f"Report saved to {report_path}")

    # Export data
    csv_path = output_dir / "friction_data.csv"
    df.to_csv(csv_path, index=False)
    logger.info(f"Data exported to {csv_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("ANALYSIS SUMMARY")
    print("=" * 60)
    print(f"\nTotal moves analyzed: {results.total_moves:,}")
    print(f"Total blunders: {results.total_blunders:,} ({100*results.total_blunders/max(1,results.total_moves):.2f}%)")
    print(f"Total friction gaps: {results.total_friction_gaps:,}")

    if results.correlation_no_time_pressure:
        corr = results.correlation_no_time_pressure
        print(f"\nCore hypothesis (no time pressure):")
        print(f"  Correlation (think time vs blunder): {corr.coefficient:.4f}")
        print(f"  P-value: {corr.p_value:.6f}")
        print(f"  Result: {'SUPPORTED' if corr.coefficient < 0 and corr.is_significant else 'NOT SUPPORTED'}")

    print(f"\nFriction gap analysis:")
    print(f"  Blunder rate WITH friction gap: {100*results.blunder_rate_with_friction_gap:.2f}%")
    print(f"  Blunder rate WITHOUT friction gap: {100*results.blunder_rate_without_friction_gap:.2f}%")
    print(f"  Relative risk: {results.relative_risk:.2f}x")

    print("\n" + "=" * 60)


def run_quick_analysis(config: dict, pgn_path: str, sample: int = 100):
    """
    Quick analysis without engine evaluation.

    Analyzes think time patterns in relation to move number,
    time pressure, etc. Useful for initial data exploration.
    """
    logger.info("=== Quick Analysis (No Engine) ===")

    parser = PGNParser(config)
    pgn_path = Path(pgn_path)

    if not pgn_path.exists():
        logger.error(f"PGN file not found: {pgn_path}")
        return

    all_moves = []
    games_count = 0

    for game in tqdm(parser.parse_file(pgn_path), desc="Parsing", total=sample):
        for move in game.moves:
            if move.think_time is not None:
                all_moves.append({
                    'game_id': game.game_id,
                    'ply': move.ply,
                    'think_time': move.think_time,
                    'clock_after': move.clock_after,
                    'is_white': move.is_white,
                    'rating': game.white_rating if move.is_white else game.black_rating,
                })

        games_count += 1
        if games_count >= sample:
            break

    if not all_moves:
        logger.error("No moves with clock data found")
        return

    df = pd.DataFrame(all_moves)

    print("\n" + "=" * 60)
    print("QUICK ANALYSIS RESULTS")
    print("=" * 60)
    print(f"\nGames analyzed: {games_count}")
    print(f"Moves with clock data: {len(df)}")
    print(f"\nThink time statistics:")
    print(f"  Mean: {df['think_time'].mean():.2f} seconds")
    print(f"  Median: {df['think_time'].median():.2f} seconds")
    print(f"  Std: {df['think_time'].std():.2f} seconds")
    print(f"  Min: {df['think_time'].min():.2f} seconds")
    print(f"  Max: {df['think_time'].max():.2f} seconds")

    # Time pressure analysis
    df['time_pressure'] = df['clock_after'] < 30
    pressure_df = df[df['time_pressure']]
    no_pressure_df = df[~df['time_pressure']]

    print(f"\nTime pressure analysis:")
    print(f"  Moves under time pressure: {len(pressure_df)} ({100*len(pressure_df)/len(df):.1f}%)")
    print(f"  Mean think time (pressure): {pressure_df['think_time'].mean():.2f} sec")
    print(f"  Mean think time (no pressure): {no_pressure_df['think_time'].mean():.2f} sec")

    # Think time by move number
    df['move_number'] = (df['ply'] + 1) // 2
    by_move = df.groupby('move_number')['think_time'].mean()

    print(f"\nThink time by move number (first 20):")
    for move_num in range(1, min(21, len(by_move) + 1)):
        if move_num in by_move.index:
            print(f"  Move {move_num:2d}: {by_move[move_num]:.2f} sec")

    print("\n" + "=" * 60)


def main():
    parser = argparse.ArgumentParser(
        description='Lichess Friction Analysis Pipeline'
    )
    parser.add_argument(
        '--config', '-c',
        default='config.yaml',
        help='Path to config file'
    )

    subparsers = parser.add_subparsers(dest='command', help='Commands')

    # Parse command
    parse_parser = subparsers.add_parser('parse', help='Parse PGN files')
    parse_parser.add_argument('pgn', help='Path to PGN file')
    parse_parser.add_argument('--limit', '-l', type=int, help='Limit number of games')

    # Evaluate command
    eval_parser = subparsers.add_parser('evaluate', help='Evaluate positions with engine')
    eval_parser.add_argument('--limit', '-l', type=int, help='Limit number of games')

    # Analyze command
    analyze_parser = subparsers.add_parser('analyze', help='Run statistical analysis')
    analyze_parser.add_argument('--output', '-o', help='Output directory')

    # Quick command (no engine)
    quick_parser = subparsers.add_parser('quick', help='Quick analysis without engine')
    quick_parser.add_argument('pgn', help='Path to PGN file')
    quick_parser.add_argument('--sample', '-s', type=int, default=100, help='Sample size')

    # Full pipeline
    full_parser = subparsers.add_parser('full', help='Run full pipeline')
    full_parser.add_argument('pgn', help='Path to PGN file')
    full_parser.add_argument('--limit', '-l', type=int, help='Limit number of games')

    # Stats command
    stats_parser = subparsers.add_parser('stats', help='Show database statistics')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    config = load_config(args.config)

    if args.command == 'parse':
        run_phase1_parse(config, args.pgn, args.limit)

    elif args.command == 'evaluate':
        run_phase2_evaluate(config, args.limit)

    elif args.command == 'analyze':
        run_phase3_analyze(config, args.output)

    elif args.command == 'quick':
        run_quick_analysis(config, args.pgn, args.sample)

    elif args.command == 'full':
        run_phase1_parse(config, args.pgn, args.limit)
        run_phase2_evaluate(config, args.limit)
        run_phase3_analyze(config)

    elif args.command == 'stats':
        db = Database(config['data']['database_path'])
        stats = db.get_stats()
        print("\nDatabase Statistics:")
        for key, value in stats.items():
            print(f"  {key}: {value:,}")


if __name__ == '__main__':
    main()
