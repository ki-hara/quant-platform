# Radar Candidate Similarity Reconstruction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an isolated, reproducible research pipeline that discovers and validates radar0458's SOXL candidate eligibility, Top3 ordering, and displayed similarity formula without copying site results into the product.

**Architecture:** Keep all reverse-engineering code in a standalone `research/radar0458` Python package that is excluded from production Docker images. Import only parsed, authenticated page output; calculate the complete local candidate universe independently; evaluate eligibility and distance hypotheses under blocked time validation; and stop before product integration unless one frozen formula reproduces every post-2011 trading day exactly.

**Tech Stack:** Python 3.12, uv, pandas, NumPy, SciPy, httpx, pytest, Ruff, JSONL research artifacts, authenticated gstack browser collection.

## Global Constraints

- Completion requires exact Top3 dates, exact rank order, and displayed similarity rounded to `0.01%p` for every U.S. trading day from 2012 onward.
- Data from 2010 and 2011 may be used only for feature warm-up and historical candidates.
- This plan freezes the historical audit end at `2026-07-21`; a later execution must fingerprint a new end-date manifest before collecting additional days.
- Do not add radar recommendation behavior to `backend/app` or `frontend/src` during this plan.
- Do not store credentials, cookies, authorization headers, raw authenticated HTML, or account identifiers in Git.
- Do not encode date-specific exceptions or cache official Top3 results as the reconstructed formula.
- Use deterministic tests for parsing, feature calculations, ranking, and validation. Exploratory hypothesis runs do not require test-first iterations when a fixed expected result does not yet exist.
- Commit each task independently. Do not include the user's existing modification to `docs/superpowers/plans/2026-06-26-strategy-operations-ui-implementation.md`.
- Stop and report rather than naming the result an official reconstruction when any completion gate fails.

---

## File Map

**Research package and safe storage**

- Modify `.gitignore`: exclude local radar data, raw responses, generated reports, and the research virtual environment.
- Create `research/radar0458/pyproject.toml`: isolated dependencies, CLI entry point, pytest, and Ruff configuration.
- Create `research/radar0458/uv.lock`: reproducible research dependency lock.
- Create `research/radar0458/README.md`: commands, authentication boundary, and stop conditions.
- Create `research/radar0458/src/radar_research/models.py`: immutable samples, features, candidates, metric specs, and validation records.
- Create `research/radar0458/src/radar_research/storage.py`: deterministic Decimal-safe JSONL load and save.

**Official output ingestion**

- Create `research/radar0458/src/radar_research/parser.py`: parse the visible Korean recommendation text into typed samples.
- Create `research/radar0458/src/radar_research/importer.py`: normalize existing gstack JSON batches and reject login/error responses.
- Create `research/radar0458/src/radar_research/cli.py`: one CLI with import, feature, diagnose, fit, probe, validate, and audit commands.
- Create `research/radar0458/docs/response-contract.md`: same-origin request inventory, response sizes, and compact-response findings.
- Create `research/radar0458/schemas/official-sample.schema.json`: browser extraction contract without authentication data.

**Independent market calculation**

- Create `research/radar0458/src/radar_research/market_data.py`: cached Yahoo chart JSON retrieval and close-series normalization.
- Create `research/radar0458/src/radar_research/features.py`: MA20/60/120, slope, distance, RSI variants, ROC, volatility, and hidden-state diagnostics.
- Create `research/radar0458/src/radar_research/feature_calibration.py`: select and freeze the data/formula variant that matches official displayed features.

**Candidate and distance discovery**

- Create `research/radar0458/src/radar_research/candidate_pool.py`: causal candidate universe and hard eligibility rules.
- Create `research/radar0458/src/radar_research/filters.py`: configurable candidate filters and post-ranking de-duplication.
- Create `research/radar0458/src/radar_research/diagnostics.py`: exact/order/adjacent/distant/similarity mismatch reports.
- Create `research/radar0458/src/radar_research/distance.py`: metric, normalization, input rounding, and similarity transforms.
- Create `research/radar0458/src/radar_research/fitting.py`: ranking and rounded-similarity constrained fitting.
- Create `research/radar0458/src/radar_research/active_learning.py`: choose dates that maximize disagreement between surviving hypotheses.

**Validation and cost control**

- Create `research/radar0458/src/radar_research/validation.py`: blocked discovery, validation, holdout, and exact-match reports.
- Create `research/radar0458/src/radar_research/audit.py`: request-cost estimation, cached manifest generation, and large-fetch approval gate.
- Create `research/radar0458/schemas/formula-bundle.schema.json`: frozen formula artifact contract.
- Create `research/radar0458/config/validation-dates.json`: result-free intermediate and holdout dates fixed before formula fitting.
- Create `docs/research/radar0458-reconstruction-report.md`: final evidence, formula or stop reason, and exact validation counts.

**Tests and committed fixtures**

- Create `research/radar0458/tests/fixtures/recommend_2022_09_14.json`: sanitized visible output fixture with three official analogs.
- Create `research/radar0458/tests/fixtures/site_plot_trace.json`: sanitized full-precision close/MA trace for market-data calibration.
- Create focused tests under `research/radar0458/tests/` matching each module name.

## Task 1: Isolated Research Package and Typed Storage

**Files:**
- Modify: `.gitignore`
- Create: `research/radar0458/pyproject.toml`
- Create: `research/radar0458/uv.lock`
- Create: `research/radar0458/README.md`
- Create: `research/radar0458/src/radar_research/__init__.py`
- Create: `research/radar0458/src/radar_research/models.py`
- Create: `research/radar0458/src/radar_research/storage.py`
- Create: `research/radar0458/tests/test_storage.py`

**Interfaces:**
- Produces: `FeatureVector`, `StrategyOutcome`, `AnalogMatch`, `RecommendationSample`, `CandidateRecord`, `MetricSpec`, `FormulaBundle`, `dump_jsonl(path, records)`, and `load_samples(path)`.
- Consumes: no product modules and no authenticated data.

- [ ] **Step 1: Write the failing Decimal round-trip test**

```python
def test_sample_jsonl_round_trip_preserves_decimal_and_rank(tmp_path: Path) -> None:
    sample = make_sample(
        requested_date=date(2022, 9, 14),
        similarities=[Decimal("94.64"), Decimal("93.91"), Decimal("92.92")],
    )
    path = tmp_path / "samples.jsonl"

    dump_jsonl(path, [sample])

    assert load_samples(path) == [sample]
    assert [row.rank for row in load_samples(path)[0].analogs] == [1, 2, 3]
```

- [ ] **Step 2: Run the focused test and verify the package is missing**

Run: `cd research/radar0458; uv run pytest tests/test_storage.py -q`

Expected: FAIL during import because `radar_research` does not exist.

- [ ] **Step 3: Add the package, immutable models, and deterministic JSONL codec**

Use `@dataclass(frozen=True)` for domain records and `Decimal` for every displayed percentage. Store dates as ISO strings and decimals as strings. Reject a sample unless it has ranks `(1, 2, 3)`, unique candidate analysis-end dates, and similarities in descending order.

```python
@dataclass(frozen=True)
class FeatureVector:
    aligned: bool
    slope20: Decimal
    distance20: Decimal
    rsi14: Decimal
    roc12: Decimal
    volatility20: Decimal

@dataclass(frozen=True)
class AnalogMatch:
    rank: int
    analysis_start: date
    analysis_end: date
    performance_start: date
    performance_end: date
    similarity: Decimal
    features: FeatureVector
    outcomes: tuple[StrategyOutcome, ...]

@dataclass(frozen=True)
class RecommendationSample:
    requested_date: date
    analysis_start: date
    analysis_end: date
    current: FeatureVector
    analogs: tuple[AnalogMatch, AnalogMatch, AnalogMatch]
    collected_at: datetime
    source_fingerprint: str
```

Add these ignored paths without changing the existing `rsi/` rule:

```gitignore
research/radar0458/.venv/
research/radar0458/data/
research/radar0458/reports/generated/
research/radar0458/**/*.html
```

The research `pyproject.toml` must expose `radar-research = "radar_research.cli:main"` and pin compatible floors for `beautifulsoup4`, `httpx`, `numpy`, `pandas`, `scipy`, `pytest`, and `ruff`. Generate `uv.lock` with `uv lock`.

- [ ] **Step 4: Run package tests and lint**

Run: `cd research/radar0458; uv run pytest tests/test_storage.py -q`

Expected: PASS.

Run: `cd research/radar0458; uv run ruff check src tests`

Expected: `All checks passed!`

- [ ] **Step 5: Commit only Task 1 files**

```text
git add .gitignore research/radar0458
git commit -m "research: scaffold radar similarity analysis"
```

## Task 2: Parse and Normalize Official Visible Output

**Files:**
- Create: `research/radar0458/src/radar_research/parser.py`
- Create: `research/radar0458/src/radar_research/importer.py`
- Create: `research/radar0458/src/radar_research/cli.py`
- Create: `research/radar0458/docs/response-contract.md`
- Create: `research/radar0458/schemas/official-sample.schema.json`
- Create: `research/radar0458/tests/fixtures/recommend_2022_09_14.json`
- Create: `research/radar0458/tests/test_parser.py`
- Create: `research/radar0458/tests/test_importer.py`

**Interfaces:**
- Consumes: `RecommendationSample` and JSONL storage from Task 1.
- Produces: `parse_recommendation_text(requested_date, text, collected_at)`, `import_gstack_batches(paths)`, and CLI command `radar-research import-official`.

- [ ] **Step 1: Inspect and document one authenticated response**

Use the authenticated gstack browser to submit `2026-07-20` once. Record only same-origin method, path, status, content type, response byte count, form field names, static script names, source-map availability, and whether a compact JSON or chart-free response exists. Save no cookies or authorization data.

Expected: `response-contract.md` identifies `GET /recommend` and `POST /recommend` and either names a verified compact path or records the approximately 6MB server-rendered response.

- [ ] **Step 2: Add failing parser and authentication-boundary tests**

```python
def test_parse_known_sample_extracts_exact_top3() -> None:
    payload = load_fixture("recommend_2022_09_14.json")
    sample = parse_recommendation_text(
        requested_date=date.fromisoformat(payload["date"]),
        text=payload["text"],
        collected_at=datetime(2026, 7, 21, tzinfo=timezone.utc),
    )

    assert sample.analysis_end == date(2022, 9, 13)
    assert [row.analysis_end for row in sample.analogs] == [
        date(2022, 6, 29),
        date(2022, 4, 26),
        date(2022, 5, 11),
    ]
    assert [row.similarity for row in sample.analogs] == [
        Decimal("94.64"), Decimal("93.91"), Decimal("92.92")
    ]

def test_importer_rejects_login_redirect_text() -> None:
    with pytest.raises(OfficialSampleError, match="authentication"):
        import_gstack_batches([{"date": "2026-07-20", "status": 302, "text": "login"}])
```

- [ ] **Step 3: Run tests and verify parser imports fail**

Run: `cd research/radar0458; uv run pytest tests/test_parser.py tests/test_importer.py -q`

Expected: FAIL because parser and importer modules are missing.

- [ ] **Step 4: Implement label-anchored parsing and schema validation**

Parse the visible Korean labels rather than CSS classes. Normalize whitespace before matching. Candidate parsing must anchor each block on its analysis range, performance range, similarity, alignment mark, five features, and three Pro outcomes. Treat a missing block, a non-200 status, or text containing a login page marker as an error; never silently write a partial sample.

The browser extraction JSON schema permits only `date`, `status`, `text`, `collected_at`, and `source_fingerprint`. It rejects cookies, headers, email fields, and unknown properties with `"additionalProperties": false`.

Implement:

```python
CURRENT_RANGE = re.compile(
    r"분석 구간:\s*(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2})"
)
ANALOG_RANGE = re.compile(
    r"(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2}).*?"
    r"성과 확인 기간:\s*(\d{4}-\d{2}-\d{2})\s*~\s*(\d{4}-\d{2}-\d{2}).*?"
    r"유사도:\s*([+-]?\d+(?:\.\d+)?)%",
    re.DOTALL,
)
```

Use bounded slices between the Top3 heading and the score heading so unrelated dates are not parsed as candidates.

- [ ] **Step 5: Import the existing temporary batches into ignored JSONL**

Run:

```text
cd research/radar0458
uv run radar-research import-official --input "C:/Users/starc/AppData/Local/Temp/radar-gstack/recommend-samples-batch-*.json" --output data/official/samples.jsonl
```

Expected: `30 samples imported, 0 partial, 0 authentication failures` and no cookie-like keys in the output.

- [ ] **Step 6: Run tests, lint, and commit**

Run: `cd research/radar0458; uv run pytest tests/test_parser.py tests/test_importer.py -q`

Expected: PASS.

Run: `cd research/radar0458; uv run ruff check src tests`

Expected: `All checks passed!`

```text
git add research/radar0458
git commit -m "research: parse official radar samples"
```

## Task 3: Independent Market Data and Feature Calibration

**Files:**
- Create: `research/radar0458/src/radar_research/market_data.py`
- Create: `research/radar0458/src/radar_research/features.py`
- Create: `research/radar0458/src/radar_research/feature_calibration.py`
- Modify: `research/radar0458/src/radar_research/cli.py`
- Create: `research/radar0458/tests/fixtures/soxl_closes.csv`
- Create: `research/radar0458/tests/fixtures/site_plot_trace.json`
- Create: `research/radar0458/tests/test_market_data.py`
- Create: `research/radar0458/tests/test_features.py`
- Create: `research/radar0458/tests/test_feature_calibration.py`

**Interfaces:**
- Consumes: official samples from Task 2.
- Produces: `YahooChartClient.load_closes`, `load_site_plot_trace`, `compute_feature_variants`, `calibrate_feature_formula`, extended feature JSONL, and CLI commands `fetch-market`, `import-plot-traces`, and `calibrate-features`.

- [ ] **Step 1: Write failing formula and calibration tests**

```python
def test_core_feature_formulas_use_the_analysis_end_close() -> None:
    closes = load_close_fixture("soxl_closes.csv")
    result = compute_features(closes, date(2022, 9, 13), rsi_method="simple", ddof=1)

    assert result.slope20 == pytest.approx((result.ma20 / result.ma20_lag10 - 1) * 100)
    assert result.distance20 == pytest.approx((result.close / result.ma20 - 1) * 100)
    assert result.roc12 == pytest.approx((result.close / result.close_lag12 - 1) * 100)
    assert result.volatility20 == pytest.approx(result.return_std20 * math.sqrt(252))

def test_calibration_requires_every_displayed_feature_to_round_equal() -> None:
    report = calibrate_feature_formula(official_samples(), local_variants())
    assert report.winner.display_match_rate == Decimal("1")
    assert report.winner.max_display_error <= Decimal("0.005")
```

- [ ] **Step 2: Run tests and verify feature modules are missing**

Run: `cd research/radar0458; uv run pytest tests/test_market_data.py tests/test_features.py tests/test_feature_calibration.py -q`

Expected: FAIL during import.

- [ ] **Step 3: Implement cached raw-close retrieval and all plausible formula variants**

Fetch Yahoo chart JSON for `SOXL` from 2010-01-01 through `2026-07-21` and save it only under ignored `data/cache`. Keep both `close` and `adjclose`; never silently substitute one for the other. Import the sanitized `recommend-plot-series-*.json` traces and compare their full-precision close, MA20, and MA60 values before selecting raw or adjusted data.

Calculate these fixed formulas for each trading day:

```python
ma20 = close.rolling(20).mean()
ma60 = close.rolling(60).mean()
ma120 = close.rolling(120).mean()
slope20 = (ma20 / ma20.shift(10) - 1) * 100
distance20 = (close / ma20 - 1) * 100
roc12 = (close / close.shift(12) - 1) * 100
volatility20 = close.pct_change().rolling(20).std(ddof=ddof) * math.sqrt(252)
```

Evaluate raw versus adjusted close, simple rolling RSI versus Wilder RSI, volatility `ddof` 0 versus 1, and input rounding at no rounding, 2 decimals, 4 decimals, and 6 decimals. Also calculate MA120 distance and deterministic RSI divergence flags for later hidden-state diagnostics, but do not add them to the five-feature distance until evidence requires it.

- [ ] **Step 4: Calibrate against all collected current and candidate feature vectors**

Run:

```text
cd research/radar0458
uv run radar-research fetch-market --symbol SOXL --start 2010-01-01 --end 2026-07-21
uv run radar-research calibrate-features --samples data/official/samples.jsonl --output data/calibration/features.json
```

Expected: one variant is selected only when all five values round to the site's displayed precision for every comparable vector. If no variant reaches 100%, stop Task 3 and emit the smallest-error rows; do not proceed to candidate fitting.

- [ ] **Step 5: Verify and commit deterministic code only**

Run: `cd research/radar0458; uv run pytest -q`

Expected: PASS.

Run: `cd research/radar0458; uv run ruff check src tests`

Expected: `All checks passed!`

```text
git add research/radar0458
git commit -m "research: calibrate radar market features"
```

## Task 4: Causal Candidate Universe and Mismatch Diagnostics

**Files:**
- Create: `research/radar0458/src/radar_research/candidate_pool.py`
- Create: `research/radar0458/src/radar_research/diagnostics.py`
- Modify: `research/radar0458/src/radar_research/cli.py`
- Create: `research/radar0458/tests/test_candidate_pool.py`
- Create: `research/radar0458/tests/test_diagnostics.py`

**Interfaces:**
- Consumes: calibrated daily features and official samples.
- Produces: `EligibilitySpec`, `build_candidate_pool`, `classify_mismatch`, `DiagnosticReport`, and CLI command `diagnose`.

- [ ] **Step 1: Write failing causal eligibility and classification tests**

```python
def test_candidate_requires_completed_forward_performance_before_current_window() -> None:
    spec = EligibilitySpec(forward_calendar_days=30, same_alignment=True)
    candidates = build_candidate_pool(
        current=sample_for("2022-09-14"),
        daily_features=feature_rows(),
        spec=spec,
    )

    assert all(row.performance_end <= date(2022, 8, 15) for row in candidates)
    assert all(row.features.aligned is False for row in candidates)

@pytest.mark.parametrize(
    ("official", "predicted", "expected"),
    [
        (["2022-06-29", "2022-04-26", "2022-05-11"], ["2022-06-29", "2022-04-26", "2022-05-11"], "exact"),
        (["2022-06-29", "2022-04-26", "2022-05-11"], ["2022-04-26", "2022-06-29", "2022-05-11"], "order_only"),
        (["2022-06-29", "2022-04-26", "2022-05-11"], ["2022-06-28", "2022-04-26", "2022-05-11"], "adjacent"),
    ],
)
def test_mismatch_classification(official, predicted, expected) -> None:
    assert classify_mismatch(official, predicted, trading_day_radius=5).kind == expected
```

- [ ] **Step 2: Run tests and verify modules are missing**

Run: `cd research/radar0458; uv run pytest tests/test_candidate_pool.py tests/test_diagnostics.py -q`

Expected: FAIL during import.

- [ ] **Step 3: Implement base eligibility and mismatch reports**

Build candidates from every feature-complete U.S. trading day. Candidate analysis windows are 30 calendar days ending on the candidate date; performance windows begin on that date and end 30 calendar days later. Represent the cutoff rule as an explicit `EligibilitySpec` so `performance_end <= current.analysis_start`, `performance_end < current.analysis_end`, and other observed variants can be compared without changing code.

The base spec requires feature completeness and matching MA20/MA60 alignment. Diagnostics must report exact-set accuracy, ordered accuracy, individual candidate hits, median official-candidate local rank, and the first excluded local candidate that outranks official rank 3.

- [ ] **Step 4: Generate the first mismatch inventory**

Run:

```text
cd research/radar0458
uv run radar-research diagnose --samples data/official/samples.jsonl --features data/calibration/daily-features.jsonl --metric baseline-l1 --output reports/generated/baseline-diagnostics.json
```

Expected: on the original 30 samples, the report records `45/90` individual candidate hits and `2/30` exact Top3 sets; every mismatch has one of `order_only`, `adjacent`, `distant`, or `similarity_only`.

- [ ] **Step 5: Verify and commit**

Run: `cd research/radar0458; uv run pytest -q`

Expected: PASS.

```text
git add research/radar0458
git commit -m "research: diagnose radar candidate eligibility"
```

## Task 5: Candidate Filter and De-duplication Hypothesis Evaluator

**Files:**
- Create: `research/radar0458/src/radar_research/filters.py`
- Create: `research/radar0458/src/radar_research/hypotheses.py`
- Modify: `research/radar0458/src/radar_research/cli.py`
- Create: `research/radar0458/tests/test_filters.py`
- Create: `research/radar0458/tests/test_hypotheses.py`

**Interfaces:**
- Consumes: candidate pools and mismatch records from Task 4.
- Produces: `FilterSpec`, `SelectionSpec`, `apply_filters`, `select_distinct_top3`, `evaluate_hypotheses`, and CLI command `evaluate-filters`.

- [ ] **Step 1: Write failing filter-isolation and non-max-suppression tests**

```python
def test_distinct_selection_keeps_highest_ranked_date_inside_radius() -> None:
    ranked = candidates_on(["2022-04-25", "2022-04-26", "2022-04-27", "2022-05-11"])
    selected = select_distinct_top3(ranked, SelectionSpec(dedupe_trading_days=2))

    assert dates(selected) == [date(2022, 4, 25), date(2022, 5, 11)]

def test_each_hypothesis_changes_only_declared_dimensions() -> None:
    base = FilterSpec()
    changed = replace(base, require_same_slope_sign=True)

    assert differing_fields(base, changed) == {"require_same_slope_sign"}
```

- [ ] **Step 2: Run tests and verify modules are missing**

Run: `cd research/radar0458; uv run pytest tests/test_filters.py tests/test_hypotheses.py -q`

Expected: FAIL during import.

- [ ] **Step 3: Implement explicit, enumerable hypotheses**

Support these dimensions without date-specific values:

- candidate/current gap and complete-forward-window cutoff
- analysis-window and performance-window overlap restrictions
- candidate de-duplication radius from 0 through 20 trading days
- same slope sign
- fixed RSI buckets of 5 and 10
- fixed volatility buckets of 0.05 and 0.10
- fixed distance20 buckets of 5 and 10 percentage points
- same close/MA120 regime
- same RSI-divergence state

Evaluate one-dimensional additions first, then combinations of at most three dimensions. Sort equal candidates deterministically by similarity descending and analysis-end date ascending. Reject hypothesis sets whose validation improvement comes only from one year.

- [ ] **Step 4: Run the filter comparison on discovery years only**

Run:

```text
cd research/radar0458
uv run radar-research evaluate-filters --samples data/official/samples.jsonl --features data/calibration/daily-features.jsonl --years 2012:2022 --output reports/generated/filter-hypotheses.json
```

Expected: report every tested spec, Top3 set/order counts, mismatch types, and complexity. Do not read 2023+ validation output during hypothesis selection.

- [ ] **Step 5: Verify and commit**

Run: `cd research/radar0458; uv run pytest -q`

Expected: PASS.

```text
git add research/radar0458
git commit -m "research: evaluate radar candidate filters"
```

## Task 6: Constrained Distance and Similarity Fitting

**Files:**
- Create: `research/radar0458/src/radar_research/distance.py`
- Create: `research/radar0458/src/radar_research/fitting.py`
- Modify: `research/radar0458/src/radar_research/cli.py`
- Create: `research/radar0458/tests/test_distance.py`
- Create: `research/radar0458/tests/test_fitting.py`

**Interfaces:**
- Consumes: official samples, calibrated features, and surviving filter specs.
- Produces: `distance(current, candidate, spec)`, `similarity(distance, transform)`, `fit_formula_candidates`, ranked `FormulaBundle` candidates, and CLI command `fit`.

- [ ] **Step 1: Write failing synthetic ranking and rounding-interval tests**

```python
def test_weighted_l1_orders_synthetic_official_top3() -> None:
    spec = MetricSpec(kind="l1", weights=(2, 1, 1, 1, 4), scales=(1, 1, 1, 1, 1))
    ranked = rank_candidates(synthetic_current(), synthetic_candidates(), spec)
    assert [row.candidate_id for row in ranked[:3]] == ["A", "B", "C"]

@pytest.mark.parametrize(
    ("predicted", "displayed", "loss"),
    [(96.025, 96.03, 0), (96.0349, 96.03, 0), (96.02, 96.03, 0.005)],
)
def test_similarity_interval_loss(predicted, displayed, loss) -> None:
    assert similarity_interval_loss(predicted, displayed) == pytest.approx(loss)
```

- [ ] **Step 2: Run tests and verify distance modules are missing**

Run: `cd research/radar0458; uv run pytest tests/test_distance.py tests/test_fitting.py -q`

Expected: FAIL during import.

- [ ] **Step 3: Implement metric families and constrained objective**

Support weighted L1, weighted squared/L2, robust scale, standard-deviation scale, relative-difference, Mahalanobis diagnostic, and cosine diagnostic metrics. Support unrounded inputs and 2-, 4-, and 6-decimal input rounding. Support `100 - distance`, `100 * exp(-distance)`, and `100 / (1 + distance)` similarity transforms.

The objective combines:

```python
rank_loss = sum(max(0.0, margin - (score_left - score_right)) for left, right in constraints)
display_loss = sum(similarity_interval_loss(predicted, displayed) for predicted, displayed in rows)
complexity_loss = 0.001 * active_parameter_count
total_loss = rank_loss + display_loss + complexity_loss
```

Create constraints `official1 > official2 > official3 > every eligible non-selected candidate`. Use a deterministic SciPy seed and blocked year folds. Keep at least the ten best structurally distinct formulas for active learning; do not select only by in-sample loss.

- [ ] **Step 4: Fit discovery data and verify the report is honest**

Run:

```text
cd research/radar0458
uv run radar-research fit --samples data/official/samples.jsonl --features data/calibration/daily-features.jsonl --filters reports/generated/filter-hypotheses.json --years 2012:2022 --output reports/generated/formula-candidates.json
```

Expected: output includes formula parameters, discovery Top3 set/order accuracy, similarity interval accuracy, fold scores, and complexity. A formula below 100% remains labeled `candidate`, never `complete`.

- [ ] **Step 5: Verify and commit**

Run: `cd research/radar0458; uv run pytest -q`

Expected: PASS.

```text
git add research/radar0458
git commit -m "research: fit radar similarity formulas"
```

## Task 7: Active Probe Selection and Request-Cost Gate

**Files:**
- Create: `research/radar0458/src/radar_research/active_learning.py`
- Create: `research/radar0458/src/radar_research/audit.py`
- Modify: `research/radar0458/src/radar_research/cli.py`
- Create: `research/radar0458/config/validation-dates.json`
- Create: `research/radar0458/tests/test_active_learning.py`
- Create: `research/radar0458/tests/test_audit.py`

**Interfaces:**
- Consumes: surviving formula candidates and all locally calculable query dates.
- Produces: `select_probe_dates`, `build_fixed_validation_dates`, `estimate_request_cost`, `build_query_manifest`, `LargeFetchApprovalRequired`, and CLI commands `probes`, `freeze-validation-dates`, and `audit-manifest`.

- [ ] **Step 1: Write failing disagreement and cost-gate tests**

```python
def test_probe_selection_prefers_formula_disagreement() -> None:
    probes = select_probe_dates(query_rows(), formula_predictions(), limit=2)
    assert [row.requested_date for row in probes] == [date(2023, 8, 28), date(2024, 5, 15)]

def test_large_fetch_requires_explicit_approval() -> None:
    estimate = estimate_request_cost(requests=3600, bytes_per_response=6_000_000, seconds_between=2)
    assert estimate.gigabytes > Decimal("20")
    with pytest.raises(LargeFetchApprovalRequired):
        build_query_manifest(all_dates(), estimate, approved_large_fetch=False)
```

- [ ] **Step 2: Run tests and verify modules are missing**

Run: `cd research/radar0458; uv run pytest tests/test_active_learning.py tests/test_audit.py -q`

Expected: FAIL during import.

- [ ] **Step 3: Implement query-by-committee and bounded manifests**

Score each unqueried date by pairwise ordered-Top3 disagreement between the ten surviving formulas, then by similarity spread and regime rarity. Select at most 25 dates per batch, balance aligned/inverted states and years, and cap cumulative active probes at 200.

The cost report contains request count, bytes, gigabytes, expected duration, batch count, and cache hits. Refuse manifests above 2GB or 30 minutes unless `--approve-large-fetch` is passed after the user sees the estimate.

- [ ] **Step 4: Freeze result-free validation dates**

Run:

```text
cd research/radar0458
uv run radar-research freeze-validation-dates --features data/calibration/daily-features.jsonl --intermediate 2023-01-01:2024-12-31:120 --holdout 2025-01-01:2026-07-21:100 --seed radar0458-validation-v1 --output config/validation-dates.json
```

Expected: exactly 120 intermediate and 100 holdout dates, balanced as closely as possible across years and aligned/inverted states. The committed file contains dates and a SHA-256 digest only, never official results.

- [ ] **Step 5: Collect only the generated active batch through the authenticated browser**

Run:

```text
cd research/radar0458
uv run radar-research probes --formulas reports/generated/formula-candidates.json --features data/calibration/daily-features.jsonl --limit 25 --max-total 200 --output data/manifests/probe-batch-01.json
```

Use `gstack:scrape` in a user-authenticated browser to submit only the dates in the manifest. Extract the `official-sample.schema.json` fields and save them under ignored `data/incoming`. Do not export the browser profile or cookies. Import the resulting JSON, rerun Tasks 4 through 6, and repeat only while new batches eliminate or separate hypotheses.

- [ ] **Step 6: Verify and commit the reusable code and fixed dates**

Run: `cd research/radar0458; uv run pytest -q`

Expected: PASS.

```text
git add research/radar0458
git commit -m "research: select informative radar probes"
```

## Task 8: Frozen Validation and Exact Audit

**Files:**
- Create: `research/radar0458/src/radar_research/validation.py`
- Create: `research/radar0458/schemas/formula-bundle.schema.json`
- Modify: `research/radar0458/src/radar_research/cli.py`
- Create: `research/radar0458/tests/test_validation.py`
- Modify: `research/radar0458/tests/test_audit.py`

**Interfaces:**
- Consumes: one frozen `FormulaBundle`, official samples, candidate features, and query manifests.
- Produces: `validate_formula`, `verify_report`, `ExactValidationReport`, nonzero CLI exit on mismatch, and immutable audit manifests.

- [ ] **Step 1: Write failing exact-gate tests**

```python
def test_validation_fails_on_one_similarity_rounding_mismatch() -> None:
    report = validate_formula(samples=two_samples_one_bad_similarity(), formula=known_formula())
    assert report.complete is False
    assert report.similarity_exact == 5
    assert report.similarity_total == 6
    assert report.first_mismatch.requested_date == date(2024, 5, 15)

def test_validation_requires_set_order_and_similarity_all_exact() -> None:
    report = validate_formula(samples=all_exact_samples(), formula=known_formula())
    assert report.complete is True
    assert report.top3_set_exact == report.total_dates
    assert report.top3_order_exact == report.total_dates
    assert report.similarity_exact == report.total_dates * 3

def test_report_verification_rejects_an_unbacked_counter() -> None:
    with pytest.raises(ReportVerificationError, match="top3_order_exact"):
        verify_report(markdown_with_order_count(99), generated_report(order_count=98))
```

- [ ] **Step 2: Run tests and verify validation module is missing**

Run: `cd research/radar0458; uv run pytest tests/test_validation.py tests/test_audit.py -q`

Expected: FAIL during import.

- [ ] **Step 3: Implement frozen period gates**

The formula bundle records feature variant, eligibility spec, selection spec, metric spec, similarity transform, source fingerprint, discovery date range, and SHA-256 digest. Validation refuses a bundle whose digest or feature variant changes between discovery and validation.

Run periods in this order without refitting:

1. discovery: 2012-2022
2. fixed intermediate validation: 2023-2024
3. untouched holdout: the 100 fixed dates from 2025-01-01 through 2026-07-21
4. full 2012+ audit

Return exit code 1 on the first mismatch and print its requested date, expected Top3, actual Top3, expected similarities, actual similarities, and the first higher-ranked excluded candidate.

Implement verify_report in the same module. It parses the fixed counter labels from the final Markdown report and compares each value with the generated JSON evidence; a missing label, extra claimed period, or unequal counter raises ReportVerificationError. Expose it as the verify-report CLI command used in Task 9.

- [ ] **Step 4: Freeze only after discovery reaches 100%, then validate untouched periods**

Run:

```text
cd research/radar0458
uv run radar-research validate --formula data/formulas/frozen.json --samples data/official/samples.jsonl --features data/calibration/daily-features.jsonl --manifest config/validation-dates.json --set intermediate --output reports/generated/validation-2023-2024.json
uv run radar-research validate --formula data/formulas/frozen.json --samples data/official/samples.jsonl --features data/calibration/daily-features.jsonl --manifest config/validation-dates.json --set holdout --output reports/generated/holdout-2025-2026-07-21.json
```

Expected: both commands report exact date, order, and similarity counts. If either fails, the formula is unfrozen, the failed period becomes discovery data, and a new future holdout is required before any completion claim.

- [ ] **Step 5: Estimate and request approval before the full audit**

Run:

```text
cd research/radar0458
uv run radar-research audit-manifest --start 2012-01-01 --end 2026-07-21 --cache data/official/samples.jsonl --bytes-per-response 6011000 --seconds-between 2 --output data/manifests/full-audit.json
```

Expected: print exact request count, estimated traffic, duration, and cache savings. If the estimate crosses the large-fetch threshold, stop for explicit user approval. After approved collection, run `validate --period 2012-01-01:2026-07-21`; completion requires all counters to equal their totals.

- [ ] **Step 6: Verify and commit**

Run: `cd research/radar0458; uv run pytest -q`

Expected: PASS.

```text
git add research/radar0458
git commit -m "research: enforce exact radar validation gates"
```

## Task 9: Execute the Investigation and Publish the Evidence Report

**Files:**
- Create: `docs/research/radar0458-reconstruction-report.md`

**Interfaces:**
- Consumes: generated calibration, filter, fit, probe, validation, and audit reports.
- Produces: one reviewable report; no product strategy implementation.

- [ ] **Step 1: Run the complete research test suite**

Run: `cd research/radar0458; uv run pytest -q`

Expected: PASS.

Run: `cd research/radar0458; uv run ruff check src tests`

Expected: `All checks passed!`

- [ ] **Step 2: Execute discovery and no more than 200 active probes**

Run import, calibration, diagnostics, filter evaluation, fitting, and probe selection in task order. After each 25-date batch, record which candidate-gate or metric hypotheses were eliminated. Stop immediately when all surviving formulas make identical predictions or when 200 active probes are exhausted.

- [ ] **Step 3: Apply the approved stop or completion branch**

If no frozen formula reaches 100% on discovery and intermediate validation, write the exact remaining mismatch count, mismatch clusters, confirmed rules, rejected hypotheses, and the next missing observation. Do not run the full audit.

If one frozen formula reaches 100%, run untouched holdout validation, obtain cost approval when required, collect the audit manifest, and run the full 2012+ exact audit.

- [ ] **Step 4: Write the evidence report with fixed sections**

The report contains:

- collection dates, sample counts, and source fingerprints
- calibrated market data source and feature formulas
- confirmed eligibility and de-duplication rules
- distance weights, scales, input rounding, and similarity transform when discovered
- discovery, intermediate, holdout, and full-audit exact counters
- first mismatch for every failed gate
- request volume and cache statistics
- explicit conclusion: `complete reconstruction` only when every completion counter is exact, otherwise `incomplete reconstruction`
- statement that no credentials or official-result lookup table were committed

- [ ] **Step 5: Verify the report against generated counters**

Run: `cd research/radar0458; uv run radar-research verify-report --report ../../docs/research/radar0458-reconstruction-report.md --generated reports/generated`

Expected: PASS only when every numeric claim in the Markdown report matches a generated JSON report.

- [ ] **Step 6: Commit the evidence report without ignored research data**

```text
git add docs/research/radar0458-reconstruction-report.md
git commit -m "docs: report radar reconstruction evidence"
```

Run: `git status --short`

Expected: only the user's pre-existing modification to `docs/superpowers/plans/2026-06-26-strategy-operations-ui-implementation.md` remains; ignored credentials, HTML, cache, and generated data do not appear.
