import time
from functools import wraps
from typing import Self
from prometheus_client import Counter, Gauge, Histogram, start_http_server
from iptracker.api import QueryResponse, QueryResult

class Metrics:
    def __init__(self) -> Self:
        self._requests_total = Counter("geoip_requests_total", "Total number of HTTP requests to the service", labelnames=["path"])
        self._request_time = Histogram("geoip_request_time_seconds", "Request processing time in seconds", labelnames=["path"])
        self._resolved_total = Counter("geoip_resolved_total", "Total number of successfully resolved IPs by source", labelnames=["source"])
        self._queried_total = Counter("geoip_queried_total", "Total number of IP addresses queried")
        self._local_db_size = Gauge("geoip_local_db_size", "Current number of cached IPs")
        
    def start_server(self, port: int, host: str = "0.0.0.0"):
        return start_http_server(port, host)
    
    def submit_request(self, path: str, time: float):
        if time < 0:
            raise ValueError("Out of range")
        
        self._requests_total.labels(path).inc()
        self._request_time.labels(path).observe(time)
        
    def time_request(self, path: str):
        def decorator(f):
            @wraps(f)
            def wrapped(*args, **kwargs):
                start_time = time.time()
                try:
                    response = f(*args, **kwargs)
                finally:
                    end_time = time.time()
                    elapsed_time = end_time - start_time
                    self.submit_request(path, elapsed_time)
                return response
            return wrapped
        return decorator
        
    def __submit_resolution_once(self, data: QueryResponse):
        if data.status == QueryResult.Success:
            self._resolved_total.labels(str(data.result.source)).inc()
        self._queried_total.inc()
    
    def submit_resolution(self, data: QueryResponse | list[QueryResponse]):
        if isinstance(data, QueryResponse):
            self.__submit_resolution_once(data)
        elif isinstance(data, list):
            for d in data:
                self.__submit_resolution_once(d)
        else:
            raise TypeError("Invalid input type")
    
    def submit_db_size(self, new_size: int):
        if new_size < 0:
            raise ValueError("Out of range")
        
        self._local_db_size.set(new_size)