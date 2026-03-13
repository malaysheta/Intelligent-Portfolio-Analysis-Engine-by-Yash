"""
src/optimizer.py
────────────────
Portfolio optimisation using scipy.optimize.minimize (SLSQP).

Implements three classical strategies:
    1. Minimum Variance Portfolio
    2. Maximum Return Portfolio
    3. Maximum Sharpe Ratio Portfolio

All optimisers enforce:
    - weights ∈ [0, 1]  (long-only)
    - sum(weights) = 1
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from scipy.optimize import minimize, OptimizeResult

from src.portfolio_metrics import (
    calculate_portfolio_return,
    calculate_portfolio_std,
    calculate_portfolio_variance,
    calculate_sharpe_ratio,
)

logger = logging.getLogger(__name__)


@dataclass
class OptimizedPortfolio:
    """Result of a single optimisation run."""

    strategy: str
    weights: dict[str, float]
    portfolio_return: float
    portfolio_std: float
    sharpe_ratio: float
    success: bool
    message: str

    def as_array(self, stocks: list[str]) -> np.ndarray:
        return np.array([self.weights[s] for s in stocks])


# ─── Internal helpers ────────────────────────────────────────────────────────

def _build_constraints() -> list[dict]:
    return [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]


def _build_bounds(n: int) -> list[tuple[float, float]]:
    return [(0.0, 1.0)] * n


def _initial_weights(n: int, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    w = rng.dirichlet(np.ones(n))
    return w


def _run_minimize(
    objective,
    n: int,
    strategy: str,
    stocks: list[str],
    asset_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float,
) -> OptimizedPortfolio:
    result: OptimizeResult = minimize(
        objective,
        x0=_initial_weights(n),
        method="SLSQP",
        bounds=_build_bounds(n),
        constraints=_build_constraints(),
        options={"maxiter": 1000, "ftol": 1e-12},
    )

    w = result.x
    ret = calculate_portfolio_return(w, asset_returns)
    var = calculate_portfolio_variance(w, cov_matrix)
    std = calculate_portfolio_std(var)
    sr = calculate_sharpe_ratio(ret, std, risk_free_rate)

    if not result.success:
        logger.warning("[%s] Optimisation did not fully converge: %s", strategy, result.message)

    return OptimizedPortfolio(
        strategy=strategy,
        weights={s: float(w[i]) for i, s in enumerate(stocks)},
        portfolio_return=ret,
        portfolio_std=std,
        sharpe_ratio=sr,
        success=result.success,
        message=result.message,
    )


# ─── Public optimisers ───────────────────────────────────────────────────────

def minimize_variance(
    stocks: list[str],
    asset_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float = 0.05,
) -> OptimizedPortfolio:
    """
    Find the portfolio with the minimum variance (lowest risk).

    Objective: minimise  wᵀ Σ w
    """
    def objective(w: np.ndarray) -> float:
        return calculate_portfolio_variance(w, cov_matrix)

    logger.info("Optimising: Minimum Variance Portfolio …")
    return _run_minimize(
        objective, len(stocks), "Minimum Variance",
        stocks, asset_returns, cov_matrix, risk_free_rate,
    )


def maximize_return(
    stocks: list[str],
    asset_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float = 0.05,
) -> OptimizedPortfolio:
    """
    Find the portfolio with the maximum expected return.

    Objective: maximise  wᵀ r  (minimise negative return)
    """
    def objective(w: np.ndarray) -> float:
        return -calculate_portfolio_return(w, asset_returns)

    logger.info("Optimising: Maximum Return Portfolio …")
    return _run_minimize(
        objective, len(stocks), "Maximum Return",
        stocks, asset_returns, cov_matrix, risk_free_rate,
    )


def maximize_sharpe(
    stocks: list[str],
    asset_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float = 0.05,
) -> OptimizedPortfolio:
    """
    Find the portfolio with the maximum Sharpe ratio (tangency portfolio).

    Objective: maximise  (wᵀr - Rf) / σ(w)
               minimise  -(wᵀr - Rf) / σ(w)
    """
    def objective(w: np.ndarray) -> float:
        ret = calculate_portfolio_return(w, asset_returns)
        var = calculate_portfolio_variance(w, cov_matrix)
        std = calculate_portfolio_std(var)
        return -calculate_sharpe_ratio(ret, std, risk_free_rate)

    logger.info("Optimising: Maximum Sharpe Ratio Portfolio …")
    return _run_minimize(
        objective, len(stocks), "Maximum Sharpe Ratio",
        stocks, asset_returns, cov_matrix, risk_free_rate,
    )


def run_all_optimizations(
    stocks: list[str],
    asset_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float = 0.05,
) -> dict[str, OptimizedPortfolio]:
    """
    Run all three optimisation strategies and return a results dict.

    Returns
    -------
    dict with keys: 'min_variance', 'max_return', 'max_sharpe'
    """
    return {
        "min_variance": minimize_variance(
            stocks, asset_returns, cov_matrix, risk_free_rate
        ),
        "max_return": maximize_return(
            stocks, asset_returns, cov_matrix, risk_free_rate
        ),
        "max_sharpe": maximize_sharpe(
            stocks, asset_returns, cov_matrix, risk_free_rate
        ),
    }
