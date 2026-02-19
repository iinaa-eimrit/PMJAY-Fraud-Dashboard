# Performance & Benchmarking

## History
The pmjay_fraud_dashboard application originally suffered from frequent Out-Of-Memory (OOM) crashes and latency spikes >12s under moderate load due to massive pandas dataframes populated via monolithic `load_dataframes()` flows.

## Optimization Timeline
- **Phase 1 (Module Extraction):** Monolithic `views.py` decomposed into vertical slices, preparing the domain boundary for precise optimization.
- **Phase 2 (Profiling & Database Audit):** Identified that ORM date filtering on `.__date` casts were forcing Full Table Scans. Rewrote queries to use `__gte` and `__lt` range checks. Added critical indices. Latency improved from ~14s to ~7s.
- **Phase 3 (PostgreSQL Study):** Proved that migrating to PostgreSQL is beneficial but insufficient on its own. Pandas memory allocations were still exhausting workstation RAM.
- **Phase 4 (DataFrame Decomposition):** Began incremental decomposition of Pandas `pd.cut()` and `value_counts()` pipelines into Django ORM aggregations. Eliminated O(N) memory complexity in `get_ophthalmology_distribution_data` and `get_ophthalmology_demographics_data`.

## Profiling Methodology
We do not rely on guesses. Every optimization follows:
1. Establish a baseline metric (execution time, peak memory, query count).
2. Measure database planner usage using `EXPLAIN`.
3. Implement the new pattern incrementally.
4. Verify functional output parity.
5. Capture performance improvements using the `Timer` context managers now embedded in `utils/logging.py`.

## Known Bottlenecks
1. **Excel Generation (`views.py`):** Generating multi-sheet openpyxl workbooks synchronously blocks the web thread entirely and triggers OOM limits.
   - *Target:* Defer to Background Workers (Celery).
2. **OT Violation Computation:** Requires analyzing hospital daily limits against cases via Windowing functions. This is complex to write natively in Django ORM without heavy N+1.
   - *Target:* Convert to Native SQL `OVER (PARTITION BY)`.
3. **CSV Imports:** Blocks web responses during upload processing.
   - *Target:* Defer to Background Workers (Celery).

## Performance Targets
- **P95 Latency (API Endpoints):** < 500ms
- **Peak Memory (API Endpoints):** < 100MB overhead per worker.
- **Export Wait Time:** Immediate ACK (HTTP 202), asynchronous completion < 120s.
