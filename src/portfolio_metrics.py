"""
src/portfolio_metrics.py
────────────────────────
Core portfolio mathematics:
    - Portfolio return
    - Portfolio variance
    - Portfolio standard deviation
    - Sharpe ratio
All functions accept numpy arrays and plain floats, making them
easy to call from the optimiser and Monte Carlo simulation.
"""

from __future__ import annotations

import numpy as np


def calculate_portfolio_return(
    weights: np.ndarray,
    asset_returns: np.ndarray,
) -> float:
    """
    Compute portfolio expected return.

    Formula
    -------
    Rp = Σ(wᵢ · Rᵢ)   ≡   wᵀ · r

    Parameters
    ----------
    weights : np.ndarray
        1-D array of portfolio weights (must sum to 1).
    asset_returns : np.ndarray
        1-D array of expected returns for each asset.

    Returns
    -------
    float
        Weighted portfolio return.
    """
    weights = np.asarray(weights, dtype=float)
    asset_returns = np.asarray(asset_returns, dtype=float)
    return float(np.dot(weights, asset_returns))


def calculate_portfolio_variance(
    weights: np.ndarray,
    cov_matrix: np.ndarray,
) -> float:
    """
    Compute portfolio variance using the quadratic form.

    Formula
    -------
    σ² = wᵀ · Σ · w

    Parameters
    ----------
    weights : np.ndarray
        1-D array of portfolio weights.
    cov_matrix : np.ndarray
        n × n covariance matrix Σ.

    Returns
    -------
    float
        Portfolio variance σ².
    """
    weights = np.asarray(weights, dtype=float)
    cov_matrix = np.asarray(cov_matrix, dtype=float)
    return float(weights @ cov_matrix @ weights)


def calculate_portfolio_std(variance: float) -> float:
    """
    Compute portfolio standard deviation from variance.

    Formula
    -------
    σ = √(σ²)

    Parameters
    ----------
    variance : float
        Portfolio variance σ².

    Returns
    -------
    float
        Portfolio standard deviation σ.
    """
    if variance < 0:
        raise ValueError(f"Variance cannot be negative. Got: {variance:.6f}")
    return float(np.sqrt(variance))


def calculate_sharpe_ratio(
    portfolio_return: float,
    portfolio_std: float,
    risk_free_rate: float = 0.05,
) -> float:
    """
    Compute the Sharpe ratio.

    Formula
    -------
    SR = (Rp - Rf) / σ

    Parameters
    ----------
    portfolio_return : float
        Expected portfolio return Rp.
    portfolio_std : float
        Portfolio standard deviation σ.
    risk_free_rate : float
        Risk-free rate Rf (default 0.05 = 5 %).

    Returns
    -------
    float
        Sharpe ratio. Returns 0.0 when σ ≈ 0 to avoid division by zero.
    """
    if portfolio_std < 1e-12:
        return 0.0
    return float((portfolio_return - risk_free_rate) / portfolio_std)


def portfolio_summary(
    weights: np.ndarray,
    asset_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float = 0.05,
) -> dict[str, float]:
    """
    Compute and return the three core portfolio metrics in one call.

    Parameters
    ----------
    weights : np.ndarray
        Portfolio weights.
    asset_returns : np.ndarray
        Per-asset expected returns.
    cov_matrix : np.ndarray
        Covariance matrix.
    risk_free_rate : float
        Risk-free rate for Sharpe calculation.

    Returns
    -------
    dict with keys: 'portfolio_return', 'portfolio_std', 'sharpe_ratio'
    """
    ret = calculate_portfolio_return(weights, asset_returns)
    var = calculate_portfolio_variance(weights, cov_matrix)
    std = calculate_portfolio_std(var)
    sr = calculate_sharpe_ratio(ret, std, risk_free_rate)
    return {
        "portfolio_return": ret,
        "portfolio_variance": var,
        "portfolio_std": std,
        "sharpe_ratio": sr,
    }
