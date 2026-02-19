# Testing Architecture & Regression Harness

This document describes the testing strategy, infrastructure, and execution guidelines for the PMJAY Fraud Dashboard application.

## 1. Test Categories

The test suite is strictly categorized to provide reliable feedback across different layers of the application.

*   **`tests/unit/`**: Tests for zero-dependency shared utilities (e.g., date helpers, pagination calculation, responses). These run instantaneously and NEVER skip.
*   **`tests/integration/`**: Tests covering the Django ORM, controllers, and APIs (e.g., Dashboard). These require the test database and NEVER skip.
*   **`tests/data_processing/`**: Tests covering the complex Pandas/NumPy dataframe transformations (e.g., Ophthalmology). These are dynamically skipped on incompatible local environments but run completely on CI.
*   **`tests/performance/`**: Reserved for benchmark tests ensuring query and aggregation regressions do not occur over time.

## 2. Environment Compatibility (The NumPy Bug)

**Important:** The current local development environment uses Python 3.14 on Windows with an experimental MINGW-W64 build of NumPy. This build immediately segfaults on import. 

To prevent the `pytest` runner from crashing locally, `tests/conftest.py` executes a safe subprocess check at startup:
1. If NumPy successfully imports, all tests execute.
2. If NumPy crashes, `conftest.py` safely intercepts the crash and dynamically applies `@pytest.mark.skip` to all tests decorated with `@pytest.mark.data_processing`.

You will see a large warning in the console when this occurs:
`ENVIRONMENT WARNING: Data Processing Tests Skipped`

**Do not hardcode skips.** When this code runs on a standard Linux CI/CD environment, the environment check will pass and all data processing tests will execute.

## 3. Running the Tests

To run the complete suite locally:
```bash
pytest tests/
```

To run with coverage:
```bash
pytest tests/ --cov=pmjay_fraud_dashboard_app/features --cov=pmjay_fraud_dashboard_app/utils
```

To run a specific category:
```bash
pytest tests/ -m unit
pytest tests/ -m integration
```

## 4. Coverage Targets
As we continue to extract features from the `views.py` monolith, we enforce the following minimum coverage thresholds for newly extracted modules:
* Utilities: **95%+**
* Selectors: **90%+**
* Services: **85%+**
* Views: **80%+**

## 5. Mocking Policy
*   **External Dependencies Only:** We only mock external systems (emails, caches, filesystems).
*   **Never Mock Core Logic:** We do not mock Pandas dataframe aggregation logic or ORM query building inside our integration/processing tests. The goal is complete confidence in the business rules.
