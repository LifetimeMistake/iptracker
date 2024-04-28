import logging
from typing import Optional
from pymongo import MongoClient
from iptracker.constants import DS_CACHE_EXPIRATION
from iptracker.host import HostData, HostDataSource

class HostDataStore:
    def __init__(self, connection: MongoClient | str, cache_expiration_seconds: Optional[int] = None):
        self._logger = logging.getLogger()
        
        if isinstance(connection, str):
            self._connection = MongoClient(connection)
        else:
            self._connection = connection
            
        db = self._connection.get_database()
        db.cache.create_index("created_at", expireAfterSeconds=cache_expiration_seconds or DS_CACHE_EXPIRATION)
        db.cache.create_index("host", unique=True)
        self._db = db
        self._hosts = db.get_collection("hosts")
            
    def server_info(self):
        return self._connection.server_info()
    
    def get(self, address: str) -> Optional[HostData]:
        result = self._hosts.find_one({"host": address}, { "_id": 0 })
        if not result:
            self._logger.debug("Host %s not found in cache", address)
            return None
        
        host = result["host"]
        date = result["created_at"]
        fields = result["fields"]
        
        self._logger.debug("Host %s fetched from cache", address)
        return HostData(host, date, HostDataSource.Local, fields)
    
    def set(self, host_data: HostData):
        obj = {
            "host": host_data.host,
            "created_at": host_data.fetched_at,
            "fields": host_data.fields
        }
        
        result = self._hosts.update_one(
            {"host": host_data.host},
            obj,
            upsert=True
        )
        
        self._logger.debug("Host %s submitted to cache", host_data.host)
        return result.modified_count == 1