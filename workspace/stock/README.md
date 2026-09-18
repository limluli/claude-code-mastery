# 한국 주식 자동매매 프로그램

한국투자증권(KIS) API를 기반으로 한국 주식(코스피/코스닥)을 자동매매하는 프로그램입니다.

## 특징

- 이평선 교차(MA Cross), RSI 등 검증된 기본 전략 탑재
- 백테스팅 엔진으로 전략 성과 사전 검증
- 모의투자 모드로 안전하게 테스트
- 리스크 관리: 손절/익절, 일일 손실 한도(서킷브레이커)
- 실시간 시세 수신(WebSocket) + 과거 데이터 조회(REST)
- 텔레그램 알림으로 거래 모니터링

## 준비 사항

### Phase 0: 계좌 & API 키 발급

1. **한국투자증권 모의투자 계좌 신청**
   - https://www.koreainvestment.com 에서 모의투자 계좌 개설

2. **KIS Developers 앱키 발급**
   - https://apiportal.koreainvestment.com 에서 회원가입
   - "내 서비스" → "앱키 관리" → "실시간 데이터 앱키 신청"
   - 모의투자용 앱키와 실전용 앱키 별도로 발급 권장

3. **`.env` 파일 설정**
   ```bash
   cp .env.example .env
   ```
   발급받은 앱키/시크릿/계좌번호를 `.env` 파일에 입력

## 설치 & 실행

### 의존성 설치
```bash
poetry install
```

### 토큰 발급 테스트 (Phase 1 완료 기준)
```bash
poetry run python -m stock.auth.kis_auth
```
성공 메시지가 나오면 API 연동 완료.

### 백테스트 실행 (Phase 3)
```bash
poetry run python scripts/run_backtest.py --strategy ma_cross --start-date 2023-01-01 --end-date 2024-01-01
```

### 모의투자 실행 (Phase 4+)
```bash
poetry run python scripts/run_live.py --mode paper
```

### 실전 실행 (Phase 6+ / 충분한 검증 후만!)
```bash
poetry run python scripts/run_live.py --mode live
```

## 프로젝트 구조

```
stock/
├── config/settings.py           # 설정 로더
├── src/stock/
│   ├── auth/kis_auth.py         # KIS OAuth 토큰 관리
│   ├── market_data/             # 시세 데이터 (REST/WebSocket)
│   ├── strategy/                # 매매 전략 (이평선, RSI 등)
│   ├── backtest/                # 백테스팅 엔진
│   ├── execution/               # 주문 실행
│   ├── risk/                    # 리스크 관리
│   ├── scheduler/               # 장 운영시간 관리
│   ├── notification/            # 텔레그램 알림
│   └── logging/                 # 로깅
├── scripts/
│   ├── run_live.py              # 실거래 진입점
│   └── run_backtest.py          # 백테스팅 실행
└── tests/                       # pytest 테스트
```

## Phase별 진행 상황

- [ ] Phase 0: 계좌/환경 준비
- [x] Phase 1: 프로젝트 스캐폴딩 + 인증 모듈
- [ ] Phase 2: 시세 데이터 수집
- [ ] Phase 3: 백테스팅 + 기본 전략
- [ ] Phase 4: 모의투자 자동 주문
- [ ] Phase 5: 리스크 관리 & 알림
- [ ] Phase 6: 모의투자 검증 & 실전 전환

## 주의사항

⚠️ **반드시 읽으세요**

- **실거래 전에 반드시 충분한 백테스트 & 모의투자 검증을 거칠 것**
- 자동매매는 시장 변동성, API 오류, 네트워크 단절 등의 위험이 있습니다
- 본인이 감당할 수 있는 자금으로만 운영하세요
- 과최적화(overfitting) 위험을 항상 염두에 두고 실거래 전 샘플 외 검증 필수
- API Rate Limit 주의 (초당 호출 제한 있음)
- 장 시작/종료 시간, 휴장일 정확히 관리

## 법률 고지

- 본 프로그램은 교육/개인 투자 목적으로만 사용하세요
- 투자 손익은 전적으로 사용자 본인의 책임입니다
- 개발자는 손실에 대한 책임을 지지 않습니다

## 참고 자료

- [KIS Developers API 문서](https://apiportal.koreainvestment.com/)
- [한국거래소 휴장일 캘린더](http://www.krx.co.kr/)
