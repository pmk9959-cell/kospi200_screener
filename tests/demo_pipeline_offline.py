"""
오프라인 데모.
샌드박스에서 KRX/Yahoo 에 접근할 수 없으므로, 합성 OHLCV 로 main.py 와
동일한 indicators 파이프라인을 돌려 출력 포맷을 미리 확인.

사용자는 로컬에서 `python main.py 005930` 으로 실제 데이터로 동일 출력 확인.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from indicators import compute_all
from tests.test_indicators import make_synthetic


def main():
    print("\n" + "="*70)
    print("  Phase 1 출력 포맷 미리보기 (합성 데이터)")
    print("="*70 + "\n")

    df = make_synthetic(n=500)
    print(f"[합성 OHLCV] {len(df)}행, {df.index.min().date()} ~ {df.index.max().date()}\n")
    print(df.tail(3).to_string())

    enriched = compute_all(df)
    added = [c for c in enriched.columns if c not in df.columns]
    print(f"\n[compute_all] 지표 컬럼 {len(added)}개 추가:")
    for i in range(0, len(added), 6):
        print("  " + ", ".join(added[i:i+6]))

    last = enriched.iloc[-1]
    snapshot = {
        "종가":           f"{last['close']:,.0f}",
        "5일선":          f"{last['ma5']:,.0f}",
        "20일선":         f"{last['ma20']:,.0f}",
        "60일선":         f"{last['ma60']:,.0f}",
        "120일선":        f"{last['ma120']:,.0f}",
        "200일선":        f"{last['ma200']:,.0f}",
        "RSI(14)":        f"{last['rsi14']:.1f}",
        "MACD / signal":  f"{last['macd']:.1f} / {last['macd_signal']:.1f}",
        "Stoch %K / %D":  f"{last['stoch_k']:.1f} / {last['stoch_d']:.1f}",
        "ATR(14)":        f"{last['atr14']:,.0f}",
        "BB %B":          f"{last['bb_pctb']:.2f}",
        "BB width":       f"{last['bb_width']:.3f}",
        "ADX / +DI / -DI": f"{last['adx']:.1f} / {last['plus_di']:.1f} / {last['minus_di']:.1f}",
        "OBV":            f"{last['obv']:,.0f}",
        "거래량비(5/20)": f"{last['vol_ratio_5']:.2f}x / {last['vol_ratio_20']:.2f}x",
        "20일평균거래대금": f"{int(last['tv_ma20']):,}원",
    }

    print("\n[최근일 지표 스냅샷]")
    width = max(len(k) for k in snapshot)
    for k, v in snapshot.items():
        print(f"  {k:<{width}}  {v}")

    # 마지막 행 NaN 점검
    nan_count = enriched.iloc[-1].isna().sum()
    assert nan_count == 0, f"마지막 행 NaN {nan_count}개 — 워밍업 부족"
    print(f"\n✅ 데모 완료: {len(enriched)}행 × {len(enriched.columns)}컬럼, 마지막 행 NaN 0개")
    print("\n→ 로컬에서 실제 삼성전자 데이터로 검증:  python main.py 005930\n")


if __name__ == "__main__":
    main()
