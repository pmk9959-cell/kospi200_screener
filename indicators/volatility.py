"""
변동성 지표: ATR (Wilder), Bollinger Bands.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def true_range(high: pd.Series, low: pd.Series, close: pd.Series) -> pd.Series:
    prev_close = close.shift()
    return pd.concat([
        high - low,
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)


def atr(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.Series:
    """Wilder's ATR. 손절가 산정의 핵심 지표."""
    tr = true_range(high, low, close)
    return tr.ewm(alpha=1 / period, adjust=False).mean()


def bollinger(
    close: pd.Series,
    period: int = 20,
    std_mult: float = 2.0,
) -> pd.DataFrame:
    """
    표준 볼린저밴드.
    bb_pctb : (close - lower) / (upper - lower)  # 0~1 사이가 정상범위
    bb_width: (upper - lower) / mid              # 변동성 압축/확장 지표
    """
    mid = close.rolling(period).mean()
    std = close.rolling(period).std(ddof=0)   # 모집단 표준편차 (관용적)
    upper = mid + std_mult * std
    lower = mid - std_mult * std
    band = (upper - lower).replace(0, np.nan)

    return pd.DataFrame({
        "bb_mid": mid,
        "bb_upper": upper,
        "bb_lower": lower,
        "bb_width": band / mid,
        "bb_pctb": (close - lower) / band,
    })
