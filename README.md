# 퀀트 전략 연구 및 매매 지원 플랫폼

FastAPI 백엔드와 React/Vite 프론트엔드로 구성된 전략 연구, 백테스트, 수동 매매 지원 플랫폼입니다. 자동매매 주문 전송은 구현하지 않습니다. 사용자는 매일 시장 데이터를 갱신하고, 오늘의 LOC 종가 지정가 매수 가격과 수량, 매도 후보, 보유 포지션, 거래내역을 확인한 뒤 실제 증권사 주문은 직접 처리합니다.

## 주요 구성

- Backend: FastAPI, SQLAlchemy, SQLite
- Frontend: React, TypeScript, Vite
- Chart: Lightweight Charts
- Market Data: FinanceDataReader 기반 Yahoo Finance/시장 데이터 조회
- Architecture: Repository Pattern, Service Layer, DTO, Domain Layer, Strategy Engine, Backtest Engine 분리

## 로컬 실행

백엔드:

```powershell
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --host 127.0.0.1 --port 8000
```

프론트엔드:

```powershell
cd frontend
npm install
npm run dev -- --host 127.0.0.1 --port 5173
```

접속 주소:

- Backend health: `http://127.0.0.1:8000/api/health`
- Frontend: `http://127.0.0.1:5173`

## 운영 흐름

1. 대시보드에서 전략 설정을 선택합니다.
2. `시장 데이터 갱신`을 눌러 투자 종목과 QQQ RSI 기준 데이터를 명시적으로 갱신합니다.
3. `운용 모드`에서 QQQ 주간 RSI 추천 모드와 확정 모드를 비교합니다.
4. 추천을 그대로 쓸 경우 `추천 적용`을 누르고, 판단이 다르면 안전/공세 모드를 직접 확정합니다.
5. `오늘의 LOC 매수`에서 전일 종가 기준 LOC 지정가, 매수 수량, 필요 현금, 차단 사유를 확인합니다.
6. 실제 증권사에는 사용자가 직접 LOC 또는 종가 기준 주문을 넣습니다.
7. 실제 체결 결과가 시스템 계산과 다르면 거래/포지션 화면에서 수동 또는 보정 거래로 기록합니다.

## LOC 매수 기준

- LOC 지정가 = 전일 종가 × `(1 + 확정 모드 매수조건 / 100)`
- 1회 배정금 = Capital ÷ 확정 모드 분할수
- 수량 = `floor(1회 배정금 ÷ LOC 지정가)`
- 수수료는 필요 현금과 백테스트 결과에 반영됩니다.
- 백테스트에서는 당일 종가가 LOC 지정가 이하일 때만 체결되며, 체결가는 당일 종가입니다. 당일 저가가 지정가 아래로 내려가도 종가가 지정가보다 높으면 체결되지 않습니다.

## RSI 모드

현재 Dynamic Wave 전략의 모드 추천은 QQQ 주간 RSI(14)를 사용합니다.

- RSI는 휴장일을 제외한 주간 마지막 종가 기준으로 계산합니다.
- 이번 주와 저번 주 RSI를 비교해 다음 주 적용 모드를 추천합니다.
- 추천 모드는 자동으로 확정되지 않습니다. 사용자가 직접 적용하거나 안전/공세를 수동 선택해야 합니다.

## 백테스트

백테스트 요청은 다음 모드 정책을 지원합니다.

- `fixed_safe`: 전체 기간 안전 모드
- `fixed_aggressive`: 전체 기간 공세 모드
- `weekly_rsi`: 주간 QQQ RSI 추천을 다음 주부터 적용

일별 스냅샷 CSV에는 자산, 현금, 누적 수수료와 함께 적용 모드와 규칙 코드가 포함됩니다.

## Docker Compose

```powershell
docker compose up --build
```

- Backend: `http://localhost:8000`
- Frontend: `http://localhost:5173`
- SQLite 볼륨: `quant-data`

중지:

```powershell
docker compose down
```

볼륨까지 삭제:

```powershell
docker compose down -v
```

## 검증

백엔드 테스트:

```powershell
cd backend
uv run pytest -q
```

프론트엔드 빌드:

```powershell
cd frontend
npm run build
```

## 주의

이 플랫폼은 매매 의사결정을 돕는 도구입니다. 증권사 주문, 자동 체결, 계좌 연동 기능은 제공하지 않습니다. 시장 데이터 제공자의 지연, 누락, 수정 데이터 가능성을 고려해 실제 주문 전에는 증권사 화면의 가격과 체결 상태를 확인해야 합니다.
