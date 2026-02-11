# Engineering Decisions Log

## 1. Metrics Interface over Direct Coupling
**Context:** We need application observability (latency, cache hits, events).
**Decision:** We chose to build a backend-agnostic `MetricsBackend` (defaulting to logging) rather than hardcoding `prometheus_client` across the application.
**Justification:** This allows domain code to emit `track_latency()` natively. When operations deploy a specific APM (NewRelic, Datadog, Prometheus), they simply inject a new concrete `MetricsBackend` adapter.

## 2. contextvars vs threading.local
**Context:** We need to trace request IDs across deep function stacks without explicitly passing `request` objects to every utility and service.
**Decision:** We use `contextvars` rather than `threading.local()`.
**Justification:** Django now supports async views, and future optimizations may leverage `asyncio` or `sync_to_async`. `contextvars` correctly propagates across threadpools and async loops, avoiding mixed-state bugs inherent to thread-locals.

## 3. SQLite vs PostgreSQL Benchmark Results
**Context:** The legacy app faced significant latency and OOM issues. We suspected SQLite locking and missing indices.
**Decision:** We benchmarked PostgreSQL in Phase 2 but discovered it did not solve the primary bottleneck. 
**Justification:** The bottleneck was transferring 150k+ rows to Pandas in memory. Rather than immediately migrating to PostgreSQL, we are decomposing the DataFrame workflows into pure ORM/SQL abstractions. PostgreSQL migration is deferred until the application is memory-efficient.

## 4. Shared ORM Annotations
**Context:** DataFrame refactoring requires pushing categorical binning logic into SQL using `Case/When`.
**Decision:** We abstract these annotations (`get_age_bucket_annotation`) into `utils/orm_annotations.py`.
**Justification:** Prevents domain leakage. Multiple endpoints (Show Cause, Penalty Engine) will eventually need the same binning logic.
