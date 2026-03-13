"""
main.py
───────
Portfolio Analysis & ML Prediction — Main Pipeline

Usage:
    python main.py [--excel PATH] [--no-plots]

Pipeline stages:
    1. Load Excel data
    2. Validate matrices & weights
    3. Compute portfolio metrics
    4. Run optimisation (Min Variance, Max Return, Max Sharpe)
    5. Train ML models & predict
    6. Monte Carlo simulation
    7. Generate visualisation plots
    8. Print formatted report
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

# ── Module imports ────────────────────────────────────────────────────────────
# Add project root to sys.path so 'src' and 'config' are importable when the
# script is run directly from any working directory.
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from config.settings import (
    EXCEL_PATH,
    MONTE_CARLO_SIMULATIONS,
    OUTPUTS_DIR,
    PLOT_DPI,
    RANDOM_STATE,
    RISK_FREE_RATE,
    STOCK_NAMES,
    N_SYNTHETIC_SAMPLES,
    TRAIN_TEST_SPLIT,
)
from src.data_loader import load_portfolio_data
from src.validation import validate_all
from src.portfolio_metrics import portfolio_summary
from src.optimizer import run_all_optimizations
from src.ml_model import train_and_predict
from src.monte_carlo import run_monte_carlo
from src.visualization import generate_all_plots

# ── Logging ───────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── ANSI colour helpers ────────────────────────────────────────────────────────
BOLD = "\033[1m"
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
MAGENTA = "\033[95m"
RESET = "\033[0m"
DIM = "\033[2m"


def _header(text: str, color: str = CYAN) -> None:
    width = 60
    print(f"\n{color}{BOLD}{'─' * width}{RESET}")
    print(f"{color}{BOLD}  {text}{RESET}")
    print(f"{color}{BOLD}{'─' * width}{RESET}")


def _row(label: str, value: float | str, indent: int = 4) -> None:
    pad = " " * indent
    if isinstance(value, float):
        print(f"{pad}{label:<30} {GREEN}{value:>12.5f}{RESET}")
    else:
        print(f"{pad}{label:<30} {GREEN}{value!s:>12}{RESET}")


def _section(title: str) -> None:
    print(f"\n  {YELLOW}{BOLD}{title}{RESET}")


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline
# ─────────────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Portfolio Analytics & ML Prediction Pipeline"
    )
    parser.add_argument(
        "--excel",
        type=Path,
        default=None,
        help="Path to portfolio Excel file (overrides settings.py)",
    )
    parser.add_argument(
        "--no-plots",
        action="store_true",
        help="Skip generating visualisation plots (faster in CI/CD)",
    )
    return parser.parse_args()


def main() -> None:
    t0 = time.perf_counter()
    args = parse_args()

    excel_path: Path = args.excel or EXCEL_PATH

    print(f"\n{CYAN}{BOLD}{'═' * 60}{RESET}")
    print(f"{CYAN}{BOLD}  Portfolio Analysis & ML Prediction Engine{RESET}")
    print(f"{CYAN}{BOLD}  Stocks: {', '.join(STOCK_NAMES)}{RESET}")
    print(f"{CYAN}{BOLD}{'═' * 60}{RESET}\n")

    # ── 1. DATA INGESTION ────────────────────────────────────────────────────
    _header("Stage 1: Data Ingestion", CYAN)
    logger.info("Excel file path: %s", excel_path)
    data = load_portfolio_data(excel_path)
    logger.info("Stocks loaded: %s", data.stocks)

    # ── 2. VALIDATION ────────────────────────────────────────────────────────
    _header("Stage 2: Data Validation", CYAN)
    valid = validate_all(data)
    if valid:
        logger.info("All validation checks PASSED ✓")
    else:
        logger.warning("Some validation checks failed — proceeding with caution.")

    _section("Weights Summary")
    for stock, w in data.weights.items():
        _row(stock, w)
    _row("SUM", sum(data.weights.values()))

    # ── 3. PORTFOLIO METRICS ─────────────────────────────────────────────────
    _header("Stage 3: Portfolio Metrics", CYAN)
    metrics = portfolio_summary(
        data.weights_array,
        data.returns_array,
        data.covariance_matrix,
        RISK_FREE_RATE,
    )
    _section("Current Portfolio")
    _row("Portfolio Return", metrics["portfolio_return"])
    _row("Portfolio Std Dev", metrics["portfolio_std"])
    _row("Portfolio Variance", metrics["portfolio_variance"])
    _row("Sharpe Ratio", metrics["sharpe_ratio"])
    _row("Risk-Free Rate", RISK_FREE_RATE)

    # Cross-check against Excel stats
    _section("Excel Reference (from file)")
    _row("Return  (Excel)", data.portfolio_stats.get("portfolio_return", float("nan")))
    _row("Std Dev (Excel)", data.portfolio_stats.get("portfolio_std", float("nan")))
    _row("Sharpe  (Excel)", data.portfolio_stats.get("sharpe_ratio", float("nan")))

    # ── 4. PORTFOLIO OPTIMISATION ────────────────────────────────────────────
    _header("Stage 4: Portfolio Optimisation", CYAN)
    optimized = run_all_optimizations(
        data.stocks,
        data.returns_array,
        data.covariance_matrix,
        RISK_FREE_RATE,
    )

    strategy_display = {
        "min_variance": ("Minimum Variance Portfolio", YELLOW),
        "max_return":   ("Maximum Return Portfolio",   MAGENTA),
        "max_sharpe":   ("Maximum Sharpe Portfolio",   GREEN),
    }
    for key, opt in optimized.items():
        label, color = strategy_display[key]
        _section(label)
        _row("Return", opt.portfolio_return)
        _row("Std Dev", opt.portfolio_std)
        _row("Sharpe Ratio", opt.sharpe_ratio)
        print(f"    {DIM}Weights:{RESET}")
        for stock, w in opt.weights.items():
            print(f"      {stock:<15} {w:.4f}")

    # ── 5. MACHINE LEARNING PREDICTION ───────────────────────────────────────
    _header("Stage 5: ML Prediction", CYAN)
    predictions_csv = OUTPUTS_DIR / "predictions.csv"
    ml_results = train_and_predict(
        base_weights=data.weights_array,
        asset_returns=data.returns_array,
        cov_matrix=data.covariance_matrix,
        risk_free_rate=RISK_FREE_RATE,
        n_samples=N_SYNTHETIC_SAMPLES,
        test_size=1 - TRAIN_TEST_SPLIT,
        random_state=RANDOM_STATE,
        output_path=predictions_csv,
    )

    _section("ML Predictions (next-period estimate)")
    print(f"\n  {'Model':<22} {'Pred Return':>13} {'Pred Std':>12} {'Pred Sharpe':>13}")
    print(f"  {'─'*22} {'─'*13} {'─'*12} {'─'*13}")
    for _, row_data in ml_results.predictions.iterrows():
        print(
            f"  {row_data['Model']:<22} "
            f"{row_data['Predicted_Return']:>13.5f} "
            f"{row_data['Predicted_Std']:>12.5f} "
            f"{row_data['Predicted_Sharpe']:>13.5f}"
        )

    # ── 6. MONTE CARLO SIMULATION ────────────────────────────────────────────
    _header("Stage 6: Monte Carlo Simulation", CYAN)
    mc_results = run_monte_carlo(
        stocks=data.stocks,
        asset_returns=data.returns_array,
        cov_matrix=data.covariance_matrix,
        risk_free_rate=RISK_FREE_RATE,
        n_simulations=MONTE_CARLO_SIMULATIONS,
        random_state=RANDOM_STATE,
    )

    _section(f"Simulation Results ({MONTE_CARLO_SIMULATIONS:,} portfolios)")
    mc_best = mc_results.max_sharpe_portfolio
    _row("Best MC Return",  mc_best["portfolio_return"])
    _row("Best MC Std",     mc_best["portfolio_std"])
    _row("Best MC Sharpe",  mc_best["sharpe_ratio"])

    # ── 7. VISUALISATION ─────────────────────────────────────────────────────
    if not args.no_plots:
        _header("Stage 7: Visualisation", CYAN)
        OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
        generate_all_plots(
            mc_results=mc_results,
            current_return=metrics["portfolio_return"],
            current_std=metrics["portfolio_std"],
            optimized=optimized,
            stocks=data.stocks,
            asset_returns=data.returns_array,
            cov_matrix=data.covariance_matrix,
            corr_df=data.correlation_df,
            cov_df=data.covariance_df,
            outputs_dir=OUTPUTS_DIR,
            dpi=PLOT_DPI,
        )
        logger.info("All plots saved to '%s'.", OUTPUTS_DIR)
    else:
        logger.info("Plot generation skipped (--no-plots).")

    # ── 8. FINAL REPORT ──────────────────────────────────────────────────────
    elapsed = time.perf_counter() - t0
    print(f"\n{CYAN}{BOLD}{'═' * 60}{RESET}")
    print(f"{CYAN}{BOLD}  PORTFOLIO ANALYSIS REPORT{RESET}")
    print(f"{CYAN}{BOLD}{'═' * 60}{RESET}")

    print(f"""
  {BOLD}Current Portfolio{RESET}
    Return   : {GREEN}{metrics['portfolio_return']:.5f}{RESET}
    Risk     : {GREEN}{metrics['portfolio_std']:.5f}{RESET}
    Sharpe   : {GREEN}{metrics['sharpe_ratio']:.5f}{RESET}

  {BOLD}Optimised Portfolio (Max Sharpe){RESET}
    Return   : {GREEN}{optimized['max_sharpe'].portfolio_return:.5f}{RESET}
    Risk     : {GREEN}{optimized['max_sharpe'].portfolio_std:.5f}{RESET}
    Sharpe   : {GREEN}{optimized['max_sharpe'].sharpe_ratio:.5f}{RESET}

  {BOLD}ML Predicted Next Period{RESET}""")

    for _, row_data in ml_results.predictions.iterrows():
        print(
            f"    [{row_data['Model']}]\n"
            f"      Return : {GREEN}{row_data['Predicted_Return']:.5f}{RESET}\n"
            f"      Risk   : {GREEN}{row_data['Predicted_Std']:.5f}{RESET}\n"
            f"      Sharpe : {GREEN}{row_data['Predicted_Sharpe']:.5f}{RESET}\n"
        )

    outputs = list(OUTPUTS_DIR.glob("*")) if OUTPUTS_DIR.exists() else []
    if outputs:
        print(f"  {BOLD}Output Files{RESET}")
        for f in sorted(outputs):
            print(f"    • {f.name}")

    print(f"\n  {DIM}Pipeline completed in {elapsed:.1f}s{RESET}")
    print(f"{CYAN}{BOLD}{'═' * 60}{RESET}\n")


if __name__ == "__main__":
    main()
