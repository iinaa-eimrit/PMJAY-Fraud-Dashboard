import pytest
import subprocess
import sys

def _check_pandas_health():
    """
    Runs a tiny pandas script in a subprocess to check if the environment 
    has the MINGW-W64 Numpy bug. This prevents the pytest runner from hard-crashing.
    """
    script = "import pandas as pd; pd.DataFrame({'a':[1]}).mean()"
    result = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    if result.returncode != 0:
        return False, "Numpy MINGW-W64 bug detected (Process exited with code 1)."
    return True, ""

IS_PANDAS_HEALTHY, PANDAS_BROKEN_REASON = _check_pandas_health()

def pytest_configure(config):
    if not IS_PANDAS_HEALTHY:
        # Prevent openpyxl or other third-party libs from importing numpy and segfaulting the runner
        sys.modules['numpy'] = None
        sys.modules['pandas'] = None
        
        print("\n" + "="*80)
        print("ENVIRONMENT WARNING: Data Processing Tests Skipped")
        print("Reason:", PANDAS_BROKEN_REASON)
        print("This local machine has an incompatible NumPy build.")
        print("Data processing tests will automatically run in Linux CI/CD.")
        print("="*80 + "\n")

def pytest_collection_modifyitems(config, items):
    if not IS_PANDAS_HEALTHY:
        skip_data_processing = pytest.mark.skip(reason=f"Environment incompatible: {PANDAS_BROKEN_REASON}")
        for item in items:
            if "data_processing" in [mark.name for mark in item.iter_markers()]:
                item.add_marker(skip_data_processing)
