# 퀀트 전략 플랫폼

FastAPI 백엔드와 React/Vite 프론트엔드로 구성된 퀀트 전략 실험용 플랫폼입니다. 현재 UI는 한국어 중심으로 구성되어 있으며, 전략 설정, 라이브 신호 기록, 백테스트 실행과 결과 확인을 한 흐름에서 다룹니다.

자동 매매 주문 전송은 구현되어 있지 않습니다. 이 프로젝트는 전략 신호와 백테스트를 검토하고, 사용자가 체결 내역을 기록하는 도구입니다.

## 주요 구성

- 백엔드: FastAPI, SQLAlchemy, SQLite
- 프론트엔드: React, TypeScript, Vite
- 시장 데이터: FinanceDataReader
- 캐시: SQLite의 가격 데이터 캐시
- 전략 로직: 라이브 신호 판단과 백테스트가 같은 전략 엔진을 공유

## 백엔드 로컬 실행

```powershell
cd backend
uv sync --extra dev
uv run uvicorn app.main:app --reload
```

기본 API 주소는 `http://localhost:8000`입니다. 헬스 체크는 `GET /api/health`에서 확인할 수 있습니다.

환경 변수는 `QUANT_` 접두사를 사용합니다.

```powershell
$env:QUANT_DATABASE_URL="sqlite:///./quant_platform.db"
$env:QUANT_DEFAULT_OWNER_ID="default"
$env:QUANT_MARKET_DATA_PROVIDER="finance_data_reader"
```

## 프론트엔드 로컬 실행

```powershell
cd frontend
npm install
npm run dev
```

기본 화면 주소는 `http://localhost:5173`입니다. API 주소를 바꾸려면 `VITE_API_BASE_URL`을 설정합니다.

```powershell
$env:VITE_API_BASE_URL="http://localhost:8000"
npm run dev
```

## Docker Compose 실행

```powershell
docker compose up --build
```

- 백엔드: `http://localhost:8000`
- 프론트엔드: `http://localhost:5173`
- SQLite 데이터베이스: `quant-data` 볼륨의 `/data/quant_platform.db`
- 백엔드 컨테이너는 추적 중인 `uv.lock`을 기준으로 런타임 의존성만 설치합니다.
- 프론트엔드 컨테이너는 추적 중인 `package-lock.json`을 기준으로 `npm ci`를 실행합니다.

Compose는 기본 환경 변수로 `QUANT_DEFAULT_OWNER_ID=default`, `QUANT_MARKET_DATA_PROVIDER=finance_data_reader`, `VITE_API_BASE_URL=http://localhost:8000`을 설정합니다.

중지하려면 다음을 실행합니다.

```powershell
docker compose down
```

데이터 볼륨까지 삭제하려면 다음을 실행합니다.

```powershell
docker compose down -v
```

## 기본 Owner 동작

서버 시작 시 `QUANT_DEFAULT_OWNER_ID` 값에 해당하는 Owner가 없으면 자동으로 생성합니다. 기본값은 `default`이며, 전략 설정 API는 현재 이 기본 Owner 기준으로 전략 설정을 조회하고 생성합니다.

## Dynamic Wave 예시 흐름

1. 프론트엔드에서 전략 설정 화면을 엽니다.
2. `dynamic_wave` 전략을 선택하고 심볼, 초기 자본, 수수료율, 슬리피지율을 입력합니다.
3. 기본 설정에는 안전 모드와 공격 모드의 분할 매수 수, 최대 보유 기간, 매수/매도 기준 퍼센트가 포함됩니다.
4. 설정을 저장하면 라이브 포트폴리오가 초기 자본으로 준비됩니다.
5. 백테스트 화면에서 저장한 전략 설정과 시작일/종료일을 선택해 실행합니다.
6. 결과 화면에서 수익률, 최대 낙폭, 승률, 거래 내역, 일별 자산 변화를 확인하고 CSV로 내려받을 수 있습니다.

## 테스트와 검증

백엔드 테스트:

```powershell
cd backend
uv run --extra dev pytest -v
```

프론트엔드 빌드:

```powershell
cd frontend
npm run build
```

Docker Compose 설정 확인:

```powershell
docker compose config
```

## 참고

FinanceDataReader 호출 결과는 SQLite에 캐시되어 같은 가격 데이터를 반복 조회할 때 외부 요청을 줄입니다. 백테스트와 라이브 신호 처리에서 사용하는 전략 판단 로직은 같은 전략 엔진을 사용하므로, 화면에서 확인하는 결과와 백테스트 결과의 기준이 일관되도록 설계되어 있습니다.
