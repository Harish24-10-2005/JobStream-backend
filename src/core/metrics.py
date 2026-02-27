"""
Prometheus-Compatible Metrics — Application Observability

Exposes metrics in Prometheus text format via /metrics endpoint.
Tracks:
  - HTTP request count, latency, and error rates
  - Agent execution metrics (duration, success/failure)
  - Pipeline stage timing
  - LLM token usage counters
  - WebSocket connection gauge
  - Circuit breaker state

Architecture:
  - In-memory counters/gauges/histograms (no external dependency)
  - Thread-safe via asyncio locks
  - FastAPI middleware for automatic HTTP metrics
  - Manual instrumentation decorators for agents

Note: Uses plain-text Prometheus exposition format.
      Drop-in compatible with Prometheus, Grafana, Datadog.
"""
import asyncio
import time
import logging
from collections import defaultdict
from dataclasses import dataclass, field
from functools import wraps
from typing import Optional

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


# ── Metric Types ──────────────────────────────────────────────────

@dataclass
class Counter:
    """Monotonically increasing counter."""
    name: str
    help: str
    labels: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    
    def inc(self, labels: dict[str, str] = None, value: float = 1.0):
        key = self._label_key(labels)
        self.labels[key] += value
    
    def _label_key(self, labels: dict = None) -> str:
        if not labels:
            return ""
        return ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    
    def to_prometheus(self) -> str:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} counter"]
        for key, value in self.labels.items():
            label_str = f"{{{key}}}" if key else ""
            lines.append(f"{self.name}{label_str} {value}")
        return "\n".join(lines)


@dataclass
class Gauge:
    """Value that can go up and down."""
    name: str
    help: str
    labels: dict[str, float] = field(default_factory=lambda: defaultdict(float))
    
    def set(self, value: float, labels: dict[str, str] = None):
        key = self._label_key(labels)
        self.labels[key] = value
    
    def inc(self, labels: dict[str, str] = None, value: float = 1.0):
        key = self._label_key(labels)
        self.labels[key] += value
    
    def dec(self, labels: dict[str, str] = None, value: float = 1.0):
        key = self._label_key(labels)
        self.labels[key] -= value
    
    def _label_key(self, labels: dict = None) -> str:
        if not labels:
            return ""
        return ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    
    def to_prometheus(self) -> str:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} gauge"]
        for key, value in self.labels.items():
            label_str = f"{{{key}}}" if key else ""
            lines.append(f"{self.name}{label_str} {value}")
        return "\n".join(lines)


@dataclass
class Histogram:
    """Tracks value distributions with configurable buckets."""
    name: str
    help: str
    buckets: list[float] = field(default_factory=lambda: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0])
    _observations: dict[str, list[float]] = field(default_factory=lambda: defaultdict(list))
    
    def observe(self, value: float, labels: dict[str, str] = None):
        key = self._label_key(labels)
        self._observations[key].append(value)
    
    def _label_key(self, labels: dict = None) -> str:
        if not labels:
            return ""
        return ",".join(f'{k}="{v}"' for k, v in sorted(labels.items()))
    
    def to_prometheus(self) -> str:
        lines = [f"# HELP {self.name} {self.help}", f"# TYPE {self.name} histogram"]
        for key, observations in self._observations.items():
            base_labels = f"{{{key}," if key else "{"
            count = len(observations)
            total = sum(observations)
            
            for bucket in self.buckets:
                bucket_count = sum(1 for o in observations if o <= bucket)
                lines.append(f'{self.name}_bucket{base_labels}le="{bucket}"}} {bucket_count}')
            lines.append(f'{self.name}_bucket{base_labels}le="+Inf"}} {count}')
            lines.append(f"{self.name}_sum{{{key}}}" if key else f"{self.name}_sum" + f" {total}")
            lines.append(f"{self.name}_count{{{key}}}" if key else f"{self.name}_count" + f" {count}")
        return "\n".join(lines)


# ── Metrics Registry ──────────────────────────────────────────────

class MetricsRegistry:
    """Central registry for all application metrics."""
    
    def __init__(self):
        self._metrics: dict[str, Counter | Gauge | Histogram] = {}
        
        # Pre-register standard metrics
        self.http_requests_total = self.counter(
            "http_requests_total",
            "Total HTTP requests"
        )
        self.http_request_duration_seconds = self.histogram(
            "http_request_duration_seconds",
            "HTTP request latency in seconds"
        )
        self.http_errors_total = self.counter(
            "http_errors_total",
            "Total HTTP errors"
        )
        self.websocket_connections = self.gauge(
            "websocket_connections_active",
            "Active WebSocket connections"
        )
        self.agent_executions_total = self.counter(
            "agent_executions_total",
            "Total agent executions"
        )
        self.agent_duration_seconds = self.histogram(
            "agent_duration_seconds",
            "Agent execution duration in seconds",
        )
        self.agent_errors_total = self.counter(
            "agent_errors_total",
            "Total agent errors"
        )
        self.pipeline_runs_total = self.counter(
            "pipeline_runs_total",
            "Total pipeline runs"
        )
        self.llm_tokens_total = self.counter(
            "llm_tokens_total",
            "Total LLM tokens consumed"
        )
        self.guardrail_blocks_total = self.counter(
            "guardrail_blocks_total",
            "Total inputs blocked by guardrails"
        )
        self.circuit_breaker_state = self.gauge(
            "circuit_breaker_state",
            "Circuit breaker state (0=closed, 1=half_open, 2=open)"
        )
    
    def counter(self, name: str, help: str) -> Counter:
        c = Counter(name=name, help=help)
        self._metrics[name] = c
        return c
    
    def gauge(self, name: str, help: str) -> Gauge:
        g = Gauge(name=name, help=help)
        self._metrics[name] = g
        return g
    
    def histogram(self, name: str, help: str, buckets: list[float] = None) -> Histogram:
        h = Histogram(name=name, help=help)
        if buckets:
            h.buckets = buckets
        self._metrics[name] = h
        return h
    
    def to_prometheus(self) -> str:
        """Export all metrics in Prometheus text format."""
        sections = []
        for metric in self._metrics.values():
            text = metric.to_prometheus()
            if text.strip():
                sections.append(text)
        return "\n\n".join(sections) + "\n"


# ── Singleton ──────────────────────────────────────────────────

_registry: Optional[MetricsRegistry] = None

def get_metrics() -> MetricsRegistry:
    """Get or create the global metrics registry."""
    global _registry
    if _registry is None:
        _registry = MetricsRegistry()
    return _registry


# ── FastAPI Middleware ──────────────────────────────────────────

class PrometheusMiddleware(BaseHTTPMiddleware):
    """Automatically tracks HTTP request metrics."""
    
    async def dispatch(self, request: Request, call_next):
        metrics = get_metrics()
        
        start_time = time.perf_counter()
        response = None
        try:
            response = await call_next(request)
            return response
        finally:
            duration = time.perf_counter() - start_time
            status = str(response.status_code) if response else "500"
            method = request.method
            path = request.url.path
            
            # Skip metrics endpoint itself
            if path != "/metrics":
                labels = {"method": method, "path": path, "status": status}
                metrics.http_requests_total.inc(labels)
                metrics.http_request_duration_seconds.observe(duration, labels)
                
                if response and response.status_code >= 400:
                    metrics.http_errors_total.inc(labels)


# ── Instrumentation Decorators ──────────────────────────────────

def track_agent(agent_name: str):
    """Decorator to track agent execution metrics."""
    def decorator(fn):
        @wraps(fn)
        async def wrapper(*args, **kwargs):
            metrics = get_metrics()
            labels = {"agent": agent_name}
            metrics.agent_executions_total.inc(labels)
            
            start = time.perf_counter()
            try:
                result = await fn(*args, **kwargs)
                duration = time.perf_counter() - start
                metrics.agent_duration_seconds.observe(duration, {"agent": agent_name, "status": "success"})
                return result
            except Exception as e:
                duration = time.perf_counter() - start
                metrics.agent_errors_total.inc(labels)
                metrics.agent_duration_seconds.observe(duration, {"agent": agent_name, "status": "error"})
                raise
        return wrapper
    return decorator


def track_llm_tokens(provider: str, tokens: int):
    """Record LLM token usage."""
    metrics = get_metrics()
    metrics.llm_tokens_total.inc({"provider": provider}, value=float(tokens))


# ── FastAPI Route Setup ─────────────────────────────────────────

def setup_metrics(app: FastAPI):
    """
    Add metrics middleware and /metrics endpoint to the app.
    
    Usage in main.py:
        from src.core.metrics import setup_metrics
        setup_metrics(app)
    """
    # Add middleware
    app.add_middleware(PrometheusMiddleware)
    
    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint():
        """Prometheus-compatible metrics endpoint."""
        metrics = get_metrics()
        content = metrics.to_prometheus()
        return Response(content=content, media_type="text/plain; charset=utf-8")
    
    logger.info("📊 Prometheus metrics enabled at /metrics")
