"""
추세 지표: SMA / EMA / MACD / ADX (+DI/-DI)
모두 pandas-ta 가 아닌 순수 pandas 로 구현 (의존성 최소화 + 검증 용이).
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def sma(close: pd.Series, period: int) -> pd.Series:
    return close.rolling(window=period, min_periods=period).mean()


def ema(close: pd.Series, period: int) -> pd.Series:
    return close.ewm(span=period, adjust=False).mean()


def add_moving_averages(
    df: pd.DataFrame,
    periods: list[int] = (5, 20, 60, 120, 200),
    col: str = "close",
) -> pd.DataFrame:
    """원본 DF + ma{period} 컬럼들. 원본 보존."""
    out = df.copy()
    for p in periods:
        out[f"ma{p}"] = sma(df[col], p)
    return out


def macd(
    close: pd.Series,
    fast: int = 12,
    slow: int = 26,
    signal: int = 9,
) -> pd.DataFrame:
    """표준 MACD: EMA(fast) - EMA(slow), signal = EMA(MACD)."""
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    hist = macd_line - signal_line
    return pd.DataFrame({
        "macd": macd_line,
        "macd_signal": signal_line,
        "macd_hist": hist,
    })


def adx(
    high: pd.Series,
    low: pd.Series,
    close: pd.Series,
    period: int = 14,
) -> pd.DataFrame:
    """
    Welles Wilder ADX (+DI / -DI).
    Wilder's smoothing = EMA with alpha = 1/period (adjust=False).
    """
    high = high.astype(float)
    low = low.astype(float)
    close = close.astype(float)

    up_move = high.diff()
    down_move = -low.diff()

    plus_dm = pd.Series(
        np.where((up_move > down_move) & (up_move > 0), up_move, 0.0),
        index=high.index,
    )
    minus_dm = pd.Series(
        np.where((down_move > up_move) & (down_move > 0), down_move, 0.0),
        index=high.index,
    )

    prev_close = close.shift()
    tr = pd.concat([
        (high - low),
        (high - prev_close).abs(),
        (low - prev_close).abs(),
    ], axis=1).max(axis=1)

    atr_w = tr.ewm(alpha=1 / period, adjust=False).mean()
    plus_di = 100 * plus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_w.replace(0, np.nan)
    minus_di = 100 * minus_dm.ewm(alpha=1 / period, adjust=False).mean() / atr_w.replace(0, np.nan)

    di_sum = (plus_di + minus_di).replace(0, np.nan)
    dx = 100 * (plus_di - minus_di).abs() / di_sum
    adx_val = dx.ewm(alpha=1 / period, adjust=False).mean()

    return pd.DataFrame({
        "plus_di": plus_di,
        "minus_di": minus_di,
        "adx": adx_val,
    })
