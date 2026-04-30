"""
지표 통합 진입점.

사용 예:
    from indicators import compute_all
    enriched = compute_all(ohlcv_df)

`enriched` 는 원본 OHLCV + 모든 지표 컬럼을 합친 DataFrame.
"""
from __future__ import annotations

import pandas as pd

from .trend import sma, ema, add_moving_averages, macd, adx
from .momentum import rsi, stochastic
from .volatility import atr, bollinger, true_range
from .volume import obv, volume_ratio, trading_value_ma

__all__ = [
    "sma", "ema", "add_moving_averages", "macd", "adx",
    "rsi", "stochastic",
    "atr", "bollinger", "true_range",
    "obv", "volume_ratio", "trading_value_ma",
    "compute_all",
]


DEFAULT_INDICATOR_CFG = {
    "ma_periods": [5, 20, 60, 120, 200],
    "rsi_period": 14,
    "macd": {"fast": 12, "slow": 26, "signal": 9},
    "stochastic": {"k_period": 14, "k_smooth": 3, "d_period": 3},
    "bollinger": {"period": 20, "std_mult": 2.0},
    "atr_period": 14,
    "adx_period": 14,
}


def compute_all(df: pd.DataFrame, cfg: dict | None = None) -> pd.DataFrame:
    """
    OHLCV DataFrame 에 모든 지표 컬럼 추가.

    필수 컬럼: open, high, low, close, volume
    선택 컬럼: trading_value (있으면 tv_ma20 추가)
    """
    cfg = {**DEFAULT_INDICATOR_CFG, **(cfg or {})}

    required = {"open", "high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"OHLCV DF 필수 컬럼 누락: {missing}")

    out = df.copy()

    # ── 추세 ──
    out = add_moving_averages(out, periods=cfg["ma_periods"])
    m = macd(out["close"], **cfg["macd"])
    out = pd.concat([out, m], axis=1)
    a = adx(out["high"], out["low"], out["close"], period=cfg["adx_period"])
    out = pd.concat([out, a], axis=1)

    # ── 모멘텀 ──
    out[f"rsi{cfg['rsi_period']}"] = rsi(out["close"], cfg["rsi_period"])
    s = stochastic(out["high"], out["low"], out["close"], **cfg["stochastic"])
    out = pd.concat([out, s], axis=1)

    # ── 변동성 ──
    out[f"atr{cfg['atr_period']}"] = atr(
        out["high"], out["low"], out["close"], period=cfg["atr_period"]
    )
    bb = bollinger(out["close"], **cfg["bollinger"])
    out = pd.concat([out, bb], axis=1)

    # ── 거래량 ──
    out["obv"] = obv(out["close"], out["volume"])
    out["vol_ratio_5"] = volume_ratio(out["volume"], period=5)
    out["vol_ratio_20"] = volume_ratio(out["volume"], period=20)
    if "trading_value" in out.columns:
        out["tv_ma20"] = trading_value_ma(out["trading_value"], period=20)

    return out
