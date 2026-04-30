"""
Parquet 기반 디스크 캐시.

- key = prefix_<md5(json(kwargs))>  (kwargs 순서 무관)
- TTL: 파일 mtime 기준
- 모든 호출은 DataFrame 만 다룸 (단순화)
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

CACHE_DIR = Path(__file__).resolve().parent / "cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)


def cache_key(prefix: str, **kwargs: Any) -> str:
    """안정적인 캐시 키 생성. kwargs 순서가 달라도 같은 키."""
    payload = json.dumps(kwargs, sort_keys=True, default=str)
    digest = hashlib.md5(payload.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}_{digest}"


def load_cache(key: str, max_age_hours: float | None = None) -> pd.DataFrame | None:
    """캐시에서 DataFrame 로드. 없거나 만료면 None."""
    path = CACHE_DIR / f"{key}.parquet"
    if not path.exists():
        return None
    if max_age_hours is not None:
        age = datetime.now() - datetime.fromtimestamp(path.stat().st_mtime)
        if age > timedelta(hours=max_age_hours):
            return None
    try:
        return pd.read_parquet(path)
    except Exception:
        # 손상된 캐시는 무시하고 재수집 유도
        return None


def save_cache(key: str, df: pd.DataFrame) -> None:
    path = CACHE_DIR / f"{key}.parquet"
    df.to_parquet(path)


def clear_cache(prefix: str | None = None) -> int:
    """prefix 시작 캐시 삭제 (없으면 전체)."""
    n = 0
    for p in CACHE_DIR.glob("*.parquet"):
        if prefix is None or p.name.startswith(prefix):
            p.unlink()
            n += 1
    return n
