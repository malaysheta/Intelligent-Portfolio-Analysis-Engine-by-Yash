"""
config/settings.py
──────────────────
Loads environment variables from .env and exposes typed constants
for use throughout the project.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Resolve paths relative to the project root (one level up from config/)
PROJECT_ROOT: Path = Path(__file__).parent.parent
DATA_DIR: Path = PROJECT_ROOT / "data"
OUTPUTS_DIR: Path = PROJECT_ROOT / "outputs"

# Load .env from project root
load_dotenv(PROJECT_ROOT / ".env")

# ── Risk & simulation parameters ────────────────────────────────────────────
RISK_FREE_RATE: float = float(os.getenv("RISK_FREE_RATE", "0.05"))
MONTE_CARLO_SIMULATIONS: int = int(os.getenv("MONTE_CARLO_SIMULATIONS", "10000"))
RANDOM_STATE: int = int(os.getenv("RANDOM_STATE", "42"))

# ── Excel data file ──────────────────────────────────────────────────────────
# Auto-discover: check data/ first, then the parent folder (where the original lives)
EXCEL_FILENAME: str = os.getenv(
    "EXCEL_FILENAME", "Multiple Stock Portfolio - Min S.D.xlsx"
)

def _find_excel() -> Path:
    """Search for the Excel file in data/ then the parent directory."""
    candidates = [
        DATA_DIR / EXCEL_FILENAME,
        PROJECT_ROOT.parent / EXCEL_FILENAME,   # d:\PlaceMent\yash\
        Path(os.getenv("EXCEL_PATH", "")) if os.getenv("EXCEL_PATH") else None,
    ]
    for p in candidates:
        if p and p.exists():
            return p
    # Return default (data_loader will handle missing file gracefully)
    return DATA_DIR / EXCEL_FILENAME

EXCEL_PATH: Path = _find_excel()

# ── Stock ticker labels ──────────────────────────────────────────────────────
STOCK_NAMES: list[str] = ["Divi's", "TD Power", "Godrej", "Coforge", "CDSL"]

# ── ML parameters ────────────────────────────────────────────────────────────
TRAIN_TEST_SPLIT: float = 0.80
N_SYNTHETIC_SAMPLES: int = 5000   # synthetic weight-perturbed portfolios for ML

# ── Plot style ───────────────────────────────────────────────────────────────
PLOT_DPI: int = 150
