"""
모멘텀 지표: RSI(Wilder), Slow Stochastic.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def rsi(close: pd.Series, period: int = 14) -> pd.Series:
    """
    Wilder's RSI. (단순 평균이 아닌 EMA(alpha=1/period) 평균)
    값 범위: 0~100.
    """
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    out = 100 - (100 / (1 + rs))
    # avg_loss == 0 (무손실 구간) 인 경우 RSI = 100
    out = out.where(avg_loss != 0, 100.0)
    return out


def stochastic(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    k_period: int = 14,
    k_smooth: int = 3,
    d_period: int = 3,
) -> pd.DataFrame:
    """
    Slow Stochastic.
    fast_k = 100 * (C - LL) / (HH - LL)
    slow_k = SMA(fast_k, k_smooth)
    slow_d = SMA(slow_k, d_period)
    """
    lowest = low.rolling(k_period).min()
    highest = high.rolling(k_period).max()
    denom = (highest - lowest).replace(0, np.nan)
    fast_k = 100 * (close - lowest) / denom
    slow_k = fast_k.rolling(k_smooth).mean()
    slow_d = slow_k.rolling(d_period).mean()
    return pd.DataFrame({"stoch_k": slow_k, "stoch_d": slow_d})
