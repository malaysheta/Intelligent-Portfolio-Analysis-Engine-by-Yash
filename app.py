"""
app.py
──────
Flask backend for the Portfolio ML Web Frontend.

Endpoints:
    GET  /                          → serve the SPA (index.html)
    GET  /api/stocks/search?q=      → Yahoo Finance ticker autocomplete
    POST /api/run-analysis          → full pipeline, returns JSON results
"""

from __future__ import annotations

import json
import logging
import sys
import traceback
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_from_directory
from flask_cors import CORS

# ── Ensure project root is on sys.path ────────────────────────────────────────
PROJECT_ROOT = Path(__file__).parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.yahoo_finance_loader import search_tickers, fetch_portfolio_data
from src.portfolio_metrics import portfolio_summary
from src.optimizer import run_all_optimizations
from src.monte_carlo import run_monte_carlo
from src.ml_model import train_and_predict

import numpy as np

# ── App setup ─────────────────────────────────────────────────────────────────
app = Flask(
    __name__,
    static_folder=str(PROJECT_ROOT / "frontend"),
    static_url_path="/static",
)
CORS(app)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _safe_float(v) -> float:
    """Return a JSON-safe float (nan/inf → 0.0)."""
    try:
        f = float(v)
        return 0.0 if (f != f or f == float("inf") or f == float("-inf")) else f
    except Exception:
        return 0.0


class _NpEncoder(json.JSONEncoder):
    """JSON encoder that handles NumPy scalars and arrays."""
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return _safe_float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        return super().default(obj)


# ── Routes ────────────────────────────────────────────────────────────────────

@app.route("/")
def index():
    """Serve the main SPA HTML file."""
    return send_from_directory(str(PROJECT_ROOT / "frontend"), "index.html")


@app.route("/api/stocks/search")
def stocks_search():
    """
    GET /api/stocks/search?q=<query>
    Returns a list of matching Yahoo Finance tickers.
    """
    query = request.args.get("q", "").strip()
    if len(query) < 1:
        return jsonify([])
    results = search_tickers(query, max_results=8)
    return jsonify(results)


@app.route("/api/run-analysis", methods=["POST"])
def run_analysis():
    """
    POST /api/run-analysis
    Body (JSON):
        tickers     : list[str]   — Yahoo Finance ticker symbols
        start_date  : str         — 'YYYY-MM-DD'
        end_date    : str         — 'YYYY-MM-DD'
        weights     : dict        — {ticker: weight} (will be normalised)
        risk_free_rate     : float  (default 0.05)
        n_simulations      : int    (default 5000)
        n_synthetic        : int    (default 3000)
    """
    try:
        body = request.get_json(force=True) or {}
        tickers: list[str]  = body.get("tickers", [])
        start_date: str     = body.get("start_date", "2020-01-01")
        end_date: str       = body.get("end_date",   "2024-12-31")
        weights_raw: dict   = body.get("weights", {})
        risk_free_rate: float = float(body.get("risk_free_rate", 0.05))
        n_simulations: int    = int(body.get("n_simulations", 5000))
        n_synthetic: int      = int(body.get("n_synthetic", 3000))

        if not tickers:
            return jsonify({"error": "No tickers provided"}), 400

        # ── 1. Fetch Yahoo Finance data ───────────────────────────────────────
        data = fetch_portfolio_data(
            tickers=tickers,
            start_date=start_date,
            end_date=end_date,
            weights=weights_raw if weights_raw else None,
        )

        stocks       = data["stocks"]
        w_arr        = data["weights_array"]
        r_arr        = data["returns_array"]
        cov_arr      = data["covariance_matrix"]
        corr_mat     = data["correlation_matrix"]

        # ── 2. Portfolio metrics ──────────────────────────────────────────────
        metrics = portfolio_summary(w_arr, r_arr, cov_arr, risk_free_rate)

        # ── 3. Optimisation ───────────────────────────────────────────────────
        optimized = run_all_optimizations(stocks, r_arr, cov_arr, risk_free_rate)

        def _opt_to_dict(opt) -> dict:
            return {
                "return":  _safe_float(opt.portfolio_return),
                "std":     _safe_float(opt.portfolio_std),
                "sharpe":  _safe_float(opt.sharpe_ratio),
                "weights": {s: _safe_float(v) for s, v in opt.weights.items()},
                "success": opt.success,
            }

        # ── 4. ML Prediction ─────────────────────────────────────────────────
        predictions_csv = PROJECT_ROOT / "outputs" / "predictions_web.csv"
        predictions_csv.parent.mkdir(parents=True, exist_ok=True)

        try:
            ml_results = train_and_predict(
                base_weights=w_arr,
                asset_returns=r_arr,
                cov_matrix=cov_arr,
                risk_free_rate=risk_free_rate,
                n_samples=n_synthetic,
                test_size=0.20,
                random_state=42,
                output_path=predictions_csv,
            )
            ml_preds = []
            for _, row in ml_results.predictions.iterrows():
                ml_preds.append({
                    "model":  str(row["Model"]),
                    "return": _safe_float(row["Predicted_Return"]),
                    "std":    _safe_float(row["Predicted_Std"]),
                    "sharpe": _safe_float(row["Predicted_Sharpe"]),
                })
        except Exception as ml_err:
            logger.warning("ML prediction failed: %s", ml_err)
            ml_preds = []

        # ── 5. Monte Carlo ────────────────────────────────────────────────────
        mc = run_monte_carlo(
            stocks=stocks,
            asset_returns=r_arr,
            cov_matrix=cov_arr,
            risk_free_rate=risk_free_rate,
            n_simulations=n_simulations,
            random_state=42,
        )

        # Sample max 2000 points for the frontend scatter chart
        mc_df = mc.df[["portfolio_std", "portfolio_return", "sharpe_ratio"]].copy()
        if len(mc_df) > 2000:
            mc_df = mc_df.sample(2000, random_state=42)

        mc_scatter = [
            {
                "x": _safe_float(row["portfolio_std"]),
                "y": _safe_float(row["portfolio_return"]),
                "sharpe": _safe_float(row["sharpe_ratio"]),
            }
            for _, row in mc_df.iterrows()
        ]

        # ── 6. Assemble response ──────────────────────────────────────────────
        result = {
            "stocks": stocks,
            "data_points": data["data_points"],
            "date_range": data["date_range"],

            "current_portfolio": {
                "return":    _safe_float(metrics["portfolio_return"]),
                "std":       _safe_float(metrics["portfolio_std"]),
                "variance":  _safe_float(metrics["portfolio_variance"]),
                "sharpe":    _safe_float(metrics["sharpe_ratio"]),
                "weights":   {s: _safe_float(w) for s, w in data["weights"].items()},
                "asset_returns": {s: _safe_float(r) for s, r in data["returns"].items()},
            },

            "optimization": {
                "min_variance": _opt_to_dict(optimized["min_variance"]),
                "max_return":   _opt_to_dict(optimized["max_return"]),
                "max_sharpe":   _opt_to_dict(optimized["max_sharpe"]),
            },

            "ml_predictions": ml_preds,

            "monte_carlo": {
                "n_simulations": n_simulations,
                "scatter": mc_scatter,
                "min_risk": {
                    "return": _safe_float(mc.min_std_portfolio["portfolio_return"]),
                    "std":    _safe_float(mc.min_std_portfolio["portfolio_std"]),
                    "sharpe": _safe_float(mc.min_std_portfolio["sharpe_ratio"]),
                },
                "max_sharpe": {
                    "return": _safe_float(mc.max_sharpe_portfolio["portfolio_return"]),
                    "std":    _safe_float(mc.max_sharpe_portfolio["portfolio_std"]),
                    "sharpe": _safe_float(mc.max_sharpe_portfolio["sharpe_ratio"]),
                },
            },

            "correlation_matrix": {
                "labels": stocks,
                "data": [[_safe_float(corr_mat[i][j]) for j in range(len(stocks))]
                         for i in range(len(stocks))],
            },

            "price_history": data.get("price_history", []),
        }

        return app.response_class(
            response=json.dumps(result, cls=_NpEncoder),
            status=200,
            mimetype="application/json",
        )

    except Exception as exc:
        logger.error("run-analysis failed:\n%s", traceback.format_exc())
        return jsonify({"error": str(exc)}), 500


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print("\n" + "=" * 55)
    print("  Portfolio ML -- Web Server")
    print("  http://localhost:5000")
    print("=" * 55 + "\n")
    app.run(debug=True, port=5000, use_reloader=False)
