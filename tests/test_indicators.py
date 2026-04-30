"""
지표 단위 테스트.
- 네트워크 없이 합성 OHLCV 로 모든 지표 계산이 정상 동작/범위 내인지 검증.
- pytest 없이 단독 실행 가능: `python -m tests.test_indicators` 또는 `python tests/test_indicators.py`
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

# 프로젝트 루트를 path 에 추가 (단독 실행 시)
ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from indicators.trend import sma, ema, macd, adx, add_moving_averages
from indicators.momentum import rsi, stochastic
from indicators.volatility import atr, bollinger, true_range
from indicators.volume import obv, volume_ratio
from indicators import compute_all


def make_synthetic(n: int = 400, seed: int = 42) -> pd.DataFrame:
    """기하 브라운 운동 + intraday 노이즈로 그럴듯한 OHLCV 생성."""
    rng = np.random.default_rng(seed)
    rets = rng.normal(0.0005, 0.015, n)
    close = 70_000 * np.exp(np.cumsum(rets))
    intraday_noise = rng.normal(0, 0.008, n)
    high = close * (1 + np.abs(intraday_noise))
    low = close * (1 - np.abs(intraday_noise))
    open_ = close * (1 + rng.normal(0, 0.003, n))
    # open/close 가 high-low 안에 들도록 보정
    high = np.maximum.reduce([high, open_, close])
    low = np.minimum.reduce([low, open_, close])
    volume = rng.integers(5_000_000, 30_000_000, n)
    trading_value = (volume * close).astype(np.int64)
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": volume,
            "trading_value": trading_value,
        },
        index=idx,
    )


def test_sma_exact():
    df = make_synthetic()
    s = sma(df["close"], 20)
    expected = df["close"].iloc[-20:].mean()
    assert np.isclose(s.iloc[-1], expected), f"SMA 불일치: {s.iloc[-1]} vs {expected}"
    # NaN 처리: 처음 19개는 NaN
    assert s.iloc[:19].isna().all()
    assert not s.iloc[19:].isna().any()
    print(f"  ✓ SMA(20) exact match: {s.iloc[-1]:,.0f}")


def test_ema_smoothing():
    df = make_synthetic()
    e = ema(df["close"], 20)
    # EMA 는 처음부터 값이 있어야 함 (adjust=False)
    assert not e.isna().any()
    # EMA 는 SMA 보다 최근 가격에 민감 → 변동성 더 큼
    print(f"  ✓ EMA(20) computed, last = {e.iloc[-1]:,.0f}")


def test_rsi_range():
    df = make_synthetic()
    r = rsi(df["close"], 14).dropna()
    assert (r >= 0).all() and (r <= 100).all(), f"RSI 범위 이탈: {r.min()}~{r.max()}"
    print(f"  ✓ RSI(14) range = [{r.min():.1f}, {r.max():.1f}]")


def test_rsi_edge_no_loss():
    """무손실 단조증가 시리즈에서 RSI = 100 인지 확인."""
    s = pd.Series(np.linspace(100, 200, 50))
    r = rsi(s, 14).dropna()
    # 마지막 RSI 는 100 에 매우 근접해야 함
    assert r.iloc[-1] > 99, f"단조증가 RSI 가 100 근처여야 함: {r.iloc[-1]}"
    print(f"  ✓ RSI 단조증가 = {r.iloc[-1]:.2f}")


def test_macd_structure():
    df = make_synthetic()
    m = macd(df["close"]).dropna()
    assert set(m.columns) == {"macd", "macd_signal", "macd_hist"}
    # hist = macd - signal 이어야 함
    assert np.allclose(m["macd_hist"], m["macd"] - m["macd_signal"])
    print(f"  ✓ MACD identity hist = macd - signal 검증")


def test_stochastic_range():
    df = make_synthetic()
    st = stochastic(df["high"], df["low"], df["close"]).dropna()
    assert st["stoch_k"].between(0, 100).all()
    assert st["stoch_d"].between(0, 100).all()
    print(f"  ✓ Stochastic %K = [{st['stoch_k'].min():.1f}, {st['stoch_k'].max():.1f}]")


def test_bollinger_ordering():
    df = make_synthetic()
    bb = bollinger(df["close"]).dropna()
    assert (bb["bb_upper"] >= bb["bb_mid"]).all()
    assert (bb["bb_mid"] >= bb["bb_lower"]).all()
    # %B 가 0~1 사이가 통상적이지만 밴드 밖 데이터도 존재 → 그냥 finite 확인
    assert np.isfinite(bb["bb_pctb"]).all()
    print(f"  ✓ Bollinger 상단≥중심≥하단 ordering OK")


def test_atr_positive():
    df = make_synthetic()
    a = atr(df["high"], df["low"], df["close"]).dropna()
    assert (a > 0).all(), "ATR 은 항상 양수여야 함"
    print(f"  ✓ ATR(14) last = {a.iloc[-1]:.0f}")


def test_adx_range():
    df = make_synthetic()
    a = adx(df["high"], df["low"], df["close"]).dropna()
    assert a["adx"].between(0, 100).all()
    assert a["plus_di"].between(0, 100).all()
    assert a["minus_di"].between(0, 100).all()
    print(f"  ✓ ADX(14) last = {a['adx'].iloc[-1]:.1f}, +DI={a['plus_di'].iloc[-1]:.1f}, -DI={a['minus_di'].iloc[-1]:.1f}")


def test_obv_correctness():
    """OBV 가 정의대로 누적되는지 손계산으로 검증."""
    close = pd.Series([100, 102, 101, 101, 105])
    volume = pd.Series([10, 20, 30, 40, 50])
    o = obv(close, volume)
    # 첫날: 0 (이전 없음)
    # 2일차: 102>100 → +20
    # 3일차: 101<102 → -30 → 누적 -10
    # 4일차: 101==101 → 0  → 누적 -10
    # 5일차: 105>101 → +50 → 누적 40
    expected = [0.0, 20.0, -10.0, -10.0, 40.0]
    assert np.allclose(o.values, expected), f"OBV 불일치: {o.values} vs {expected}"
    print(f"  ✓ OBV 손계산 일치")


def test_compute_all_smoke():
    """compute_all 이 모든 컬럼을 추가하고 NaN 채워지는 지점이 합리적인지."""
    df = make_synthetic(n=500)
    out = compute_all(df)
    added = [c for c in out.columns if c not in df.columns]
    print(f"  ✓ compute_all → {len(added)}개 지표 컬럼 추가")
    # 200일선이 있으면 마지막 행은 모든 지표가 채워져 있어야 함
    last_nan = out.iloc[-1].isna().sum()
    assert last_nan == 0, f"마지막 행에 NaN {last_nan}개 → 워밍업 부족"


def main():
    tests = [
        ("SMA exact",          test_sma_exact),
        ("EMA smoothing",      test_ema_smoothing),
        ("RSI range",          test_rsi_range),
        ("RSI 무손실 케이스",  test_rsi_edge_no_loss),
        ("MACD identity",      test_macd_structure),
        ("Stochastic range",   test_stochastic_range),
        ("Bollinger ordering", test_bollinger_ordering),
        ("ATR positive",       test_atr_positive),
        ("ADX range",          test_adx_range),
        ("OBV 손계산",         test_obv_correctness),
        ("compute_all smoke",  test_compute_all_smoke),
    ]
    print(f"\n=== 지표 단위 테스트 ({len(tests)}개) ===\n")
    for name, fn in tests:
        try:
            fn()
        except AssertionError as e:
            print(f"  ✗ {name} FAILED: {e}")
            return 1
        except Exception as e:
            print(f"  ✗ {name} ERROR: {type(e).__name__}: {e}")
            return 1
    print("\n✅ 전체 테스트 통과\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
