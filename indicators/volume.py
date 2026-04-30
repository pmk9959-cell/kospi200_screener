"""
거래량 지표: OBV, 거래량 비율, 거래대금 이동평균.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def obv(close: pd.Series, volume: pd.Series) -> pd.Series:
    """
    On-Balance Volume.
    오늘 종가 > 어제 종가  → +volume
    오늘 종가 < 어제 종가  → -volume
    동가                    →  0
    """
    direction = np.sign(close.diff()).fillna(0)
    return (direction * volume).cumsum()


def volume_ratio(volume: pd.Series, period: int = 5) -> pd.Series:
    """현재 거래량 / N일 평균 거래량. 1.5 이상이면 거래량 폭증."""
    avg = volume.rolling(period).mean()
    return volume / avg.replace(0, np.nan)


def trading_value_ma(trading_value: pd.Series, period: int = 20) -> pd.Series:
    """N일 평균 거래대금 (단기 전략 유동성 필터에 사용: 50억원 이상 등)."""
    return trading_value.rolling(period).mean()
