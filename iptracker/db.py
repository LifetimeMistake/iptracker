from typing import Optional
from pymongo import MongoClient
from iptracker.host import HostData

class HostDataStore:
    def __init__(self, connection: MongoClient | str, cache_expiration_seconds: Optional[int] = 2592000):
        if isinstance(connection, str):
            self._connection = MongoClient(connection)
        else:
            self._connection = connection
            
        db = self._connection.get_database()
        db.cache.create_index("created_at", expireAfterSeconds=cache_expiration_seconds)
        db.cache.create_index("host", unique=True)
        self._db = db
        self._hosts = db.get_collection("hosts")
            
    def server_info(self):
        return self._connection.server_info()
    
    def get(self, address: str) -> Optional[HostData]:
        result = self._hosts.find_one({"host": address}, { "_id": 0 })
        if not result:
            return None
        
        host = result["host"]
        fields = result["fields"]
        
        return HostData(host, fields)
    
    def set(self, host_data: HostData):
        obj = {
            "host": host_data.host,
            "fields": host_data.fields
        }
        
        result = self._hosts.update_one(
            {"host": host_data.host},
            obj,
            upsert=True
        )
        
        return result.modified_count == 1