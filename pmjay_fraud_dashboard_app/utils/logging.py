import time
import logging
import functools
from .context import get_request_context_dict

class ContextFilter(logging.Filter):
    """
    Injects contextvars (like request_id) into log records.
    """
    def filter(self, record):
        ctx = get_request_context_dict()
        record.request_id = ctx.get('request_id')
        record.correlation_id = ctx.get('correlation_id')
        record.user_id = ctx.get('user_id')
        
        # Ensure default fields are present to avoid KeyError in formatters if extra={} is missing
        if not hasattr(record, 'feature'):
            record.feature = None
        if not hasattr(record, 'endpoint'):
            record.endpoint = None
        if not hasattr(record, 'execution_time_ms'):
            record.execution_time_ms = None
            
        return True

# Initialize a central logger
logger = logging.getLogger('pmjay_dashboard')

class Timer:
    """Context manager for timing execution of code blocks."""
    def __init__(self, description, feature=None, endpoint=None):
        self.description = description
        self.feature = feature
        self.endpoint = endpoint
        
    def __enter__(self):
        self.start = time.time()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.end = time.time()
        duration_ms = (self.end - self.start) * 1000
        
        extra = {
            'execution_time_ms': round(duration_ms, 2),
            'feature': self.feature,
            'endpoint': self.endpoint
        }
        
        if exc_type is None:
            logger.info(f"{self.description} completed", extra=extra)
        else:
            logger.error(f"{self.description} failed", exc_info=(exc_type, exc_val, exc_tb), extra=extra)

def time_execution(description=None, feature=None, endpoint=None):
    """
    Decorator for timing function execution.
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            desc = description or f"Execution of {func.__name__}"
            with Timer(desc, feature=feature, endpoint=endpoint):
                return func(*args, **kwargs)
        return wrapper
    return decorator
