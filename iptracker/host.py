from datetime import datetime
from enum import Enum
from typing import Any

class HostDataSource(Enum):
    Local = 0
    Remote = 1

class HostData:
    def __init__(self, host: str, fetch_date: datetime, source: HostDataSource, fields: dict[str, Any]) -> None:
        self._host = host
        self._source = source
        self._date = fetch_date
        self._fields = fields
        
    @property
    def host(self):
        return self._host
    
    @property
    def source(self):
        return self._source
    
    @property
    def fetched_at(self):
        return self._date
    
    @property
    def fields(self):
        return self._fields
        
    def __getitem__(self, field: str):
        return self._fields[field]
    
    def __setitem__(self, field: str, value: Any):
        self._fields[field] = value
        
    def __delitem__(self, field: str):
        del self._fields[field]