"""
Phase 1 end-to-end 검증 스크립트.

흐름:
  1) KOSPI 200 종목 마스터에서 005930(삼성전자) 존재 확인
  2) 최근 ~400 영업일 OHLCV 수집 (pykrx → FDR fallback)
  3) pykrx 펀더멘털 (PER/PBR/EPS/BPS/DIV) 수집
  4) compute_all 로 전 지표 계산
  5) 마지막 행 요약 + 캐시 위치 출력

사용:
    python main.py                    # 기본: 005930 (삼성전자)
    python main.py 000660             # SK하이닉스
    python main.py 005930 200         # 200영업일치
"""
from __future__ import annotations

import sys
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from data.fetcher import (
    get_kospi200_tickers,
    get_ohlcv,
    get_fundamental,
    get_market_cap,
    get_ticker_name,
)
from data.cache import CACHE_DIR
from indicators import compute_all


def fmt_won(x) -> str:
    try:
        return f"{int(x):,}원"
    except Exception:
        return str(x)


def run(ticker: str = "005930", lookback_days: int = 400, check_universe: bool = True) -> pd.DataFrame:
    name = get_ticker_name(ticker)
    print(f"\n{'='*70}")
    print(f"  Phase 1 검증 — {ticker} ({name})")
    print(f"{'='*70}\n")

    # ── 1) 유니버스 확인 ──
    if check_universe:
        print("[1/4] KOSPI 200 종목 마스터 조회…")
        try:
            tickers = get_kospi200_tickers()
            print(f"      → {len(tickers)}개 종목 (예: {tickers[:5]} …)")
            if ticker not in tickers:
                print(f"      ⚠ {ticker} 가 KOSPI 200 에 없습니다 (편입 변경 또는 코드 오류)")
        except Exception as e:
            print(f"      ⚠ 유니버스 조회 실패: {e}")

    # ── 2) OHLCV ──
    end_dt = datetime.now()
    start_dt = end_dt - timedelta(days=int(lookback_days * 1.5))   # 영업일 보정
    start = start_dt.strftime("%Y-%m-%d")
    end = end_dt.strftime("%Y-%m-%d")

    print(f"\n[2/4] OHLCV 수집  ({start} ~ {end})")
    df = get_ohlcv(ticker, start, end)
    print(f"      → {len(df)} 영업일, 기간: {df.index.min().date()} ~ {df.index.max().date()}")
    print(f"      → 컬럼: {list(df.columns)}")
    print("\n      [최근 5일]")
    print(df.tail(5).to_string())

    # ── 3) 펀더멘털 ──
    print(f"\n[3/4] 펀더멘털 (pykrx)")
    try:
        fund = get_fundamental(ticker)
        if fund.empty:
            print("      ⚠ 펀더멘털 데이터 없음 (장중 또는 휴장)")
        else:
            row = fund.iloc[-1]
            print(f"      → 기준일: {fund.index[-1].date()}")
            for k, v in row.items():
                print(f"        {k}: {v}")
    except Exception as e:
        print(f"      ⚠ 펀더멘털 조회 실패: {e}")

    try:
        cap = get_market_cap(ticker)
        if cap:
            print("\n      [시가총액 정보]")
            for k, v in cap.items():
                print(f"        {k}: {fmt_won(v) if k in ('시가총액','거래대금') else v}")
    except Exception as e:
        print(f"      ⚠ 시총 조회 실패: {e}")

    # ── 4) 지표 ──
    print(f"\n[4/4] 보조지표 계산 (compute_all)")
    enriched = compute_all(df)
    added = [c for c in enriched.columns if c not in df.columns]
    print(f"      → 추가된 지표 컬럼 {len(added)}개:")
    for i in range(0, len(added), 6):
        print("        " + ", ".join(added[i:i+6]))

    print("\n      [최근일 지표 스냅샷]")
    last = enriched.iloc[-1]
    snapshot = {
        "종가":           f"{last['close']:,.0f}",
        "5일선":          f"{last['ma5']:,.0f}",
        "20일선":         f"{last['ma20']:,.0f}",
        "60일선":         f"{last['ma60']:,.0f}",
        "120일선":        f"{last['ma120']:,.0f}",
        "200일선":        f"{last['ma200']:,.0f}" if pd.notna(last['ma200']) else "(데이터 부족)",
        "RSI(14)":        f"{last['rsi14']:.1f}",
        "MACD":           f"{last['macd']:.1f}",
        "MACD signal":    f"{last['macd_signal']:.1f}",
        "MACD hist":      f"{last['macd_hist']:.1f}",
        "Stoch %K":       f"{last['stoch_k']:.1f}",
        "Stoch %D":       f"{last['stoch_d']:.1f}",
        "ATR(14)":        f"{last['atr14']:,.0f}",
        "BB %B":          f"{last['bb_pctb']:.2f}",
        "BB width":       f"{last['bb_width']:.3f}",
        "ADX(14)":        f"{last['adx']:.1f}",
        "+DI":            f"{last['plus_di']:.1f}",
        "-DI":            f"{last['minus_di']:.1f}",
        "OBV":            f"{last['obv']:,.0f}",
        "거래량비(5)":    f"{last['vol_ratio_5']:.2f}x",
        "거래량비(20)":   f"{last['vol_ratio_20']:.2f}x",
    }
    if "tv_ma20" in enriched.columns and pd.notna(last["tv_ma20"]):
        snapshot["20일평균거래대금"] = fmt_won(last["tv_ma20"])

    width = max(len(k) for k in snapshot)
    for k, v in snapshot.items():
        print(f"        {k:<{width}}  {v}")

    print(f"\n      캐시 위치: {CACHE_DIR}")
    print(f"\n{'='*70}")
    print(f"  ✅ Phase 1 완료 — {len(enriched)}행 × {len(enriched.columns)}컬럼")
    print(f"{'='*70}\n")

    return enriched


if __name__ == "__main__":
    args = sys.argv[1:]
    ticker = args[0] if len(args) >= 1 else "005930"
    lookback = int(args[1]) if len(args) >= 2 else 400
    run(ticker=ticker, lookback_days=lookback)
