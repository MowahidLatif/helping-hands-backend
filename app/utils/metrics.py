from prometheus_client import Counter, Histogram

REQUEST_COUNT = Counter(
    "app_http_requests_total",
    "Total HTTP requests handled by the app",
    ["method", "path", "status"],
)

REQUEST_DURATION_SECONDS = Histogram(
    "app_http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "path"],
)

RATE_LIMIT_HITS = Counter(
    "app_rate_limit_hits_total",
    "Total requests rejected by rate limiting",
    ["path"],
)
