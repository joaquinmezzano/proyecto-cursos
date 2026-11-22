from requests.auth import HTTPBasicAuth

FLOWABLE_URL = "http://localhost:8080/flowable-ui/process-api"
AUTH = HTTPBasicAuth("admin", "test")

DB_CONFIG = {
    "host": "localhost",
    "port": 5434,
    "dbname": "institucion",
    "user": "flowable",
    "password": "flow10",
}
