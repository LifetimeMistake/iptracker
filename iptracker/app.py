import json
import os
from flask import Flask, request
from pymongo import MongoClient
from iptracker.api import IPAPI, response_to_dict
from iptracker.db import HostDataStore
from iptracker.resolver import HostResolver
from iptracker.constants import DEFAULT_APP_HOST, DEFAULT_APP_PORT, DEFAULT_METRICS_PORT
from iptracker.metrics import Metrics

MONGO_URI = os.getenv("MONGO_URI")
CACHE_EXPIRATION_TIME = os.getenv("CACHE_EXPIRATION_TIME")
COLLECTED_FIELDS = os.getenv("COLLECTED_FIELDS")
COLLECTED_FIELDS = COLLECTED_FIELDS.split(",") if COLLECTED_FIELDS else None
IPAPI_USER_AGENT = os.getenv("USER_AGENT")
IPAPI_URL = os.getenv("IPAPI_URL")
IPAPI_BATCH_SIZE = os.getenv("IPAPI_BATCH_SIZE")
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

APP_HOST = os.getenv("APP_HOST", DEFAULT_APP_HOST)
APP_PORT = int(os.getenv("APP_PORT", DEFAULT_APP_PORT))
METRICS_PORT = int(os.getenv("METRICS_PORT", DEFAULT_METRICS_PORT))

app = Flask(__name__)
app.logger.setLevel(LOG_LEVEL)

api = IPAPI(IPAPI_URL, IPAPI_BATCH_SIZE, IPAPI_USER_AGENT)
ds = None

if MONGO_URI:
    connection = MongoClient(MONGO_URI)
    ds = HostDataStore(ds, CACHE_EXPIRATION_TIME)
else:
    app.logger.warning("MongoDB URI not set. Queries will not be cached locally.")

resolver = HostResolver(api, ds)
metrics = Metrics()

@app.route("/json/<ip_address>", methods=["GET", "POST"])
@metrics.time_request("/json")
def endpoint_single(ip_address):
    fields = request.args.get("fields", None)
    fields = fields.split(",") if fields else COLLECTED_FIELDS
    skip_cache = request.method == "POST"
    result = resolver.query(ip_address, fields, skip_cache)
    include_fetch_date = True if fields and "fetched_at" in fields else False
    include_data_source = True if fields and "data_source" in fields else False
    
    return app.response_class(
        response=json.dumps(response_to_dict(result, include_fetch_date, include_data_source), default=str),
        status=200,
        mimetype='application/json'
    )

@app.route("/batch", methods=["POST"])
@metrics.time_request("/batch")
def endpoint_batch():
    fields = request.args.get("fields", None)
    fields = fields.split(",") if fields else COLLECTED_FIELDS
    ip_addresses = request.json
    results = resolver.query(ip_addresses, fields)
    include_fetch_date = True if fields and "fetched_at" in fields else False
    include_data_source = True if fields and "data_source" in fields else False
    
    results = [response_to_dict(x, include_fetch_date, include_data_source) for x in results]
    return app.response_class(
        response=json.dumps(results, default=str),
        status=200,
        mimetype='application/json'
    )

if __name__ == '__main__':
    metrics.start_server(host=APP_HOST, port=METRICS_PORT)
    app.run(host=APP_HOST, port=APP_PORT)