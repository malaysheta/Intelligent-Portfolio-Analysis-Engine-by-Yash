"""
src/yahoo_finance_loader.py
───────────────────────────
Fetch real stock data from Yahoo Finance using yfinance.
Computes annualised returns and covariance matrix from daily OHLCV data.
Returns a dict compatible with the rest of the pipeline.
"""

from __future__ import annotations

import logging
from typing import Optional

import numpy as np
import pandas as pd
import yfinance as yf

logger = logging.getLogger(__name__)

TRADING_DAYS = 252  # annualisation factor


def search_tickers(query: str, max_results: int = 8) -> list[dict]:
    """
    Search Yahoo Finance for tickers matching *query*.
    Returns a list of dicts: [{symbol, name, exchange, type}, ...].
    """
    try:
        results = []
        ticker = yf.Ticker(query.upper())
        info = ticker.fast_info
        # Try direct ticker lookup first
        try:
            name = ticker.info.get("longName") or ticker.info.get("shortName", "")
            exch = ticker.info.get("exchange", "")
            if name:
                results.append({
                    "symbol": query.upper(),
                    "name": name,
                    "exchange": exch,
                    "type": "EQUITY",
                })
        except Exception:
            pass

        # Use yfinance search
        try:
            import requests
            url = (
                f"https://query2.finance.yahoo.com/v1/finance/search"
                f"?q={query}&quotesCount={max_results}&newsCount=0&listsCount=0"
            )
            headers = {"User-Agent": "Mozilla/5.0"}
            resp = requests.get(url, headers=headers, timeout=5)
            if resp.ok:
                data = resp.json()
                for item in data.get("quotes", [])[:max_results]:
                    symbol = item.get("symbol", "")
                    name = item.get("longname") or item.get("shortname", symbol)
                    exchange = item.get("exchange", "")
                    qtype = item.get("quoteType", "")
                    # Skip if duplicate
                    if any(r["symbol"] == symbol for r in results):
                        continue
                    results.append({
                        "symbol": symbol,
                        "name": name,
                        "exchange": exchange,
                        "type": qtype,
                    })
        except Exception as e:
            logger.warning("Yahoo search API failed: %s", e)

        return results[:max_results]

    except Exception as e:
        logger.error("search_tickers error: %s", e)
        return []


def fetch_portfolio_data(
    tickers: list[str],
    start_date: str,
    end_date: str,
    weights: Optional[dict[str, float]] = None,
) -> dict:
    """
    Fetch historical price data for *tickers* from Yahoo Finance and compute
    all portfolio statistics required by the ML pipeline.

    Parameters
    ----------
    tickers : list[str]
        List of Yahoo Finance ticker symbols (e.g. ['AAPL', 'MSFT']).
    start_date : str
        Start date in 'YYYY-MM-DD' format.
    end_date : str
        End date in 'YYYY-MM-DD' format.
    weights : dict[str, float] | None
        Portfolio weights keyed by ticker. If None, equal weights are used.
        Weights are normalised to sum to 1.

    Returns
    -------
    dict with keys:
        stocks, weights, weights_array, returns, returns_array,
        covariance_matrix, correlation_matrix, variance_matrix,
        covariance_df, correlation_df, portfolio_stats,
        price_history (DataFrame), daily_returns (DataFrame)
    """
    logger.info("Fetching data for %s from %s to %s", tickers, start_date, end_date)

    try:
        # Download adjusted close prices
        raw = yf.download(
            tickers,
            start=start_date,
            end=end_date,
            auto_adjust=True,
            progress=False,
        )

        if raw.empty:
            raise ValueError("No data returned from Yahoo Finance for the given parameters.")

        # Extract 'Close' column
        if isinstance(raw.columns, pd.MultiIndex):
            prices = raw["Close"]
        else:
            prices = raw[["Close"]] if "Close" in raw.columns else raw

        # Handle single ticker case
        if len(tickers) == 1:
            prices.columns = tickers

        # Drop tickers with no data
        prices = prices.dropna(axis=1, how="all")
        valid_tickers = list(prices.columns)
        if not valid_tickers:
            raise ValueError("All tickers returned empty data. Check symbols and date range.")

        missing = [t for t in tickers if t not in valid_tickers]
        if missing:
            logger.warning("No data for tickers: %s — they will be excluded.", missing)

        tickers = valid_tickers

        # Compute daily log returns
        daily_returns = np.log(prices / prices.shift(1)).dropna()

        if len(daily_returns) < 2:
            raise ValueError("Insufficient overlapping historical data for these stocks in the selected date range.")

        # Annualised mean returns
        ann_returns = daily_returns.mean() * TRADING_DAYS  # Series

        # Annualised covariance matrix
        ann_cov = daily_returns.cov() * TRADING_DAYS     # DataFrame

        # Correlation matrix
        corr = daily_returns.corr()

        # Per-asset variance (diagonal of cov)
        var_arr = np.diag(ann_cov.values)

        # Normalise weights
        n = len(tickers)
        if weights is None:
            w_dict = {t: 1.0 / n for t in tickers}
        else:
            # Keep only valid tickers, fill missing with 0
            raw_w = {t: weights.get(t, 0.0) for t in tickers}
            total = sum(raw_w.values())
            if total <= 0:
                w_dict = {t: 1.0 / n for t in tickers}
            else:
                w_dict = {t: v / total for t, v in raw_w.items()}

        w_arr = np.array([w_dict[t] for t in tickers])
        r_arr = ann_returns.values
        cov_arr = ann_cov.values

        # Current portfolio stats
        port_return = float(w_arr @ r_arr)
        port_var = float(w_arr @ cov_arr @ w_arr)
        port_std = float(np.sqrt(max(port_var, 0)))

        # Price history for chart (normalised to 100)
        try:
            base_prices = prices.bfill().iloc[0]
            price_norm = (prices / base_prices * 100).reset_index()
            price_norm = price_norm.where(pd.notnull(price_norm), None)  # Ensure NaN -> None
        except Exception:
            price_norm = prices.reset_index().where(pd.notnull(prices.reset_index()), None)

        # Convert to JSON-friendly format
        price_history = price_norm.rename(columns={"Date": "date"}).to_dict(orient="records")
        # Make dates strings
        for row in price_history:
            if hasattr(row.get("date"), "strftime"):
                row["date"] = row["date"].strftime("%Y-%m-%d")

        logger.info("Data fetched. Tickers: %s, Days: %d", tickers, len(daily_returns))

        return {
            "stocks": tickers,
            "weights": w_dict,
            "weights_array": w_arr,
            "returns": dict(zip(tickers, r_arr.tolist())),
            "returns_array": r_arr,
            "covariance_matrix": cov_arr,
            "correlation_matrix": corr.values,
            "variance_matrix": var_arr,
            "covariance_df": ann_cov,
            "correlation_df": corr,
            "portfolio_stats": {
                "portfolio_return": port_return,
                "portfolio_std": port_std,
                "sharpe_ratio": 0.0,  # filled by pipeline
            },
            "price_history": price_history,
            "daily_returns_df": daily_returns,
            "data_points": len(daily_returns),
            "date_range": {"start": start_date, "end": end_date},
        }

    except Exception as exc:
        logger.error("fetch_portfolio_data failed: %s", exc)
        raise
