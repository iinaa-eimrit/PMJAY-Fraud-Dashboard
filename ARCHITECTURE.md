# Architecture Principles

## 1. Modular Extraction (Vertical Slicing)
The codebase is currently undergoing a refactor from a monolithic structure to domain-driven vertical slices.
- Modules are grouped by feature (e.g., `features/ophthalmology`).
- Features encapsulate their own `views.py`, `services.py`, `selectors.py`, and `urls.py`.
- Shared code resides in `utils/`.
- **Dependency Rule:** Feature modules MUST NEVER import from the legacy monolith.

## 2. Observability Foundation
- **Request Context:** We use `contextvars` to tie `request_id`, `correlation_id`, and `user_id` to every asynchronous operation or thread execution without needing to explicitly pass a `request` object down the call stack.
- **Metrics Interface:** We abstract metrics (`track_count`, `track_latency`, `track_gauge`) through a backend-agnostic `MetricsBackend`. This ensures we can easily swap to Prometheus or OpenTelemetry in the future without modifying application logic.

## 3. DataFrame Decomposition Strategy
The legacy application heavily relied on Pandas for processing 150,000+ row CSVs and returning synchronous HTTP responses. This causes severe peak memory usage and CPU contention.
- **Target Architecture:** Push synchronous API data retrieval into the database layer using Django ORM and Native SQL (especially for Window functions).
- **Asynchronous Tier:** Pandas is restricted to asynchronous Celery/Background Tasks where it will process bulk Excel Generation and Data Ingestions without blocking web threads.
