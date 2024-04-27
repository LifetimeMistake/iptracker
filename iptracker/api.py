import ipaddress
import json
import logging
import time
import datetime
from enum import Enum
from typing import Any, Generator, Optional, Self
import requests
from iptracker.host import HostData, HostDataSource
from iptracker.constants import IPAPI_REQUIRED_FIELDS, IPAPI_URL, IPAPI_DEFAULT_FIELDS, IPAPI_USER_AGENT, IPAPI_BATCH_SIZE, LOGGER_NAME

class QueryResult(Enum):
    Success = 0
    Fail = 1

class QueryResponse:
    def __init__(self, result: QueryResult, host: str, error: Optional[str], data: Optional[HostData]) -> Self:
        self._result = result
        self._host = host
        self._error = error
        self._data = data
    
    def success(data: HostData) -> Self:
        return QueryResponse(
            QueryResult.Success,
            data.host,
            None,
            data
        )
    
    def fail(host: str, error: str) -> Self:
        return QueryResponse(
            QueryResult.Fail,
            host,
            error,
            None
        )
        
    @property
    def status(self) -> QueryResult:
        return self._result
    
    @property
    def host(self) -> str:
        return self._host
    
    @property
    def error_message(self) -> Optional[str]:
        return self._error
    
    @property
    def result(self) -> Optional[HostData]:
        return self._data
    
def generate_splits(data, batch_size: int) -> Generator[Any, Any, None]:
    for i in range(0, len(data), batch_size):
        yield data[i:i + batch_size]
        
def generate_fields(fields: list[str]) -> str:
    for field in IPAPI_REQUIRED_FIELDS:
        if field not in fields:
            fields.append(field)
            
    return ",".join(fields)

def json_to_response(data) -> QueryResponse:
    if data["status"] == "success":
        return QueryResponse.success(HostData(
            data["query"], 
            datetime.datetime.now(datetime.UTC),
            HostDataSource.Remote,
            {k:v for k,v in data.items() if k not in ["status", "message", "query"]}
        ))
    elif data["status"] == "fail":
        return QueryResponse.fail(
            data["query"],
            data["message"]
        )
    else:
        raise ValueError(f"Invalid remote status: {data['status']}")
    
def find_host_errors(host: str) -> Optional[str]:
    try:
        address = ipaddress.ip_address(host)
        if not address.is_global:
            return "private range"
    except Exception:
        return "invalid query"
    
    return None

class IPAPI:
    def __init__(self, api_url: Optional[str] = None, batch_size: Optional[int] = None, user_agent: Optional[str] = None) -> Self:
        self._logger = logging.getLogger(LOGGER_NAME)
        self._api_url = (api_url or IPAPI_URL).strip("/")
        self._batch_size = batch_size or IPAPI_BATCH_SIZE
        self._user_agent = user_agent or IPAPI_USER_AGENT
        
    def query(self, hosts: str | list[str], filters: Optional[list[str]] = None) -> QueryResponse | list[QueryResponse]:
        if isinstance(hosts, str):
            # validate host address
            host_error = find_host_errors(hosts)
            if host_error:
                return QueryResponse.fail(hosts, host_error)
            
            return self.__query_one(hosts, filters)
        elif isinstance(hosts, list):
            results = []
            def validate_hosts():
                for x in hosts:
                    host_error = find_host_errors(x)
                    if host_error:
                        results.append(QueryResponse.fail(x, host_error))
                        continue
                    
                    yield x
            
            for batch in generate_splits(validate_hosts(), self._batch_size):
                results.extend(self.__query_batch(batch, filters))
            return results
        else:
            raise TypeError("Invalid input type")
    
    def __query_one(self, host: str, filters: Optional[list[str]] = None) -> QueryResponse:
        self._logger.info("Resolving host %s", host)
        
        request_url = f"{self._api_url}/json/{host}"
        response = requests.get(
            request_url,
            params={"fields": generate_fields(filters) if filters else IPAPI_DEFAULT_FIELDS},
            headers={"User-Agent": self._user_agent}
        )
        
        headers = response.headers
        if response.status_code == 429 or "X-Rl" in headers and int(headers["X-Rl"]) == 0:
            wait_time = int(headers["X-Ttl"]) + 1
            self._logger.info("Rate limit reached, waiting for %d seconds", wait_time)
            time.sleep(wait_time)
            # Retry request
            return self.__query_one(host, filters)
        
        if response.status_code != 200:
            self._logger.error("IPAPI remote error: %d, %s", response.status_code, response.text)
            raise Exception(f"Remote error: {response.status_code}")
        
        return json_to_response(response.json())
    
    def __query_batch(self, hosts: list[str], filters: Optional[str] = None) -> list[QueryResponse]:
        if len(hosts) > self._batch_size:
            raise ValueError(f"Invalid batch size: {len(hosts)}, maximum allowed size is {self._batch_size}")
        
        results = []
                
        self._logger.info("Resolving %d hosts", len(hosts))
        request_url = f"{self._api_url}/batch"
        response = requests.post(
            request_url,
            params={"fields": generate_fields(filters) if filters else IPAPI_DEFAULT_FIELDS},
            headers={"User-Agent": self._user_agent, "Content-Type": "application/json"},
            data=json.dumps(hosts)
        )
        
        headers = response.headers
        if response.status_code == 429 or "X-Rl" in headers and int(headers["X-Rl"]) == 0:
            wait_time = int(headers["X-Ttl"]) + 1
            self._logger.info("Rate limit reached, waiting for %d seconds", wait_time)
            time.sleep(wait_time)
            # Retry request
            return self.__query_batch(hosts, filters)
        
        if response.status_code != 200:
            self._logger.error("IPAPI remote error: %d, %s", response.status_code, response.text)
            raise Exception(f"Remote error: {response.status_code}")
        
        for host in response.json():
            results.append(json_to_response(host))
            
        return results