import logging
from typing import Optional, Self
from iptracker.api import IPAPI, QueryResponse, QueryResult, find_host_errors
from iptracker.constants import IPAPI_DEFAULT_FIELDS, IPAPI_SYSTEM_FIELDS
from iptracker.db import HostDataStore
from iptracker.host import HostData

def has_all_fields(host: HostData, fields: list[str]) -> bool:
    for field in fields:
        if field not in host.fields:
            return False        
    
    return True

def filter_hostdata(host: HostData, fields: list[str]) -> HostData:
    return HostData(
        host.host,
        host.fetched_at,
        host.source,
        {k:v for k,v in host.fields.items() if k in fields}
    )
    
def filter_fields(fields: list[str]) -> list[str]:
    filtered_fields = [*fields]
    for field in IPAPI_SYSTEM_FIELDS:
        if field in filtered_fields:
            filtered_fields.remove(field)
            
    return filtered_fields

class HostResolver:
    def __init__(self, api: Optional[IPAPI] = None, local_db: Optional[HostDataStore] = None) -> Self:
        self._remote_api = api or IPAPI()
        self._local_db = local_db
        self._logger = logging.getLogger()
    
    def query(self, hosts: str | list[str], fields: Optional[list[str]] = None, skip_cache: bool = False) -> QueryResponse | list[QueryResponse]:
        fields = filter_fields(fields or IPAPI_DEFAULT_FIELDS)
        
        if isinstance(hosts, str):
            return self.__query_one(hosts, fields, skip_cache)
        elif isinstance(hosts, list):
            return self.__query_many(hosts, fields, skip_cache)
        else:
            raise TypeError("Invalid input type")
    
    def __query_one(self, host: str, fields: list[str], skip_cache: bool) -> QueryResponse:
        if self._local_db and not skip_cache:
            host_error = find_host_errors(host)
            if host_error:
                return QueryResponse.fail(host, host_error)
            
            db_result = self._local_db.get(host)
            if db_result and has_all_fields(db_result, fields):
                return QueryResponse.success(filter_hostdata(db_result, fields))
            
        remote_result = self._remote_api.query(host, fields)
        if remote_result.status == QueryResult.Success and self._local_db:
            if not self._local_db.set(remote_result.result):
                self._logger.warn(f"Failed to push host {remote_result.host} to local DB")
        
        return remote_result
    
    def __query_many(self, hosts: list[str], fields: list[str], skip_cache: bool) -> list[QueryResponse]:
        queue = []
        result = []
        
        self._logger.debug(f"Querying {len(hosts)} hosts")
        if self._local_db and not skip_cache:
            for host in hosts:
                host_error = find_host_errors(host)
                if host_error:
                    result.append(QueryResponse.fail(host, host_error))
                    continue
                
                db_result = self._local_db.get(host)
                if db_result and has_all_fields(db_result, fields):
                    result.append(QueryResponse.success(filter_hostdata(db_result, fields)))
                    continue
                
                queue.append(host)
        else:
            queue = hosts
                
        self._logger.debug(f"Resolved {len(result)} queries locally")
                
        remote_results = self._remote_api.query(queue, fields)
        if self._local_db:
            for result in remote_results:
                if result.status != QueryResult.Success:
                    continue
                if not self._local_db.set(result.result):
                    self._logger.warn(f"Failed to push host {result.host} to local DB")
                    
        result.extend(remote_results)
        return result