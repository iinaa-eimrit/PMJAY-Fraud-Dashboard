import logging

logger = logging.getLogger('pmjay_dashboard.metrics')

class MetricsBackend:
    """Abstract interface for metrics backends."""
    
    def count(self, name: str, increment: int = 1, tags: dict = None):
        raise NotImplementedError
        
    def histogram(self, name: str, value: float, tags: dict = None):
        raise NotImplementedError
        
    def gauge(self, name: str, value: float, tags: dict = None):
        raise NotImplementedError


class LoggingMetricsBackend(MetricsBackend):
    """
    A lightweight default metrics implementation suitable for development.
    Emits metrics as structured log events.
    """
    
    def count(self, name: str, increment: int = 1, tags: dict = None):
        tags = tags or {}
        logger.info(f"Metric Count: {name}", extra={'metric_type': 'count', 'metric_name': name, 'metric_value': increment, 'metric_tags': tags})
        
    def histogram(self, name: str, value: float, tags: dict = None):
        tags = tags or {}
        logger.info(f"Metric Histogram: {name}", extra={'metric_type': 'histogram', 'metric_name': name, 'metric_value': value, 'metric_tags': tags})
        
    def gauge(self, name: str, value: float, tags: dict = None):
        tags = tags or {}
        logger.info(f"Metric Gauge: {name}", extra={'metric_type': 'gauge', 'metric_name': name, 'metric_value': value, 'metric_tags': tags})


# Singleton metrics client
_client = LoggingMetricsBackend()

def track_count(name: str, increment: int = 1, tags: dict = None):
    _client.count(name, increment, tags)

def track_latency(name: str, duration_ms: float, tags: dict = None):
    _client.histogram(name, duration_ms, tags)

def track_gauge(name: str, value: float, tags: dict = None):
    _client.gauge(name, value, tags)
    
def track_cache_hit(cache_name: str):
    track_count('cache.hit', tags={'cache_name': cache_name})

def track_cache_miss(cache_name: str):
    track_count('cache.miss', tags={'cache_name': cache_name})
