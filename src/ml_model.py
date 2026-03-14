"""
src/ml_model.py
───────────────
Machine-learning module for predicting portfolio return, risk, and
Sharpe ratio.

Approach
--------
Because we only have a single historical portfolio snapshot (one Excel
file), we generate a *synthetic training dataset* by randomly perturbing
the portfolio weights around the given snapshot.  For each synthetic
portfolio we compute ground-truth labels using the known covariance
matrix and per-asset returns.  This is standard practice in portfolio ML
research when historical snapshots are unavailable.

Models
------
1. Linear Regression (baseline)
2. Random Forest Regressor (non-linear ensemble)

For each target (return / std / Sharpe) we train both models and pick the
best one by R² on the held-out test set.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import LinearRegression
from sklearn.model_selection import train_test_split, KFold
from sklearn.metrics import (
    mean_absolute_error,
    mean_absolute_percentage_error,
    mean_squared_error,
    r2_score,
)
from sklearn.preprocessing import StandardScaler

from src.portfolio_metrics import (
    calculate_portfolio_return,
    calculate_portfolio_std,
    calculate_portfolio_variance,
    calculate_sharpe_ratio,
)

logger = logging.getLogger(__name__)


# ─── Data structures ─────────────────────────────────────────────────────────

@dataclass
class MLResults:
    """Holds training metrics and predictions from ML models."""

    predictions: pd.DataFrame
    train_metrics: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)
    cv_metrics: dict[str, dict[str, dict[str, float]]] = field(default_factory=dict)
    # predictions columns: model, predicted_return, predicted_std, predicted_sharpe
    # cv_metrics structure: {label_col: {model_name: {mae_mean, mae_std, rmse_mean, ...}}}


# ─── Synthetic dataset generation ────────────────────────────────────────────

def _generate_synthetic_data(
    base_weights: np.ndarray,
    asset_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float,
    n_samples: int,
    random_state: int,
) -> pd.DataFrame:
    """
    Generate n_samples random portfolios around the given base weights.

    Each sample is a valid long-only portfolio (weights ≥ 0, sum = 1).
    Labels (return, std, sharpe) are computed analytically.

    Parameters
    ----------
    base_weights : np.ndarray
        Reference weights used to seed the Dirichlet distribution.
    n_samples : int
        Number of synthetic portfolios to generate.
    random_state : int
        RNG seed for reproducibility.

    Returns
    -------
    pd.DataFrame
        Columns: w_0 … w_{n-1}, cov features, label_return, label_std, label_sharpe.
    """
    rng = np.random.default_rng(random_state)
    n = len(base_weights)

    # Use Dirichlet sampling for valid weight vectors (long-only, sum=1)
    # concentration parameter α = 5 keeps samples close to the base
    alpha = base_weights * 10 + 0.5   # soften zeros
    weights_matrix = rng.dirichlet(alpha, size=n_samples)  # (n_samples, n)

    records = []
    for w in weights_matrix:
        ret = calculate_portfolio_return(w, asset_returns)
        var = calculate_portfolio_variance(w, cov_matrix)
        std = calculate_portfolio_std(var)
        sr = calculate_sharpe_ratio(ret, std, risk_free_rate)

        # Features: weights + upper triangle of covariance + correlations
        cov_upper = cov_matrix[np.triu_indices(n)]
        row = list(w) + list(cov_upper) + [ret, std, sr]
        records.append(row)

    # Column names
    weight_cols = [f"w_{i}" for i in range(n)]
    cov_cols = [f"cov_{i}_{j}" for i, j in zip(*np.triu_indices(n))]
    df = pd.DataFrame(
        records,
        columns=weight_cols + cov_cols + ["label_return", "label_std", "label_sharpe"],
    )
    return df


def _build_features_labels(
    df: pd.DataFrame,
    target: str,
) -> tuple[np.ndarray, np.ndarray]:
    """Split DataFrame into feature matrix X and label vector y."""
    label_cols = ["label_return", "label_std", "label_sharpe"]
    X = df.drop(columns=label_cols).values
    y = df[target].values
    return X, y


# ─── Cross-validation helper ─────────────────────────────────────────────────

def _run_cross_validation(
    X: np.ndarray,
    y: np.ndarray,
    model,
    n_folds: int = 5,
    random_state: int = 42,
) -> dict[str, float]:
    """
    Run K-Fold cross-validation and compute MAE, RMSE, MSE, R², and MAPE.

    Returns a dict with keys like 'mae_mean', 'mae_std', 'rmse_mean', etc.
    """
    from sklearn.base import clone

    kf = KFold(n_splits=n_folds, shuffle=True, random_state=random_state)
    scaler = StandardScaler()

    fold_metrics: dict[str, list[float]] = {
        "mae": [], "rmse": [], "mse": [], "r2": [], "mape": [],
    }

    for train_idx, val_idx in kf.split(X):
        X_tr, X_val = X[train_idx], X[val_idx]
        y_tr, y_val = y[train_idx], y[val_idx]

        X_tr_s = scaler.fit_transform(X_tr)
        X_val_s = scaler.transform(X_val)

        m = clone(model)
        m.fit(X_tr_s, y_tr)
        y_pred = m.predict(X_val_s)

        fold_metrics["mae"].append(mean_absolute_error(y_val, y_pred))
        fold_metrics["mse"].append(mean_squared_error(y_val, y_pred))
        fold_metrics["rmse"].append(float(np.sqrt(mean_squared_error(y_val, y_pred))))
        fold_metrics["r2"].append(r2_score(y_val, y_pred))
        # Guard MAPE against near-zero actuals
        try:
            fold_metrics["mape"].append(mean_absolute_percentage_error(y_val, y_pred))
        except Exception:
            fold_metrics["mape"].append(float("nan"))

    result: dict[str, float] = {}
    for metric_name, values in fold_metrics.items():
        arr = np.array(values)
        result[f"{metric_name}_mean"] = float(np.nanmean(arr))
        result[f"{metric_name}_std"] = float(np.nanstd(arr))
    return result


# ─── Training & prediction ────────────────────────────────────────────────────

def train_and_predict(
    base_weights: np.ndarray,
    asset_returns: np.ndarray,
    cov_matrix: np.ndarray,
    risk_free_rate: float = 0.05,
    n_samples: int = 5000,
    test_size: float = 0.20,
    random_state: int = 42,
    n_cv_folds: int = 5,
    output_path: Path | None = None,
) -> MLResults:
    """
    Train Linear Regression and Random Forest Regressor on synthetic
    portfolio data and return predictions for the base portfolio.

    Parameters
    ----------
    base_weights : np.ndarray
        Current portfolio weights (used as the prediction input).
    asset_returns : np.ndarray
        Per-asset expected returns.
    cov_matrix : np.ndarray
        Covariance matrix.
    risk_free_rate : float
        Risk-free rate.
    n_samples : int
        Number of synthetic training samples.
    test_size : float
        Fraction of data held out for testing (0.20 = 20 %).
    random_state : int
        RNG seed.
    output_path : Path | None
        If provided, save predictions.csv here.

    Returns
    -------
    MLResults
    """
    logger.info("Generating %d synthetic portfolio samples …", n_samples)
    df = _generate_synthetic_data(
        base_weights, asset_returns, cov_matrix, risk_free_rate, n_samples, random_state
    )

    n = len(base_weights)
    cov_upper = cov_matrix[np.triu_indices(n)]
    base_features = np.concatenate([base_weights, cov_upper]).reshape(1, -1)

    targets = {
        "label_return": "Predicted_Return",
        "label_std": "Predicted_Std",
        "label_sharpe": "Predicted_Sharpe",
    }

    models = {
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(
            n_estimators=200,
            max_depth=8,
            random_state=random_state,
            n_jobs=1,
        ),
    }

    results: dict[str, dict[str, float]] = {name: {} for name in models}
    train_metrics: dict[str, dict[str, dict[str, float]]] = {
        label: {name: {} for name in models} for label in targets
    }
    cv_metrics: dict[str, dict[str, dict[str, float]]] = {
        label: {name: {} for name in models} for label in targets
    }

    scaler = StandardScaler()

    for label_col, pred_name in targets.items():
        X, y = _build_features_labels(df, label_col)
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )
        X_train_s = scaler.fit_transform(X_train)
        X_test_s = scaler.transform(X_test)
        base_s = scaler.transform(base_features)

        for model_name, model in models.items():
            model.fit(X_train_s, y_train)
            y_pred_test = model.predict(X_test_s)

            mse = mean_squared_error(y_test, y_pred_test)
            r2 = r2_score(y_test, y_pred_test)
            train_metrics[label_col][model_name] = {"mse": mse, "r2": r2}

            # ── Cross-validation ──────────────────────────────────────
            cv_result = _run_cross_validation(
                X, y, model, n_folds=n_cv_folds, random_state=random_state
            )
            cv_metrics[label_col][model_name] = cv_result

            pred_val = float(model.predict(base_s)[0])
            results[model_name][pred_name] = pred_val

            logger.info(
                "  [%s → %s] R²=%.4f  MSE=%.6f  CV-MAE=%.6f  Prediction=%.6f",
                model_name, pred_name, r2, mse,
                cv_result["mae_mean"], pred_val,
            )

    # ── Build predictions DataFrame ──────────────────────────────────────
    pred_rows = []
    for model_name, preds in results.items():
        pred_rows.append({
            "Model": model_name,
            "Predicted_Return": preds["Predicted_Return"],
            "Predicted_Std": preds["Predicted_Std"],
            "Predicted_Sharpe": preds["Predicted_Sharpe"],
        })
    predictions_df = pd.DataFrame(pred_rows)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        predictions_df.to_csv(output_path, index=False)
        logger.info("Predictions saved to '%s'.", output_path)

    return MLResults(
        predictions=predictions_df,
        train_metrics=train_metrics,
        cv_metrics=cv_metrics,
    )
