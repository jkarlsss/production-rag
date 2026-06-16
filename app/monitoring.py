import logging
import json
import time
from datetime import datetime, timezone
from functools import wraps
from typing import Callable, Any, Optional


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_obj = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName
        }
        
        # Merge any extra data attached to the record
        if hasattr(record, "extra_data"):
            log_obj.update(record.extra_data)
        
        return json.dumps(log_obj)


def get_logger(name: str = "production-api") -> logging.Logger:
    """Create a structured JSON logger."""
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    return logger
  
  
class MetricsCollector:
    """
    Collect metrics for a function
    
    In production, replace this with prometheus client:
    from prometheus_client import Counter, Histogram
    """
    
    def __init__(self):
        self._requests_total = 0  # Uniformed naming pattern
        self._errors_total = 0
        self._latency_sum = 0.0
        self._latency_count = 0
        self._tokens_input = 0
        self._tokens_output = 0   # Fixed typo from _token_output to plural
        self._cache_hits = 0
        self._cache_misses = 0
        
    def record_request(
        self,
        latency_ms: float,
        is_error: bool = False,
        tokens_input: int = 0,
        tokens_output: int = 0,
        cache_hit: Optional[bool] = None,
    ):
        """Record telemetry metadata for a single request round-trip."""
        self._requests_total += 1
        
        if is_error:
            self._errors_total += 1
            
        # Latency calculations
        self._latency_sum += latency_ms
        self._latency_count += 1
        
        # Token metrics
        self._tokens_input += tokens_input
        self._tokens_output += tokens_output
        
        # Cache tracking (only increments if cache evaluations actually occurred)
        if cache_hit is True:
            self._cache_hits += 1
        elif cache_hit is False:
            self._cache_misses += 1
      
    @property
    def summary(self) -> dict:
        """Compute summary metrics."""
        avg_latency = (
            self._latency_sum / self._latency_count
            if self._latency_count > 0 else 0.0
        )
        error_rate = (
            self._errors_total / self._requests_total
            if self._requests_total > 0 else 0.0
        )
        cache_total = self._cache_hits + self._cache_misses
        cache_hit_rate = (
            self._cache_hits / cache_total
            if cache_total > 0 else 0.0
        )
        
        return {
            "total_requests": self._requests_total,
            "total_errors": self._errors_total,
            "error_rate": f"{error_rate:.2%}",
            "avg_latency_ms": round(avg_latency, 2),
            "cache_hit_rate": f"{cache_hit_rate:.2%}",
            "total_input_tokens": self._tokens_input,
            "total_output_tokens": self._tokens_output
        }
    

# === Request Timer (utility) ===

class RequestTimer:
    """Context manager for timing requests."""
    
    def __enter__(self):
        self.start_time = time.time()
        return self
      
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.elapsed = (time.time() - self.start_time) * 1000
    