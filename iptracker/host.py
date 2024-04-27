from typing import Any

class HostData:
    def __init__(self, host: str, fields: dict[str, Any]) -> None:
        self._host = host
        self._fields = fields
        
    @property
    def host(self):
        return self._host
    
    @property
    def fields(self):
        return self._fields
        
    def __getitem__(self, field: str):
        return self._fields[field]
    
    def __setitem__(self, field: str, value: Any):
        self._fields[field] = value
        
    def __delitem__(self, field: str):
        del self._fields[field]