# Operations Guide

## Health Probes
The platform provides lightweight, dependency-aware health checks for load balancers and container orchestrators.

- **Liveness (`/health/live`)**: Returns HTTP 200 immediately. Indicates the web container is alive and accepting connections. Ideal for Kubernetes `livenessProbe`.
- **Readiness (`/health/ready`)**: Verifies downstream connections (e.g., executing a dummy query on the database). Returns HTTP 200 if OK, or HTTP 503 if a dependency is degraded. Ideal for Kubernetes `readinessProbe`.

## Structured Logging
Logs are emitted via Python's standard `logging` to stdout, formatted with key=value attributes for log aggregators (e.g., Fluentd, Datadog, Splunk).

**Available Context:**
- `request_id`: A unique UUID4 attached to every web request. Useful for distributed tracing.
- `correlation_id`: Used when a downstream service initiates the request.
- `execution_time_ms`: Present in completion logs, recording total operation time.
- `feature` / `endpoint`: Specific tags attached when using the `@time_execution` or `Timer` context decorators.

**Log Format Example:**
```
time="2023-11-20 14:22:01,001" level="INFO" logger="pmjay_dashboard.requests" request_id="a1b2c3d4..." feature="None" endpoint="None" execution_time_ms="45.1" message="GET /health/live 200"
```
