# Yahoo Daily Open Capture Design

## Goal

Capture the SOXL regular-session opening price as soon as Yahoo exposes the current-day daily candle, without waiting for the 09:30 one-minute candle to complete and without depending on an open browser page.

## Root Cause

The current provider requests the exact 09:30 one-minute candle. Yahoo may not publish that candle until the minute has been aggregated, so polling it every five seconds cannot make the opening price available immediately. The polling interval is not the primary delay.

## Selected Design

### Daily-candle provider

Replace the one-minute request with a Yahoo chart request using `interval=1d`. Parse only the candle whose timestamp, converted with `America/New_York`, matches the requested order date.

The provider accepts the daily candle's `open` when it is present, finite, and greater than zero. It does not require `high`, `low`, or `close`, because those values are still forming after the regular session begins. It rejects a prior-day candle, a missing open, a malformed payload, and any request made before the calculated regular-session start.

### DST-aware capture window

Treat the regular-session start as 09:30 in `America/New_York`, not as a fixed Korean or UTC time. Python `zoneinfo.ZoneInfo("America/New_York")` determines whether the date uses EST or EDT. The collector begins exactly five seconds before that calculated instant, which corresponds to either 22:29:55 or 23:29:55 in Korea depending on daylight-saving time.

### Server-owned polling

Start a background collector from the FastAPI lifespan so capture does not depend on the page being open. During the capture window it polls Yahoo once per second. When a valid opening price is received, it snapshots the value once for every saved order sheet for that session date that does not yet have a provider open, then stops the active polling for that session.

The existing request-time capture remains as a recovery path. If the app restarts after the session opens or the background collector temporarily fails, the next API request still attempts the same daily-candle lookup.

### UI refresh

While the current order sheet is waiting around the calculated market-open window, the page checks the backend once per second. The browser does not call Yahoo directly. Once the backend reports a confirmed provider open, the page stops rapid polling and renders the buy price, quantity, and LOC buy price from the persisted snapshot.

### Source identity and observability

Persist the source as `yahoo_1d_regular_session`. Keep the provider's last-checked timestamp and failure reason. The existing manual override remains available only after an automatic provider open has been captured.

## Failure Handling

- Before the regular-session start: return a waiting result and never accept a daily candle.
- Current-day daily candle absent: continue polling once per second during the capture window.
- Yahoo timeout or malformed response: record the failure, retry on the next tick, and keep the last valid snapshot immutable.
- App restart: calculate the session state from the current New York time and immediately attempt recovery when the session is already open and an order sheet remains unresolved.
- No saved order sheet: do not perform continuous Yahoo polling; a later sheet save triggers request-time capture.

## Verification

- Provider tests prove exact target-date selection, prior-day rejection, pre-open rejection, acceptance when high/low/close are missing, and invalid-open rejection.
- Scheduling tests cover both EDT and EST dates and assert that capture begins five seconds before the corresponding UTC instant.
- Collector tests prove one-second retries, capture without a browser request, snapshot-once behavior, and restart recovery.
- API tests prove that the response source changes to `yahoo_1d_regular_session` without changing manual override behavior.
- Frontend tests prove one-second waiting refresh and that rapid polling stops when the open becomes ready.
