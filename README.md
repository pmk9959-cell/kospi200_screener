# KOSPI 200 Screener — Phase 1

기획서 §11 Phase 1 (데이터 수집 + 캐시 + 보조지표) 구현체.

## 무엇이 들어있나

```
kospi200_screener/
├── config/strategies.yaml          # 전략 파라미터 (Phase 2+ 사용)
├── data/
│   ├── fetcher.py                  # pykrx 1차 / FDR 2차 OHLCV·펀더멘털 수집
│   ├── cache.py                    # parquet 기반 TTL 캐시
│   └── cache/                      # 캐시 저장 위치
├── indicators/
│   ├── trend.py                    # SMA/EMA/MACD/ADX
│   ├── momentum.py                 # RSI(Wilder)/Stochastic
│   ├── volatility.py               # ATR(Wilder)/Bollinger
│   ├── volume.py                   # OBV/거래량비/거래대금MA
│   └── __init__.py                 # compute_all() 통합 엔트리
├── tests/
│   ├── test_indicators.py          # 11개 단위 테스트 (네트워크 불필요)
│   └── demo_pipeline_offline.py    # 합성 데이터로 main 흐름 미리보기
├── main.py                         # Phase 1 end-to-end 검증 (삼성전자)
├── requirements.txt
└── README.md
```

## 빠른 시작

```bash
# 1. 의존성 설치
pip install -r requirements.txt

# 2. 지표 단위 테스트 (네트워크 불필요)
python tests/test_indicators.py

# 3. 합성 데이터 데모 (출력 포맷 미리보기)
python tests/demo_pipeline_offline.py

# 4. 실제 데이터 end-to-end (삼성전자)
python main.py
# 또는: python main.py 000660 300   # SK하이닉스, 300영업일치
```

## 산출 데이터 포맷

`compute_all(ohlcv_df)` 결과 — 원본 7개 + 지표 24개 = 총 30개 컬럼:

| 카테고리 | 컬럼 |
|---|---|
| OHLCV | `open`, `high`, `low`, `close`, `volume`, `trading_value`, `change` |
| 추세 | `ma5/20/60/120/200`, `macd`, `macd_signal`, `macd_hist`, `adx`, `plus_di`, `minus_di` |
| 모멘텀 | `rsi14`, `stoch_k`, `stoch_d` |
| 변동성 | `atr14`, `bb_mid/upper/lower`, `bb_width`, `bb_pctb` |
| 거래량 | `obv`, `vol_ratio_5`, `vol_ratio_20`, `tv_ma20` |

## 설계 원칙

- **외부 의존성 최소화** — 보조지표는 pandas/numpy만으로 직접 구현. Wilder's smoothing 등 정통 정의 준수, pandas-ta numpy 2.x 호환 이슈 회피.
- **2단계 데이터 소스** — pykrx(1차)가 실패하면 FinanceDataReader(2차)로 자동 fallback.
- **Parquet 캐시 + TTL** — OHLCV는 24시간, 종목 마스터는 30일 캐시. 동일 키 호출은 디스크 hit.
- **컬럼명 영문 통일** — pykrx 한글 컬럼(시가/고가/…)은 fetcher 단에서 영문으로 정규화.

## 검증 결과

```
=== 지표 단위 테스트 (11개) ===
  ✓ SMA(20) exact match
  ✓ EMA(20) computed
  ✓ RSI(14) range [0, 100]
  ✓ RSI 단조증가 = 100.00 (edge case)
  ✓ MACD identity hist = macd - signal
  ✓ Stochastic %K/%D in [0, 100]
  ✓ Bollinger 상단≥중심≥하단
  ✓ ATR(14) > 0
  ✓ ADX(14) in [0, 100]
  ✓ OBV 손계산 일치
  ✓ compute_all → 24개 지표 컬럼, 마지막 행 NaN 0개
```

## 알려진 한계

- pykrx는 KRX 서버에 직접 의존 → 점검/장애 시 FDR로 자동 fallback.
- `get_market_fundamental()` 은 비영업일에 빈 DataFrame을 반환 → fetcher가 7일 안에서 가용일 자동 탐색.
- 200일선이 채워지려면 최소 200영업일치 데이터 필요 → `main.py` 기본 lookback 400일.

## 다음 단계 (Phase 2)

기획서 §11 로드맵에 따라:

1. `strategies/medium_term.py` — 중기 전략 필터/스코어링
2. `screening/scorer.py` — 통합 스코어 + ATR 기반 진입/손절가
3. `backtest/engine.py` — vectorbt 인샘플 (2018-2024) 백테스트
