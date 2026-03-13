"""
src/validation.py
─────────────────
Validates the portfolio data extracted from the Excel file.
Every validator returns (bool, list[str]) — pass flag + list of issues.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from src.data_loader import PortfolioData

logger = logging.getLogger(__name__)

_TOL = 1e-6


def validate_weights(weights: dict[str, float]) -> tuple[bool, list[str]]:
    """
    Validate that portfolio weights sum to 1.0 within a small tolerance.

    Parameters
    ----------
    weights : dict[str, float]
        Stock → weight mapping.

    Returns
    -------
    tuple[bool, list[str]]
        (passed, issues)
    """
    issues: list[str] = []

    if not weights:
        issues.append("Weights dictionary is empty.")
        return False, issues

    total = sum(weights.values())
    if abs(total - 1.0) > _TOL:
        issues.append(
            f"Weights sum to {total:.8f} instead of 1.0 "
            f"(deviation: {abs(total - 1.0):.2e})."
        )

    for stock, w in weights.items():
        if w < 0:
            issues.append(f"Negative weight for '{stock}': {w}")
        if w > 1:
            issues.append(f"Weight > 1 for '{stock}': {w} — check for errors.")

    passed = len(issues) == 0
    return passed, issues


def validate_covariance_matrix(
    cov: np.ndarray,
    stock_names: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """
    Validate the covariance matrix for shape, symmetry, and
    positive semi-definiteness.

    Parameters
    ----------
    cov : np.ndarray
        n × n covariance matrix.
    stock_names : list[str] | None
        Optional stock labels for readable error messages.

    Returns
    -------
    tuple[bool, list[str]]
        (passed, issues)
    """
    issues: list[str] = []

    if cov.ndim != 2 or cov.shape[0] != cov.shape[1]:
        issues.append(f"Covariance matrix must be square. Got shape: {cov.shape}.")
        return False, issues

    # Symmetry
    if not np.allclose(cov, cov.T, atol=_TOL):
        max_asym = np.max(np.abs(cov - cov.T))
        issues.append(
            f"Covariance matrix is not symmetric "
            f"(max asymmetry: {max_asym:.2e}). Auto-symmetrising."
        )

    # Positive semi-definiteness via eigenvalues
    eigvals = np.linalg.eigvalsh(cov)
    min_eig = float(np.min(eigvals))
    if min_eig < -_TOL:
        issues.append(
            f"Covariance matrix is not positive semi-definite "
            f"(min eigenvalue: {min_eig:.4f})."
        )

    # NaN / Inf
    if np.any(~np.isfinite(cov)):
        issues.append("Covariance matrix contains NaN or Inf values.")

    passed = len(issues) == 0
    return passed, issues


def validate_correlation_matrix(
    corr: np.ndarray,
    stock_names: list[str] | None = None,
) -> tuple[bool, list[str]]:
    """
    Validate the correlation matrix: values in [-1, 1], diagonal = 1,
    and symmetry.

    Parameters
    ----------
    corr : np.ndarray
        n × n correlation matrix.
    stock_names : list[str] | None
        Optional stock labels.

    Returns
    -------
    tuple[bool, list[str]]
        (passed, issues)
    """
    issues: list[str] = []

    if corr.ndim != 2 or corr.shape[0] != corr.shape[1]:
        issues.append(f"Correlation matrix must be square. Got shape: {corr.shape}.")
        return False, issues

    # Value range
    if np.any(corr > 1 + _TOL) or np.any(corr < -1 - _TOL):
        out_of_range = np.sum((corr > 1 + _TOL) | (corr < -1 - _TOL))
        issues.append(
            f"Correlation matrix has {out_of_range} value(s) outside [-1, 1]."
        )

    # Diagonal = 1
    diag = np.diag(corr)
    if not np.allclose(diag, 1.0, atol=1e-3):
        issues.append(
            f"Correlation diagonal should be 1.0; got: {diag}"
        )

    # Symmetry
    if not np.allclose(corr, corr.T, atol=_TOL):
        issues.append("Correlation matrix is not symmetric.")

    # NaN / Inf
    if np.any(~np.isfinite(corr)):
        issues.append("Correlation matrix contains NaN or Inf values.")

    passed = len(issues) == 0
    return passed, issues


def validate_all(data: "PortfolioData") -> bool:
    """
    Run all validations on a PortfolioData instance and log results.

    Returns
    -------
    bool
        True if all checks pass (or only have warnings).
    """
    all_ok = True

    # ── Weights ──────────────────────────────────────────────────────────
    w_ok, w_issues = validate_weights(data.weights)
    if not w_ok:
        for msg in w_issues:
            logger.warning("  [WEIGHT]  %s", msg)
        all_ok = False
    else:
        logger.info("  [WEIGHT]  ✓  sum(weights) = %.6f", sum(data.weights.values()))

    # ── Covariance ───────────────────────────────────────────────────────
    cov_ok, cov_issues = validate_covariance_matrix(data.covariance_matrix, data.stocks)
    if not cov_ok:
        for msg in cov_issues:
            logger.warning("  [COV]     %s", msg)
        all_ok = False
    else:
        logger.info("  [COV]     ✓  Covariance matrix is valid.")

    # ── Correlation ──────────────────────────────────────────────────────
    corr_ok, corr_issues = validate_correlation_matrix(
        data.correlation_matrix, data.stocks
    )
    if not corr_ok:
        for msg in corr_issues:
            logger.warning("  [CORR]    %s", msg)
        all_ok = False
    else:
        logger.info("  [CORR]    ✓  Correlation matrix is valid.")

    return all_ok
