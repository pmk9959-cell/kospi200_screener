"""
KRX 데이터 수집 레이어.

- 1차: pykrx (KRX 공식 데이터, 거래대금/시가총액/외인보유 등 풍부)
- 2차: FinanceDataReader (pykrx 장애시 fallback)
- 모든 결과는 cache.py 를 통해 parquet 캐시
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Iterable

import pandas as pd

from .cache import cache_key, load_cache, save_cache


# ---------------- 헬퍼 ----------------

def _normalize_date(d: str) -> str:
    """YYYY-MM-DD 또는 YYYYMMDD → YYYYMMDD"""
    return d.replace("-", "")


def _to_dash(d8: str) -> str:
    """YYYYMMDD → YYYY-MM-DD"""
    return f"{d8[:4]}-{d8[4:6]}-{d8[6:]}"


# ---------------- 종목 마스터 ----------------

def get_kospi200_tickers(use_cache: bool = True, ttl_days: int = 30) -> list[str]:
    """KOSPI 200 편입 종목 코드 리스트."""
    today_month = datetime.now().strftime("%Y-%m")
    key = cache_key("kospi200_tickers", month=today_month)

    if use_cache:
        cached = load_cache(key, max_age_hours=ttl_days * 24)
        if cached is not None:
            return cached["ticker"].astype(str).tolist()

    from pykrx import stock
    tickers = stock.get_index_portfolio_deposit_file("1028")
    df = pd.DataFrame({"ticker": [str(t) for t in tickers]})
    save_cache(key, df)
    return df["ticker"].tolist()


def get_ticker_name(ticker: str) -> str:
    """종목 코드 → 종목명. (캐시 없음, 가벼운 호출)"""
    try:
        from pykrx import stock
        return stock.get_market_ticker_name(ticker)
    except Exception:
        return ticker


# ---------------- OHLCV ----------------

OHLCV_COLS = ["open", "high", "low", "close", "volume", "trading_value", "change"]


def get_ohlcv(
    ticker: str,
    start: str,
    end: str,
    use_cache: bool = True,
    ttl_hours: float = 24,
) -> pd.DataFrame:
    """
    일봉 OHLCV 조회.

    Returns
    -------
    DataFrame with columns:
        open, high, low, close, volume, trading_value, change
        index: DatetimeIndex (date)
    """
    s, e = _normalize_date(start), _normalize_date(end)
    key = cache_key("ohlcv", ticker=ticker, start=s, end=e)

    if use_cache:
        cached = load_cache(key, max_age_hours=ttl_hours)
        if cached is not None and not cached.empty:
            return cached

    df = _fetch_ohlcv_pykrx(ticker, s, e)
    if df is None or df.empty:
        df = _fetch_ohlcv_fdr(ticker, s, e)

    if df is None or df.empty:
        raise RuntimeError(f"OHLCV fetch failed for {ticker} ({s}~{e})")

    # 필수 컬럼 보강
    for col in OHLCV_COLS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[OHLCV_COLS].sort_index()
    save_cache(key, df)
    return df


def _fetch_ohlcv_pykrx(ticker: str, start8: str, end8: str) -> pd.DataFrame | None:
    try:
        from pykrx import stock
        raw = stock.get_market_ohlcv(start8, end8, ticker)
        if raw is None or raw.empty:
            return None
        # pykrx 한글 컬럼: 시가/고가/저가/종가/거래량/거래대금/등락률
        rename = {
            "시가": "open", "고가": "high", "저가": "low", "종가": "close",
            "거래량": "volume", "거래대금": "trading_value", "등락률": "change",
        }
        df = raw.rename(columns=rename)
        df.index.name = "date"
        if not isinstance(df.index, pd.DatetimeIndex):
            df.index = pd.to_datetime(df.index)
        return df
    except Exception as exc:
        print(f"  [pykrx OHLCV failed] {ticker}: {exc}")
        return None


def _fetch_ohlcv_fdr(ticker: str, start8: str, end8: str) -> pd.DataFrame | None:
    try:
        import FinanceDataReader as fdr
        df = fdr.DataReader(ticker, _to_dash(start8), _to_dash(end8))
        if df is None or df.empty:
            return None
        df = df.rename(columns={c: c.lower() for c in df.columns})
        # FDR change 는 등락률(소수)이므로 % 로 변환
        if "change" in df.columns:
            df["change"] = df["change"] * 100
        if "trading_value" not in df.columns:
            df["trading_value"] = df["close"] * df["volume"]
        df.index.name = "date"
        return df
    except Exception as exc:
        print(f"  [FDR OHLCV failed] {ticker}: {exc}")
        return None


# ---------------- 펀더멘털 (pykrx 기본) ----------------

def get_fundamental(
    ticker: str,
    date: str | None = None,
    use_cache: bool = True,
    ttl_hours: float = 24,
) -> pd.DataFrame:
    """
    pykrx 펀더멘털 (PER/PBR/EPS/BPS/DIV/DPS).
    date None 이면 오늘 → 영업일 보정.
    """
    if date is None:
        date = datetime.now().strftime("%Y%m%d")
    d = _normalize_date(date)
    key = cache_key("fundamental", ticker=ticker, date=d)

    if use_cache:
        cached = load_cache(key, max_age_hours=ttl_hours)
        if cached is not None and not cached.empty:
            return cached

    from pykrx import stock
    # pykrx 는 비영업일이면 빈 DF 반환 → 직전 7일 안에서 가용한 날 탐색
    for back in range(0, 7):
        try_date = (datetime.strptime(d, "%Y%m%d") - timedelta(days=back)).strftime("%Y%m%d")
        try:
            df = stock.get_market_fundamental(try_date, try_date, ticker)
            if df is not None and not df.empty:
                df.index = pd.to_datetime(df.index)
                save_cache(key, df)
                return df
        except Exception:
            continue
    return pd.DataFrame()


# ---------------- 시장 거래대금/시총 (선택) ----------------

def get_market_cap(ticker: str, date: str | None = None) -> dict:
    """시가총액/상장주식수 등."""
    if date is None:
        date = datetime.now().strftime("%Y%m%d")
    d = _normalize_date(date)
    from pykrx import stock
    for back in range(0, 7):
        try_date = (datetime.strptime(d, "%Y%m%d") - timedelta(days=back)).strftime("%Y%m%d")
        try:
            df = stock.get_market_cap(try_date, try_date, ticker)
            if df is not None and not df.empty:
                row = df.iloc[-1]
                return row.to_dict()
        except Exception:
            continue
    return {}
