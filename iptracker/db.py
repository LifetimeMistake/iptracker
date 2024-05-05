from typing import Optional
from pymongo import MongoClient
from iptracker.constants import DS_CACHE_EXPIRATION
from iptracker.host import HostData, HostDataSource
from iptracker.metrics import Metrics

class HostDataStore:
    def __init__(self, connection: MongoClient | str, cache_expiration_seconds: Optional[int] = None, metrics: Optional[Metrics] = None):        
        if isinstance(connection, str):
            self._connection = MongoClient(connection)
        else:
            self._connection = connection
            
        db = self._connection.get_database()
        hosts = db.get_collection("hosts")
        
        self._db = db
        self._hosts = hosts
        self._metrics = metrics
        
        hosts.create_index("created_at", expireAfterSeconds=cache_expiration_seconds or DS_CACHE_EXPIRATION)
        hosts.create_index("host", unique=True)
        self.__update_metrics()
        
    def __update_metrics(self):
        if not self._metrics:
            return
        
        db_size = self._hosts.count_documents({})
        self._metrics.submit_db_size(db_size)
            
    def server_info(self):
        return self._connection.server_info()
    
    def get(self, address: str) -> Optional[HostData]:
        result = self._hosts.find_one({"host": address}, { "_id": 0 })
        if not result:
            return None
        
        host = result["host"]
        date = result["created_at"]
        fields = result["fields"]
        
        return HostData(host, date, HostDataSource.Local, fields)
    
    def set(self, host_data: HostData) -> bool:
        obj = {
            "host": host_data.host,
            "created_at": host_data.fetched_at,
            "fields": host_data.fields
        }
        
        result = self._hosts.update_one(
            {"host": host_data.host},
            {"$set": obj},
            upsert=True
        )
        
        result = result.upserted_id is not None or result.modified_count == 1
        if result:
            self.__update_metrics()
            
        return result