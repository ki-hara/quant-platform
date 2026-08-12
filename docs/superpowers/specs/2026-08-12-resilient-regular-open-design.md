# Resilient Regular-Session Open Capture Design

## Goal

Capture the SOXL regular-session opening price within a few seconds of the New
York market open without depending on a completed daily candle or a single
market-data vendor. A malformed or delayed vendor response must not block other
providers. Manual entry remains available as the final operational fallback.

## Scope

This change affects only the opening-price lookup used by the Gold Toilet order
interpreter. Historical market data, backtests, and other dashboard prices keep
their existing providers.

## Provider strategy

The collector will use a composite regular-open provider with two independent
sources:

1. CNBC quote data sourced from NYSE Arca/CTA. It requires no API key and
   exposes an explicit regular-session `open` value.
2. Finnhub's US real-time Quote API. It requires the free API key configured as
   `QUANT_FINNHUB_API_KEY` and exposes the day's `o`, `h`, `l`, and quote time.

Yahoo will no longer be an authority for automatic opening-price capture. It
may remain elsewhere in the application, but neither its daily candle nor its
first minute candle can finalize the Gold Toilet opening price.

The two providers are queried concurrently so a slow or failed request cannot
delay the other. The collector polls every two seconds from five seconds before
the scheduled New York open. Two-second polling stays below Finnhub's free
60-requests-per-minute limit and gives a worst-case scheduling delay of about
two seconds after a provider publishes the open. Collection stops for a sheet
as soon as a value is saved.

If `QUANT_FINNHUB_API_KEY` is absent, CNBC remains operational by itself and the
missing optional key is recorded as provider diagnostic information rather
than preventing application startup.

## Validation and arbitration

No provider value is eligible before 09:30 in `America/New_York` on the target
session date. A provider response is valid only when:

- the market/quote timestamp belongs to the requested session and is at or
  after 09:30;
- the explicit open is finite and greater than zero;
- when high and low are present, `low <= open <= high` and both are positive;
- the response identifies the requested symbol.

When only one provider is valid, that value is saved immediately. When both are
valid and differ by at most five cents, the NYSE Arca/CTA value wins because it
is closer to the listing venue feed. When the difference exceeds five cents,
the composite provider waits for one additional polling cycle. If the same two
validated values persist, the NYSE Arca/CTA value wins; this bounds disagreement
recovery to roughly two seconds instead of waiting indefinitely. The conflict
and both observed values are retained in the failure/diagnostic reason until
the final value is stored.

## Data flow

1. The existing collector wakes during the capture window and loads unresolved
   order sheets.
2. The composite provider concurrently requests CNBC and Finnhub.
3. Each provider parses and validates only its own response format.
4. The composite provider applies the arbitration rules and returns the chosen
   regular-session open or a diagnostic failure.
5. The existing repository snapshots the chosen value and records its source.
6. The order interpreter calculates the regular buy and LOC order quantities
   from the stored opening price as it does today.

The stored source label becomes `cnbc_us_quote` or `finnhub_us_quote`. Existing
rows labelled `yahoo_1d_regular_session` remain readable for historical
compatibility, but new automatic captures never use that source.

## Failure handling

HTTP errors, timeouts, throttling, missing fields, stale timestamps, malformed
OHLC values, and provider-specific error responses are converted into explicit
failure reasons. One provider's failure never masks a valid result from the
other. If neither provider is valid, the collector continues polling and the
page remains eligible for manual opening-price entry after the regular session
starts.

Provider requests use short independent timeouts. API keys are read only from
environment configuration and are never returned to the frontend, written to
logs, or committed to the repository.

## User interface

The existing pending and manual-entry behavior remains. Once captured, the
page displays a Korean source label:

- `NYSE Arca 실시간 시세`
- `Finnhub 미국 실시간 시세`

No new monitoring controls or order execution behavior are introduced.

## Tests

Tests will be written before production changes and will cover:

- CNBC parsing of a current-session explicit open;
- Finnhub parsing of a current-session explicit open;
- rejection before 09:30 and rejection of stale, non-finite, or impossible
  OHLC responses;
- immediate fallback when one provider fails;
- NYSE Arca/CTA preference within five cents;
- one-cycle bounded handling of a larger disagreement;
- operation without a Finnhub key;
- collector persistence of the selected price and source;
- API compatibility with historical Yahoo-labelled records;
- Korean source labels in the frontend.

Live provider responses are not used in the automated test suite. Contract
fixtures model the required response fields so tests remain deterministic.

## Deployment

The code can deploy with CNBC-only operation. To enable redundant Finnhub
lookup, add `QUANT_FINNHUB_API_KEY` to `/opt/quant-platform/.env` on the server
and restart the application. The secret is not passed through the browser or
GitHub source control.
