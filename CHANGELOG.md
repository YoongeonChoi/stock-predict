# Changelog

All notable changes to this project are tracked here.

## v2.4.0 - 2026-03-23

- 대시보드, 비교, 스크리너, 워치리스트, 포트폴리오, 국가/종목 상세 등 주요 화면의 사용자 노출 문구를 한국어 중심으로 재정비했습니다.
- API 상태와 시스템 진단 카드를 홈 화면에서 분리하고 `/settings` 페이지로 이동해 운영 정보와 투자 정보의 역할을 분리했습니다.
- Fed, BIS, 한국은행, KDI, BOJ 공식 리포트를 하루 단위로 동기화하는 기관 리서치 아카이브를 추가했습니다.
- 아카이브에서 PDF 직접 열기와 공식 원문 링크 이동을 함께 지원하고, 직접 다운로드 실패 시 내보내기 허브로 자연스럽게 우회하도록 정리했습니다.
- 한국 시장을 기본 시작점으로 두도록 홈 대시보드, 레이더, 히트맵, 캘린더 기본값을 조정했습니다.
- 버전, README, 테스트, 에러 코드 문서를 `2.4.0` 기준으로 동기화했습니다.

## v2.3.0 - 2026-03-23

- Added a month-scoped market calendar API with color-coded normalized events, recurring fallback generation, and Korean event descriptions
- Rebuilt the calendar UI into a monthly schedule board that refreshes when the month changes and surfaces high-impact events inline
- Reworked archive exports with robust direct download handling, a dedicated export hub page, and CORS `Content-Disposition` exposure
- Upgraded the next-day forecast engine to `signal-v2.3` with candle control, regime overlay, localized news scoring, and stronger confidence shrinkage
- Localized major user-facing detail panels into Korean, including forecast cards, diagnostics, archive flows, navigation, and Prediction Lab summaries
- Added regression coverage for monthly calendar shaping and bullish/bearish forecast separation
- Added repository-wide contribution standards for humans and AI, including required README/error-code/version synchronization rules and a PR checklist

## v2.2.1 - 2026-03-22

- Synchronized backend and frontend version metadata to `2.2.1`
- Added explicit error codes for:
  - `SP-5006` system diagnostics
  - `SP-5007` prediction research
  - `SP-5008` portfolio analytics
  - `SP-9999` unexpected server errors
- Wired research/system/portfolio routers to return structured `AppError` responses
- Updated README release/version guidance and error code reference

## v2.2.0 - 2026-03-22

- Added next-day forecast engine
- Added market regime analysis and opportunity radar
- Added portfolio risk coach and stress testing
- Added prediction lab with calibration and validation analytics
- Added runtime diagnostics and startup task visibility