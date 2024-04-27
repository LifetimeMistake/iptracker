__version__ = "0.1.0"
LOGGER_NAME = "iptracker_logger"
DS_CACHE_EXPIRATION = 2592000
IPAPI_URL = "http://ip-api.com"
IPAPI_BATCH_SIZE = 100
IPAPI_REQUIRED_FIELDS = ["status", "message", "query"]
IPAPI_DEFAULT_FIELDS = "status,message,query,country,countryCode,region,regionName,city,zip,lat,lon,timezone,isp,org,as,mobile,proxy,hosting"
IPAPI_USER_AGENT = f"iptracker/{__version__}"