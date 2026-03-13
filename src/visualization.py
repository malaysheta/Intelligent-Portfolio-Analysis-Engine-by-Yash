"""
src/visualization.py
────────────────────
All matplotlib/seaborn charts for the portfolio analysis:

    1. Efficient Frontier (Monte Carlo scatter + optimal portfolios)
    2. Risk vs Return (scatter with stock names annotated)
    3. Correlation matrix heatmap
    4. Covariance matrix heatmap
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

import matplotlib
matplotlib.use("Agg")   # non-interactive backend — safe on all platforms
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
import seaborn as sns

if TYPE_CHECKING:
    from src.monte_carlo import MonteCarloResults
    from src.optimizer import OptimizedPortfolio

logger = logging.getLogger(__name__)

# ── Style ────────────────────────────────────────────────────────────────────
PALETTE = {
    "scatter": "#4A90D9",
    "current": "#F5A623",
    "min_var": "#7ED321",
    "max_ret": "#D0021B",
    "max_sr": "#9B59B6",
    "frontier": "#E8E8E8",
}


def _save(fig: plt.Figure, path: Path, dpi: int = 150) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved plot → %s", path)


# ─── 1. Efficient Frontier ───────────────────────────────────────────────────

def plot_efficient_frontier(
    mc_results: "MonteCarloResults",
    current_return: float,
    current_std: float,
    optimized: dict[str, "OptimizedPortfolio"] | None = None,
    output_path: Path = Path("outputs/efficient_frontier.png"),
    dpi: int = 150,
) -> None:
    """
    Plot the simulated efficient frontier and mark special portfolios.

    Parameters
    ----------
    mc_results : MonteCarloResults
        Results from :func:`monte_carlo.run_monte_carlo`.
    current_return : float
        Current portfolio expected return.
    current_std : float
        Current portfolio std deviation.
    optimized : dict | None
        Optimised portfolios from optimizer.run_all_optimizations.
    output_path : Path
        Where to save the PNG.
    """
    df = mc_results.df
    fig, ax = plt.subplots(figsize=(12, 7))
    fig.patch.set_facecolor("#0F1117")
    ax.set_facecolor("#0F1117")

    # Monte Carlo scatter coloured by Sharpe ratio
    sc = ax.scatter(
        df["portfolio_std"],
        df["portfolio_return"],
        c=df["sharpe_ratio"],
        cmap="plasma",
        alpha=0.4,
        s=4,
        linewidths=0,
        label=f"{mc_results.n_simulations:,} Random Portfolios",
    )
    cbar = fig.colorbar(sc, ax=ax, fraction=0.03, pad=0.02)
    cbar.set_label("Sharpe Ratio", color="white", fontsize=10)
    cbar.ax.yaxis.set_tick_params(color="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

    # Special MC portfolios
    for row, label, color, marker in [
        (mc_results.min_std_portfolio, "MC Min Risk", PALETTE["min_var"], "^"),
        (mc_results.max_return_portfolio, "MC Max Return", PALETTE["max_ret"], "s"),
        (mc_results.max_sharpe_portfolio, "MC Max Sharpe", PALETTE["max_sr"], "D"),
    ]:
        ax.scatter(
            row["portfolio_std"], row["portfolio_return"],
            c=color, s=120, marker=marker, zorder=5, label=label,
        )

    # Current portfolio
    ax.scatter(
        current_std, current_return,
        c=PALETTE["current"], s=200, marker="*", zorder=6,
        label=f"Current Portfolio (SR={( current_return - 0.05) / current_std:.3f})",
        edgecolors="white", linewidths=0.5,
    )

    # Optimised portfolios
    if optimized:
        opt_styles = {
            "min_variance": ("Min Variance", PALETTE["min_var"], "o"),
            "max_return": ("Max Return", PALETTE["max_ret"], "P"),
            "max_sharpe": ("Max Sharpe", PALETTE["max_sr"], "H"),
        }
        for key, opt in optimized.items():
            lbl, clr, mkr = opt_styles.get(key, (key, "white", "o"))
            ax.scatter(
                opt.portfolio_std, opt.portfolio_return,
                c=clr, s=160, marker=mkr, zorder=7,
                label=f"Opt {lbl} (SR={opt.sharpe_ratio:.3f})",
                edgecolors="white", linewidths=0.8,
            )

    # Styling
    for spine in ax.spines.values():
        spine.set_edgecolor("#333333")
    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")
    ax.set_xlabel("Portfolio Risk (Std Deviation)", fontsize=13)
    ax.set_ylabel("Portfolio Return", fontsize=13)
    ax.set_title("Monte Carlo Efficient Frontier", fontsize=16, fontweight="bold", pad=15)

    legend = ax.legend(
        loc="upper left", fontsize=9, framealpha=0.2,
        labelcolor="white", facecolor="#222222",
    )

    ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=1))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=1))

    _save(fig, output_path, dpi)


# ─── 2. Risk vs Return ───────────────────────────────────────────────────────

def plot_risk_return(
    stocks: list[str],
    asset_returns: np.ndarray,
    asset_stds: np.ndarray,
    output_path: Path = Path("outputs/risk_return.png"),
    dpi: int = 150,
) -> None:
    """
    Scatter plot of individual stocks' risk vs return.

    Parameters
    ----------
    stocks : list[str]
        Stock names.
    asset_returns : np.ndarray
        Expected return per stock.
    asset_stds : np.ndarray
        Std deviation per stock (sqrt of diagonal of cov matrix).
    """
    fig, ax = plt.subplots(figsize=(9, 6))
    fig.patch.set_facecolor("#0F1117")
    ax.set_facecolor("#0F1117")

    colors = plt.cm.tab10(np.linspace(0, 0.9, len(stocks)))  # type: ignore[attr-defined]
    for i, (s, r, std, c) in enumerate(zip(stocks, asset_returns, asset_stds, colors)):
        ax.scatter(std, r, s=180, color=c, zorder=5)
        ax.annotate(
            s, (std, r),
            textcoords="offset points", xytext=(8, 4),
            fontsize=10, color=c, fontweight="bold",
        )

    for spine in ax.spines.values():
        spine.set_edgecolor("#333333")
    ax.tick_params(colors="white")
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")
    ax.title.set_color("white")
    ax.set_xlabel("Risk (Std Deviation)", fontsize=12)
    ax.set_ylabel("Expected Return", fontsize=12)
    ax.set_title("Individual Stock — Risk vs Return", fontsize=14, fontweight="bold")

    ax.xaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=1))
    ax.yaxis.set_major_formatter(mticker.PercentFormatter(xmax=1, decimals=1))

    _save(fig, output_path, dpi)


# ─── 3 & 4. Heatmaps ────────────────────────────────────────────────────────

def _heatmap(
    matrix_df: pd.DataFrame,
    title: str,
    output_path: Path,
    fmt: str = ".4f",
    cmap: str = "coolwarm",
    dpi: int = 150,
    vmin: float | None = None,
    vmax: float | None = None,
) -> None:
    """Generic heatmap renderer."""
    fig, ax = plt.subplots(figsize=(8, 6))
    fig.patch.set_facecolor("#0F1117")
    ax.set_facecolor("#0F1117")

    mask = None  # show all cells
    sns.heatmap(
        matrix_df,
        annot=True,
        fmt=fmt,
        cmap=cmap,
        linewidths=0.5,
        linecolor="#333333",
        ax=ax,
        vmin=vmin,
        vmax=vmax,
        annot_kws={"size": 9, "color": "white"},
        cbar_kws={"shrink": 0.8},
    )

    ax.set_title(title, fontsize=14, fontweight="bold", color="white", pad=12)
    ax.tick_params(colors="white", labelsize=9)
    ax.xaxis.label.set_color("white")
    ax.yaxis.label.set_color("white")

    # Colour bar text
    cbar = ax.collections[0].colorbar
    cbar.ax.tick_params(colors="white")
    plt.setp(cbar.ax.yaxis.get_ticklabels(), color="white")

    _save(fig, output_path, dpi)


def plot_correlation_heatmap(
    corr_df: pd.DataFrame,
    output_path: Path = Path("outputs/correlation_heatmap.png"),
    dpi: int = 150,
) -> None:
    """Plot the correlation matrix as a heatmap."""
    _heatmap(
        corr_df, "Correlation Matrix",
        output_path, fmt=".3f", cmap="RdYlGn",
        vmin=-1, vmax=1, dpi=dpi,
    )


def plot_covariance_heatmap(
    cov_df: pd.DataFrame,
    output_path: Path = Path("outputs/covariance_heatmap.png"),
    dpi: int = 150,
) -> None:
    """Plot the covariance matrix as a heatmap."""
    _heatmap(
        cov_df, "Covariance Matrix",
        output_path, fmt=".6f", cmap="Blues", dpi=dpi,
    )


# ─── Convenience: generate all plots ────────────────────────────────────────

def generate_all_plots(
    mc_results: "MonteCarloResults",
    current_return: float,
    current_std: float,
    optimized: dict[str, "OptimizedPortfolio"],
    stocks: list[str],
    asset_returns: np.ndarray,
    cov_matrix: np.ndarray,
    corr_df: pd.DataFrame,
    cov_df: pd.DataFrame,
    outputs_dir: Path = Path("outputs"),
    dpi: int = 150,
) -> None:
    """Generate and save all four portfolio charts."""
    plot_efficient_frontier(
        mc_results, current_return, current_std, optimized,
        output_path=outputs_dir / "efficient_frontier.png", dpi=dpi,
    )
    asset_stds = np.sqrt(np.diag(cov_matrix))
    plot_risk_return(
        stocks, asset_returns, asset_stds,
        output_path=outputs_dir / "risk_return.png", dpi=dpi,
    )
    plot_correlation_heatmap(corr_df, outputs_dir / "correlation_heatmap.png", dpi)
    plot_covariance_heatmap(cov_df, outputs_dir / "covariance_heatmap.png", dpi)
