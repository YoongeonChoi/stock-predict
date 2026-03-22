# Changelog

All notable changes to this project are tracked here.

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
