"""
src/monte_carlo.py
──────────────────
Monte Carlo simulation: generate N random long-only portfolios and
compute their return, risk, and Sharpe ratio.

Used to:
    1. Approximate the efficient frontier visually.
    2. Identify approximate optimal portfolios from the sample.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
import pandas as pd

from src.portfolio_metrics import (
    calculate_portfolio_return,
    calculate_portfolio_std,
    calculate_portfolio_variance,
    calculate_sharpe_ratio,
)

logger = logging.getLogger(__name__)


@dataclass
class MonteCarloResults:
    """Results of Monte Carlo portfolio simulation."""

    df: pd.DataFrame                # columns: return, std, sharpe, w_0 … w_{n-1}
    n_simulations: int
    min_std_portfolio: pd.Series
    max_return_portfolio: pd.Series
    max_sharpe_portfolio: pd.Series


def run_monte_carlo(
    stocks: list[str],
    asset_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float = 0.05,
    n_simulations: int = 10_000,
    random_state: int = 42,
) -> MonteCarloResults:
    """
    Simulate *n_simulations* random portfolios.

    Each portfolio's weights are drawn from a Dirichlet distribution
    (uniform concentration) to ensure they are non-negative and sum to 1.

    Parameters
    ----------
    stocks : list[str]
        Stock names (used for column naming).
    asset_returns : np.ndarray
        Per-asset expected returns.
    cov_matrix : np.ndarray
        n × n covariance matrix.
    risk_free_rate : float
        Risk-free rate for Sharpe computation.
    n_simulations : int
        Number of random portfolios to generate.
    random_state : int
        Numpy RNG seed.

    Returns
    -------
    MonteCarloResults
    """
    n = len(stocks)
    rng = np.random.default_rng(random_state)
    logger.info("Running Monte Carlo simulation (%d portfolios) …", n_simulations)

    # Sample all weights at once — much faster than a Python loop
    weights_matrix = rng.dirichlet(np.ones(n), size=n_simulations)  # (N, n)

    # Vectorised return computation
    port_returns = weights_matrix @ asset_returns  # (N,)

    # Vectorised variance: diag(W Σ Wᵀ)
    # (N, n) @ (n, n) → (N, n) → element-wise * (N, n) → sum over stocks
    port_vars = np.sum((weights_matrix @ cov_matrix) * weights_matrix, axis=1)
    port_stds = np.sqrt(port_vars)

    # Sharpe
    port_sharpes = np.where(
        port_stds > 1e-12,
        (port_returns - risk_free_rate) / port_stds,
        0.0,
    )

    # Build DataFrame
    weight_cols = {f"w_{s}": weights_matrix[:, i] for i, s in enumerate(stocks)}
    df = pd.DataFrame({
        "portfolio_return": port_returns,
        "portfolio_std": port_stds,
        "sharpe_ratio": port_sharpes,
        **weight_cols,
    })

    min_std_idx = df["portfolio_std"].idxmin()
    max_ret_idx = df["portfolio_return"].idxmax()
    max_sr_idx = df["sharpe_ratio"].idxmax()

    logger.info(
        "  Min Risk       → Return=%.4f  Std=%.4f  Sharpe=%.4f",
        df.loc[min_std_idx, "portfolio_return"],
        df.loc[min_std_idx, "portfolio_std"],
        df.loc[min_std_idx, "sharpe_ratio"],
    )
    logger.info(
        "  Max Return     → Return=%.4f  Std=%.4f  Sharpe=%.4f",
        df.loc[max_ret_idx, "portfolio_return"],
        df.loc[max_ret_idx, "portfolio_std"],
        df.loc[max_ret_idx, "sharpe_ratio"],
    )
    logger.info(
        "  Max Sharpe     → Return=%.4f  Std=%.4f  Sharpe=%.4f",
        df.loc[max_sr_idx, "portfolio_return"],
        df.loc[max_sr_idx, "portfolio_std"],
        df.loc[max_sr_idx, "sharpe_ratio"],
    )

    return MonteCarloResults(
        df=df,
        n_simulations=n_simulations,
        min_std_portfolio=df.loc[min_std_idx],
        max_return_portfolio=df.loc[max_ret_idx],
        max_sharpe_portfolio=df.loc[max_sr_idx],
    )
