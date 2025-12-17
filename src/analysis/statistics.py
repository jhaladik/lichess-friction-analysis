"""
Statistical Analysis Module - Hypothesis testing for friction-blunder correlation.

Core hypothesis: Negative correlation between thinking time and blunder probability
in non-time-pressure conditions.
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import stats

try:
    import statsmodels.api as sm
    from statsmodels.stats.contingency_tables import mcnemar
    HAS_STATSMODELS = True
except ImportError:
    HAS_STATSMODELS = False

logger = logging.getLogger(__name__)


@dataclass
class CorrelationResult:
    """Result of correlation analysis."""
    coefficient: float
    p_value: float
    n: int
    method: str

    @property
    def is_significant(self) -> bool:
        return self.p_value < 0.05

    def __str__(self):
        sig = "***" if self.p_value < 0.001 else "**" if self.p_value < 0.01 else "*" if self.p_value < 0.05 else ""
        return f"r={self.coefficient:.4f}, p={self.p_value:.4f}{sig}, n={self.n}"


@dataclass
class TTestResult:
    """Result of t-test."""
    statistic: float
    p_value: float
    mean_group1: float
    mean_group2: float
    std_group1: float
    std_group2: float
    n_group1: int
    n_group2: int
    effect_size: float  # Cohen's d

    @property
    def is_significant(self) -> bool:
        return self.p_value < 0.05


@dataclass
class ChiSquareResult:
    """Result of chi-square test."""
    statistic: float
    p_value: float
    dof: int
    contingency_table: np.ndarray
    expected: np.ndarray

    @property
    def is_significant(self) -> bool:
        return self.p_value < 0.05


@dataclass
class RegressionResult:
    """Result of logistic regression."""
    coefficients: Dict[str, float]
    p_values: Dict[str, float]
    odds_ratios: Dict[str, float]
    pseudo_r2: float
    n: int
    converged: bool


@dataclass
class AnalysisResults:
    """Complete analysis results."""
    # Sample info
    total_moves: int = 0
    total_blunders: int = 0
    total_friction_gaps: int = 0

    # Core hypothesis
    correlation_blunder_thinktime: Optional[CorrelationResult] = None
    correlation_no_time_pressure: Optional[CorrelationResult] = None

    # T-tests
    ttest_blunder_vs_nonblunder: Optional[TTestResult] = None

    # Chi-square
    chi_square_friction_gap: Optional[ChiSquareResult] = None

    # Logistic regression
    logistic_regression: Optional[RegressionResult] = None

    # Segmented analysis
    blunder_rate_by_friction_level: Dict[str, float] = field(default_factory=dict)
    blunder_rate_by_rating_band: Dict[str, float] = field(default_factory=dict)
    blunder_rate_by_game_phase: Dict[str, float] = field(default_factory=dict)

    # Friction gap analysis
    blunder_rate_with_friction_gap: float = 0.0
    blunder_rate_without_friction_gap: float = 0.0
    relative_risk: float = 0.0


class StatisticalAnalyzer:
    """Performs statistical analysis on friction data."""

    def __init__(self, config: dict):
        self.config = config
        self.significance_level = config.get('analysis', {}).get('significance_level', 0.05)
        self.rating_bands = config.get('analysis', {}).get(
            'rating_bands', [1000, 1200, 1400, 1600, 1800, 2000, 2200, 2500]
        )

    def analyze(self, df: pd.DataFrame) -> AnalysisResults:
        """
        Perform complete statistical analysis.

        Args:
            df: DataFrame with friction analysis data

        Returns:
            AnalysisResults with all statistical tests
        """
        results = AnalysisResults()

        # Basic counts
        results.total_moves = len(df)
        results.total_blunders = df['is_blunder'].sum()
        results.total_friction_gaps = df['friction_gap'].sum()

        logger.info(f"Analyzing {results.total_moves} moves, "
                    f"{results.total_blunders} blunders, "
                    f"{results.total_friction_gaps} friction gaps")

        # Convert boolean columns from int to bool
        bool_cols = ['time_pressure', 'is_blunder', 'is_mistake', 'is_inaccuracy',
                     'has_alternatives', 'expected_friction', 'actual_friction', 'friction_gap']
        for col in bool_cols:
            if col in df.columns:
                df[col] = df[col].astype(bool)

        # Filter for non-time-pressure moves (core hypothesis)
        df_no_pressure = df[~df['time_pressure']]

        # Core hypothesis: correlation between think time and blunder
        results.correlation_blunder_thinktime = self._correlation(
            df, 'think_time_normalized', 'is_blunder'
        )

        results.correlation_no_time_pressure = self._correlation(
            df_no_pressure, 'think_time_normalized', 'is_blunder'
        )

        # T-test: think time for blunders vs non-blunders
        results.ttest_blunder_vs_nonblunder = self._ttest(
            df_no_pressure[df_no_pressure['is_blunder']]['think_time_normalized'],
            df_no_pressure[~df_no_pressure['is_blunder']]['think_time_normalized']
        )

        # Chi-square: friction gap vs blunder
        results.chi_square_friction_gap = self._chi_square(
            df_no_pressure, 'friction_gap', 'is_blunder'
        )

        # Logistic regression
        if HAS_STATSMODELS and len(df_no_pressure) > 100:
            results.logistic_regression = self._logistic_regression(df_no_pressure)

        # Segmented analysis
        results.blunder_rate_by_friction_level = self._blunder_rate_by_category(
            df_no_pressure, 'friction_level'
        )

        results.blunder_rate_by_rating_band = self._blunder_rate_by_rating(df_no_pressure)

        results.blunder_rate_by_game_phase = self._blunder_rate_by_phase(df_no_pressure)

        # Friction gap analysis
        friction_gap_df = df_no_pressure[df_no_pressure['friction_gap']]
        no_friction_gap_df = df_no_pressure[~df_no_pressure['friction_gap']]

        if len(friction_gap_df) > 0:
            results.blunder_rate_with_friction_gap = friction_gap_df['is_blunder'].mean()
        if len(no_friction_gap_df) > 0:
            results.blunder_rate_without_friction_gap = no_friction_gap_df['is_blunder'].mean()

        if results.blunder_rate_without_friction_gap > 0:
            results.relative_risk = (
                results.blunder_rate_with_friction_gap /
                results.blunder_rate_without_friction_gap
            )

        return results

    def _correlation(self, df: pd.DataFrame, col1: str, col2: str) -> CorrelationResult:
        """Calculate point-biserial correlation (for binary variable)."""
        valid = df[[col1, col2]].dropna()
        if len(valid) < 10:
            return CorrelationResult(0, 1, len(valid), 'point_biserial')

        # Point-biserial correlation for binary variable
        coef, p_value = stats.pointbiserialr(valid[col2], valid[col1])

        return CorrelationResult(
            coefficient=coef,
            p_value=p_value,
            n=len(valid),
            method='point_biserial'
        )

    def _ttest(self, group1: pd.Series, group2: pd.Series) -> TTestResult:
        """Perform independent samples t-test."""
        g1 = group1.dropna()
        g2 = group2.dropna()

        if len(g1) < 2 or len(g2) < 2:
            return TTestResult(0, 1, 0, 0, 0, 0, len(g1), len(g2), 0)

        statistic, p_value = stats.ttest_ind(g1, g2)

        # Cohen's d effect size
        pooled_std = np.sqrt(
            ((len(g1) - 1) * g1.std() ** 2 + (len(g2) - 1) * g2.std() ** 2) /
            (len(g1) + len(g2) - 2)
        )
        effect_size = (g1.mean() - g2.mean()) / pooled_std if pooled_std > 0 else 0

        return TTestResult(
            statistic=statistic,
            p_value=p_value,
            mean_group1=g1.mean(),
            mean_group2=g2.mean(),
            std_group1=g1.std(),
            std_group2=g2.std(),
            n_group1=len(g1),
            n_group2=len(g2),
            effect_size=effect_size
        )

    def _chi_square(self, df: pd.DataFrame, col1: str, col2: str) -> ChiSquareResult:
        """Perform chi-square test of independence."""
        contingency = pd.crosstab(df[col1], df[col2])

        if contingency.shape != (2, 2):
            # Not a 2x2 table, return empty result
            return ChiSquareResult(0, 1, 1, np.array([[0, 0], [0, 0]]), np.array([[0, 0], [0, 0]]))

        chi2, p_value, dof, expected = stats.chi2_contingency(contingency)

        return ChiSquareResult(
            statistic=chi2,
            p_value=p_value,
            dof=dof,
            contingency_table=contingency.values,
            expected=expected
        )

    def _logistic_regression(self, df: pd.DataFrame) -> Optional[RegressionResult]:
        """
        Logistic regression predicting blunder from friction metrics.

        Controls for: rating, game phase, complexity, time remaining, optionality
        """
        if not HAS_STATSMODELS:
            return None

        # Prepare features
        features = ['think_time_normalized', 'player_rating', 'game_phase',
                    'num_legal_moves', 'time_remaining', 'has_alternatives']

        # Filter to rows with all features present
        model_df = df[features + ['is_blunder']].dropna()

        if len(model_df) < 50:
            return None

        try:
            X = model_df[features].astype(float)
            X = sm.add_constant(X)
            y = model_df['is_blunder'].astype(int)

            model = sm.Logit(y, X)
            result = model.fit(disp=False, maxiter=100)

            coefficients = dict(zip(X.columns, result.params))
            p_values = dict(zip(X.columns, result.pvalues))
            odds_ratios = {k: np.exp(v) for k, v in coefficients.items()}

            return RegressionResult(
                coefficients=coefficients,
                p_values=p_values,
                odds_ratios=odds_ratios,
                pseudo_r2=result.prsquared,
                n=len(model_df),
                converged=result.converged
            )

        except Exception as e:
            logger.warning(f"Logistic regression failed: {e}")
            return None

    def _blunder_rate_by_category(self, df: pd.DataFrame, column: str) -> Dict[str, float]:
        """Calculate blunder rate by categorical variable."""
        result = {}
        for category in df[column].unique():
            subset = df[df[column] == category]
            if len(subset) > 0:
                result[str(category)] = subset['is_blunder'].mean()
        return result

    def _blunder_rate_by_rating(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate blunder rate by rating band."""
        result = {}
        for i in range(len(self.rating_bands) - 1):
            low, high = self.rating_bands[i], self.rating_bands[i + 1]
            subset = df[(df['player_rating'] >= low) & (df['player_rating'] < high)]
            if len(subset) > 0:
                result[f"{low}-{high}"] = subset['is_blunder'].mean()
        return result

    def _blunder_rate_by_phase(self, df: pd.DataFrame) -> Dict[str, float]:
        """Calculate blunder rate by game phase."""
        result = {}

        # Opening: phase > 0.7
        opening = df[df['game_phase'] > 0.7]
        if len(opening) > 0:
            result['opening'] = opening['is_blunder'].mean()

        # Middlegame: 0.3 < phase <= 0.7
        middlegame = df[(df['game_phase'] > 0.3) & (df['game_phase'] <= 0.7)]
        if len(middlegame) > 0:
            result['middlegame'] = middlegame['is_blunder'].mean()

        # Endgame: phase <= 0.3
        endgame = df[df['game_phase'] <= 0.3]
        if len(endgame) > 0:
            result['endgame'] = endgame['is_blunder'].mean()

        return result

    def generate_report(self, results: AnalysisResults) -> str:
        """Generate markdown report from analysis results."""
        lines = [
            "# Friction Analysis Report",
            "",
            "## Summary Statistics",
            f"- Moves analyzed: {results.total_moves:,}",
            f"- Blunders identified: {results.total_blunders:,} ({100*results.total_blunders/max(1,results.total_moves):.2f}%)",
            f"- Friction gaps identified: {results.total_friction_gaps:,} ({100*results.total_friction_gaps/max(1,results.total_moves):.2f}%)",
            "",
            "## Core Hypothesis Test",
            "",
            "**Hypothesis:** Negative correlation between thinking time and blunder probability in non-time-pressure conditions.",
            "",
        ]

        if results.correlation_no_time_pressure:
            corr = results.correlation_no_time_pressure
            lines.extend([
                f"- Correlation (think time vs blunder): r = {corr.coefficient:.4f}",
                f"- P-value: {corr.p_value:.6f}",
                f"- Sample size: {corr.n:,}",
                f"- **{'SUPPORTED' if corr.coefficient < 0 and corr.is_significant else 'NOT SUPPORTED'}**",
                "",
            ])

        if results.ttest_blunder_vs_nonblunder:
            tt = results.ttest_blunder_vs_nonblunder
            lines.extend([
                "### T-Test: Think Time (Blunders vs Non-Blunders)",
                f"- Mean think time (blunders): {tt.mean_group1:.3f} (normalized)",
                f"- Mean think time (non-blunders): {tt.mean_group2:.3f} (normalized)",
                f"- T-statistic: {tt.statistic:.3f}",
                f"- P-value: {tt.p_value:.6f}",
                f"- Effect size (Cohen's d): {tt.effect_size:.3f}",
                "",
            ])

        lines.extend([
            "## Friction Gap Analysis",
            "",
            f"- Blunder rate WITH friction gap: {100*results.blunder_rate_with_friction_gap:.2f}%",
            f"- Blunder rate WITHOUT friction gap: {100*results.blunder_rate_without_friction_gap:.2f}%",
            f"- Relative risk: {results.relative_risk:.2f}x",
            "",
        ])

        if results.chi_square_friction_gap:
            chi = results.chi_square_friction_gap
            lines.extend([
                f"- Chi-square statistic: {chi.statistic:.3f}",
                f"- P-value: {chi.p_value:.6f}",
                "",
            ])

        # Blunder rate by friction level
        if results.blunder_rate_by_friction_level:
            lines.extend([
                "## Blunder Rate by Friction Level",
                "",
            ])
            for level, rate in sorted(results.blunder_rate_by_friction_level.items()):
                lines.append(f"- {level}: {100*rate:.2f}%")
            lines.append("")

        # Logistic regression
        if results.logistic_regression and results.logistic_regression.converged:
            reg = results.logistic_regression
            lines.extend([
                "## Logistic Regression",
                "",
                f"Pseudo R²: {reg.pseudo_r2:.4f}",
                f"N: {reg.n:,}",
                "",
                "| Variable | Coefficient | Odds Ratio | P-value |",
                "|----------|-------------|------------|---------|",
            ])
            for var in reg.coefficients:
                if var == 'const':
                    continue
                lines.append(
                    f"| {var} | {reg.coefficients[var]:.4f} | "
                    f"{reg.odds_ratios[var]:.4f} | {reg.p_values[var]:.4f} |"
                )
            lines.append("")

        return "\n".join(lines)
